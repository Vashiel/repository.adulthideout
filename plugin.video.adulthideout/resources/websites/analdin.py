import re
import os
import sys
import urllib.parse
import xbmc
import xbmcgui
import xbmcplugin
from resources.lib.base_website import BaseWebsite

try:
    current_dir = os.path.dirname(os.path.abspath(__file__))
    vendor_path = os.path.abspath(os.path.join(current_dir, "..", "lib", "vendor"))
    if os.path.exists(vendor_path) and vendor_path not in sys.path:
        sys.path.insert(0, vendor_path)
except Exception:
    pass

try:
    import cloudscraper
    _HAS_CF = True
except Exception:
    cloudscraper = None
    _HAS_CF = False

try:
    from curl_cffi import requests as curl_requests
    _HAS_CURL = True
except Exception:
    curl_requests = None
    _HAS_CURL = False

import requests


class AnaldinWebsite(BaseWebsite):
    def __init__(self, addon_handle, addon=None):
        super().__init__(
            name="analdin",
            base_url="https://www.analdin.com",
            search_url="https://www.analdin.com/search/?q={}",
            addon_handle=addon_handle,
            addon=addon
        )
        self.sort_options = ["Top Rated", "Most Popular"]
        self.content_types = ["All"]
        self.sort_paths = {
            0: "/top-rated/",
            1: "/most-popular/"
        }
        self.icon = os.path.join(self.addon.getAddonInfo('path'), 'resources', 'logos', 'analdin.png')
        self.user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
        self.session = self._build_session()

    def _build_session(self):
        if _HAS_CURL:
            try:
                return curl_requests.Session(impersonate="chrome123", verify=False)
            except Exception:
                pass
        if _HAS_CF:
            try:
                return cloudscraper.create_scraper()
            except Exception:
                pass
        s = requests.Session()
        s.headers.update({"User-Agent": self.user_agent})
        return s

    def get_start_url_and_label(self):
        sort_id = f"{self.name}_sort_by"
        sort_setting = str(self.addon.getSetting(sort_id) or '0')
        sort_index = int(sort_setting) if sort_setting.isdigit() else 0
        path = self.sort_paths.get(sort_index, "/top-rated/")
        label_text = self.sort_options[sort_index] if 0 <= sort_index < len(self.sort_options) else self.sort_options[0]
        label = f"Analdin - {label_text}"
        return f"{self.base_url}{path}", label

    def make_request(self, url, referer=None):
        headers = {
            'User-Agent': self.user_agent,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
        }
        if referer:
            headers['Referer'] = referer
        try:
            r = self.session.get(url, headers=headers, timeout=20)
            if r.status_code == 200:
                return r.text
        except Exception as e:
            xbmc.log(f"[AdultHideout][Analdin] Request error for {url}: {e}", xbmc.LOGWARNING)
        return None

    def process_content(self, url):
        self.add_basic_dirs(url)
        self.process_video_list(url)

    def add_basic_dirs(self, current_url):
        self.add_dir('[COLOR blue]Search[/COLOR]', '', 5, self.icons.get('search'))
        self.add_dir('Categories', f'{self.base_url}/de/kategorien/', 8, self.icons.get('categories'))

    def process_video_list(self, url):
        content = self.make_request(url)
        if not content:
            self.notify_error("Failed to load page")
            self.end_directory()
            return

        video_pattern = r'href="(https://www\.analdin\.com/(?:de/)?videos/(\d+)/([^"]+)/)"'
        video_matches = re.findall(video_pattern, content)
        
        seen = set()
        unique_videos = []
        for full_url, video_id, title_slug in video_matches:
            if full_url not in seen:
                seen.add(full_url)
                unique_videos.append((full_url, video_id, title_slug))

        items_added = 0
        for video_url, video_id, title_slug in unique_videos:
            title = title_slug.replace('-', ' ').title()
            id_prefix = str(int(video_id) // 1000 * 1000)
            thumb = f"https://i.analdin.com/contents/videos_screenshots/{id_prefix}/{video_id}/preview.jpg"
            self.add_link(title, video_url, 4, thumb, self.fanart)
            items_added += 1

        if items_added > 0:
            page_match = re.search(r'/(\d+)/$', url)
            current_page = int(page_match.group(1)) if page_match else 1
            next_page = current_page + 1
            
            if page_match:
                next_url = re.sub(r'/\d+/$', f'/{next_page}/', url)
            else:
                base = url.rstrip('/')
                next_url = f"{base}/{next_page}/"
            
            self.add_dir(f"[COLOR blue]Next Page ({next_page}) >>[/COLOR]", next_url, 2, self.icons.get('default'))
        else:
            self.notify_error("No videos found")
                
        self.end_directory()

    def process_categories(self, url):
        cat_url = "https://www.analdin.com/de/kategorien/"
        content = self.make_request(cat_url)
        
        if not content:
            self.notify_error("Failed to load categories")
            self.end_directory()
            return
        
        cat_pattern = r'<a class="item" href="(https://www\.analdin\.com/de/kategorien/[^"]+/)" title="([^"]+)"[\s\S]*?<img class="thumb" src="([^"]+)"'
        categories = re.findall(cat_pattern, content)
        
        if not categories:
            cat_pattern2 = r'href="(https://www\.analdin\.com/de/kategorien/([^"]+)/)"[^>]*title="([^"]+)"'
            matches = re.findall(cat_pattern2, content)
            for url_full, slug, title in matches:
                thumb = f"https://i.analdin.com/contents/categories/{slug}.jpg"
                self.add_dir(title, url_full, 2, thumb)
        else:
            for url_full, title, thumb in categories:
                self.add_dir(title, url_full, 2, thumb)
        
        if not categories and not matches:
            self.notify_error("No categories found")
            
        self.end_directory()

    def resolve_recording_stream(self, url):
        content = self.make_request(url)
        if not content:
            return None

        video_url = None
        mp4_match = re.search(r"video_url['\"]?\s*[:=]\s*['\"]([^'\"]+\.mp4[^'\"]*)['\"]", content)
        if mp4_match:
            video_url = mp4_match.group(1)
        if not video_url:
            source_match = re.search(r'<source[^>]+src=["\']([^"\']+\.mp4[^"\']*)["\']', content)
            if source_match:
                video_url = source_match.group(1)
        if not video_url:
            mp4_urls = re.findall(r'"(https?://[^"]+\.mp4[^"]*)"', content)
            if mp4_urls:
                video_url = mp4_urls[0]

        if not video_url:
            return None

        video_url = video_url.replace('\\/', '/')
        headers = {
            "User-Agent": self.user_agent,
            "Referer": url
        }
        return {"url": video_url, "headers": headers, "extension": "mp4"}

    def play_video(self, url):
        resolved = self.resolve_recording_stream(url)
        if resolved:
            video_url = resolved["url"]
            headers = resolved.get("headers", {})
            try:
                from resources.lib.proxy_utils import ProxyController, PlaybackGuard
                controller = ProxyController(video_url, upstream_headers=headers)
                local_url = controller.start()

                monitor = xbmc.Monitor()
                player = xbmc.Player()
                guard = PlaybackGuard(player, monitor, local_url, controller)
                guard.start()

                li = xbmcgui.ListItem(path=local_url)
                li.setMimeType('video/mp4')
                li.setProperty('IsPlayable', 'true')
                li.setContentLookup(False)
                xbmcplugin.setResolvedUrl(self.addon_handle, True, li)
                guard.join()
            except ImportError:
                headers_str = urllib.parse.urlencode(headers)
                li = xbmcgui.ListItem(path=video_url + '|' + headers_str)
                li.setMimeType('video/mp4')
                li.setProperty('IsPlayable', 'true')
                li.setContentLookup(False)
                xbmcplugin.setResolvedUrl(self.addon_handle, True, li)
            return

        self.notify_error("No video source found")
        xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
