#!/usr/bin/env python
# -*- coding: utf-8 -*-

import re
import sys
import urllib.parse as urllib_parse
import urllib.request as urllib_request
from http.cookiejar import CookieJar
import xbmc
import xbmcgui
import xbmcplugin
import xbmcvfs
import html
from resources.lib.base_website import BaseWebsite
from resources.lib.decoders.porntn_decoder import kvs_decode

class PorntnWebsite(BaseWebsite):
    config = {
        "name": "porntn",
        "base_url": "https://porndd.com",
        "search_url": "https://porndd.com/search/{}/"
    }

    def __init__(self, addon_handle):
        super().__init__(
            name=self.config["name"],
            base_url=self.config["base_url"].rstrip('/'),
            search_url=self.config["search_url"],
            addon_handle=addon_handle
        )
        self.sort_options = ["Trending", "Latest", "Most Viewed", "Top Rated", "Longest"]
        self.sort_paths = {
            "Trending": "/",
            "Latest": "/latest-updates/",
            "Most Viewed": "/most-viewed/",
            "Top Rated": "/top-rated/",
            "Longest": "/longest-videos/"
        }
        self.cookie_jar = CookieJar()
        self.opener = urllib_request.build_opener(urllib_request.HTTPCookieProcessor(self.cookie_jar))
        self.opener.addheaders = [('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/5.0 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36')]

    def make_request(self, url, headers=None, data=None, max_retries=3, retry_wait=5000):
        headers = headers or {'Referer': self.base_url}
        if data:
            data = urllib_parse.urlencode(data).encode('utf-8')
        for attempt in range(max_retries):
            try:
                request = urllib_request.Request(url, data=data, headers=headers)
                with self.opener.open(request, timeout=60) as response:
                    return response.read().decode('utf-8', errors='ignore')
            except Exception as e:
                self.logger.error(f"Request to {url} failed on attempt {attempt + 1}: {e}")
                if attempt < max_retries - 1:
                    xbmc.sleep(retry_wait)
        self.notify_error(f"Failed to fetch URL: {url}")
        return None

    def check_url(self, url):
        try:
            request = urllib_request.Request(url, method='HEAD', headers={'Referer': self.base_url})
            with self.opener.open(request, timeout=5) as response:
                return response.getcode() == 200
        except Exception:
            return False

    def process_content(self, url):
        self.add_dir('[COLOR blue]Search[/COLOR]', '', 5, self.icons['search'])
        self.add_dir('Categories', f"{self.base_url}/categories/", 8, self.icons['categories'])
        
        content = self.make_request(url)
        if not content:
            return

        video_pattern = r'<div class="item[^"]*">\s*<a href="([^"]+)"\s*title="([^"]+)".*?data-original="([^"]+)".*?<div class="duration">([^<]+)</div>'
        matches = re.findall(video_pattern, content, re.DOTALL)
        
        if not matches:
            self.notify_info("No videos found on this page.")
        
        for video_url, title, thumbnail, duration in matches:
            if not video_url.startswith("http"):
                video_url = urllib_parse.urljoin(self.base_url, video_url)
            
            if thumbnail.startswith("//"):
                thumbnail = "https:" + thumbnail

            display_title = f'{html.unescape(title)} [COLOR yellow]({duration.strip()})[/COLOR]'
            self.add_link(display_title, video_url, 4, thumbnail, self.fanart)

        next_page_match = re.search(r'<li class="next"><a href="([^"]+)"', content)
        if next_page_match:
            next_url = next_page_match.group(1)
            if not next_url.startswith("http"):
                 next_url = urllib_parse.urljoin(url, next_url)
            self.add_dir("[COLOR blue]Next Page >>>>[/COLOR]", next_url, 2, self.icons['default'])

        self.end_directory()

    def process_categories(self, url):
        categories_url = urllib_parse.urljoin(self.base_url, "/categories/")
        content = self.make_request(categories_url)
        if not content:
            self.notify_error("Failed to load categories")
            return

        category_pattern = r'<a class="item" href="([^"]+)".*?<strong class="title">([^<]+)</strong>.*?<div class="videos">([^<]+)</div>'
        matches = re.findall(category_pattern, content, re.DOTALL)

        if not matches:
            self.notify_info("No categories found.")
            self.end_directory()
            return

        for cat_url, name, count_text in matches:
            display_title = f"{html.unescape(name.strip())} ({count_text.strip()})"
            if not cat_url.startswith("http"):
                cat_url = urllib_parse.urljoin(self.base_url, cat_url)
            self.add_dir(display_title, cat_url, 2, self.icons['categories'])
            
        self.end_directory()

    def play_video(self, url):
        content = self.make_request(url)
        if not content:
            return

        license_match = re.search(r"license_code[\"']?\s*:\s*[\"']([a-zA-Z0-9$]+)[\"']", content)
        encoded_urls = re.findall(r"[\"'](function/[^\"']+)[\"']", content)
        
        if license_match and encoded_urls:
            license_code = license_match.group(1)
            for encoded_url in reversed(encoded_urls):
                decoded_stream_url = kvs_decode(encoded_url, license_code)
                if decoded_stream_url:
                    if not decoded_stream_url.startswith("http"):
                        decoded_stream_url = urllib_parse.urljoin(self.base_url, decoded_stream_url)
                    
                    if self.check_url(decoded_stream_url):
                        li = xbmcgui.ListItem(path=decoded_stream_url)
                        li.setMimeType('video/mp4')
                        li.setProperty('Referer', url)
                        xbmcplugin.setResolvedUrl(self.addon_handle, True, li)
                        return

        stream_match = re.search(r"[\"'](https?://[^\"']+\.mp4[^\"']*)[\"']", content)
        if stream_match:
            stream_url = stream_match.group(1).replace('&amp;', '&')
            if self.check_url(stream_url):
                 li = xbmcgui.ListItem(path=stream_url)
                 li.setMimeType('video/mp4')
                 li.setProperty('Referer', url)
                 xbmcplugin.setResolvedUrl(self.addon_handle, True, li)
                 return

        self.notify_error("Could not find a playable video stream.")