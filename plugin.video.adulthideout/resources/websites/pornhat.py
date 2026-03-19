import re
import urllib.parse
import html
import os
import xbmc
import xbmcgui
import xbmcplugin
import sys
from resources.lib.base_website import BaseWebsite

class PornHat(BaseWebsite):
    
    def __init__(self, addon_handle, addon=None):
        super().__init__(
            name="pornhat",
            base_url="https://www.pornhat.com",
            search_url="https://www.pornhat.com/search/video/?q={}",
            addon_handle=addon_handle,
            addon=addon
        )
        self.logo = self.icon
        self.icons['default'] = self.logo
        self.icons['search'] = os.path.join(self.addon.getAddonInfo('path'), 'resources', 'logos', 'search.png')
        self.icons['categories'] = os.path.join(self.addon.getAddonInfo('path'), 'resources', 'logos', 'categories.png')
        
        # Sorting Options
        self.sort_options = ["Newest", "Top Rated", "Most Viewed", "Longest"]
        self.sort_paths = {
            "Newest": "/",
            "Top Rated": "/top-rated/",
            "Most Viewed": "/most-viewed/",
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
            # Mandatory items for KVAT
            self.add_dir("Search", "", 5, self.icons['search'])
            self.add_dir("Categories", "categories", 8, self.icons['categories'])
            
            # Follow with home page videos
            url, _ = self.get_start_url_and_label()
            self.get_listing(url)
            return

        # Consistent navigation for sub-listings
        self.add_dir("Search", "", 5, self.icons['search'])
        self.add_dir("Categories", "categories", 8, self.icons['categories'])
        
        self.get_listing(url)

    def get_listing(self, url):
        html_content = self.make_request(url)
        if not html_content:
            return self.end_directory()

        # Regex captures: link, title, thumbnail
        item_pattern = r'<div[^>]*class="[^"]*thumb-bl-video[^"]*"[^>]*>.*?<a[^>]*href="([^"]+)"[^>]*title="([^"]+)"[^>]*>.*?<img[^>]*(?:src|data-original)="([^"]+)"'
        items = re.findall(item_pattern, html_content, re.DOTALL)

        for link, title, thumb in items:
            title = html.unescape(title.strip())
            if not link.startswith('http'):
                link = urllib.parse.urljoin(self.base_url, link)
            if not thumb.startswith('http'):
                thumb = urllib.parse.urljoin(self.base_url, thumb)
            
            self.add_link(title, link, 4, thumb, self.fanart)

        # Pagination for KVAT
        next_match = re.search(r'<li[^>]*class="[^"]*next[^"]*"[^>]*>.*?<a[^>]*href="([^"]+)"', html_content, re.DOTALL)
        if not next_match:
            next_match = re.search(r'<a[^>]*href="([^"]+)"[^>]*>(?:Next|Next &raquo;)</a>', html_content, re.IGNORECASE)

        if next_match:
            next_url = next_match.group(1)
            if not next_url.startswith('http'):
                next_url = urllib.parse.urljoin(self.base_url, next_url)
            self.add_dir("Next >>", next_url, 2, self.icons['default'])

        self.end_directory()

    def process_categories(self, url):
        if url == "categories":
            url = urllib.parse.urljoin(self.base_url, "/channels/")
            
        html_content = self.make_request(url)
        if not html_content:
            return self.end_directory()

        # Regex for categories
        cat_block_pattern = r'<a[^>]*href="(/sites/[^/]+/)"[^>]*>.*?<img[^>]*(?:src|data-original)="([^"]+)"[^>]*>.*?<p>([^<]+)'
        cats = re.findall(cat_block_pattern, html_content, re.DOTALL)

        for link, thumb, name in cats:
            name = name.strip()
            if not link.startswith('http'):
                link = urllib.parse.urljoin(self.base_url, link)
            if not thumb.startswith('http'):
                thumb = urllib.parse.urljoin(self.base_url, thumb)
            
            # Categories point to listing (mode 2)
            self.add_dir(name, link, 2, thumb)

        self.end_directory()

    def play_video(self, url):
        html_content = self.make_request(url)
        if not html_content:
            return
        
        # Look for the video URL in the script
        video_match = re.search(r"let url = '([^']+)';", html_content)
        if not video_match:
             video_match = re.search(r"videoUrl\s*=\s*'([^']+)'", html_content)
             
        if video_match:
            video_url = video_match.group(1)
            if video_url.startswith('//'):
                video_url = "https:" + video_url
            
            liz = xbmcgui.ListItem(path=video_url)
            xbmcplugin.setResolvedUrl(self.addon_handle, True, listitem=liz)
        else:
            self.logger.error("Could not find video URL in page source")
            self.notify_error("Could not resolve video URL")
