
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

class PornMZ(BaseWebsite):
    
    def __init__(self, addon_handle, addon=None):
        super().__init__(
            name="pornmz",
            base_url="https://pornmz.com",
            search_url="https://pornmz.com/?s={}",
            addon_handle=addon_handle,
            addon=addon
        )
        self.scraper = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'windows', 'desktop': True})
        
        self.logo = os.path.join(self.addon.getAddonInfo('path'), 'resources', 'logos', 'pornmz.png')
        self.icons['default'] = self.logo
        self.icons['search'] = os.path.join(self.addon.getAddonInfo('path'), 'resources', 'logos', 'search.png')
        self.icons['categories'] = os.path.join(self.addon.getAddonInfo('path'), 'resources', 'logos', 'categories.png')

    def make_request(self, url):
        try:
            self.logger.info(f"Requesting: {url}")
            # User reported slow loading, increased timeout to 60s
            response = self.scraper.get(url, timeout=60)
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
            url = self.base_url + "/"
            
        html_content = self.make_request(url)
        if not html_content:
            return []

        # Extract Main Content
        main_content = self.slice_content(html_content)
        
        videos = []
        # Robust regex for videos
        item_pattern = r'<a[^>]*href="([^"]*video/id=pm(?!actor)[^"]+)"[^>]*>.*?<img[^>]*(?:src|data-src)="([^"]+)"[^>]*alt="([^"]+)"'
        
        items = re.findall(item_pattern, main_content, re.DOTALL)
        
        for link, thumb, title in items:
            # Quote thumb URL to handle special chars like em-dash
            thumb = urllib.parse.quote(thumb, safe=":/")
            
            videos.append({
                "title": html.unescape(title.strip()),
                "url": link,
                "thumb": thumb,
                "duration": ""
            })

        # Pagination (Check main content first, then fallback to full)
        # Using main_content for pagination reduces risk of sidebars
        next_match = re.search(r'<a href="([^"]+/page/\d+)">Next</a>', html_content)
        if next_match:
            videos.append({
                "title": "Next Page >>",
                "url": next_match.group(1),
                "type": "next_page"
            })

        return videos

    def get_categories(self, url=None):
        if not url:
            url = f"{self.base_url}/categories"
            
        html_content = self.make_request(url)
        if not html_content:
            return []

        # Slice content for categories too
        main_content = self.slice_content(html_content)
        
        cats = []
        # Updated Regex for cat items
        cat_pattern = r'<a[^>]*href="([^"]*pmvideo/c/[^"]+)"[^>]*>.*?<img[^>]*(?:src|data-src)="([^"]+)"[^>]*>.*?<span[^>]*class="cat-title"[^>]*>(.*?)</span>'
        
        items = re.findall(cat_pattern, main_content, re.DOTALL)
        for link, thumb, title in items:
            thumb = urllib.parse.quote(thumb, safe=":/")
            
            cats.append({
                "title": html.unescape(title.strip()),
                "url": link,
                "thumb": thumb
            })

        # Pagination for Categories (Numeric only, no "Next" text usually)
        # Pattern: <a href=".../page/2" class="inactive">2</a>
        # We need to find the link for the *next* page.
        # Simple approach: find 'current' class, then finding the link immediately after it?
        # Or just find all page links and see if there is one > current?
        # Let's try to find the "next page" logic by looking for class="inactive" that is higher than current?
        # Actually, simpler: Look for the current page number, then look for N+1.
        
        current_page_match = re.search(r'<a class="current">(\d+)</a>', html_content)
        if current_page_match:
            current_page = int(current_page_match.group(1))
            next_page = current_page + 1
            # Look for link to next page
            # href=".../categories/page/2"
            next_page_regex = r'<a href="([^"]+/page/' + str(next_page) + r')[^"]*"'
            next_cat_match = re.search(next_page_regex, html_content)
            
            if next_cat_match:
                cats.append({
                    "title": "Next Page >>",
                    "url": next_cat_match.group(1),
                    "type": "next_page"
                })

        return cats

    def slice_content(self, html_content):
        # Extract Main Content
        start_idx = -1
        for marker in ['<div id="primary"', '<main', '<div class="main-content"']:
            idx = html_content.find(marker)
            if idx != -1:
                start_idx = idx
                break
        
        end_idx = -1
        for marker in ['<aside', '<div id="secondary"', '<footer', '<div id="footer"', '<div class="footer"']:
            idx = html_content.find(marker)
            if idx != -1:
                end_idx = idx
                break

        if start_idx != -1:
            if end_idx != -1 and end_idx > start_idx:
                return html_content[start_idx:end_idx]
            else:
                return html_content[start_idx:]
        return html_content

    def resolve(self, url):
        html_content = self.make_request(url)
        if not html_content:
            return None, None

        # Extract contentURL meta
        video_url_match = re.search(r'<meta itemprop="contentURL" content="([^"]+)"', html_content)
        if video_url_match:
            return video_url_match.group(1), url

        return None, None

    def play_video(self, url):
        resolved_url, referer = self.resolve(url)
        if resolved_url:
            ua = self.scraper.headers.get('User-Agent', '')
            final_url = resolved_url + f"|User-Agent={urllib.parse.quote(ua)}"
            
            li = xbmcgui.ListItem(path=final_url)
            # If it's m3u8, Kodi handles it if we set property
            if '.m3u8' in resolved_url:
                li.setProperty('inputstream', 'inputstream.adaptive')
                li.setProperty('inputstream.adaptive.manifest_type', 'hls')
                li.setMimeType('application/vnd.apple.mpegurl')
            else:
                li.setMimeType('video/mp4')
                
            li.setProperty('IsPlayable', 'true')
            xbmcplugin.setResolvedUrl(self.addon_handle, True, li)
        else:
            xbmcgui.Dialog().notification('AdultHideout', 'Could not resolve video URL', xbmcgui.NOTIFICATION_ERROR, 3000)
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())

    def process_content(self, url):
        # Handle Category Pagination or Root Categories
        if url == "categories" or "/categories/page/" in url:
            self.add_dir("Search", "", 5, self.icons['search'])
            # If it's a pagination URL, pass it directly
            target = url if "/categories/page/" in url else None
            
            # We now call get_categories with the target URL
            cats = self.get_categories(target)
            
            for cat in cats:
                 if cat.get('type') == 'next_page':
                     self.add_dir(cat['title'], cat['url'], 2, self.icons['default'])
                 else:
                     self.add_dir(cat['title'], cat['url'], 2, cat['thumb'])
            
            self.end_directory("videos")
            return

        videos = self.get_listing(url)
        
        # Header navigation
        if url == "BOOTSTRAP" or url == self.base_url or "/page/" in url:
            self.add_dir("Search", "", 5, self.icons['search'])
            self.add_dir("Categories", "categories", 2, self.icons['categories'])

        for v in videos:
            if v.get('type') == 'next_page':
                self.add_dir(v['title'], v['url'], 2, self.icons['default'])
            else:
                self.add_link(
                    name=v['title'],
                    url=v['url'],
                    mode=4,
                    icon=v.get('thumb'),
                    fanart=self.fanart,
                    info_labels={'plot': v['title']}
                )

        self.end_directory("videos")
