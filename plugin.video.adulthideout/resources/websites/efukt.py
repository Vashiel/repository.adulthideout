#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import os
import xbmcaddon

# Vendor-Pfad
try:
    addon_path = xbmcaddon.Addon().getAddonInfo('path')
    vendor_path = os.path.join(addon_path, 'resources', 'lib', 'vendor')
    if vendor_path not in sys.path:
        sys.path.insert(0, vendor_path)
except Exception:
    pass

import re
import urllib.parse
import html
import json
import xbmcgui
import xbmcplugin
import requests
from resources.lib.base_website import BaseWebsite

class EfuktWebsite(BaseWebsite):
    def __init__(self, addon_handle):
        super().__init__(
            name='efukt',
            base_url='https://efukt.com/',
            search_url='https://efukt.com/search/{}/',
            addon_handle=addon_handle
        )
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36',
            'Referer': self.base_url,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8'
        })

    def make_request(self, url):
        try:
            url = urllib.parse.quote(url, safe=':/?=&%')
            self.logger.info(f"Fetching: {url}")
            response = self.session.get(url, timeout=15)
            response.raise_for_status()
            return response.text
        except Exception as e:
            self.logger.error(f"Request failed: {e}")
            self.notify_error("Connection Error")
            return None

    def process_content(self, url):
        if not url or url == "BOOTSTRAP":
             url = self.base_url

        content = self.make_request(url)
        
        self.add_dir('[COLOR blue]Search[/COLOR]', '', 5, self.icons['search'])
        self.add_dir('Categories', urllib.parse.urljoin(self.base_url, 'categories/'), 8, self.icons['categories'])

        if content:
            self.parse_video_list(content)
            self.add_next_button(content)
        
        self.end_directory()

    def process_categories(self, url):
        content = self.make_request(url)
        if not content:
            self.end_directory()
            return
        
        # Pattern für Kategorien
        pattern = re.compile(
            r'<a\s+href="([^"]+)"[^>]*title="([^"]+)"[^>]*>.*?'
            r'background-image:\s*url\(\'?([^\')]+)\'?\).*?'
            r'<h3\s+class="title[^"]*">([^<]+)</h3>',
            re.DOTALL | re.IGNORECASE
        )
        matches = pattern.findall(content)
        
        # Fallback Pattern
        if not matches:
             matches = re.findall(r'<a class="tile" href="([^"]+)">.*?<img src="([^"]+)".*?<p>([^<]+)</p>', content, re.DOTALL)
             matches = [(m[0], "unused", m[1], m[2]) for m in matches]

        for cat_url, _, thumb, name in matches:
            full_url = urllib.parse.urljoin(self.base_url, cat_url)
            full_thumb = urllib.parse.urljoin(self.base_url, thumb)
            display_name = html.unescape(name.strip())
            self.add_dir(display_name, full_url, 2, full_thumb, self.fanart)
            
        self.end_directory(content_type='videos')

    def parse_video_list(self, content):
        video_pattern = re.compile(
            r'<a\s+href="([^"]+)"\s+title="([^"]+)"\s+class="thumb"\s+style="background-image:\s*url\(\'?([^\')]+)\'?\);"\s*>',
            re.IGNORECASE
        )
        matches = video_pattern.findall(content)

        seen_urls = set()
        for video_url, title, thumbnail in matches:
            if video_url in seen_urls: continue
            seen_urls.add(video_url)

            full_video_url = urllib.parse.urljoin(self.base_url, video_url)
            full_thumbnail_url = urllib.parse.urljoin(self.base_url, thumbnail)
            
            self.add_link(html.unescape(title.strip()), full_video_url, 4, full_thumbnail_url, self.fanart)

    def add_next_button(self, content):
        next_page_match = re.search(r'<a href="([^"]+)" class="[^"]*next_page[^"]*"', content)
        if next_page_match:
            next_url = urllib.parse.urljoin(self.base_url, html.unescape(next_page_match.group(1)))
            self.add_dir('[COLOR blue]Next Page >>>>[/COLOR]', next_url, 2, self.icons['default'], self.fanart)

    def play_video(self, url):
        content = self.make_request(url)
        if not content:
            self.notify_error("Failed to load page")
            return

        stream_url = self._extract_stream(content)
        
        # Fallback: Iframes durchsuchen
        if not stream_url:
            iframe_matches = re.findall(r'<iframe[^>]+src="([^"]+)"', content, re.IGNORECASE)
            for iframe_src in iframe_matches:
                if not iframe_src.startswith("http"):
                    iframe_src = urllib.parse.urljoin(self.base_url, iframe_src)
                
                self.logger.info(f"Checking iframe: {iframe_src}")
                iframe_content = self.make_request(iframe_src)
                if iframe_content:
                    stream_url = self._extract_stream(iframe_content)
                    if stream_url: break

        if stream_url:
            if not stream_url.startswith('http'):
                stream_url = urllib.parse.urljoin(self.base_url, stream_url)
                
            headers = urllib.parse.urlencode({
                'User-Agent': self.session.headers['User-Agent'],
                'Referer': url
            })
            
            li = xbmcgui.ListItem(path=f"{stream_url}|{headers}")
            li.setProperty('IsPlayable', 'true')
            li.setMimeType('video/mp4')
            xbmcplugin.setResolvedUrl(self.addon_handle, True, li)
        else:
            self.logger.error(f"No stream found for: {url}")
            self.notify_error("No playable stream found")
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem(path=url))

    def _extract_stream(self, content):
        # 1. Source Tag mit type video/mp4 (flexibler)
        # Sucht nach <source ... src="..." ... type="video/mp4"> oder umgekehrt
        m = re.search(r'<source[^>]+src="([^"]+)"[^>]*type=["\']video/mp4["\']', content, re.IGNORECASE)
        if m: return html.unescape(m.group(1))
        
        m = re.search(r'<source[^>]+type=["\']video/mp4["\'][^>]*src="([^"]+)"', content, re.IGNORECASE)
        if m: return html.unescape(m.group(1))

        # 2. Generisches Video src
        m = re.search(r'<video[^>]+src="([^"]+)"', content, re.IGNORECASE)
        if m: return html.unescape(m.group(1))
        
        # 3. JSON-LD oder Script-Variablen
        m = re.search(r'(?:file|src|video_url|contentUrl)\s*[:=]\s*["\']([^"\']+\.mp4[^"\']*)["\']', content, re.IGNORECASE)
        if m: return html.unescape(m.group(1).replace(r'\/', '/'))

        # 4. JSON-LD Block parsing
        try:
            json_match = re.search(r'<script type="application/ld\+json">(.*?)</script>', content, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group(1))
                if 'contentUrl' in data:
                    return data['contentUrl']
        except: pass

        return None