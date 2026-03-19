#!/usr/bin/env python
# -*- coding: utf-8 -*-

import re
import urllib.parse
import html
import os
import sys
import xbmc
import xbmcgui
import xbmcplugin
import xbmcaddon
from resources.lib.base_website import BaseWebsite


class Porn300(BaseWebsite):

    def __init__(self, addon_handle=None, addon=None):
        super().__init__(
            name="porn300",
            base_url="https://www.porn300.com",
            search_url="https://www.porn300.com/search/?q={}",
            addon_handle=addon_handle,
            addon=addon
        )
        self.icons['search'] = os.path.join(
            self.addon.getAddonInfo('path'), 'resources', 'logos', 'search.png')
        self.icons['categories'] = os.path.join(
            self.addon.getAddonInfo('path'), 'resources', 'logos', 'categories.png')

        self.sort_options = []
        self.sort_paths = {}

        self._headers = {
            'User-Agent': (
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                'AppleWebKit/537.36 (KHTML, like Gecko) '
                'Chrome/122.0.0.0 Safari/537.36'
            ),
            'Referer': self.base_url,
            'Accept-Language': 'en-US,en;q=0.9',
        }

    # ------------------------------------------------------------------ #
    #  HTTP helper                                                         #
    # ------------------------------------------------------------------ #
    def make_request(self, url):
        try:
            import requests
            self.logger.info(f"[Porn300] GET {url}")
            response = requests.get(url, headers=self._headers, timeout=20)
            if response.status_code == 200:
                return response.text
            self.logger.error(f"[Porn300] HTTP {response.status_code} for {url}")
            return None
        except Exception as e:
            self.logger.error(f"[Porn300] Request error: {e}")
            return None

    # ------------------------------------------------------------------ #
    #  Content dispatcher                                                  #
    # ------------------------------------------------------------------ #
    def process_content(self, url):
        # Persistent nav
        self.add_dir("Search", "", 5, self.icons['search'])
        self.add_dir("Categories", urllib.parse.urljoin(self.base_url, "/categories/"), 8,
                     self.icons['categories'])

        if url == "BOOTSTRAP":
            url = self.base_url

        # Main categories index vs category sub-page /category/asian
        if url.rstrip('/').endswith('/categories') or url.rstrip('/').endswith('/kategorien'):
            self._get_categories_page(url)
            return

        self._get_listing(url)

    # ------------------------------------------------------------------ #
    #  Video listing                                                       #
    # ------------------------------------------------------------------ #
    def _get_listing(self, url):
        page_html = self.make_request(url)
        if not page_html:
            return self.end_directory()

        # Grid item pattern based on browser findings
        item_pattern = re.compile(
            r'<a\s+[^>]*href=["\'](/video/[^"\']+)["\'][^>]*>.*?'
            r'<img[^>]+src=["\']([^"\']+(?:\.jpg|\.webp)[^"\']*)["\'][^>]*>.*?'
            r'<span[^>]+class=["\'][^"\']*duration[^"\']*["\'][^>]*>\s*([^<]*)\s*</span>.*?'
            r'<h3[^>]*>\s*([^<]+)\s*</h3>',
            re.DOTALL | re.IGNORECASE
        )
        items = item_pattern.findall(page_html)

        if not items:
            # Fallback for listings without duration (e.g. some search results)
            item_pattern2 = re.compile(
                r'<a\s+[^>]*href=["\'](/video/[^"\']+)["\'][^>]*>.*?'
                r'<img[^>]+src=["\']([^"\']+(?:\.jpg|\.webp)[^"\']*)["\'][^>]*>.*?'
                r'<h3>\s*([^<]+)\s*</h3>',
                re.DOTALL | re.IGNORECASE
            )
            for slug, thumb, title in item_pattern2.findall(page_html):
                if thumb.startswith('data:'):
                    continue
                title = html.unescape(title.strip())
                video_url = urllib.parse.urljoin(self.base_url, slug)
                self.add_link(title, video_url, 4, thumb, self.fanart,
                               info_labels={'title': title, 'plot': title})
        else:
            for slug, thumb, duration, title in items:
                if thumb.startswith('data:'):
                    continue
                title = html.unescape(title.strip())
                duration_secs = self.convert_duration(duration.strip())
                video_url = urllib.parse.urljoin(self.base_url, slug)
                info = {'title': title, 'plot': title}
                if duration_secs:
                    info['duration'] = duration_secs
                self.add_link(title, video_url, 4, thumb, self.fanart, info_labels=info)

        # Pagination
        next_url = self._find_next_page(url, page_html, len(items))
        if next_url:
            self.add_dir("Next Page >>", next_url, 2, self.icons['default'])

        self.end_directory()

    def _find_next_page(self, current_url, page_html, item_count):
        if item_count < 8:
            return None

        # link rel="next" is very reliable on this site
        link_next = re.search(r'<link\s+rel=["\']next["\'][^>]+href=["\']([^"\']+)["\']',
                               page_html, re.IGNORECASE)
        if link_next:
            href = link_next.group(1)
            if not href.startswith('http'):
                href = urllib.parse.urljoin(self.base_url, href)
            return href

        m = re.search(r'[?&]page=(\d+)', current_url)
        if m:
            next_num = int(m.group(1)) + 1
            return re.sub(r'([?&]page=)\d+', rf'\g<1>{next_num}', current_url)

        sep = '&' if '?' in current_url else '?'
        return current_url.rstrip('/') + f'{sep}page=2'

    # ------------------------------------------------------------------ #
    #  Categories                                                          #
    # ------------------------------------------------------------------ #
    def process_categories(self, url):
        if not url.startswith('http'):
            url = urllib.parse.urljoin(self.base_url, url)
        self._get_categories_page(url)

    def _get_categories_page(self, url):
        page_html = self.make_request(url)
        if not page_html:
            return self.end_directory()

        # Robust category pattern based on actual site structure
        # <a href="/category/slug/"> ... <img src/data-src="url"> ... <h3>Name</h3> (sometimes with count or SVG)
        cat_pattern = re.compile(
            r'<a[^>]*href=["\'](/category/[^"\']+)["\'][^>]*>.*?'
            r'<img([^>]+)>.*?'
            r'<h3[^>]*>(.*?)</h3>',
            re.DOTALL | re.IGNORECASE
        )
        
        found_count = 0
        for cat_url_slug, img_attrs, h3_content in cat_pattern.findall(page_html):
            # Clean content: remove SVG, escape HTML, strip whitespace
            name = re.sub(r'<svg.*?</svg>', '', h3_content, flags=re.DOTALL)
            name = html.unescape(name.strip())
            name = re.sub(r'\s+', ' ', name).strip()
            
            if name and not name.lower() == "kategorien":
                cat_url = urllib.parse.urljoin(self.base_url, cat_url_slug)
                
                thumb = ""
                m_data = re.search(r'data-src=["\']([^"\']+)["\']', img_attrs, re.IGNORECASE)
                if m_data:
                    thumb = m_data.group(1)
                else:
                    m_src = re.search(r'src=["\']([^"\']+)["\']', img_attrs, re.IGNORECASE)
                    if m_src:
                        thumb = m_src.group(1)
                
                if thumb.startswith('data:'):
                    thumb = ""
                elif thumb and not thumb.startswith('http'):
                    thumb = urllib.parse.urljoin(self.base_url, thumb)
                
                if not thumb:
                    thumb = self.icons.get('categories')

                found_count += 1
                self.add_dir(name, cat_url, 2, thumb)
        
        self.logger.info(f"[Porn300] Extracted {found_count} categories from {url}")

        # Category Pagination: The site uses the same pagination logic for categories
        next_url = self._find_next_page(url, page_html, found_count)
        if next_url:
            self.add_dir("Next Page >>", next_url, 8, self.icons['default'])
        
        self.end_directory()

    # ------------------------------------------------------------------ #
    #  Playback                                                            #
    # ------------------------------------------------------------------ #
    def play_video(self, url):
        page_html = self.make_request(url)
        if not page_html:
            self._fail_playback()
            return

        stream_url = None
        sources = []

        # 1. Look for <source> tags
        src_tags = re.finditer(r'<source[^>]+src=["\']([^"\']+\.(?:m3u8|mp4)[^"\']*)["\'][^>]*>', page_html, re.IGNORECASE)
        for m in src_tags:
            tag_html = m.group(0)
            url_str = m.group(1)
            res_val = 0
            res_m = re.search(r'(?:title|label|res|quality)=["\']?.*?(\d{3,4})p?["\']?', tag_html, re.IGNORECASE)
            url_res_m = re.search(r'(?:_|-|/)(\d{3,4})p?\.mp4', url_str, re.IGNORECASE)

            if res_m:
                 res_val = int(res_m.group(1))
            elif url_res_m:
                 res_val = int(url_res_m.group(1))

            sources.append((res_val, url_str))

        # 2. Extract JS setup objects
        js_sources = re.finditer(r'\{[^}]*?file["\']?\s*:\s*["\']([^"\']+\.(?:m3u8|mp4)[^"\']*)["\'][^}]*\}', page_html, re.IGNORECASE)
        for m in js_sources:
             js_obj = m.group(0)
             url_str = m.group(1)
             res_val = 0
             res_m = re.search(r'label["\']?\s*:\s*["\']?(\d{3,4})', js_obj, re.IGNORECASE)
             if res_m:
                 res_val = int(res_m.group(1))
             sources.append((res_val, url_str))

        # 3. Native regex fallback
        for rx in [
            r'["\']?file["\']?\s*:\s*["\']([^"\']+\.(?:m3u8|mp4)[^"\']*)["\']',
            r'["\']?src["\']?\s*:\s*["\']([^"\']+\.(?:m3u8|mp4)[^"\']*)["\']',
        ]:
            js_matches = re.finditer(rx, page_html, re.IGNORECASE)
            for m in js_matches:
                 url_str = m.group(1)
                 res_val = 0
                 url_res_m = re.search(r'(?:_|-|/)(\d{3,4})p?\.mp4', url_str, re.IGNORECASE)
                 if url_res_m:
                     res_val = int(url_res_m.group(1))
                 sources.append((res_val, url_str))

        if sources:
            sources.sort(key=lambda x: x[0], reverse=True)
            self.logger.info(f"[Porn300] Sources found: {sources}")
            stream_url = sources[0][1]

        if stream_url:
            if stream_url.startswith('//'):
                stream_url = 'https:' + stream_url
            
            ua = self._headers['User-Agent']
            final = stream_url + f'|User-Agent={urllib.parse.quote(ua)}&Referer={urllib.parse.quote(url)}'
            li = xbmcgui.ListItem(path=final)
            if '.m3u8' in stream_url:
                li.setProperty('inputstream', 'inputstream.adaptive')
                li.setProperty('inputstream.adaptive.manifest_type', 'hls')
                li.setMimeType('application/vnd.apple.mpegurl')
            else:
                li.setMimeType('video/mp4')
            li.setProperty('IsPlayable', 'true')
            xbmcplugin.setResolvedUrl(self.addon_handle, True, li)
        else:
            self.logger.error(f"[Porn300] Could not find stream in: {url}")
            self._fail_playback()

    def _fail_playback(self):
        self.notify_error("Could not resolve video stream.")
        xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())

    def convert_duration(self, duration_str):
        if not duration_str:
            return 0
        try:
            parts = duration_str.split(':')
            if len(parts) == 2:
                return int(parts[0]) * 60 + int(parts[1])
            elif len(parts) == 3:
                return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
        except:
            pass
        return 0
