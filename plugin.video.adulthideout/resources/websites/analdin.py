import re
import os
import urllib.parse
import urllib.request
import xbmc
import xbmcgui
import xbmcplugin
from resources.lib.base_website import BaseWebsite


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

    def get_start_url_and_label(self):
        sort_id = f"{self.name}_sort_by"
        sort_index = int(self.addon.getSetting(sort_id) or '0')
        path = self.sort_paths.get(sort_index, "/top-rated/")
        label = f"Analdin - {self.sort_options[sort_index]}"
        return f"{self.base_url}{path}", label

    def make_request(self, url):
        try:
            req = urllib.request.Request(url, headers={
                'User-Agent': "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            })
            with urllib.request.urlopen(req, timeout=15) as response:
                return response.read().decode('utf-8')
        except Exception:
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
        
        if not categories:
            self.notify_error("No categories found")
            
        self.end_directory()

    def play_video(self, url):
        content = self.make_request(url)
        if not content:
            self.notify_error("Failed to load video page")
            return

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
            self.notify_error("No video source found")
            return

        video_url = video_url.replace('\\/', '/')
        
        try:
            from resources.lib.proxy_utils import ProxyController, PlaybackGuard
            
            controller = ProxyController(video_url, upstream_headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Referer": url
            })
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
            headers_str = 'User-Agent={}&Referer={}'.format(
                urllib.parse.quote("Mozilla/5.0"),
                urllib.parse.quote(url)
            )
            li = xbmcgui.ListItem(path=video_url + '|' + headers_str)
            li.setMimeType('video/mp4')
            li.setProperty('IsPlayable', 'true')
            xbmcplugin.setResolvedUrl(self.addon_handle, True, li)
