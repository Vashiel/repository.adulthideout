#!/usr/bin/env python
# -*- coding: utf-8 -*-

import re
import urllib.parse
import urllib.request
import html
import sys
import xbmc
import xbmcgui
import xbmcplugin
from resources.lib.base_website import BaseWebsite

class HeavyRWebsite(BaseWebsite):
    def __init__(self, addon_handle):
        super().__init__(
            name="heavy-r",
            base_url="https://www.heavy-r.com",
            search_url="https://www.heavy-r.com/index.php",
            addon_handle=addon_handle
        )
        self.sort_options = ["Recent Uploads", "Most Viewed", "Top Rated", "Recent Favorites"]
        self.sort_paths = {
            "Recent Uploads": "/videos/recent/",
            "Most Viewed": "/videos/most_viewed/",
            "Top Rated": "/videos/top_rated/",
            "Recent Favorites": "/videos/recent_favorites/"
        }
        self.categories_url = f"{self.base_url}/categories/"

    def get_headers(self, url):
        return {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Referer": f"{self.base_url}/",
            "Accept-Language": "de-DE,de;q=0.9"
        }

    def make_request(self, url, headers=None, post_data=None, max_retries=3, retry_wait=5000):
        headers = headers or self.get_headers(url)
        encoded_post_data = urllib.parse.urlencode(post_data).encode('utf-8') if post_data else None
            
        for attempt in range(max_retries):
            try:
                request = urllib.request.Request(url, data=encoded_post_data, headers=headers)
                with urllib.request.urlopen(request, timeout=60) as response:
                    return response.read().decode('utf-8', errors='ignore')
            except Exception:
                if attempt < max_retries - 1:
                    xbmc.sleep(retry_wait)
        self.notify_error(f"Failed to fetch URL: {url}")
        return ""

    def add_basic_dirs(self, current_url):
        context_menu = [('Sort by...', f'RunPlugin({sys.argv[0]}?mode=7&website={self.name}&action=select_sort&original_url={urllib.parse.quote_plus(current_url)})')]
        self.add_dir('[COLOR blue]Search[/COLOR]', '', 5, self.icons['search'], context_menu=context_menu)
        self.add_dir('Categories', self.categories_url, 8, self.icons['categories'], context_menu=context_menu)

    def process_content(self, url):
        self.add_basic_dirs(url)
        content = self.make_request(url)
        if content:
            self.parse_video_list(content, url)
            self.add_next_button(content, url)
        self.end_directory()

    def parse_video_list(self, content, current_url):
        pattern = r'<div class="video-item.*?">.*?<a href="([^"]+)" class="image">.*?<img src="([^"]+)"[^>]*?alt="([^"]+)"'
        matches = re.findall(pattern, content, re.DOTALL)
        context_menu = [('Sort by...', f'RunPlugin({sys.argv[0]}?mode=7&website={self.name}&action=select_sort&original_url={urllib.parse.quote_plus(current_url)})')]

        for video_url, thumbnail, title in matches:
            full_url = urllib.parse.urljoin(self.base_url, video_url)
            thumbnail_http = thumbnail.replace("https://", "http://")
            self.add_link(html.unescape(title.strip()), full_url, 4, thumbnail_http, self.fanart, context_menu=context_menu)

    def process_categories(self, url):
        self.add_basic_dirs(url)
        content = self.make_request(url)
        if not content:
            self.end_directory()
            return
            
        pattern = r'<div class="video-item category">.*?<a href="([^"]+)" class="image.*?">.*?<img src="([^"]+)" alt="([^"]+)"'
        matches = re.findall(pattern, content, re.DOTALL)
        
        for link, thumb, name in matches:
            full_url = urllib.parse.urljoin(self.base_url, link)
            full_thumb_url = urllib.parse.urljoin(self.base_url, thumb)
            thumbnail_http = full_thumb_url.replace("https://", "http://")
            self.add_dir(html.unescape(name.strip()), full_url, 2, thumbnail_http, self.fanart)
            
        self.add_next_button(content, url)
        self.end_directory()

    def add_next_button(self, content, current_url):
        match = re.search(r'<a[^>]+href="([^"]+)"[^>]*>Next</a>', content, re.IGNORECASE)
        if match:
            next_url = urllib.parse.urljoin(self.base_url, match.group(1))
            self.add_dir('[COLOR blue]Next Page >>>>[/COLOR]', next_url, 2, self.icons['default'], self.fanart)

    def play_video(self, url):
        content = self.make_request(url)
        if not content:
            self.notify_error("Failed to load video page")
            return
        
        match = re.search(r'<source[^>]+src=["\']([^"\']+\.mp4)', content, re.IGNORECASE)
        if not match:
            self.notify_error("No video source found")
            return
            
        video_url = match.group(1)
        video_url_http = video_url.replace("https://", "http://")
        
        li = xbmcgui.ListItem(path=video_url_http)
        li.setProperty("IsPlayable", "true")
        li.setMimeType("video/mp4")
        xbmcplugin.setResolvedUrl(self.addon_handle, True, li)

    def search(self, query):
        if not query:
            return
        post_data = {'keyword': query, 'handler': 'search', 'action': 'do_search'}
        content = self.make_request(self.search_url, post_data=post_data)
        if content:
            self.add_basic_dirs(self.search_url)
            self.parse_video_list(content, self.search_url)
        self.end_directory()