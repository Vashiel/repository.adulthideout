#!/usr/bin/env python
# -*- coding: utf-8 -*-

import re
import urllib.parse
import urllib.request
from http.cookiejar import CookieJar
from io import BytesIO
import gzip
import html
import os
import xbmc
import xbmcaddon
import xbmcgui
import xbmcplugin
import xbmcvfs
from resources.lib.base_website import BaseWebsite

class DaftpornWebsite(BaseWebsite):
    def __init__(self, addon_handle):
        super().__init__(
            name="daftporn",
            base_url="https://www.daftporn.com",
            search_url="https://www.daftporn.com/?p=search&newstr={}&r=s",
            addon_handle=addon_handle
        )
        self.categories_url = f"{self.base_url}/extreme-videos/"

    def make_request(self, url, headers=None, post_data=None, max_retries=3, retry_wait=5000):
        headers = headers or {
            "User-Agent": "Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Mobile Safari/537.36",
            "Accept": "*/*",
            "Referer": self.base_url
        }
        
        for attempt in range(max_retries):
            try:
                request = urllib.request.Request(url, data=post_data, headers=headers)
                with urllib.request.urlopen(request, timeout=60) as response:
                    encoding = response.info().get('Content-Encoding')
                    raw_data = response.read()
                    if encoding == 'gzip':
                        buf = BytesIO(raw_data)
                        with gzip.GzipFile(fileobj=buf) as f:
                            data = f.read()
                    else:
                        data = raw_data
                    return data.decode('utf-8', errors='ignore')
            except Exception:
                if attempt < max_retries - 1:
                    xbmc.sleep(retry_wait)
        self.notify_error(f"Failed to fetch URL: {url}")
        return ""

    def add_basic_dirs(self):
        self.add_dir('[COLOR blue]Search[/COLOR]', '', 5, self.icons['search'])
        self.add_dir('Categories', self.categories_url, 8, self.icons['categories'])

    def process_content(self, url):
        self.add_basic_dirs()
        content = self.make_request(url)
        if content:
            self.parse_video_list(content, url)
            self.add_next_button(content, url)
        self.end_directory()

    def process_categories(self, url):
        self.add_dir('[COLOR blue]Back to Main Menu[/COLOR]', self.base_url, 2, self.icons['default'])
        content = self.make_request(url)
        if not content:
            self.end_directory()
            return
            
        pattern = r'<a class="url16" href="([^"]+)" title="[^"]+">([^<]+)</a>\s*\((\d+)\)'
        matches = re.findall(pattern, content)

        for cat_url, name, count in matches:
            display_name = f"{html.unescape(name.strip())} ({count})"
            full_cat_url = urllib.parse.urljoin(self.base_url, cat_url)
            self.add_dir(display_name, full_cat_url, 2, self.icons['categories'], self.fanart)
        
        self.end_directory(content_type='videos')

    def parse_video_list(self, content, current_url):
        pattern = r'<div class="plugcontainer">.*?<a href="([^"]+)".*?<img src="([^"]+)"[^>]*alt="([^"]*)"'
        matches = re.findall(pattern, content, re.DOTALL)
        
        for video_url, thumbnail, title in matches:
            if "out.php" in video_url:
                continue
            
            full_url = urllib.parse.urljoin(self.base_url, video_url)
            display_title = html.unescape(title.strip()) if title else "Untitled"
            
            self.add_link(display_title, full_url, 4, thumbnail, self.fanart)

    def add_next_button(self, content, url):
        next_page_match = re.search(r'<a href="([^"]+)" class="plugurl" title="next page">next</a>', content)
        if not next_page_match:
             next_page_match = re.search(r'<div class="prevnext">.*?<a href="([^"]+)"[^>]*>next</a>', content)

        if next_page_match:
            next_url_path = html.unescape(next_page_match.group(1))
            next_url = urllib.parse.urljoin(self.base_url, next_url_path)
            self.add_dir('[COLOR blue]Next Page >>>>[/COLOR]', next_url, 2, self.icons['default'], self.fanart)

    def play_video(self, url):
        content = self.make_request(url)
        if not content:
            self.notify_error("Failed to load video page")
            return

        stream_url = self._extract_stream_url(content, url)
        if not stream_url:
            stream_url = self._check_iframes(content, url)
        
        if not stream_url:
            self.notify_error("Could not find a playable video stream.")
            return

        li = xbmcgui.ListItem(path=stream_url)
        li.setProperty('IsPlayable', 'true')
        li.setMimeType("video/mp4" if stream_url.endswith(".mp4") else "application/x-mpegURL")
        xbmcplugin.setResolvedUrl(self.addon_handle, True, li)

    def _extract_stream_url(self, content, base_url):
        patterns = [
            r'<source\s+src="([^"]+\.(?:mp4|m3u8))"',
            r'<video[^>]+src="([^"]+\.(?:mp4|m3u8))"',
            r'["\']file["\']\s*:\s*["\']([^"]+\.(?:mp4|m3u8))',
            r"initHlsPlayer\('([^']+\.m3u8[^']*)'\)"
        ]
        for pattern in patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                stream_url = match.group(1)
                return urllib.parse.urljoin(base_url, stream_url)
        return None

    def _check_iframes(self, content, base_url):
        iframe_matches = re.findall(r'<iframe[^>]+src="([^"]+)"', content, re.IGNORECASE)
        for iframe_url in iframe_matches:
            iframe_url = urllib.parse.urljoin(base_url, iframe_url)
            iframe_content = self.make_request(iframe_url)
            if iframe_content:
                stream_url = self._extract_stream_url(iframe_content, iframe_url)
                if stream_url:
                    return stream_url
        return None