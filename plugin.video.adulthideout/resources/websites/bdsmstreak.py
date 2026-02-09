
import re
import sys
import urllib.parse
import urllib.request
import xbmcgui
import xbmcplugin
import xbmc
from resources.lib.base_website import BaseWebsite

class BdsmstreakWebsite(BaseWebsite):
    def __init__(self, addon_handle, addon=None):
        super().__init__(
            name="bdsmstreak",
            base_url="https://bdsmstreak.com",
            search_url="https://bdsmstreak.com/search?search={}",
            addon_handle=addon_handle,
            addon=addon
        )
        self.sort_options = ["Newest", "Popular"]
        self.ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

    def get_start_url_and_label(self):
        setting_id = f"{self.name}_sort_by"
        try:
            sort_index = int(self.addon.getSetting(setting_id) or '0')
        except ValueError:
            sort_index = 0
        
        if sort_index == 1:
            return f"{self.base_url}/most", f"BDSMstreak - Popular"
        return self.base_url, f"BDSMstreak - Newest"

    def make_request(self, url):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': self.ua})
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
        else:
             self.notify_error("Failed to load content")
        self.end_directory()

    def add_basic_dirs(self, current_url):
        self.add_dir('[COLOR blue]Search[/COLOR]', '', 5, self.icons['search'])
        self.add_dir('Categories', f'{self.base_url}/categories/', 8, self.icons['categories'])

    def parse_video_list(self, content, current_url):
        new_pattern = r'class="video-card"[^>]*>.*?<a href="(/video/[^"]+)"[^>]*>.*?background-image: url\(\'([^\']+)\'\).*?<h3[^>]*class="video-title"[^>]*>([^<]+)</h3>'
        new_matches = re.finditer(new_pattern, content, re.DOTALL)
        
        count = 0
        for match in new_matches:
            video_url, thumb, title = match.groups()
            full_url = urllib.parse.urljoin(self.base_url, video_url)
            full_thumb = urllib.parse.urljoin(self.base_url, thumb)
            self.add_link(title.strip(), full_url, 4, full_thumb, self.fanart)
            count += 1

        if count == 0:
            modern_pattern = r'class="vidlink"[^>]+href="([^"]+)"[^>]*>.*?class="video-card-modern">.*?<img[^>]+alt="([^"]+)"[^>]*src="([^"]+)"'
            modern_matches = re.finditer(modern_pattern, content, re.DOTALL)
            for match in modern_matches:
                video_url, title, thumb = match.groups()
                full_url = urllib.parse.urljoin(self.base_url, video_url)
                full_thumb = urllib.parse.urljoin(self.base_url, thumb)
                self.add_link(title.strip(), full_url, 4, full_thumb, self.fanart)
                count += 1
            
        if count == 0:
             pattern2 = r'<a[^>]+href="(/video/[^"]+)"[^>]*>.*?<img[^>]+src="([^"]+)"'
             matches2 = re.findall(pattern2, content, re.DOTALL)
             for video_url, thumb in matches2:
                full_url = urllib.parse.urljoin(self.base_url, video_url)
                title = video_url.split('/')[-1].replace('-', ' ').title()
                full_thumb = urllib.parse.urljoin(self.base_url, thumb)
                self.add_link(title, full_url, 4, full_thumb, self.fanart)
                count += 1

    def add_next_button(self, content, current_url):
        pattern = r'<a class="page-link"[^>]+href="([^"]+)"'
        match = re.search(pattern, content, re.IGNORECASE)
        if match:
            next_url = match.group(1)
            full_next_url = urllib.parse.urljoin(self.base_url, next_url)
            self.add_dir('[COLOR blue]Next Page >>>>[/COLOR]', full_next_url, 2, self.icons['default'], self.fanart)

    def play_video(self, url):
        content = self.make_request(url)
        if content:
            match = re.search(r'<source[^>]+src="([^"]+)"[^>]*type="video/mp4"', content)
            if not match:
                match = re.search(r'<source[^>]+src="([^"]+)"', content)
            if match:
                video_url = match.group(1)
                if not video_url.startswith('http'):
                    video_url = urllib.parse.urljoin(self.base_url, video_url)
                
                video_url += f"|User-Agent={urllib.parse.quote(self.ua)}"
                
                li = xbmcgui.ListItem(path=video_url)
                xbmcplugin.setResolvedUrl(self.addon_handle, True, li)
                return
        self.notify_error("No video found")

    def process_categories(self, url):
        content = self.make_request(url)
        if content:
            pattern = r'href=[\'"](/category/([^\'"]+))[\'"]'
            matches = re.findall(pattern, content)
            
            seen = set()
            for cat_url, slug in matches:
                if cat_url in seen:
                    continue
                seen.add(cat_url)
                
                if "page=" in cat_url:
                    continue
                
                name = slug.replace('-', ' ').replace("'", '').title()
                full_url = urllib.parse.urljoin(self.base_url, cat_url)
                self.add_dir(name, full_url, 2, self.icons['default'], self.fanart)

        self.end_directory()
