#!/usr/bin/env python
# -*- coding: utf-8 -*-

# [CHANGELOG]
# - FIXED: Category content listing now works (mapped /cat/ URLs to API query params)
# - OPTIMIZED: Refined URL parsing logic in process_content to handle search, categories, and API links
# - KEPT: Hybrid playback logic (Hash calculation + XHR) for reliability
# - KEPT: Cloudscraper for Cloudflare bypass

import sys
import os
import re
import json
import urllib.parse
import xbmc
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

class Eporner(BaseWebsite):
    BASE_URL_STR = "https://www.eporner.com/"
    API_BASE = "https://www.eporner.com/api/v2/video/search/"
    
    def __init__(self, addon_handle):
        super().__init__(
            name="eporner",
            base_url=self.BASE_URL_STR,
            search_url="https://www.eporner.com/search/{}/",
            addon_handle=addon_handle
        )
        
        self.sort_options = ["Newest", "Most Viewed", "Top Rated", "Longest"]
        self.api_order_params = { 
            "Newest": "latest", 
            "Most Viewed": "most-popular", 
            "Top Rated": "top-rated", 
            "Longest": "longest" 
        }
        self.gay_filter_options = ["Exclude Gay (Straight)", "Only Gay", "Include Gay (Both)"]
        self.gay_filter_map = { "0": "0", "1": "2", "2": "1" }

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

    def make_request(self, url, headers=None):
        if not headers:
            headers = {'Referer': self.base_url}
        try:
            self.session.headers.update(headers)
            response = self.session.get(url, timeout=20)
            if response.status_code == 200:
                return response.text
        except Exception:
            pass
        return None

    def add_basic_dirs(self, current_url):
        encoded_url = urllib.parse.quote_plus(current_url)
        context_menu = [
            ('Filter Content...', f'RunPlugin({sys.argv[0]}?mode=7&action=select_gay_filter&website={self.name}&original_url={encoded_url})')
        ]
        
        cat_url = urllib.parse.urljoin(self.base_url, 'cats/')
        self.add_dir('[COLOR blue]Search[/COLOR]', '', 5, self.icons['search'], self.fanart, context_menu=context_menu)
        self.add_dir('Categories', cat_url, 8, self.icons['categories'], self.fanart, context_menu=context_menu)

    def process_content(self, url):
        # Handle main categories list
        if '/cats/' in url:
            self.process_categories(url)
            return

        self.add_basic_dirs(url)

        page = 1
        query = ""
        
        # URL Parsing Logic
        if "api/v2" in url:
            # Case 1: Pagination URL (already has params)
            parsed = urllib.parse.urlparse(url)
            params = urllib.parse.parse_qs(parsed.query)
            query = params.get('query', [''])[0]
            page = int(params.get('page', ['1'])[0])
        else:
            # Case 2: Web URL (Search or Category)
            # Remove trailing slash and split
            clean_url = url.rstrip('/')
            parts = clean_url.split('/')
            
            if '/cat/' in url:
                # Category URL: https://www.eporner.com/cat/teen/
                # Extract the category slug to use as query
                if parts:
                    # Last part is usually the category name
                    query = parts[-1]
                    # Handle pagination in category urls if present (rarely via this path in this plugin logic, but for safety)
                    if query.isdigit(): 
                        page = int(query)
                        query = parts[-2]
            elif '/search/' in url:
                # Search URL: https://www.eporner.com/search/term/
                if parts:
                    if parts[-1].isdigit():
                        query = parts[-2]
                        page = int(parts[-1])
                    else:
                        query = parts[-1]

        # Load User Settings
        saved_sort_idx = self.addon.getSetting(f'{self.name}_sort_by') or '0'
        try: sort_idx = int(saved_sort_idx)
        except: sort_idx = 0
        if sort_idx >= len(self.sort_options): sort_idx = 0
        sort_key = self.sort_options[sort_idx]
        
        saved_gay_idx = self.addon.getSetting('eporner_gay_filter') or '0'
        
        # Build API Params
        api_params = {
            'query': query,
            'page': page,
            'per_page': '30',
            'order': self.api_order_params.get(sort_key, 'most-popular'),
            'gay': self.gay_filter_map.get(saved_gay_idx, '0'),
            'thumbsize': 'medium',
            'format': 'json'
        }
        
        api_url = f"{self.API_BASE}?{urllib.parse.urlencode(api_params)}"
        self.render_video_list(api_url, page, query, sort_key, saved_gay_idx, url)
        self.end_directory()

    def render_video_list(self, api_url, current_page, query, sort_key, gay_idx, original_url):
        data_str = self.make_request(api_url)
        if not data_str: return

        try:
            data = json.loads(data_str)
            videos = data.get('videos', [])
            
            encoded_url = urllib.parse.quote_plus(original_url)
            context_menu = [
                ('Filter Content...', f'RunPlugin({sys.argv[0]}?mode=7&action=select_gay_filter&website={self.name}&original_url={encoded_url})')
            ]

            for video in videos:
                title = video.get('title')
                duration = video.get('length_sec')
                rating = video.get('rate')
                views = video.get('views')
                thumb = video.get('default_thumb', {}).get('src')
                vid_url = video.get('url')

                display_name = f"{title} [COLOR yellow]({self._format_duration(duration)})[/COLOR] [COLOR blue]★{rating}[/COLOR]"
                
                info = {
                    'plot': f"Views: {views}\nRating: {rating}",
                    'duration': int(duration) if duration else 0,
                    'mediatype': 'video'
                }
                
                self.add_link(display_name, vid_url, 4, thumb, self.fanart, info_labels=info, context_menu=context_menu)

            if len(videos) >= 20:
                next_page = current_page + 1
                next_api_params = {
                    'query': query,
                    'page': next_page,
                    'order': self.api_order_params.get(sort_key, 'most-popular'),
                    'gay': self.gay_filter_map.get(gay_idx, '0')
                }
                next_url = f"{self.base_url}api/v2/video/search/?{urllib.parse.urlencode(next_api_params)}"
                self.add_dir('[COLOR blue]Next Page >>>>[/COLOR]', next_url, 2, self.icons['default'], self.fanart, context_menu=context_menu)

        except Exception:
            pass

    def process_categories(self, url):
        cat_url = urllib.parse.urljoin(self.base_url, 'cats/')
        content = self.make_request(cat_url)
        if not content: 
            self.notify_error('Failed to load categories')
            self.end_directory()
            return

        content = re.sub(r'\s+', ' ', content)
        pattern = r'<a[^>]+href="(/cat/[^"]+)"[^>]*>\s*([^<]*)'
        matches = re.findall(pattern, content, re.IGNORECASE)
        
        unique_categories = {}
        for url_part, name in matches:
            clean_key = url_part.strip('/')
            if clean_key not in unique_categories:
                clean_name = name.strip() or clean_key.split('/')[-1].replace('-', ' ').capitalize()
                unique_categories[clean_key] = clean_name

        encoded_url = urllib.parse.quote_plus(url)
        context_menu = [
            ('Filter Content...', f'RunPlugin({sys.argv[0]}?mode=7&action=select_gay_filter&website={self.name}&original_url={encoded_url})')
        ]

        for url_part_key, name in sorted(unique_categories.items(), key=lambda x: x[1]):
            full_url = urllib.parse.urljoin(self.base_url, f'{url_part_key}/')
            self.add_dir(name, full_url, 2, self.icons['categories'], self.fanart, context_menu=context_menu)
        
        self.end_directory()

    def play_video(self, url):
        content = self.make_request(url)
        if not content: return self.notify_error("Failed to load page")

        embed_match = re.search(r"vid\s*=\s*'(.+?)'.*?hash\s*=\s*'(.+?)'", content, re.DOTALL)
        if not embed_match: return self.notify_error("Video protected")

        vid, hash_str = embed_match.groups()

        parts = []
        for i in range(0, len(hash_str), 8):
            try:
                num = int(hash_str[i:i+8], 16)
                table = '0123456789abcdefghijklmnopqrstuvwxyz'
                s = ''
                if num == 0: s = table[0]
                while num: s = table[num % 36] + s; num //= 36
                parts.append(s)
            except: pass
        hash_val = ''.join(parts)

        json_url = f'{self.base_url}xhr/video/{vid}?hash={hash_val}&domain=www.eporner.com&fallback=false&embed=true&supportedFormats=dash,mp4'
        xhr_headers = {'X-Requested-With': 'XMLHttpRequest', 'Referer': url}
        
        api_content = self.make_request(json_url, headers=xhr_headers)
        if not api_content: return self.notify_error("Failed to authorize")

        try:
            data = json.loads(api_content)
            stream_url = None
            
            sources = data.get('sources', {}).get('mp4', {})
            if isinstance(sources, dict):
                mp4_urls = [v.get('src') for v in sources.values() if isinstance(v, dict) and v.get('src')]
                if mp4_urls:
                    stream_url = max(mp4_urls, key=lambda u: int(re.search(r'(\d+)p', u).group(1)) if re.search(r'(\d+)p', u) else 0)
            
            if not stream_url:
                stream_url = data.get('sources', {}).get('hls', {}).get('auto', {}).get('src')

            if stream_url:
                kodi_headers = {'User-Agent': self.ua, 'Referer': url}
                if self.session:
                    cookies = self.session.cookies.get_dict()
                    if cookies:
                        kodi_headers['Cookie'] = "; ".join([f"{k}={v}" for k, v in cookies.items()])
                
                final_url = f"{stream_url}|{urllib.parse.urlencode(kodi_headers)}"
                
                li = xbmcgui.ListItem(path=final_url)
                li.setProperty('IsPlayable', 'true')
                if '.m3u8' in stream_url:
                    li.setMimeType('application/vnd.apple.mpegurl')
                    li.setProperty('inputstream', 'inputstream.adaptive')
                    li.setProperty('inputstream.adaptive.manifest_type', 'hls')
                else:
                    li.setMimeType('video/mp4')
                
                xbmcplugin.setResolvedUrl(self.addon_handle, True, li)
            else:
                self.notify_error("No stream found")

        except Exception:
            self.notify_error("Parse error")

    def select_sort(self, original_url=None):
        if not original_url: return
        try: current = int(self.addon.getSetting(f'{self.name}_sort_by') or '0')
        except: current = 0
        
        idx = xbmcgui.Dialog().select("Sort by...", self.sort_options, preselect=current)
        if idx != -1:
            self.addon.setSetting(f'{self.name}_sort_by', str(idx))
            xbmc.executebuiltin(f"Container.Update({sys.argv[0]}?mode=2&url={urllib.parse.quote_plus(original_url)}&website={self.name},replace)")

    def select_gay_filter(self, original_url=None):
        if not original_url: return
        try: current = int(self.addon.getSetting('eporner_gay_filter') or '0')
        except: current = 0
        
        idx = xbmcgui.Dialog().select("Filter Content...", self.gay_filter_options, preselect=current)
        if idx != -1:
            self.addon.setSetting('eporner_gay_filter', str(idx))
            xbmc.executebuiltin(f"Container.Update({sys.argv[0]}?mode=2&url={urllib.parse.quote_plus(original_url)}&website={self.name},replace)")

    def _format_duration(self, seconds):
        try:
            seconds = int(seconds)
            m, s = divmod(seconds, 60)
            if m > 60: h, m = divmod(m, 60); return f"{h}:{m:02d}:{s:02d}"
            return f"{m}:{s:02d}"
        except: return "0:00"

    def notify_error(self, msg):
        xbmcgui.Dialog().notification('AdultHideout', msg, xbmcgui.NOTIFICATION_ERROR)