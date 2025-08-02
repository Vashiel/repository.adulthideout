#!/usr/bin/env python
# -*- coding: utf-8 -*-

import re
import json
import urllib.parse
import urllib.request
from http.cookiejar import CookieJar
from io import BytesIO
import gzip
import xbmc
import xbmcgui
import xbmcplugin
import sys
from resources.lib.base_website import BaseWebsite

class epornerWebsite(BaseWebsite):
    def __init__(self, addon_handle):
        super().__init__(
            name='eporner',
            base_url='https://www.eporner.com/',
            search_url='https://www.eporner.com/search/{}',
            addon_handle=addon_handle
        )
        
        self.sort_options = ["Newest", "Most Viewed", "Top Rated", "Longest"]
        self.gay_filter_options = ["Exclude Gay (Straight)", "Only Gay", "Include Gay (Both)"]
        
        self.sort_paths = { "Newest": "", "Most Viewed": "most-viewed/", "Top Rated": "top-rated/", "Longest": "longest/" }
        self.api_order_params = { "Newest": "latest", "Most Viewed": "most-popular", "Top Rated": "top-rated", "Longest": "longest" }
        self.gay_filter_map = { "0": "0", "1": "2", "2": "1" }

    def get_headers(self, url):
        return {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36', 'Accept': '*/*', 'Accept-Language': 'de-DE,de;q=0.9', 'Origin': 'https://www.eporner.com', 'Referer': url, 'Connection': 'keep-alive'}

    def make_request(self, url, headers=None, use_cookies=False, max_retries=3):
        headers = headers or self.get_headers(url)
        for attempt in range(max_retries):
            try:
                request = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(request, timeout=60) as response:
                    content = response.read()
                    if response.info().get('Content-Encoding') == 'gzip': content = gzip.GzipFile(fileobj=BytesIO(content)).read()
                    return content.decode('utf-8', errors='ignore')
            except Exception as e:
                self.logger.error(f"Request failed for {url} on attempt {attempt + 1}: {e}")
                if attempt < max_retries - 1: xbmc.sleep(5000)
        self.notify_error(f"Failed to fetch URL: {url}"); return ""

    def add_basic_dirs(self, current_url):
        context_menu = [
            ('Sort by...', f'RunPlugin({sys.argv[0]}?mode=7&action=select_sort&website={self.name}&original_url={urllib.parse.quote_plus(current_url)})'),
            ('Filter Content...', f'RunPlugin({sys.argv[0]}?mode=7&action=select_gay_filter&website={self.name}&original_url={urllib.parse.quote_plus(current_url)})')
        ]
        self.add_dir('Search eporner', '', 5, self.icons['search'], self.fanart, context_menu=context_menu)
        self.add_dir('Categories', f'{self.base_url}cats/', 8, self.icons['categories'], self.fanart, context_menu=context_menu)

    def process_content(self, url):
        self.add_basic_dirs(url)
        parsed_url = urllib.parse.urlparse(url)
        path = parsed_url.path.strip('/')
        query_dict = urllib.parse.parse_qs(parsed_url.query)
        page = query_dict.get('page', ['1'])[0]
        
        path_to_key_map = {v.strip('/'): k for k, v in self.sort_paths.items() if v}

        if path in path_to_key_map:
            sort_key = path_to_key_map[path]
        else:
            saved_sort_setting = self.addon.getSetting(f'{self.name}_sort_by') or '0'
            try:
                sort_index = int(saved_sort_setting)
            except ValueError:
                try: sort_index = self.sort_options.index(saved_sort_setting)
                except ValueError: sort_index = 0
            
            if not 0 <= sort_index < len(self.sort_options): sort_index = 0
            sort_key = self.sort_options[sort_index]
        
        gay_filter_index = self.addon.getSetting('eporner_gay_filter') or '0'
        
        api_params = {
            'format': 'json', 'page': page, 'per_page': '30',
            'gay': self.gay_filter_map.get(gay_filter_index, '0'),
            'order': self.api_order_params.get(sort_key, 'latest')
        }
        
        if path.startswith('search/'): api_params['query'] = path.split('search/')[1]
        elif path.startswith('cat/'): api_params['query'] = path.split('/')[-1]

        api_endpoint = f'{self.base_url}api/v2/video/search/'
        final_api_url = f"{api_endpoint}?{urllib.parse.urlencode(api_params)}"
        
        content = self.make_request(final_api_url, use_cookies=True)
        if not content: self.end_directory(); return

        try: data = json.loads(content)
        except json.JSONDecodeError: self.notify_error('Invalid API response.'); self.end_directory(); return

        videos = data.get('videos', [])
        if not videos: self.notify_info('No videos found.')
        
        context_menu = [
            ('Sort by...', f'RunPlugin({sys.argv[0]}?mode=7&action=select_sort&website={self.name}&original_url={urllib.parse.quote_plus(url)})'),
            ('Filter Content...', f'RunPlugin({sys.argv[0]}?mode=7&action=select_gay_filter&website={self.name}&original_url={urllib.parse.quote_plus(url)})')
        ]
        for video in videos:
            display_title = f"{video.get('title', 'No Title')} [{video.get('length_min', '0:00')}]"
            self.add_link(display_title, video.get('url', ''), 4, video.get('default_thumb', {}).get('src', ''), self.fanart, context_menu=context_menu)

        if len(videos) >= 30:
            next_page = int(page) + 1
            query_dict['page'] = [str(next_page)]
            next_page_url = parsed_url._replace(query=urllib.parse.urlencode(query_dict, doseq=True)).geturl()
            self.add_dir(f'Next Page ({next_page})', next_page_url, 2, self.icon, self.fanart, context_menu=context_menu)

        self.end_directory()

    def play_video(self, url):
        content = self.make_request(url, use_cookies=True)
        if not content: return self.notify_error("Failed to load video page")
        embed_match = re.search(r"vid\s*=\s*'(.+?)'.*?hash\s*=\s*'(.+?)'", content, re.DOTALL)
        if not embed_match: return self.notify_error('Failed to extract video data')
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
            except Exception: pass
        hash_val = ''.join(parts)
        json_url = f'{self.base_url}xhr/video/{vid}?hash={hash_val}&domain=www.eporner.com&fallback=false&embed=true&supportedFormats=dash,mp4'
        headers = {**self.get_headers(url), 'X-Requested-With': 'XMLHttpRequest'}
        content = self.make_request(json_url, headers=headers, use_cookies=True)
        if not content: return self.notify_error('Failed to load video JSON data')
        try: data = json.loads(content)
        except json.JSONDecodeError: return self.notify_error('Invalid video JSON data')
        stream_url = None
        sources = data.get('sources', {}).get('mp4', {})
        if isinstance(sources, dict):
            mp4_urls = [v.get('src', '') for v in sources.values() if isinstance(v, dict) and v.get('src')]
            if mp4_urls: stream_url = max(mp4_urls, key=lambda u: int(re.search(r'(\d+)p', u).group(1) if re.search(r'(\d+)p', u) else 0), default=None)
        if not stream_url: stream_url = data.get('sources', {}).get('hls', {}).get('auto', {}).get('src')
        if not stream_url: return self.notify_error('No playable stream found')
        li = xbmcgui.ListItem(path=stream_url)
        li.setProperty('IsPlayable', 'true')
        if '.m3u8' in stream_url:
            li.setMimeType('application/vnd.apple.mpegurl'); li.setProperty('inputstream', 'inputstream.adaptive'); li.setProperty('inputstream.adaptive.manifest_type', 'hls')
        else: li.setMimeType('video/mp4')
        xbmcplugin.setResolvedUrl(self.addon_handle, True, li)

    def process_categories(self, url):
        content = self.make_request(f'{self.base_url}cats/', use_cookies=False)
        if not content: self.notify_error('Failed to load categories'); self.end_directory(); return
        content = re.sub(r'\s+', ' ', content)
        pattern = r'<a[^>]+href="(/cat/[^"]+)"[^>]*>\s*([^<]*)'
        matches = re.findall(pattern, content, re.IGNORECASE)
        unique_categories = {url_part.strip('/'): name.strip() or url_part.strip('/').split('/')[-1].replace('-', ' ').capitalize() for url_part, name in matches}
        context_menu = [('Sort by...', f'RunPlugin({sys.argv[0]}?mode=7&action=select_sort&website={self.name}&original_url={urllib.parse.quote_plus(url)})')]
        for url_part_key, name in sorted(unique_categories.items(), key=lambda x: x[1]):
            full_url = f'{self.base_url}{url_part_key}/'
            self.add_dir(name, full_url, 2, self.icons['categories'], self.fanart, context_menu=context_menu)
        self.end_directory()

    def select_gay_filter(self, original_url=None):
        if not original_url: self.notify_error("Cannot apply filter: page context is missing."); return
        try: current_idx = int(self.addon.getSetting('eporner_gay_filter') or '0')
        except (ValueError, IndexError): current_idx = 0
        dialog = xbmcgui.Dialog()
        idx = dialog.select("Filter Content...", self.gay_filter_options, preselect=current_idx)
        if idx != -1:
            self.addon.setSetting('eporner_gay_filter', str(idx))
            xbmc.executebuiltin(f"Container.Update({sys.argv[0]}?mode=2&url={urllib.parse.quote_plus(original_url)}&website={self.name},replace)")