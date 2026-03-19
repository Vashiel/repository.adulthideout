import sys
import xbmcgui
import xbmcplugin
import json
import re
import base64
import urllib.parse
from resources.lib.base_website import BaseWebsite

class Upornia(BaseWebsite):
    BASE_URL = "https://upornia.com"
    API_LIST_SEARCH_URL = BASE_URL + '/api/videos.php?params=86400/str/{sort}/60/search..{page}.all..&s={query}&sort={sort}&date=all&type=all&duration=all'
    API_LIST_ROOT_URL = BASE_URL + '/api/json/videos/86400/str/{sort}/60/..{page}.all..day.json'
    API_VIDEO_URL = BASE_URL + '/api/videofile.php?video_id={id}&lifetime=8640000'

    def __init__(self, addon_handle, addon=None):
        super().__init__(
            name="upornia",
            base_url=self.BASE_URL,
            search_url="SEARCH:{}",
            addon_handle=addon_handle,
            addon=addon
        )
        self.sort_options = ['Most Popular', 'Latest Updates', 'Top Rated']
        self.sort_paths = {
            0: "most-popular",
            1: "latest-updates",
            2: "top-rated"
        }
        self.ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        self.headers = {
            'User-Agent': self.ua,
            'Referer': self.BASE_URL,
            'X-Requested-With': 'XMLHttpRequest'
        }

    def make_request(self, url, headers=None):
        req_headers = self.headers.copy()
        if headers:
            req_headers.update(headers)
        try:
            import urllib.request
            req = urllib.request.Request(url, headers=req_headers)
            with urllib.request.urlopen(req, timeout=15) as response:
                return response.read().decode('utf-8')
        except Exception as e:
            import xbmc
            xbmc.log(f"[upornia] API Request Error: {e}", xbmc.LOGWARNING)
            return None

    def tdecode(self, vidurl):
        # Custom decoding logic reverse-engineered from Cumination/Dobbelina
        replacemap = {'M': r'\u041c', 'A': r'\u0410', 'B': r'\u0412', 'C': r'\u0421', 'E': r'\u0415', '=': '~', '+': '.', '/': ','}
        for key, val in replacemap.items():
            vidurl = vidurl.replace(val, key)
        try:
            vidurl = base64.b64decode(vidurl).decode('utf-8')
        except Exception:
            return None
        return vidurl

    def get_start_url_and_label(self):
        sort_id = f"{self.name}_sort_by"
        sort_index = int(self.addon.getSetting(sort_id) or '0')
        sort = self.sort_paths.get(sort_index, "latest-updates")
        label = f"Upornia - {self.sort_options[sort_index]}"
        return f"SORT:{sort}", label

    def process_content(self, url):
        sort = 'latest-updates'
        query = ''
        page = 1

        if url == "BOOTSTRAP" or url == self.BASE_URL:
            # Overwrite with sorting
            sort_id = f"{self.name}_sort_by"
            sort_index = int(self.addon.getSetting(sort_id) or '0')
            sort = self.sort_paths.get(sort_index, "latest-updates")
        elif url.startswith("SORT:"):
            sort = url.replace("SORT:", "")
        elif url.startswith("SEARCH:"):
            sort = 'relevance'
            query = url.replace("SEARCH:", "")
        elif url.startswith("PAGE:"):
            # Format: PAGE:2:latest-updates:query_text
            parts = url.split(":", 3)
            if len(parts) >= 2: page = int(parts[1])
            if len(parts) >= 3: sort = parts[2]
            if len(parts) >= 4: query = parts[3]
        
        if query:
            api_url = self.API_LIST_SEARCH_URL.format(sort=sort, page=page, query=urllib.parse.quote(query))
        else:
            api_url = self.API_LIST_ROOT_URL.format(sort=sort, page=page)
            
        content = self.make_request(api_url, headers=self.headers)
        if not content:
            self.notify_error("API Request Failed")
            self.end_directory()
            return

        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            self.notify_error("Invalid API Response")
            return

        if 'videos' not in data:
            self.notify_error("No videos found")
            self.end_directory()
            return

        videos = data['videos']
        
        
        # Basic Dirs
        if not query:
             self.add_dir("Search", "SEARCH:input", 5, self.icons.get('search', self.icon))
             if page == 1:
                 self.add_dir("Categories", "CATEGORIES", 8, self.icons.get('categories', self.icon))

        # Process videos
        for video in videos:
            vid_id = video.get('video_id')
            title = video.get('title')
            thumb = video.get('scr') # 'scr' seems to be the thumbnail key in Upornia JSON
            duration = video.get('duration')
            
            # Construct playable URL trigger
            video_url = f"PLAY_VIDEO:{vid_id}"
            self.add_link(title, video_url, 4, thumb, self.fanart)

        # Pagination
        if len(videos) == 60: 
            next_url = f"PAGE:{page + 1}:{sort}:{query}"
            self.add_dir(f"[COLOR blue]Next Page ({page + 1}) >>[/COLOR]", next_url, 2, self.icons.get('default'))

        self.end_directory()

    def process_categories(self, url):
        import urllib.request
        api_url = "https://upornia.com/api/json/categories/14400/str.all.en.json"
        content = self.make_request(api_url, headers=self.headers)
        if not content:
            self.end_directory()
            return
            
        try:
            data = json.loads(content)
            cats = data.get('categories', [])
            for cat in cats:
                title = cat.get('title')
                cat_dir = cat.get('dir')
                cat_url = f"PAGE:1:latest-updates:{cat_dir}"  # Approximate it with search or rely on root category filter if it existed, but passing cat as search query works well enough for generic terms
                self.add_dir(title, cat_url, 2, self.icons.get('categories'))
        except Exception:
            pass
            
        self.end_directory()

    def play_video(self, url):
        # Url format: PLAY_VIDEO:12345
        if url.startswith("PLAY_VIDEO:"):
            vid_id = url.split(":")[1]
        else:
            self.notify_error("Invalid Video ID")
            return

        # Fetch video details
        details_url = self.API_VIDEO_URL.format(id=vid_id)
        content = self.make_request(details_url, headers=self.headers)
        
        if not content:
            self.notify_error("Failed to get video details")
            return

        # Extract encoded URL
        match = re.search(r'video_url":"([^"]+)', content)
        if not match:
            self.notify_error("Video URL not found in API")
            return

        encoded_url = match.group(1)
        final_url = self.tdecode(encoded_url)
        
        if not final_url:
            self.notify_error("Failed to decode video URL")
            return

        if not final_url.startswith('http'):
            final_url = self.BASE_URL + final_url

        try:
            from resources.lib.proxy_utils import ProxyController, PlaybackGuard
            controller = ProxyController(final_url, upstream_headers={
                "User-Agent": self.ua,
                "Referer": self.BASE_URL
            })
            local_url = controller.start()
            
            li = xbmcgui.ListItem(path=local_url)
            li.setMimeType('video/mp4')
            li.setProperty('IsPlayable', 'true')
            li.setContentLookup(False)
            
            xbmcplugin.setResolvedUrl(self.addon_handle, True, li)
            
            import xbmc
            monitor = xbmc.Monitor()
            while not monitor.abortRequested() and not xbmc.Player().isPlaying():
                monitor.waitForAbort(0.5)
            while not monitor.abortRequested() and xbmc.Player().isPlaying():
                monitor.waitForAbort(1)
            controller.stop()

        except ImportError:
            li = xbmcgui.ListItem(path=final_url)
            li.setMimeType('video/mp4')
            li.setProperty('IsPlayable', 'true')
            xbmcplugin.setResolvedUrl(self.addon_handle, True, li)
