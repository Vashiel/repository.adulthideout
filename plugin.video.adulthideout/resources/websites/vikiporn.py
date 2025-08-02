#!/usr/bin/env python
# -*- coding: utf-8 -*-

import re
import urllib.parse
import urllib.request
from http.cookiejar import CookieJar
import html
import xbmc
import xbmcaddon
import xbmcgui
import xbmcplugin
import xbmcvfs
import os
from resources.lib.base_website import BaseWebsite

class VikipornWebsite(BaseWebsite):
    config = {
        "name": "vikiporn",
        "base_url": "https://www.vikiporn.com",
        "search_url": "https://www.vikiporn.com/search/?q={}"
    }

    def __init__(self, addon_handle):
        super().__init__(
            name=self.config["name"],
            base_url=self.config["base_url"],
            search_url=self.config["search_url"],
            addon_handle=addon_handle
        )

    def get_extended_headers(self, referer=None, is_json=False):
        headers = {
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/*,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Cache-Control': 'no-cache',
            'Pragma': 'no-cache',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36'
        }
        if referer:
            headers['Referer'] = referer
        return headers

    def make_request(self, url, headers=None, max_retries=3, retry_wait=5000):
        headers = headers or self.get_extended_headers(url)
        cookie_jar = CookieJar()
        handler = urllib.request.HTTPCookieProcessor(cookie_jar)
        opener = urllib.request.build_opener(handler)
        for attempt in range(max_retries):
            try:
                request = urllib.request.Request(url, headers=headers)
                with opener.open(request, timeout=60) as response:
                    content = response.read().decode('utf-8', errors='ignore')
                    return content
            except (urllib.error.HTTPError, urllib.error.URLError):
                if attempt < max_retries - 1:
                    xbmc.sleep(retry_wait)
        self.notify_error(f"Failed to fetch URL: {url}")
        return ""

    def process_content(self, url):
        parsed_url = urllib.parse.urlparse(url)
        path = parsed_url.path.rstrip('/')

        content = self.make_request(url)
        if not content:
            self.notify_error("Failed to load page")
            self.end_directory()
            return

        self.add_basic_dirs(url)

        if path.endswith('/pornstars/') or '<div class="models-thumbs">' in content:
            self.process_pornstar_list(content)
        elif path.endswith('/categories/') or '<div class="categories-thumbs">' in content:
            self.process_category_list(content)
        else:
            self.process_video_list(content)

        self.add_next_button(content, url)
        self.end_directory()

    def add_basic_dirs(self, current_url):
        dirs = [
            ('[COLOR blue]Search[/COLOR]', '', 5, self.icons['search'], self.config['name']),
            ('Categories', f"{self.config['base_url']}/categories/", 2, self.icons['categories']),
            ('Pornstars', f"{self.config['base_url']}/pornstars/", 2, self.icons['pornstars']),
        ]
        for name, url, mode, icon, *extra in dirs:
            dir_name_param = extra[0] if extra else name
            self.add_dir(name, url, mode, icon, self.fanart, name_param=dir_name_param)

    def process_category_list(self, content):
        pattern = r'<div class="thumb">\s*<a class="ponn" href="([^"]+)"[^>]*>\s*<img src="([^"]+)"[^>]*>\s*<span>([^<]+)</span>'
        matches = re.findall(pattern, content, re.DOTALL)
        for item_url, thumb, name in matches:
            name = html.unescape(name.strip())
            full_url = urllib.parse.urljoin(self.config['base_url'], item_url)
            self.add_dir(name, full_url, 2, thumb, self.fanart)

    def process_pornstar_list(self, content):
        pattern = r'<div class="thumb">\s*<a href="([^"]+)" title="([^"]*)">.*?<img src="([^"]+)".*?<span>([^<]+)</span>'
        matches = re.findall(pattern, content, re.DOTALL)
        for item_url, title, thumb, name in matches:
            name = html.unescape(name.strip())
            full_url = urllib.parse.urljoin(self.config['base_url'], item_url)
            self.add_dir(name, full_url, 2, thumb, self.fanart)

    def process_video_list(self, content):
        pattern = r'<div class="thumb".*?<a class="ponn" href="([^"]+)".*?data-poster="([^"]+)".*?<span class="title">([^<]+)</span>.*?</div>'
        matches = re.findall(pattern, content, re.DOTALL)

        for video_url, thumb, name in matches:
            name = html.unescape(name.strip())
            full_video_url = urllib.parse.urljoin(self.config['base_url'], video_url)
            self.add_link(name, full_video_url, 4, thumb, self.fanart)

    def add_next_button(self, content, current_url):
        match = re.search(r'<li class="next">\s*<a rel="next" href="([^"]+)">', content)
        if match:
            next_url = urllib.parse.urljoin(self.config['base_url'], match.group(1))
            self.add_dir('[COLOR blue]Next Page >>>>[/COLOR]', next_url, 2, self.icons['default'], self.fanart)

    def play_video(self, url):
        content = self.make_request(url)
        if not content:
            self.notify_error("Failed to load video page")
            return

        match = re.search(r'<meta itemprop="contentUrl" content="([^"]+)">', content)
        
        if match:
            media_url = match.group(1)
            cleaned_url = html.unescape(media_url)
            
            li = xbmcgui.ListItem(path=cleaned_url)
            li.setProperty('IsPlayable', 'true')
            li.setMimeType('video/mp4')
            xbmcplugin.setResolvedUrl(self.addon_handle, True, li)
            return

        self.notify_error("No video source found")