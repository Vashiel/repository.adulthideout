#!/usr/bin/env python
# -*- coding: utf-8 -*-

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
from resources.lib.proxy_utils import HlsProxyController, PlaybackGuard, ProxyController

try:
    addon_path = xbmcaddon.Addon().getAddonInfo('path')
    vendor_path = os.path.join(addon_path, 'resources', 'lib', 'vendor')
    if vendor_path not in sys.path:
        sys.path.insert(0, vendor_path)
except Exception:
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
        
        self.sort_options = ["Newest", "Most Viewed", "Top Rated", "Longest", "Shortest"]
        self.api_order_params = {
            "Newest": "latest",
            "Most Viewed": "most-popular",
            "Top Rated": "top-rated",
            "Longest": "longest",
            "Shortest": "shortest"
        }
        self.gay_filter_options = ["Exclude Gay (Straight)", "Only Gay", "Include Gay (Both)"]
        self.gay_filter_map = {"0": "0", "1": "2", "2": "1"}

        self.quality_options = ["All Qualities", "720p+ (HD)", "1080p+ (Full HD)", "4K (2160p)"]
        self.duration_options = ["All Durations", "Short (< 10 min)", "10+ min", "20+ min", "30+ min"]

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

    def _format_duration(self, seconds):
        if not seconds:
            return "0:00"
        try:
            seconds = int(seconds)
            m, s = divmod(seconds, 60)
            h, m = divmod(m, 60)
            if h:
                return f"{h}:{m:02d}:{s:02d}"
            return f"{m}:{s:02d}"
        except Exception:
            return "0:00"

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

    def get_global_context_menu(self, current_url=""):
        encoded_url = urllib.parse.quote_plus(current_url or self.base_url)
        return [
            ('Select Sort...', f'RunPlugin({sys.argv[0]}?mode=7&action=select_sort&website={self.name}&original_url={encoded_url})'),
            ('Select Content Filter...', f'RunPlugin({sys.argv[0]}?mode=7&action=select_gay_filter&website={self.name}&original_url={encoded_url})'),
            ('Select Quality...', f'RunPlugin({sys.argv[0]}?mode=7&action=select_quality&website={self.name}&original_url={encoded_url})'),
            ('Select Duration...', f'RunPlugin({sys.argv[0]}?mode=7&action=select_duration&website={self.name}&original_url={encoded_url})')
        ]

    def add_basic_dirs(self, current_url):
        context_menu = self.get_global_context_menu(current_url)
        cat_url = urllib.parse.urljoin(self.base_url, 'cats/')
        self.add_dir('[COLOR blue]Search[/COLOR]', '', 5, self.icons['search'], self.fanart, context_menu=context_menu)
        self.add_dir('Categories', cat_url, 8, self.icons['categories'], self.fanart, context_menu=context_menu)

    def process_content(self, url):
        if '/cats/' in url:
            self.process_categories(url)
            return

        self.add_basic_dirs(url)

        page = 1
        query = ""
        
        if "api/v2" in url:
            parsed = urllib.parse.urlparse(url)
            params = urllib.parse.parse_qs(parsed.query)
            query = params.get('query', [''])[0]
            page = int(params.get('page', ['1'])[0])
        else:
            clean_url = url.rstrip('/')
            parts = clean_url.split('/')
            
            if '/cat/' in url:
                if parts:
                    query = parts[-1]
                    if query.isdigit(): 
                        page = int(query)
                        query = parts[-2]
            elif '/search/' in url:
                if parts:
                    if parts[-1].isdigit():
                        query = parts[-2]
                        page = int(parts[-1])
                    else:
                        query = parts[-1]

        query = urllib.parse.unquote_plus(query)

        saved_sort_idx = self.addon.getSetting(f'{self.name}_sort_by') or '0'
        try: sort_idx = int(saved_sort_idx)
        except Exception: sort_idx = 0
        if sort_idx >= len(self.sort_options): sort_idx = 0
        sort_key = "Longest" if getattr(self, "adult_hideout_full_movie_mode", False) else self.sort_options[sort_idx]
        
        saved_gay_idx = self.addon.getSetting('eporner_gay_filter') or '0'
        saved_qual_idx = self.addon.getSetting('eporner_quality_filter') or '0'
        saved_dur_idx = self.addon.getSetting('eporner_min_duration') or '0'
        try: dur_idx = int(saved_dur_idx)
        except Exception: dur_idx = 0
        if getattr(self, "adult_hideout_full_movie_mode", False):
            dur_idx = 0

        try: qual_idx = int(saved_qual_idx)
        except Exception: qual_idx = 0

        api_query = query
        hd_param = '0'

        if qual_idx == 1: # 720p+ (HD)
            hd_param = '1'
        elif qual_idx == 2: # 1080p+ (Full HD)
            hd_param = '1'
            if '1080p' not in api_query.lower():
                api_query = f"{api_query} 1080p".strip() if api_query else "1080p"
        elif qual_idx == 3: # 4K
            hd_param = '1'
            if '4k' not in api_query.lower():
                api_query = f"{api_query} 4k".strip() if api_query else "4k"

        api_params = {
            'query': api_query,
            'page': page,
            'per_page': '30',
            'order': self.api_order_params.get(sort_key, 'most-popular'),
            'gay': self.gay_filter_map.get(saved_gay_idx, '0'),
            'hd': hd_param,
            'thumbsize': 'medium',
            'format': 'json'
        }
        
        api_url = f"{self.API_BASE}?{urllib.parse.urlencode(api_params)}"
        self.render_video_list(api_url, page, query, sort_key, saved_gay_idx, dur_idx, url)
        self.end_directory()

    def render_video_list(self, api_url, current_page, query, sort_key, gay_idx, dur_idx, original_url):
        data_str = self.make_request(api_url)
        if not data_str: return

        try:
            data = json.loads(data_str)
            videos = data.get('videos', [])
            context_menu = self.get_global_context_menu(original_url)

            for video in videos:
                title = video.get('title')
                duration = video.get('length_sec')
                rating = video.get('rate')
                views = video.get('views')
                thumb = video.get('default_thumb', {}).get('src')
                vid_url = video.get('url')

                dur_sec = int(duration) if duration else 0

                # Duration filtering
                if dur_idx == 1 and dur_sec >= 600:
                    continue
                elif dur_idx == 2 and dur_sec < 600:
                    continue
                elif dur_idx == 3 and dur_sec < 1200:
                    continue
                elif dur_idx == 4 and dur_sec < 1800:
                    continue

                display_name = f"{title} [COLOR yellow]({self._format_duration(dur_sec)})[/COLOR] [COLOR blue]★{rating}[/COLOR]"
                
                info = {
                    'plot': f"Views: {views}\nRating: {rating}",
                    'duration': dur_sec,
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

        except Exception as exc:
            self.logger.error(f"[Eporner] Error rendering video list: {exc}")

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

        context_menu = self.get_global_context_menu(url)

        for url_part_key, name in sorted(unique_categories.items(), key=lambda x: x[1]):
            full_url = urllib.parse.urljoin(self.base_url, f'{url_part_key}/')
            self.add_dir(name, full_url, 2, self.icons['categories'], self.fanart, context_menu=context_menu)
        
        self.end_directory()

    def select_sort(self, original_url=None):
        dialog = xbmcgui.Dialog()
        idx = dialog.select("Select Sort...", self.sort_options)
        if idx != -1:
            self.addon.setSetting(f'{self.name}_sort_by', str(idx))
            xbmc.executebuiltin(f'Container.Update({sys.argv[0]}?mode=2&url=BOOTSTRAP&website={self.name},replace)')

    def select_gay_filter(self, original_url=None):
        dialog = xbmcgui.Dialog()
        idx = dialog.select("Select Content Filter...", self.gay_filter_options)
        if idx != -1:
            self.addon.setSetting('eporner_gay_filter', str(idx))
            xbmc.executebuiltin(f'Container.Update({sys.argv[0]}?mode=2&url=BOOTSTRAP&website={self.name},replace)')

    def select_quality(self, original_url=None):
        dialog = xbmcgui.Dialog()
        idx = dialog.select("Select Quality...", self.quality_options)
        if idx != -1:
            self.addon.setSetting('eporner_quality_filter', str(idx))
            xbmc.executebuiltin(f'Container.Update({sys.argv[0]}?mode=2&url=BOOTSTRAP&website={self.name},replace)')

    def select_duration(self, original_url=None):
        dialog = xbmcgui.Dialog()
        idx = dialog.select("Select Duration...", self.duration_options)
        if idx != -1:
            self.addon.setSetting('eporner_min_duration', str(idx))
            xbmc.executebuiltin(f'Container.Update({sys.argv[0]}?mode=2&url=BOOTSTRAP&website={self.name},replace)')

    def _select_hls_variant(self, master_m3u8_text, target_qual):
        lines = master_m3u8_text.splitlines()
        candidates = []
        for idx, line in enumerate(lines):
            if line.startswith('#EXT-X-STREAM-INF'):
                url_line = lines[idx+1] if idx+1 < len(lines) else ""
                if url_line.startswith('http'):
                    res_match = re.search(r'RESOLUTION=(\d+)x(\d+)', line)
                    height = int(res_match.group(2)) if res_match else 0
                    candidates.append((height, url_line))
        if not candidates:
            return None
        candidates.sort(key=lambda x: x[0], reverse=True)
        if target_qual == "4K":
            for h, url in candidates:
                if h >= 2160: return url
            return candidates[0][1]
        elif target_qual == "1080p":
            for h, url in candidates:
                if h == 1080: return url
            for h, url in candidates:
                if h >= 1080 and h <= 1440: return url
            return candidates[0][1]
        elif target_qual == "720p":
            for h, url in candidates:
                if h == 720: return url
            return candidates[-1][1]
        return candidates[0][1]

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
            except Exception: pass
        hash_val = ''.join(parts)

        json_url = f'{self.base_url}xhr/video/{vid}?hash={hash_val}&domain=www.eporner.com&fallback=false&embed=false&supportedFormats=dash,hls,mp4'
        xhr_headers = {'X-Requested-With': 'XMLHttpRequest', 'Referer': url, 'User-Agent': self.ua}
        
        api_content = self.make_request(json_url, headers=xhr_headers)
        if not api_content: return self.notify_error("Failed to authorize")

        try:
            data = json.loads(api_content)
            
            saved_qual_idx = self.addon.getSetting('eporner_quality_filter') or '0'
            try: qual_idx = int(saved_qual_idx)
            except Exception: qual_idx = 0

            pref_map = {0: "1080p", 1: "720p", 2: "1080p", 3: "4K"}
            target_qual = pref_map.get(qual_idx, "1080p")

            headers_str = urllib.parse.urlencode({'User-Agent': self.ua, 'Referer': url})

            # Primary: Try HLS adaptive stream with target resolution selection
            hls_sources = data.get('sources', {}).get('hls', {})
            hls_master_url = None
            if isinstance(hls_sources, dict):
                auto_hls = hls_sources.get('auto', {})
                if isinstance(auto_hls, dict):
                    hls_master_url = auto_hls.get('src')

            if hls_master_url:
                stream_url = hls_master_url
                master_text = self.make_request(hls_master_url)
                if master_text:
                    variant_url = self._select_hls_variant(master_text, target_qual)
                    if variant_url:
                        stream_url = variant_url

                play_path = f"{stream_url}|{headers_str}"
                item = xbmcgui.ListItem(path=play_path)
                item.setProperty('IsPlayable', 'true')
                item.setMimeType('application/x-mpegURL')
                item.setProperty('inputstream', 'inputstream.adaptive')
                item.setProperty('inputstream.adaptive.manifest_type', 'hls')
                item.setContentLookup(False)
                xbmcplugin.setResolvedUrl(self.addon_handle, True, item)
                return

            # Fallback: MP4 direct stream selection
            stream_url = None
            sources = data.get('sources', {}).get('mp4', {})
            if isinstance(sources, dict) and sources:
                priority = []
                if target_qual == "4K":
                    priority = ['2160p', '1440p', '1080p', '720p', '480p']
                elif target_qual == "1080p":
                    priority = ['1080p', '720p', '1440p', '2160p', '480p']
                elif target_qual == "720p":
                    priority = ['720p', '1080p', '480p', '360p']
                else:
                    priority = ['1080p', '720p', '480p', '360p']

                for p in priority:
                    for label, s_info in sources.items():
                        if isinstance(s_info, dict) and p in label.lower() and s_info.get('src'):
                            stream_url = s_info.get('src')
                            break
                    if stream_url:
                        break

                if not stream_url:
                    mp4_urls = [v.get('src') for v in sources.values() if isinstance(v, dict) and v.get('src')]
                    if mp4_urls:
                        stream_url = mp4_urls[0]

            if stream_url:
                play_path = f"{stream_url}|{headers_str}"
                item = xbmcgui.ListItem(path=play_path)
                item.setProperty('IsPlayable', 'true')
                item.setMimeType('video/mp4')
                item.setContentLookup(False)
                xbmcplugin.setResolvedUrl(self.addon_handle, True, item)
                return

            self.notify_error("Stream URL not found")
        except Exception as exc:
            self.logger.error(f"[Eporner] Play error: {exc}")
            self.notify_error("Failed to parse video sources")

    def search(self, query):
        if query:
            search_url = f"{self.API_BASE}?query={urllib.parse.quote_plus(query)}"
            self.process_content(search_url)
        else:
            self.end_directory()
