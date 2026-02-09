import re
import os
import sys
import hashlib
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
import xbmcvfs
import xbmcgui
import xbmcplugin
import xbmcaddon
import xbmc
from resources.lib.base_website import BaseWebsite

try:
    addon_path = xbmcaddon.Addon().getAddonInfo('path')
    vendor_path = os.path.join(addon_path, 'resources', 'lib', 'vendor')
    if vendor_path not in sys.path:
        sys.path.insert(0, vendor_path)
except Exception as e:
    xbmc.log(f"[Area51] Vendor path inject failed: {e}", xbmc.LOGERROR)

try:
    import cloudscraper
    _HAS_CF = True
except Exception as e:
    xbmc.log(f"[Area51] cloudscraper import failed: {e}", xbmc.LOGERROR)
    _HAS_CF = False

import requests


class Area51(BaseWebsite):
    NAME = "area51"
    BASE_URL = "https://area51.porn/"
    _shared_session = None  # Class-level session singleton

    def __init__(self, addon_handle, addon=None):
        super().__init__(
            name="area51",
            base_url="https://area51.porn/",
            search_url="https://area51.porn/search/{}/",
            addon_handle=addon_handle,
            addon=addon
        )
        self.sort_options = ['Newest', 'Most Viewed']
        self.sort_paths = {
            'Newest': '',
            'Most Viewed': 'most-popular/'
        }
        self.image_headers = ""
        self._thumb_cache_dir = self._initialize_thumb_cache()
        self._init_session()

    def _init_session(self):
        """Initialize the shared session once."""
        if Area51._shared_session is None:
            if _HAS_CF:
                Area51._shared_session = cloudscraper.create_scraper(
                    browser={
                        'browser': 'chrome',
                        'platform': 'windows',
                        'desktop': True,
                        'custom': self.get_headers()['User-Agent']
                    }
                )
                self.logger.info("Using cloudscraper for Cloudflare bypass")
            else:
                Area51._shared_session = requests.Session()
                self.logger.info("Using standard requests session")
            
            Area51._shared_session.headers.update(self.get_headers())

    def _get_session(self):
        """Get the shared cloudscraper session."""
        if Area51._shared_session is None:
            self._init_session()
        return Area51._shared_session

    def _initialize_thumb_cache(self):
        """Initialize local thumbnail cache directory."""
        addon_profile = xbmcvfs.translatePath(self.addon.getAddonInfo('profile'))
        thumb_dir = os.path.join(addon_profile, 'thumbs', self.name)
        if not xbmcvfs.exists(thumb_dir):
            xbmcvfs.mkdirs(thumb_dir)
        else:
            self._enforce_cache_limit(thumb_dir, max_size_mb=10)
        return thumb_dir

    def _enforce_cache_limit(self, cache_dir, max_size_mb=10):
        """Enforce cache size limit."""
        try:
            max_size_bytes = max_size_mb * 1024 * 1024
            files = []
            total_size = 0

            for filename in os.listdir(cache_dir):
                filepath = os.path.join(cache_dir, filename)
                if os.path.isfile(filepath):
                    stat = os.stat(filepath)
                    files.append((filepath, stat.st_size, stat.st_mtime))
                    total_size += stat.st_size

            if total_size > max_size_bytes:
                files.sort(key=lambda x: x[2])

                for filepath, size, _ in files:
                    if total_size <= max_size_bytes:
                        break
                    try:
                        os.remove(filepath)
                        total_size -= size
                        self.logger.info(f"Cache cleanup: deleted {os.path.basename(filepath)}")
                    except:
                        pass
        except Exception as e:
            self.logger.error(f"Cache cleanup failed: {e}")

    def get_headers(self, url=None):
        return {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": "https://area51.porn/",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        }

    def make_request(self, url):
        """Make HTTP request using cloudscraper/requests and return HTML content."""
        try:
            session = self._get_session()
            response = session.get(url, timeout=15)
            response.raise_for_status()
            return response.text
        except requests.Timeout:
            self.logger.error(f"Request timeout for {url}")
            return None
        except requests.RequestException as e:
            self.logger.error(f"Request failed for {url}: {e}")
            return None

    def _download_and_validate_thumb(self, url):
        """Download thumbnail and save with correct extension."""
        if not url or not url.startswith('http'):
            return url

        try:
            hashed_url = hashlib.md5(url.encode('utf-8')).hexdigest()

            valid_signatures = {
                b'\xFF\xD8\xFF': '.jpg',
                b'\x89PNG\r\n\x1a\n': '.png',
                b'GIF89a': '.gif',
                b'GIF87a': '.gif',
                b'RIFF': '.webp'
            }

            for ext in set(valid_signatures.values()):
                local_path = os.path.join(self._thumb_cache_dir, hashed_url + ext)
                if xbmcvfs.exists(local_path):
                    return local_path

            session = self._get_session()
            response = session.get(url, timeout=5)
            response.raise_for_status()
            content = response.content

            file_ext = None
            for signature, ext in valid_signatures.items():
                if content.startswith(signature):
                    if ext == '.webp' and content[8:12] == b'WEBP':
                        file_ext = ext
                        break
                    elif ext != '.webp':
                        file_ext = ext
                        break

            if file_ext:
                local_path = os.path.join(self._thumb_cache_dir, hashed_url + file_ext)
                with xbmcvfs.File(local_path, 'wb') as f:
                    f.write(content)
                return local_path
            else:
                return self.icons['default']

        except Exception as e:
            self.logger.error(f"Failed to process thumb {url}: {e}")
            return self.icons['default']

    def _preload_thumbnails(self, thumb_urls):
        """Preload all thumbnails in parallel using ThreadPoolExecutor."""
        if not thumb_urls:
            return {}
        
        result_map = {}
        
        with ThreadPoolExecutor(max_workers=20) as executor:
            future_to_url = {
                executor.submit(self._download_and_validate_thumb, url): url 
                for url in thumb_urls
            }
            
            for future in as_completed(future_to_url):
                original_url = future_to_url[future]
                try:
                    result_map[original_url] = future.result()
                except Exception as e:
                    self.logger.error(f"Parallel thumb download failed for {original_url}: {e}")
                    result_map[original_url] = self.icons['default']
        
        return result_map

    def add_link(self, name, url, mode, icon, fanart, context_menu=None, info_labels=None):
        try:
            if icon and not icon.startswith('http'):
                processed_icon = icon
            else:
                processed_icon = self._download_and_validate_thumb(icon) if icon else icon
        except Exception as e:
            self.logger.error(f"Thumb download failed: {e}")
            processed_icon = icon
        super().add_link(name, url, mode, processed_icon, fanart, context_menu, info_labels)

    def _parse_duration(self, duration_str):
        try:
            parts = duration_str.split(':')
            if len(parts) == 2:
                return int(parts[0]) * 60 + int(parts[1])
            elif len(parts) == 3:
                return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
        except:
            pass
        return 0

    def get_listing(self, url):
        html = self.make_request(url)
        if not html:
            return []

        videos = []
        pattern = r'<div class="item\s*">\s*<a href="([^"]+)"[^>]*title="([^"]+)"[^>]*>.*?<img[^>]+src="([^"]+)".*?<span class="is-hd">([^<]+)</span>'
        items = re.findall(pattern, html, re.DOTALL)

        for link, title, thumb, duration in items:
            title = title.strip()
            duration = duration.strip()
            if thumb.startswith("//"):
                thumb = "https:" + thumb

            videos.append({
                "title": title,
                "url": link,
                "thumb": thumb,
                "duration": duration
            })

        self.next_page = None
        
        has_more = re.search(r'data-parameters="[^"]*from:(\d+)"', html)
        
        page_match = re.search(r'/videos/(\d+)/', url)
        if page_match:
            current_page = int(page_match.group(1))
            if len(videos) >= 20 and has_more:
                self.next_page = f"https://area51.porn/videos/{current_page + 1}/"
        else:
            if len(videos) >= 20 and has_more:
                self.next_page = "https://area51.porn/videos/2/"

        return videos

    def get_categories(self):
        url = "https://area51.porn/category/"
        html = self.make_request(url)
        if not html:
            return []

        categories = []
        pattern = r'<a class="item_cat" href="([^"]+)" title="([^"]+)">'
        items = re.findall(pattern, html)

        for link, title in items:
            categories.append({
                "title": title.strip(),
                "url": link,
                "thumb": self.icons['default']
            })
        return categories

    def resolve(self, url):
        """Resolve video page URL to playable stream URL."""
        html = self.make_request(url)
        if not html:
            return None

        embed_match = re.search(r'property="og:video:url" content="([^"]+)"', html)
        if not embed_match:
            self.logger.error("No embed URL found in video page")
            return None
        embed_url = embed_match.group(1)

        embed_html = self.make_request(embed_url)
        if not embed_html:
            self.logger.error("Failed to load embed page")
            return None

        video_url = None

        v_match = re.search(r"video_url:\s*'([^']+)'", embed_html)
        if v_match:
            video_url = v_match.group(1)

        if not video_url:
            v_match = re.search(r'video_url:\s*"([^"]+)"', embed_html)
            if v_match:
                video_url = v_match.group(1)

        if video_url:
            try:
                session = self._get_session()
                response = session.head(video_url, timeout=10, allow_redirects=True)
                final_url = response.url
                ua = urllib.parse.quote(self.get_headers()['User-Agent'])
                return f"{final_url}|User-Agent={ua}"
            except Exception as e:
                self.logger.error(f"Failed to resolve video redirect: {e}")
                ua = urllib.parse.quote(self.get_headers()['User-Agent'])
                return f"{video_url}|User-Agent={ua}"

        return None

    def play_video(self, url):
        """Play video from given URL."""
        resolved_url = self.resolve(url)
        if resolved_url:
            li = xbmcgui.ListItem(path=resolved_url)
            li.setMimeType('video/mp4')
            li.setProperty('IsPlayable', 'true')
            xbmcplugin.setResolvedUrl(self.addon_handle, True, li)
        else:
            self.notify_error("Could not resolve video URL")
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())

    def search(self, query):
        if not query:
            return

        q = urllib.parse.quote_plus(query)
        url = f"{self.base_url}search/{q}/"
        self.process_content(url)

    def process_content(self, url):
        if url == "categories":
            cats = self.get_categories()
            for c in cats:
                self.add_dir(c['title'], c['url'], 2, c['thumb'])
            self.end_directory()
            return

        self.add_dir("[COLOR yellow]Search[/COLOR]", "", 5, self.icons['search'])
        self.add_dir("[COLOR yellow]Categories[/COLOR]", "categories", 2, self.icons['categories'])

        videos = self.get_listing(url)

        thumb_urls = [v['thumb'] for v in videos if v.get('thumb')]
        thumb_cache = self._preload_thumbnails(thumb_urls)

        for v in videos:
            cached_thumb = thumb_cache.get(v['thumb'], v['thumb'])
            self.add_link(
                name=v['title'],
                url=v['url'],
                mode=4,
                icon=cached_thumb,
                fanart=self.fanart,
                info_labels={'duration': v['duration']}
            )

        if hasattr(self, 'next_page') and self.next_page:
            self.add_dir("Next Page", self.next_page, 2, self.icons['default'])

        self.end_directory()
