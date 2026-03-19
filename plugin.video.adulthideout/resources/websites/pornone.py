import re
import urllib.parse
import html
import os
import xbmc
import xbmcgui
import xbmcplugin
import sys
from resources.lib.base_website import BaseWebsite

class PornOne(BaseWebsite):
    
    def __init__(self, addon_handle=None, addon=None):
        super().__init__(
            name="pornone",
            base_url="https://pornone.com",
            search_url="https://pornone.com/search/{}/",
            addon_handle=addon_handle,
            addon=addon
        )
        self.logo = self.icon
        self.icons['default'] = self.logo
        self.icons['search'] = os.path.join(self.addon.getAddonInfo('path'), 'resources', 'logos', 'search.png')
        self.icons['categories'] = os.path.join(self.addon.getAddonInfo('path'), 'resources', 'logos', 'categories.png')
        self.icons['channels'] = self.icons['categories'] # Fallback
        
        # Sorting Options
        self.sort_options = ["Newest", "Views", "Top Rated", "Longest"]
        self.sort_paths = {
            "Newest": "/newest/",
            "Views": "/views/",
            "Top Rated": "/rating/",
            "Longest": "/longest/"
        }

    def make_request(self, url):
        try:
            self.logger.info(f"Requesting: {url}")
            import requests
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Referer': self.base_url
            }
            response = requests.get(url, headers=headers, timeout=15)
            if response.status_code == 200:
                return response.text
            else:
                self.logger.error(f"Request failed: {response.status_code}")
                return None
        except Exception as e:
            self.logger.error(f"Request error: {e}")
            return None

    def process_content(self, url):
        if url == "BOOTSTRAP":
            self.add_dir("Search", "", 5, self.icons['search'])
            self.add_dir("Categories", "categories", 8, self.icons['categories'])
            self.add_dir("Channels", "channels", 8, self.icons['channels'])
            
            url, _ = self.get_start_url_and_label()
            self.get_listing(url)
            return

        self.add_dir("Search", "", 5, self.icons['search'])
        self.add_dir("Categories", "categories", 8, self.icons['categories'])
        
        self.get_listing(url)

    def get_listing(self, url):
        html_content = self.make_request(url)
        if not html_content:
            return self.end_directory()

        # Fixed video regex: href first, then class, then data-src
        item_pattern = r'href="([^"]+)"[^>]*class="[^"]*videocard[^"]*"[^>]*>.*?data-src="([^"]+)".*?class="videotitle[^"]*"[^>]*>([^<]+)'
        items = re.findall(item_pattern, html_content, re.DOTALL)

        for link, thumb, title in items:
            title = html.unescape(title.strip())
            if not link.startswith('http'):
                link = urllib.parse.urljoin(self.base_url, link)
            
            self.add_link(title, link, 4, thumb, self.fanart)

        # Pagination: /page/2/
        if "/page/" in url:
            curr_match = re.search(r'/page/(\d+)/', url)
            if curr_match:
                next_page = int(curr_match.group(1)) + 1
                next_url = re.sub(r'/page/\d+/', f'/page/{next_page}/', url)
            else:
                next_url = url.rstrip('/') + "/page/2/"
        else:
            next_url = url.rstrip('/') + "/page/2/"
            
        if len(items) >= 20: 
             self.add_dir("Next >>", next_url, 2, self.icons['default'])

        self.end_directory()

    def process_categories(self, url):
        if url == "categories":
            url = urllib.parse.urljoin(self.base_url, "/categories/")
        elif url == "channels":
            url = urllib.parse.urljoin(self.base_url, "/channels/")
            
        html_content = self.make_request(url)
        if not html_content:
            return self.end_directory()

        # Fixed category regex: href first, then data-src and catNameDrop
        cat_pattern = r'href="([^"]+)"[^>]*class="[^"]*popbop[^"]*"[^>]*>.*?data-src="([^"]+)".*?class="catNameDrop[^"]*"[^>]*>([^<]+)</div>'
        cats = re.findall(cat_pattern, html_content, re.DOTALL)

        for link, thumb, name in cats:
            name = html.unescape(name.strip())
            if not link.startswith('http'):
                link = urllib.parse.urljoin(self.base_url, link)
            
            self.add_dir(name, link, 2, thumb)

        self.end_directory()

    def play_video(self, url):
        html_content = self.make_request(url)
        if not html_content:
            return
        
        # Look for video URL
        # PornOne often uses a data-config or direct video.js setup
        # Research showed HLS or direct MP4
        # <source src="https://...playlist.m3u8" type="application/x-mpegURL">
        video_match = re.search(r'<source[^>]*src="([^"]+)"[^>]*type="video/mp4"', html_content)
        if not video_match:
            video_match = re.search(r'<source[^>]*src="([^"]+)"[^>]*type="application/x-mpegURL"', html_content)
            
        if video_match:
            video_url = video_match.group(1)
            if video_url.startswith('//'):
                video_url = "https:" + video_url
            
            liz = xbmcgui.ListItem(path=video_url)
            xbmcplugin.setResolvedUrl(self.addon_handle, True, listitem=liz)
        else:
            # Try to find in javascript
            js_match = re.search(r'file\s*:\s*"([^"]+\.mp4[^"]*)"', html_content)
            if js_match:
                video_url = js_match.group(1)
                liz = xbmcgui.ListItem(path=video_url)
                xbmcplugin.setResolvedUrl(self.addon_handle, True, listitem=liz)
            else:
                self.logger.error("Could not find video URL")
                self.notify_error("Could not resolve video URL")
