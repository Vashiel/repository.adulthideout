#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Changelog:
# - Final release version
# - Optimized thumbnail handling (Header injection + prioritized URLs)
# - Fixed context menu duplication bug
# - Full filtering support enabled

import re
import sys
import json
import urllib.parse
import urllib.request
from http.cookiejar import CookieJar
from io import BytesIO
import gzip
import xbmc
import xbmcgui
import xbmcplugin
from resources.lib.base_website import BaseWebsite

class XHamster(BaseWebsite):
    def __init__(self, addon_handle):
        super().__init__(
            name='xhamster',
            base_url='https://xhamster.com',
            search_url='https://xhamster.com/search/{}',
            addon_handle=addon_handle
        )
        self.categories_url = 'https://xhamster.com/categories'
        
        self.content_options = ['Straight', 'Gay', 'Shemale']
        self.content_paths = {'Straight': '', 'Gay': 'gay/', 'Shemale': 'shemale/'}
        
        self.sort_options = ['Trending', 'Newest', 'Top Rated', 'Most Popular (Weekly)', 'Most Popular (Monthly)']
        self.sort_paths = {
            'Trending': '',
            'Newest': 'newest/',
            'Top Rated': 'best/',
            'Most Popular (Weekly)': 'best/weekly/',
            'Most Popular (Monthly)': 'best/monthly/'
        }
        
        self.duration_options = ['All', '0-2 min', '2-5 min', '5-10 min', '10-30 min', '30+ min', 'Full Video']
        self.duration_data = {
            'All': ('', ''),
            '0-2 min': ('', 'max-duration=2'),
            '2-5 min': ('', 'min-duration=2&max-duration=5'),
            '5-10 min': ('', 'min-duration=5&max-duration=10'),
            '10-30 min': ('', 'min-duration=10&max-duration=30'),
            '30+ min': ('', 'min-duration=30'),
            'Full Video': ('full-length/', '')
        }
        
        self.quality_options = ['All', '720p+', '1080p+', '4K']
        self.quality_data = {
            'All': ('', ''),
            '720p+': ('hd/', ''),
            '1080p+': ('hd/', 'quality=1080p'),
            '4K': ('4k/', '')
        }

    def get_headers(self):
        return {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate',
            'Cookie': 'kt_lang=en; _agev=1; cookieConsent=1',
            'Referer': self.base_url + '/'
        }

    def make_request(self, url):
        headers = self.get_headers()
        cookie_jar = CookieJar()
        handler = urllib.request.HTTPCookieProcessor(cookie_jar)
        opener = urllib.request.build_opener(handler)
        
        try:
            request = urllib.request.Request(url, headers=headers)
            with opener.open(request, timeout=30) as response:
                content = response.read()
                if response.info().get('Content-Encoding') == 'gzip':
                    content = gzip.GzipFile(fileobj=BytesIO(content)).read()
                return content.decode('utf-8', errors='ignore')
        except Exception:
            return None

    def _select_generic(self, setting_id, options_list, title):
        current_setting = self.addon.getSetting(setting_id)
        try:
            preselect_idx = options_list.index(current_setting)
        except ValueError:
            preselect_idx = 0
        dialog = xbmcgui.Dialog()
        idx = dialog.select(title, options_list, preselect=preselect_idx)
        if idx != -1:
            self.addon.setSetting(setting_id, options_list[idx])
            xbmc.executebuiltin('Container.Refresh')

    def select_content_type(self, original_url=None):
        self._select_generic("xhamster_category", self.content_options, "Select Content Type...")

    def select_sort(self, original_url=None):
        self._select_generic("xhamster_sort_by", self.sort_options, "Sort by...")

    def select_duration(self, original_url=None):
        self._select_generic("xhamster_min_duration", self.duration_options, "Filter by Duration...")

    def select_quality(self, original_url=None):
        self._select_generic("xhamster_resolution", self.quality_options, "Filter by Quality...")

    def _build_filtered_url(self, page=1):
        content = self.addon.getSetting("xhamster_category") or self.content_options[0]
        sort = self.addon.getSetting("xhamster_sort_by") or self.sort_options[0]
        duration = self.addon.getSetting("xhamster_min_duration") or self.duration_options[0]
        quality = self.addon.getSetting("xhamster_resolution") or self.quality_options[0]
        
        content_path = self.content_paths.get(content, '')
        sort_path = self.sort_paths.get(sort, '')
        duration_path, duration_query = self.duration_data.get(duration, ('', ''))
        quality_path, quality_query = self.quality_data.get(quality, ('', ''))
        
        path_parts = [self.base_url, content_path, quality_path, duration_path, sort_path]
        if int(page) > 1:
            path_parts.append(str(page))
        
        final_url = "/".join(p.strip('/') for p in path_parts if p)
        if not urllib.parse.urlparse(final_url).path:
            final_url += '/'
        
        query_parts = [q for q in [quality_query, duration_query] if q]
        if query_parts:
            final_url += "?" + "&".join(query_parts)
        
        return final_url

    def _format_thumb_url(self, url):
        if not url:
            return self.icons['default']
        
        url = str(url).strip()
        if not url.startswith('http'):
            if url.startswith('//'):
                url = 'https:' + url
            else:
                return self.icons['default']

        headers = self.get_headers()
        ua_str = urllib.parse.quote(headers['User-Agent'])
        return f"{url}|User-Agent={ua_str}"

    def process_content(self, url):
        parsed_url = urllib.parse.urlparse(url)
        path = parsed_url.path.strip('/')

        if path == 'categories':
            self.process_categories(url)
            return

        self.add_basic_dirs(url)
        
        if 'search' in path or ('categories' in path and path != 'categories'):
            request_url = url
        else:
            page = 1
            path_parts = path.split('/')
            if path_parts and path_parts[-1].isdigit():
                page = int(path_parts[-1])
            request_url = self._build_filtered_url(page=page)

        content = self.make_request(request_url)
        if not content:
            self.notify_error('Failed to fetch content')
            self.end_directory()
            return
        
        videos = []
        json_match = re.search(r'window\.initials\s*=\s*({.*?});</script>', content, re.DOTALL)
        if json_match:
            try:
                jdata = json.loads(json_match.group(1))
                video_paths = [
                    jdata.get('pagesCategoryComponent', {}).get('trendingVideoListProps', {}).get('videoThumbProps', []),
                    jdata.get('videoListProps', {}).get('videoThumbProps', []),
                    jdata.get('searchResult', {}).get('videoThumbProps', []),
                    jdata.get('layoutPage', {}).get('videoListProps', {}).get('videoThumbProps', []),
                    jdata.get('layoutPage', {}).get('trendingVideoListProps', {}).get('videoThumbProps', []),
                    jdata.get('layoutPage', {}).get('store', {}).get('videos', [])
                ]
                for vpath in video_paths:
                    if isinstance(vpath, list) and vpath:
                        videos.extend(vpath)
                        break
            except json.JSONDecodeError:
                pass

        if not videos:
            self.notify_info('No videos found.')
            self.end_directory()
            return

        for video in videos:
            if video.get('isBlockedByGeo'):
                continue
            
            title = video.get('title', 'No Title')
            page_url = video.get('pageURL', '')
            if not page_url.startswith('http'):
                page_url = urllib.parse.urljoin(self.base_url, page_url)

            raw_thumb = video.get('thumbURL')
            if not raw_thumb:
                raw_thumb = video.get('previewURL')
            
            thumbnail = self._format_thumb_url(raw_thumb)
            
            duration = video.get('duration', 0)
            try:
                duration = int(duration)
                duration_str = f'[COLOR yellow][{duration // 60}:{duration % 60:02d}][/COLOR]' if duration > 0 else ''
            except (TypeError, ValueError):
                duration_str = ''

            context_menu = [
                ('Content Type...', f'RunPlugin({sys.argv[0]}?mode=7&action=select_content_type&website={self.name})'),
                ('Sort by...', f'RunPlugin({sys.argv[0]}?mode=7&action=select_sort&website={self.name})'),
                ('Filter by Duration...', f'RunPlugin({sys.argv[0]}?mode=7&action=select_duration&website={self.name})'),
                ('Filter by Quality...', f'RunPlugin({sys.argv[0]}?mode=7&action=select_quality&website={self.name})')
            ]

            display_title = f'{title} {duration_str}'.strip()
            self.add_link(display_title, page_url, 4, thumbnail, self.fanart, context_menu=context_menu)
        
        current_page_num = 1
        parsed_req_url = urllib.parse.urlparse(request_url)
        path_parts = parsed_req_url.path.strip('/').split('/')
        base_path_for_next = parsed_req_url.path
        
        if path_parts and path_parts[-1].isdigit():
            current_page_num = int(path_parts[-1])
            base_path_for_next = '/' + '/'.join(path_parts[:-1])
        
        next_page_num = current_page_num + 1
        next_page_path = base_path_for_next.strip('/') + '/' + str(next_page_num)
        next_page_url = urllib.parse.urljoin(self.base_url, next_page_path)
        
        if parsed_req_url.query:
            next_page_url += f"?{parsed_req_url.query}"
            
        self.add_dir('[COLOR blue]Next Page >>>>[/COLOR]', next_page_url, 2, self.icons['default'], self.fanart)
        self.end_directory()

    def add_basic_dirs(self, current_url):
        self.add_dir('[COLOR blue]Search[/COLOR]', '', 5, self.icons['search'], self.fanart)
        self.add_dir('Categories', self.categories_url, 2, self.icons['categories'], self.fanart)

    def process_categories(self, url):
        content = self.make_request(url)
        if not content:
            self.notify_error('Failed to load categories')
            self.end_directory()
            return
            
        categories_dict = {}
        json_match = re.search(r'window\.initials\s*=\s*({.*?});</script>', content, re.DOTALL)
        if json_match:
            try:
                jdata = json.loads(json_match.group(1))
                category_groups = [
                    jdata.get('layoutPage', {}).get('store', {}).get('popular', {}).get('trending', {}).get('items', []),
                ]
                assignable_groups = jdata.get('layoutPage', {}).get('store', {}).get('popular', {}).get('assignable', [])
                for group in assignable_groups:
                    if isinstance(group, dict) and 'items' in group:
                        category_groups.append(group.get('items', []))
                
                for group in category_groups:
                    for item in group:
                        if isinstance(item, dict) and 'url' in item and 'name' in item:
                            cat_url = item['url']
                            if 'categories' in cat_url:
                                raw_thumb = item.get('thumb', '') or item.get('thumbnail', '')
                                thumb = self._format_thumb_url(raw_thumb)
                                categories_dict[cat_url] = (item['name'], thumb)
            except json.JSONDecodeError:
                pass
        
        if not categories_dict:
            self.notify_error('No categories found')
            self.end_directory()
            return
            
        for cat_url, (name, thumbnail) in sorted(categories_dict.items()):
            self.add_dir(name, cat_url, 2, thumbnail or self.icons['categories'], self.fanart)
            
        self.end_directory()

    def play_video(self, url):
        content = self.make_request(urllib.parse.unquote_plus(url))
        if not content:
            self.notify_error('Failed to load video page')
            return

        stream_url = None
        
        preload_match = re.search(r'<link rel="preload" href="([^"]+\.m3u8)"', content)
        if preload_match:
            stream_url = preload_match.group(1)

        if not stream_url:
            noscript_match = re.search(r'<noscript>.*?<video[^>]+src="([^"]+\.mp4)"', content, re.DOTALL)
            if noscript_match:
                stream_url = noscript_match.group(1)

        if not stream_url:
            self.notify_error('No playable stream found')
            return

        if not stream_url.startswith('http'):
            stream_url = urllib.parse.urljoin(self.base_url, stream_url)
        
        li = xbmcgui.ListItem(path=stream_url)
        
        if '.m3u8' in stream_url:
            li.setProperty('inputstream', 'inputstream.adaptive')
            li.setProperty('inputstream.adaptive.manifest_type', 'hls')
            li.setMimeType('application/vnd.apple.mpegurl')
        else:
            li.setMimeType('video/mp4')
            
        li.setContentLookup(False)
        xbmcplugin.setResolvedUrl(self.addon_handle, True, li)