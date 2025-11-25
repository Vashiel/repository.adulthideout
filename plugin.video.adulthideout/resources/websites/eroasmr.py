#!/usr/bin/env python
# -*- coding: utf-8 -*-

# [CHANGELOG]
# - OPTIMIZED: Added 'Connection: keep-alive' to headers to help with buffering/seeking stability
# - ADDED: Cookie priming on startup to ensure Cloudflare tokens are ready
# - FIXED: Category parsing logic
# - INFO: Buffering issues are likely due to low Kodi cache size (see instructions)

import sys
import os
import re
import urllib.parse
import xbmcgui
import xbmcplugin
import xbmcaddon
from resources.lib.base_website import BaseWebsite

# Vendor injection
try:
    addon_path = xbmcaddon.Addon().getAddonInfo('path')
    vendor_path = os.path.join(addon_path, 'resources', 'lib', 'vendor')
    if vendor_path not in sys.path:
        sys.path.insert(0, vendor_path)
except:
    pass

try:
    import cloudscraper
    HAS_CLOUDSCRAPER = True
except ImportError:
    HAS_CLOUDSCRAPER = False

import requests

class EroASMR(BaseWebsite):
    def __init__(self, addon_handle):
        super().__init__(
            name='eroasmr',
            base_url='https://eroasmr.com/',
            search_url='https://eroasmr.com/?s={}',
            addon_handle=addon_handle
        )
        self.session = None
        self.ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        
        if HAS_CLOUDSCRAPER:
            self.session = cloudscraper.create_scraper(
                browser={'browser': 'chrome', 'platform': 'windows', 'desktop': True}
            )
            self.ua = self.session.headers.get('User-Agent', self.ua)
        else:
            self.session = requests.Session()
            self.session.headers.update({'User-Agent': self.ua})
            
        # Prime cookies to avoid first-request lag
        try:
            self.session.get(self.base_url, timeout=5)
        except:
            pass

    def make_request(self, url):
        try:
            headers = {'Referer': self.base_url, 'Connection': 'keep-alive'}
            self.session.headers.update(headers)
            response = self.session.get(url, timeout=20)
            if response.status_code == 200:
                return response.text
        except Exception:
            pass
        return None

    def process_content(self, url):
        if url == "BOOTSTRAP":
            url = self.base_url

        html_content = self.make_request(url)
        if not html_content:
            self.notify_error("Failed to load content")
            self.end_directory()
            return

        if url == self.base_url:
            self.add_dir('[COLOR blue]Search[/COLOR]', '', 5, self.icons['search'], self.fanart)
            self.add_dir('[COLOR blue]Categories[/COLOR]', 'CATEGORIES', 8, self.icons['categories'], self.fanart)

        video_pattern = re.compile(r'<article[^>]+class="[^"]*?viem_video[^"]*?".*?<a class="dt-image-link" href="([^"]+)".*?src="([^"]+)".*?<span class="video-duration">([^<]+)</span>.*?<h2 class="post-title.*?<a [^>]+>([^<]+)</a>', re.DOTALL)
        matches = video_pattern.findall(html_content)
        
        if not matches:
             video_pattern = re.compile(r'<article.*?>.*?<a href="([^"]+)".*?src="([^"]+)".*?title="([^"]+)"', re.DOTALL)
             matches_fallback = video_pattern.findall(html_content)
             matches = [(m[0], m[1], "0:00", m[2]) for m in matches_fallback]

        for video_url, thumb_url, duration_str, title in matches:
            info = {
                'title': title.strip(),
                'duration': self._parse_duration(duration_str.strip()),
                'plot': title.strip(),
                'mediatype': 'video'
            }
            self.add_link(title.strip(), video_url, 4, thumb_url, self.fanart, info_labels=info)

        next_page_match = re.search(r'<a class="next page-numbers" href="([^"]+)">', html_content)
        if next_page_match:
            self.add_dir('[COLOR blue]Next Page >>[/COLOR]', next_page_match.group(1), 2, self.icons['default'], self.fanart)

        self.end_directory()

    def process_categories(self, url):
        html_content = self.make_request(self.base_url)
        if not html_content: return

        category_pattern = re.compile(r'<li[^>]*><a href="([^"]+/video-category/[^"]+)">([^<]+)</a>')
        matches = category_pattern.findall(html_content)
        
        unique_cats = {}
        for cat_url, cat_name in matches:
            name = cat_name.strip()
            if name and name not in unique_cats:
                unique_cats[name] = cat_url

        for name, cat_url in sorted(unique_cats.items()):
            self.add_dir(name, cat_url, 2, self.icons['categories'], self.fanart)

        self.end_directory()

    def play_video(self, url):
        html_content = self.make_request(url)
        if not html_content:
            self.notify_error("Failed to load page")
            return

        video_url = None
        source_match = re.search(r'(?:<video[^>]*><source|<source)\s+src="([^"]+\.mp4)"', html_content)
        
        if source_match:
            video_url = source_match.group(1)
            if '/get_video/' in video_url:
                try:
                    resp = self.session.head(video_url, allow_redirects=True)
                    video_url = resp.url
                except: pass
        
        if video_url:
            headers = {
                'User-Agent': self.ua,
                'Referer': url,
                'Connection': 'keep-alive'
            }
            cookies = self.session.cookies.get_dict()
            if cookies:
                headers['Cookie'] = "; ".join([f"{k}={v}" for k, v in cookies.items()])
            
            # Pass headers to Kodi
            final_url = f"{video_url}|{urllib.parse.urlencode(headers)}"
            
            li = xbmcgui.ListItem(path=final_url)
            li.setProperty('IsPlayable', 'true')
            xbmcplugin.setResolvedUrl(self.addon_handle, True, li)
        else:
            self.notify_error("No stream found")
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())

    def _parse_duration(self, duration_str):
        try:
            parts = list(map(int, duration_str.split(':')))
            if len(parts) == 3: return parts[0] * 3600 + parts[1] * 60 + parts[2]
            elif len(parts) == 2: return parts[0] * 60 + parts[1]
        except: pass
        return 0

    def notify_error(self, msg):
        xbmcgui.Dialog().notification('EroASMR', msg, xbmcgui.NOTIFICATION_ERROR)