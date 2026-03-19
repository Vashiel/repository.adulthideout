
import re
import urllib.parse
import xbmcgui
import xbmcplugin
import xbmcaddon
import xbmc
import xbmcvfs
import sys
import os
import html
from concurrent.futures import ThreadPoolExecutor, as_completed
# Add vendor path to sys.path
try:
    addon_path = xbmcaddon.Addon().getAddonInfo('path')
    vendor_path = os.path.join(addon_path, 'resources', 'lib', 'vendor')
    if vendor_path not in sys.path:
        sys.path.insert(0, vendor_path)
except Exception:
    pass

import cloudscraper
from resources.lib.base_website import BaseWebsite

class AnySex(BaseWebsite):
    def __init__(self, addon_handle, addon=None):
        super().__init__(
            name="anysex",
            base_url="https://anysex.com",
            search_url="https://anysex.com/search/?q={}",
            addon_handle=addon_handle,
            addon=addon
        )
        self.sort_options = ["Most Recent", "Most Viewed", "Top Rated", "Best"]
        self.sort_paths = {
            "Most Recent": "/videos/new/",
            "Most Viewed": "/videos/most-viewed/",
            "Top Rated": "/videos/top-rated/",
            "Best": "/videos/best/"
        }
        self.scraper = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'windows', 'desktop': True})
        
        # Logo path
        self.logo = os.path.join(self.addon.getAddonInfo('path'), 'resources', 'logos', 'anysex.png')
        self.icons['default'] = self.logo
        self.icons['search'] = os.path.join(self.addon.getAddonInfo('path'), 'resources', 'logos', 'search.png')
        self.icons['categories'] = os.path.join(self.addon.getAddonInfo('path'), 'resources', 'logos', 'categories.png')

        # Initialize cache
        self._thumb_cache_dir = self._initialize_thumb_cache()

    def _initialize_thumb_cache(self):
        addon_profile = xbmcvfs.translatePath(self.addon.getAddonInfo('profile'))
        thumb_dir = os.path.join(addon_profile, 'thumbs', self.name)
        if not xbmcvfs.exists(thumb_dir):
            xbmcvfs.mkdirs(thumb_dir)
        return thumb_dir

    def _process_thumb(self, url):
        if not url or not url.startswith('http'):
            return url
            
        import hashlib
        try:
            hashed_url = hashlib.md5(url.encode('utf-8')).hexdigest()
            
            # Check if any version already exists
            for ext in ['.jpg', '.png', '.webp', '.gif']:
                local_path = os.path.join(self._thumb_cache_dir, hashed_url + ext)
                if xbmcvfs.exists(local_path):
                    return local_path

            # Download and detect
            response = self.scraper.get(url, timeout=10)
            if response.status_code == 200:
                content = response.content
                file_ext = '.jpg' # Default
                
                if content.startswith(b'RIFF') and b'WEBP' in content[8:12]:
                    file_ext = '.webp'
                elif content.startswith(b'\x89PNG'):
                    file_ext = '.png'
                elif content.startswith(b'GIF8'):
                    file_ext = '.gif'
                
                local_path = os.path.join(self._thumb_cache_dir, hashed_url + file_ext)
                with xbmcvfs.File(local_path, 'wb') as f:
                    f.write(content)
                return local_path
            
        except Exception as e:
            self.logger.error(f"Failed to process thumb {url}: {e}")
            
        return url # Fallback to remote if cache fails

    def _preload_thumbnails(self, thumb_urls):
        if not thumb_urls:
            return {}
        
        result_map = {}
        with ThreadPoolExecutor(max_workers=10) as executor:
            future_to_url = {executor.submit(self._process_thumb, url): url for url in thumb_urls}
            for future in as_completed(future_to_url):
                original_url = future_to_url[future]
                try:
                    result_map[original_url] = future.result()
                except Exception as e:
                    self.logger.error(f"Parallel thumb download failed for {original_url}: {e}")
                    result_map[original_url] = original_url
        return result_map

    def make_request(self, url):
        try:
            self.logger.info(f"Requesting: {url}")
            response = self.scraper.get(url)
            if response.status_code == 200:
                return response.text
            else:
                self.logger.error(f"Request failed: {response.status_code}")
                return None
        except Exception as e:
            self.logger.error(f"Request error: {e}")
            return None

    def get_listing(self, url):
        html_content = self.make_request(url)
        if not html_content: return []

        if not html_content: return []

        # Always add Search and Categories buttons
        self.add_dir("Search", "", 5, self.icons['search'])
        self.add_dir("Categories", "categories", 2, self.icons['categories'])

        videos_raw = []
        thumb_urls = []
        # Structure identified: 
        # <a href="https://anysex.com/video/..." ...><img src="..." alt="Title" ...>
        
        # We use a pattern that captures URL, Thumb, and Title (from alt)
        pattern = r'<a href="(https://anysex\.com/video/[^"]+)".*?<img[^>]+src="([^"]+)"[^>]*alt="([^"]+)"'
        items = re.findall(pattern, html_content, re.DOTALL)

        for link, thumb, title in items:
            videos_raw.append({"title": html.unescape(title.strip()), "url": link, "thumb": thumb})
            thumb_urls.append(thumb)

        # Preload thumbnails in parallel
        thumb_map = self._preload_thumbnails(thumb_urls)

        videos = []
        for v in videos_raw:
            processed_thumb = thumb_map.get(v['thumb'], v['thumb'])
            videos.append({
                "title": v['title'],
                "url": v['url'],
                "thumb": processed_thumb,
                "duration": ""
            })

        # Pagination
        # <li class="next"><a href="...">Next</a></li>
        next_page = re.search(r'<li class="next"><a href="([^"]+)"', html_content)
        if next_page:
            next_url = next_page.group(1)
            if not next_url.startswith('http'):
                next_url = urllib.parse.urljoin(self.base_url, next_url)
                
            videos.append({
                "title": "Next Page",
                "url": next_url,
                "type": "next_page"
            })

        return videos

    def process_categories(self, url):
        # Always add Search and Categories buttons even in categories list
        self.add_dir("Search", "", 5, self.icons['search'])
        self.add_dir("Categories", "categories", 2, self.icons['categories'])

        categories = self.get_categories()
        if not categories:
             self.end_directory()
             return

        for cat in categories:
            self.add_dir(
                name=cat['title'], 
                url=cat['url'], 
                mode=2, 
                icon=cat.get('thumb')
            )
            
        self.end_directory()

    def resolve(self, url):
        html_content = self.make_request(url)
        if not html_content: return None
        
        # Pattern: <source src="https://..." type="video/mp4">
        match = re.search(r'<source[^>]+src="([^"]+)"\s*type="video/mp4"', html_content)
        if match:
             video_url = match.group(1)
             if video_url.startswith("//"):
                 video_url = "https:" + video_url
             return video_url
             
        # Fallback for alternative source tag or mobile
        return None

    def play_video(self, url):
        resolved_url = self.resolve(url)
        if resolved_url:
            li = xbmcgui.ListItem(path=resolved_url)
            li.setMimeType('video/mp4')
            li.setProperty('IsPlayable', 'true')
            xbmcplugin.setResolvedUrl(self.addon_handle, True, li)
        else:
            self.notify_error("Could not resolve video URL")
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())

    def process_content(self, url):
        if url == "categories":
            return self.process_categories(url)

        videos = self.get_listing(url)
        
        for v in videos:
            if v.get('type') == 'next_page':
                self.add_dir("Next Page", v['url'], 2, self.icons['default'])
            else:
                self.add_link(
                    name=v['title'],
                    url=v['url'],
                    mode=4,
                    icon=v.get('thumb'),
                    fanart=self.fanart,
                    info_labels={'duration': v.get('duration')}
                )

        self.end_directory()

    def get_categories(self):
        url = f"{self.base_url}/videos/categories/"
        html_content = self.make_request(url)
        if not html_content: return []
        
        cats_raw = []
        thumb_urls = []
        # Structure: <a data-id="5" title="Amateur" href="https://anysex.com/videos/categories/amateur/">...<img ... src="..." alt="Amateur"/>
        pattern = r'<a[^>]+href="(https://anysex\.com/videos/categories/[^"]+)"[^>]*>.*?<img[^>]+src="([^"]+)"[^>]*alt="([^"]+)"'
        items = re.findall(pattern, html_content, re.DOTALL)
        
        for link, thumb, title in items:
             cats_raw.append({"title": html.unescape(title.strip()), "url": link, "thumb": thumb})
             thumb_urls.append(thumb)

        # Preload thumbnails
        thumb_map = self._preload_thumbnails(thumb_urls)

        cats = []
        for c in cats_raw:
             processed_thumb = thumb_map.get(c['thumb'], c['thumb'])
             cats.append({
                "title": c['title'],
                "url": c['url'],
                "thumb": processed_thumb
            })
            
        return cats

