
import re
import urllib.parse
import json
import xbmcgui
import xbmcplugin
import xbmcaddon
import xbmc
import xbmcvfs
import sys
import os
import html
from resources.lib.base_website import BaseWebsite

try:
    addon_path = xbmcaddon.Addon().getAddonInfo('path')
    vendor_path = os.path.join(addon_path, 'resources', 'lib', 'vendor')
    if vendor_path not in sys.path:
        sys.path.insert(0, vendor_path)
except Exception:
    pass

import cloudscraper

class CumLouder(BaseWebsite):
    
    def __init__(self, addon_handle, addon=None):
        super().__init__(
            name="cumlouder",
            base_url="https://www.cumlouder.com",
            search_url="https://www.cumlouder.com/search/?q={}",
            addon_handle=addon_handle,
            addon=addon
        )
        self.scraper = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'windows', 'desktop': True})
        self.scraper.cookies.set('disclaimer-confirmed', '1', domain='www.cumlouder.com')
        
        self.logo = os.path.join(self.addon.getAddonInfo('path'), 'resources', 'logos', 'cumlouder.png')
        self.icons['default'] = self.logo
        self.icons['search'] = os.path.join(self.addon.getAddonInfo('path'), 'resources', 'logos', 'search.png')
        self.icons['categories'] = os.path.join(self.addon.getAddonInfo('path'), 'resources', 'logos', 'categories.png')

        # Sorting Options
        self.sort_options = ["Newest", "Most Viewed"]
        self.sort_paths = {
            "Newest": "/series/newest/?orderBy=n",
            "Most Viewed": "/series/newest/?orderBy=v"
        }

    def make_request(self, url):
        try:
            self.logger.info(f"Requesting: {url}")
            response = self.scraper.get(url, timeout=15)
            if response.status_code == 200:
                return response.text
            else:
                self.logger.error(f"Request failed: {response.status_code}")
                return None
        except Exception as e:
            self.logger.error(f"Request error: {e}")
            return None

    def get_listing(self, url):
        if url == "BOOTSTRAP":
            # get_start_url_and_label already handles sorting, but as fallback:
            url, _ = self.get_start_url_and_label()
            
        html_content = self.make_request(url)
        if not html_content:
            return []

        videos = []
        # Item pattern: <a class="muestra-escena" href="...">...<img ... data-src="..." ... alt="...">
        item_pattern = r'<a[^>]*class="muestra-escena"[^>]*href="([^"]+)"[^>]*>.*?<img[^>]*data-src="([^"]+)"[^>]*alt="([^"]+)"'
        
        items = re.findall(item_pattern, html_content, re.DOTALL)
        
        for link, thumb, title in items:
            if link.startswith('/'):
                link = self.base_url + link
                
            if thumb.startswith('//'):
                thumb = "https:" + thumb
                
            videos.append({
                "title": html.unescape(title.strip()),
                "url": link,
                "thumb": thumb,
                "duration": ""
            })

        # Pagination
        next_match = re.search(r'<a[^>]*class="btn-pagination"[^>]*href="([^"]+)"[^>]*>Next »</a>', html_content)
        if next_match:
            next_url = next_match.group(1)
            if next_url.startswith('/'):
                next_url = self.base_url + next_url
            
            videos.append({
                "title": "Next Page >>",
                "url": next_url,
                "thumb": self.icons['default'],
                "type": "next_page"
            })

        self.logger.info(f"Found {len(videos)} videos")
        return videos

    def get_categories(self):
        url = self.base_url + "/categories/"
        html_content = self.make_request(url)
        if not html_content:
            return []

        cats = []
        # Pattern for categories based on HTML dump
        cat_pattern = r'<a[^>]*class="[^"]*muestra-categoria[^"]*"[^>]*href="([^"]+)"[^>]*>.*?<img[^>]*data-src="([^"]+)"[^>]*alt="([^"]+)"'
        
        items = re.findall(cat_pattern, html_content, re.DOTALL)
        for link, thumb, title in items:
            if link.startswith('/'):
                link = self.base_url + link
            if thumb.startswith('//'):
                thumb = "https:" + thumb
                
            cats.append({
                "title": html.unescape(title.strip()),
                "url": link,
                "thumb": thumb
            })
            
        return cats

    def resolve(self, url):
        html_content = self.make_request(url)
        if not html_content:
            return None, None
            
        # Extract video URL
        # var urlVideo = "https://...";
        match = re.search(r"var\s+urlVideo\s*=\s*['\"]([^'\"]+)['\"]", html_content)
        if match:
            return match.group(1), url
        return None, None

    def play_video(self, url):
        resolved_url, referer = self.resolve(url)
        if resolved_url:
            ua = self.scraper.headers.get('User-Agent', '')
            final_url = resolved_url + f"|User-Agent={urllib.parse.quote(ua)}&Referer={urllib.parse.quote(referer)}"
            
            li = xbmcgui.ListItem(path=final_url)
            li.setMimeType('video/mp4')
            li.setProperty('IsPlayable', 'true')
            xbmcplugin.setResolvedUrl(self.addon_handle, True, li)
        else:
            xbmcgui.Dialog().notification('AdultHideout', 'Could not resolve video URL', xbmcgui.NOTIFICATION_ERROR, 3000)
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())

    def process_content(self, url):
        # 1. Main Categories Page: No Search/Categories buttons
        if url == "categories":
            cats = self.get_categories()
            for cat in cats:
                self.add_dir(cat['title'], cat['url'], 2, cat['thumb'])
            self.end_directory("videos")
            return

        # 2. All other pages: Show Search and Categories (except on sub-categories if those were to exist)
        videos = self.get_listing(url)
        
        # Add navigation on every page (except categories handled above)
        self.add_dir("Search", "", 5, self.icons['search'])
        self.add_dir("Categories", "categories", 2, self.icons['categories'])

        for v in videos:
            if v.get('type') == 'next_page':
                self.add_dir(v['title'], v['url'], 2, v.get('thumb', self.icons['default']))
            else:
                self.add_link(
                    name=v['title'],
                    url=v['url'],
                    mode=4,
                    icon=v.get('thumb'),
                    fanart=self.fanart,
                    info_labels={'plot': v['title']}
                    # Context menu for sorting is added automatically by BaseWebsite.add_link
                )

        self.end_directory("videos")
