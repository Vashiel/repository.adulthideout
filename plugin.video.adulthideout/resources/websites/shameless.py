
import re
import sys
import urllib.parse
import urllib.request
import xbmcgui
import xbmcplugin
import xbmc
from resources.lib.base_website import BaseWebsite

class ShamelessWebsite(BaseWebsite):
    def __init__(self, addon_handle, addon=None):
        super().__init__(
            name="shameless",
            base_url="https://shameless.com",
            search_url="https://shameless.com/search/{}/",
            addon_handle=addon_handle,
            addon=addon
        )
        self.sort_options = ["Newest", "Most Popular", "Top Rated"]

    def get_start_url_and_label(self):
        setting_id = f"{self.name}_sort_order"
        sort_index = int(self.addon.getSetting(setting_id) or '0')
        
        if sort_index == 1:
            return f"{self.base_url}/most-popular/", f"Shameless - Most Popular"
        elif sort_index == 2:
            return f"{self.base_url}/top-rated/", f"Shameless - Top Rated"
        return f"{self.base_url}/latest-updates/", f"Shameless - Newest"

    def make_request(self, url):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"})
            with urllib.request.urlopen(req, timeout=15) as response:
                return response.read().decode('utf-8')
        except Exception:
            return None

    def process_content(self, url):
        self.add_basic_dirs(url)
        content = self.make_request(url)
        if content:
            self.parse_video_list(content, url)
            self.add_next_button(content, url)
        self.end_directory()

    def add_basic_dirs(self, current_url):
        self.add_dir('[COLOR blue]Search[/COLOR]', '', 5, self.icons['search'])
        self.add_dir('Categories', f'{self.base_url}/categories/', 8, self.icons['categories'])

    def parse_video_list(self, content, current_url):
        cards = re.finditer(r'<div[^>]*class="[^"]*card[^"]*"[^>]*>(.*?)</div>', content, re.DOTALL)
        
        seen_urls = set()
        for card_match in cards:
            card_html = card_match.group(1)
            
            link_m = re.search(r'<a[^>]+href="([^"]+/videos/[^"]+)"[^>]*title="([^"]+)"', card_html)
            if not link_m: continue
            
            video_url, title = link_m.groups()
            
            if not video_url.startswith('http'):
                full_url = urllib.parse.urljoin(self.base_url, video_url)
            else:
                full_url = video_url
            
            if full_url in seen_urls:
                continue
            seen_urls.add(full_url)

            thumb = self.fanart
            
            for attr in ['data-src', 'data-original', 'src']:
                img_m = re.search(r'<img[^>]+' + attr + r'="([^"]+)"', card_html)
                if img_m:
                    t_url = img_m.group(1)
                    
                    if '.mp4' in t_url or 'blank.gif' in t_url or 'placeholder' in t_url or 'data:image' in t_url:
                        continue
                    
                    if t_url.startswith('//'):
                        t_url = 'https:' + t_url
                    elif not t_url.startswith('http'):
                        t_url = urllib.parse.urljoin(self.base_url, t_url)
                    
                    thumb = t_url
                    break

            self.add_link(title.strip(), full_url, 4, thumb, self.fanart)

    def _extract_first_video_url(self, content):
        match = re.search(r'<a[^>]+href="([^"]+/videos/[^"]+)"[^>]*title="([^"]+)"', content)
        if not match:
            return None
        video_url = match.group(1)
        if not video_url.startswith('http'):
            return urllib.parse.urljoin(self.base_url, video_url)
        return video_url

    def add_next_button(self, content, current_url):
        parsed = urllib.parse.urlparse(current_url)
        path_parts = [part for part in parsed.path.strip('/').split('/') if part]
        current_page = 1
        if path_parts and path_parts[-1].isdigit():
            current_page = int(path_parts.pop())

        base_path = '/' + '/'.join(path_parts) + '/'
        next_url = urllib.parse.urljoin(self.base_url, f"{base_path}{current_page + 1}/")

        next_content = self.make_request(next_url)
        if not next_content:
            return

        current_first = self._extract_first_video_url(content)
        next_first = self._extract_first_video_url(next_content)
        if not next_first or next_first == current_first:
            return

        self.add_dir('[COLOR blue]Next Page >>>>[/COLOR]', next_url, 2, self.icons['default'], self.fanart)

    def play_video(self, url):
        content = self.make_request(url)
        if content:
            matches = re.findall(r'(https?://[^"\'\s]+/get_file/[^"\'\s]+\.mp4)', content)
            
            if matches:
                 hd = [m for m in matches if 'hd' in m or '720p' in m or '1080p' in m]
                 if hd: video_url = hd[0]
                 else: video_url = matches[0]
                 
                 li = xbmcgui.ListItem(path=video_url)
                 xbmcplugin.setResolvedUrl(self.addon_handle, True, li)
                 return
        
        self.notify_error("No video found")

    def process_categories(self, url):
        content = self.make_request(url)
        if content:
            pattern = r'<a[^>]+href="([^"]+/categories/[^"]+)"[^>]*>([^<]+)</a>'
            matches = re.findall(pattern, content)
            
            seen = set()
            for cat_url, text in matches:
                name = re.sub(r'<[^>]+>', '', text).strip()
                if not name: continue
                
                if cat_url in seen: continue
                seen.add(cat_url)
                
                full_url = cat_url
                if not full_url.startswith('http'):
                    full_url = urllib.parse.urljoin(self.base_url, full_url)
                    
                self.add_dir(name, full_url, 2, self.icons['default'], self.fanart)

        self.end_directory()
