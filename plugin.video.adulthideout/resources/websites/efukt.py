#!/usr/bin/env python
# -*- coding: utf-8 -*-

import re
import urllib.parse
import urllib.request
import sys
import html
import xbmc
import xbmcgui
import xbmcplugin
from resources.lib.base_website import BaseWebsite

class EfuktWebsite(BaseWebsite):
    def __init__(self, addon_handle):
        super().__init__(
            name='efukt',
            base_url='https://efukt.com/',
            search_url='https://efukt.com/search/{}/',
            addon_handle=addon_handle
        )

    def make_request(self, url, max_retries=3, retry_wait=5000):
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36',
            'Referer': self.base_url,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Encoding': 'identity'
        }
        for attempt in range(max_retries):
            try:
                req = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(req, timeout=60) as response:
                    return response.read().decode('utf-8', errors='ignore')
            except Exception as e:
                if attempt < max_retries - 1:
                    xbmc.sleep(retry_wait)
        self.notify_error(f"Failed to fetch URL: {url}")
        return ""

    def add_basic_dirs(self):
        self.add_dir('[COLOR blue]Search[/COLOR]', '', 5, self.icons['search'])
        self.add_dir('Categories', f"{self.base_url}categories/", 8, self.icons['categories'])

    def process_content(self, url):
        if url == self.base_url:
            self.add_basic_dirs()

        content = self.make_request(url)
        if content:
            self.parse_video_list(content, url)
            self.add_next_button(content, url)
        self.end_directory()

    def parse_video_list(self, content, current_url):
        video_pattern = r'<a\s+href="([^"]+)"\s+title="([^"]+)"\s+class="thumb"\s+style="background-image:\s*url\(\'([^\']+)\'\);">'
        matches = re.findall(video_pattern, content, re.DOTALL)

        if not matches:
            return

        for video_url, title, thumbnail in matches:
            full_video_url = urllib.parse.urljoin(self.base_url, video_url)
            full_thumbnail_url = urllib.parse.urljoin(self.base_url, thumbnail)
            display_title = html.unescape(title.strip())
            
            self.add_link(display_title, full_video_url, 4, full_thumbnail_url, self.fanart)

    def process_categories(self, url):
        content = self.make_request(url)
        if not content:
            self.end_directory()
            return
        
        cat_pattern = r'''<a.*?href="([^"]+)".*?title="([^"]+)".*?>\s*<div class="cat_img_preview" style="background-image: url\('([^']+)'\);"></div>\s*<h3 class="title[^"]*">([^<]+)</h3>\s*</a>'''
        matches = re.findall(cat_pattern, content, re.DOTALL)
        
        if not matches:
            self.notify_error("Failed to load categories.")
            self.end_directory()
            return

        for cat_url, title, thumb, name in matches:
            full_url = urllib.parse.urljoin(self.base_url, cat_url)
            display_name = html.unescape(name.strip())
            self.add_dir(display_name, full_url, 2, thumb, self.fanart)
            
        self.end_directory(content_type='videos')

    def add_next_button(self, content, current_url):
        next_page_match = re.search(r'<a href="([^"]+)" class="next_page anchored_item">', content)
        if next_page_match:
            next_url_path = html.unescape(next_page_match.group(1))
            next_url = urllib.parse.urljoin(self.base_url, next_url_path)
            self.add_dir('[COLOR blue]Next Page >>>>[/COLOR]', next_url, 2, self.icons['default'], self.fanart)

    def play_video(self, url):
        content = self.make_request(url)
        if not content:
            self.notify_error("Failed to load video page.")
            return

        media_match = re.search(r'<source\s+src="([^"]+)"\s+type="video/mp4">', content)
        if media_match:
            stream_url = html.unescape(media_match.group(1))
            
            li = xbmcgui.ListItem(path=stream_url)
            li.setProperty('IsPlayable', 'true')
            li.setMimeType('video/mp4')
            xbmcplugin.setResolvedUrl(self.addon_handle, True, li)
        else:
            self.notify_error("No playable stream found")