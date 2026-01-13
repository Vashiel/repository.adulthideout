import re
import os
import urllib.parse
import urllib.request
import xbmc
import xbmcgui
import xbmcplugin
from resources.lib.base_website import BaseWebsite


class EmpflixWebsite(BaseWebsite):
    def __init__(self, addon_handle, addon=None):
        super().__init__(
            name="empflix",
            base_url="https://www.empflix.com",
            search_url="https://www.empflix.com/search?what={}",
            addon_handle=addon_handle,
            addon=addon
        )
        self.sort_options = ["Featured", "Most Recent", "Top Rated"]
        self.content_types = ["All"]
        self.sort_paths = {
            0: "/featured",
            1: "/new",
            2: "/toprated"
        }
        self.icon = os.path.join(self.addon.getAddonInfo('path'), 'resources', 'logos', 'empflix.png')

    def get_start_url_and_label(self):
        sort_id = f"{self.name}_sort_by"
        sort_index = int(self.addon.getSetting(sort_id) or '0')
        path = self.sort_paths.get(sort_index, "/")
        label = f"EMPFlix - {self.sort_options[sort_index]}"
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
        self.add_dir('Categories', f'{self.base_url}/categories', 8, self.icons.get('categories'))

    def process_video_list(self, url):
        content = self.make_request(url)
        if not content:
            self.notify_error("Failed to load page")
            self.end_directory()
            return

        video_pattern = r'href="(https://www\.empflix\.com/[^"]+/video(\d+))"'
        video_matches = re.findall(video_pattern, content)
        
        thumb_lookup = {}
        
        thumb_pattern1 = r'"(https://img\.empflix\.com/[^"]+/(\d+)/thumbs/[^"]+\.jpg)"'
        thumb_pattern2 = r'"(https://cdnl\.empflix\.com/[^"]+/(\d+)/[^"]+\.jpg)"'
        thumb_pattern3 = r'data-src="(https://[^"]*empflix[^"]+/(\d+)[^"]+\.jpg)"'
        thumb_pattern4 = r'src="(https://img\.empflix\.com/[^"]+/thumbs/[^/]+/\d+_(\d+)l\.jpg)"'
        thumb_pattern5 = r'"(https://img\.empflix\.com/[^"]+_(\d+)l\.(?:jpg|webp))"'
        
        for pattern in [thumb_pattern1, thumb_pattern2, thumb_pattern3, thumb_pattern4, thumb_pattern5]:
            for thumb_url, vid_id in re.findall(pattern, content):
                if vid_id not in thumb_lookup:
                    thumb_lookup[vid_id] = thumb_url
        
        seen = set()
        unique_videos = []
        for full_url, video_id in video_matches:
            if full_url not in seen:
                seen.add(full_url)
                unique_videos.append((full_url, video_id))

        items_added = 0
        for video_url, video_id in unique_videos:
            title_match = re.search(r'/([^/]+)/video\d+$', video_url)
            if title_match:
                title = title_match.group(1).replace('-', ' ').title()
            else:
                title = "Unknown Video"
            
            thumb = thumb_lookup.get(video_id, "")
            if not thumb:
                vid_len = len(video_id)
                if vid_len >= 4:
                    p1 = video_id[:2]
                    p2 = video_id[2:4]
                else:
                    p1 = "0"
                    p2 = video_id[:2] if vid_len >= 2 else "0"
                thumb = f"https://img.empflix.com/a16:8q80w500r/180/{p1}/{p2}/{video_id}/thumbs/28.jpg"
            
            self.add_link(title, video_url, 4, thumb, self.fanart)
            items_added += 1

        if items_added > 0:
            page_match = re.search(r'/(\d+)/?$', url)
            current_page = int(page_match.group(1)) if page_match else 1
            next_page = current_page + 1
            
            if page_match:
                next_url = re.sub(r'/\d+/?$', f'/{next_page}/', url)
            else:
                base = url.rstrip('/')
                next_url = f"{base}/{next_page}/"
            
            self.add_dir(f"[COLOR blue]Next Page ({next_page}) >>[/COLOR]", next_url, 2, self.icons.get('default'))
        else:
            self.notify_error("No videos found")
                
        self.end_directory()

    def process_categories(self, url):
        cat_url = f"{self.base_url}/categories"
        content = self.make_request(cat_url)
        
        if not content:
            self.notify_error("Failed to load categories")
            self.end_directory()
            return
        
        cat_pattern = r'href="(https://www\.empflix\.com/[^"]+)"[^>]*>\s*<img[^>]+src="([^"]+)"[^>]*>\s*<div class="thumb-title">([^<]+)</div>'
        categories = re.findall(cat_pattern, content)
        
        if not categories:
            cat_pattern2 = r'<a class="thumb[^"]*" href="(https://www\.empflix\.com/[^"]+)"[^>]*>.*?src="([^"]+)".*?<div class="thumb-title">([^<]+)</div>'
            categories = re.findall(cat_pattern2, content, re.DOTALL)
        
        if not categories:
            thumb_lookup = {}
            thumb_pattern = r'src="(https://img\.empflix\.com/[^"]*category_avatars/([^"]+)\.jpg)"'
            for thumb_url, slug in re.findall(thumb_pattern, content):
                thumb_lookup[slug] = thumb_url
            
            cat_pattern3 = r'href="(https://www\.empflix\.com/([^"]+)-porn)"'
            for cat_url, slug in re.findall(cat_pattern3, content):
                slug_key = f"{slug}-porn"
                title = slug.replace('-', ' ').title()
                thumb = thumb_lookup.get(slug_key, self.icons.get('categories'))
                self.add_dir(title, cat_url, 2, thumb)
        else:
            for cat_url, thumb, title in categories:
                self.add_dir(title.strip(), cat_url, 2, thumb)
            
        self.end_directory()

    def process_search(self, query):
        search_url = self.search_url.format(urllib.parse.quote(query))
        content = self.make_request(search_url)
        if not content:
            self.notify_error("Search failed")
            self.end_directory()
            return

        video_pattern = r'href="(https://www\.empflix\.com/[^"]+/video(\d+))"'
        video_matches = re.findall(video_pattern, content)
        
        thumb_pattern1 = r'"(https://img\.empflix\.com/[^"]+/(\d+)/thumbs/[^"]+\.jpg)"'
        thumb_pattern2 = r'"(https://cdnl\.empflix\.com/[^"]+/(\d+)/[^"]+\.jpg)"'
        thumb_pattern3 = r'data-src="(https://[^"]*empflix[^"]+/(\d+)[^"]+\.jpg)"'
        
        thumb_lookup = {}
        for pattern in [thumb_pattern1, thumb_pattern2, thumb_pattern3]:
            for thumb_url, vid_id in re.findall(pattern, content):
                if vid_id not in thumb_lookup:
                    thumb_lookup[vid_id] = thumb_url
        
        seen = set()
        unique_videos = []
        for full_url, video_id in video_matches:
            if full_url not in seen:
                seen.add(full_url)
                unique_videos.append((full_url, video_id))

        items_added = 0
        for video_url, video_id in unique_videos:
            title_match = re.search(r'/([^/]+)/video\d+$', video_url)
            if title_match:
                title = title_match.group(1).replace('-', ' ').title()
            else:
                title = "Unknown Video"
            
            thumb = thumb_lookup.get(video_id, "")
            if not thumb:
                vid_len = len(video_id)
                if vid_len >= 4:
                    p1 = video_id[:2]
                    p2 = video_id[2:4]
                else:
                    p1 = "0"
                    p2 = video_id[:2] if vid_len >= 2 else "0"
                thumb = f"https://img.empflix.com/a16:8q80w500r/180/{p1}/{p2}/{video_id}/thumbs/28.jpg"
            
            self.add_link(title, video_url, 4, thumb, self.fanart)
            items_added += 1

        if items_added == 0:
            self.notify_error("No search results")
                
        self.end_directory()

    def play_video(self, url):
        content = self.make_request(url)
        if not content:
            self.notify_error("Failed to load video page")
            return

        video_url = None
        
        mp4_match = re.search(r'"(https?://[^"]+\.mp4[^"]*)"', content)
        if mp4_match:
            video_url = mp4_match.group(1)
        
        if not video_url:
            m3u8_match = re.search(r'"(https?://[^"]+\.m3u8[^"]*)"', content)
            if m3u8_match:
                video_url = m3u8_match.group(1)

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
