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
import xbmcvfs
import os
from datetime import datetime
from resources.lib.base_website import BaseWebsite

class XHamster(BaseWebsite):
    config = {
        "name": "xhamster",
        "base_url": "https://xhamster.com",
        "search_url": "https://xhamster.com/search/{}",
        "categories_url": "https://xhamster.com/categories"
    }

    def __init__(self, addon_handle):
        super().__init__(
            name=self.config["name"],
            base_url=self.config["base_url"],
            search_url=self.config["search_url"],
            addon_handle=addon_handle
        )
        self.filter_cache = None
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

    def select_sort_order(self, original_url=None):
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

    def get_headers(self, referer=None, is_json=False):
        headers = {
            'User-Agent': 'Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Mobile Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate',
            'Cookie': 'kt_lang=en; _agev=1; cookieConsent=1'
        }
        if referer:
            headers['Referer'] = referer
        if is_json:
            headers['Accept'] = 'application/json, text/javascript, */*; q=0.01'
            headers['X-Requested-With'] = 'XMLHttpRequest'
            headers['sec-fetch-dest'] = 'empty'
            headers['sec-fetch-mode'] = 'cors'
            headers['sec-fetch-site'] = 'same-origin'
        return headers

    def make_request(self, url, headers=None, max_retries=3, retry_wait=5000):
        is_json = 'json' in url.lower() or 'api' in url.lower()
        headers = headers or self.get_headers(url, is_json=is_json)
        cookie_jar = CookieJar()
        handler = urllib.request.HTTPCookieProcessor(cookie_jar)
        opener = urllib.request.build_opener(handler)
        for attempt in range(max_retries):
            try:
                request = urllib.request.Request(url, headers=headers)
                with opener.open(request, timeout=60) as response:
                    encoding = response.info().get('Content-Encoding')
                    raw_data = response.read()
                    if encoding == 'gzip':
                        data = gzip.GzipFile(fileobj=BytesIO(raw_data)).read()
                    else:
                        data = raw_data
                    content = data.decode('utf-8', errors='ignore')
                    return content
            except urllib.request.HTTPError:
                if attempt < max_retries - 1:
                    xbmc.sleep(retry_wait)
            except urllib.request.URLError:
                if attempt < max_retries - 1:
                    xbmc.sleep(retry_wait)
        self.notify_error(f"Failed to fetch URL: {url}")
        return ""

    def _load_filters(self, content=None):
        if self.filter_cache:
            return self.filter_cache
        if not content:
            content = self.make_request(self.config['base_url'], headers=self.get_headers())
        if not content:
            return None
        json_match = re.search(r'window\.initials\s*=\s*({.*?});</script>', content, re.DOTALL)
        if json_match:
            try:
                jdata = json.loads(json_match.group(1))
                filters = {'sort': [], 'resolution': [], 'fps': [], 'time_period': [], 'duration': []}
                filter_props = jdata.get('videoFiltersProps', {}).get('list', {})
                hub_buttons = jdata.get('videoFiltersProps', {}).get('hubDropdownButtons', [])
                for btn in hub_buttons:
                    if len(btn) >= 2:
                        filters['sort'].append({'value': btn[1].split('/')[-1] or 'featured', 'label': btn[2]})
                for q in filter_props.get('quality', []):
                    for key, val in q.items():
                        filters['resolution'].append({'value': val['value'] or '', 'label': val['label']})
                for f in filter_props.get('fps', []):
                    for key, val in f.items():
                        filters['fps'].append({'value': val['value'] or '', 'label': val['label']})
                filters['time_period'].append({'value': '', 'label': 'All Time'})
                for r in filter_props.get('range', [[]])[0]:
                    for key, val in r.items():
                        filters['time_period'].append({'value': val['value'], 'label': val['label']})
                for d in filter_props.get('duration', []):
                    for key, val in d.items():
                        filters['duration'].append({'value': val['value'], 'label': val['label']})
                self.filter_cache = filters
                return filters
            except json.JSONDecodeError:
                pass
        return None

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
        content = self.make_request(request_url, headers=self.get_headers(request_url))
        if not content:
            self.notify_error(f'Failed to fetch URL: {request_url}')
            self.end_directory()
            return
        context_menu = [
            ('Content Type...', f'RunPlugin({sys.argv[0]}?mode=7&action=select_content_type&website={self.name})'),
            ('Sort by...', f'RunPlugin({sys.argv[0]}?mode=7&action=select_sort_order&website={self.name})'),
            ('Filter by Duration...', f'RunPlugin({sys.argv[0]}?mode=7&action=select_duration&website={self.name})'),
            ('Filter by Quality...', f'RunPlugin({sys.argv[0]}?mode=7&action=select_quality&website={self.name})')
        ]
        json_match = re.search(r'window\.initials\s*=\s*({.*?});</script>', content, re.DOTALL)
        videos = []
        if json_match:
            try:
                jdata = json.loads(json_match.group(1))
                video_paths = [
                    jdata.get('layoutPage', {}).get('videoListProps', {}).get('videoThumbProps', []),
                    jdata.get('layoutPage', {}).get('trendingVideoListProps', {}).get('videoThumbProps', []),
                    jdata.get('searchResult', {}).get('videoThumbProps', []),
                    jdata.get('categoryPage', {}).get('videoThumbProps', []),
                    jdata.get('layoutPage', {}).get('store', {}).get('videos', [])
                ]
                for path in video_paths:
                    if isinstance(path, list) and path:
                        videos.extend(path)
                        break
            except json.JSONDecodeError:
                pass
        if not videos:
            pattern = r'<a\s+class="[^"]*video-thumb__image-container[^"]*"[^>]*href="([^"]+)"[^>]*title="([^"]+)"[^>]*>.*?<img[^>]+src="([^"]+)"[^>]*>(?:.*?video-thumb-info__duration[^>]*>([\d:]+)</[^>]+>)?'
            matches = re.findall(pattern, content, re.DOTALL)
            for video_url, title, thumbnail, duration in matches:
                video_url = urllib.parse.urljoin(self.base_url, video_url)
                title = urllib.parse.unquote(title)
                duration_str = f'[{duration}]' if duration else '[N/A]'
                videos.append({'pageURL': video_url, 'title': title, 'thumbURL': thumbnail, 'duration': duration_str})
        if not videos:
            self.notify_error('No videos found')
            self.end_directory()
            return
        for video in videos:
            if video.get('isBlockedByGeo'):
                continue
            title = video.get('title', 'No Title')
            page_url = video.get('pageURL', '')
            thumbnail = video.get('thumbURL', '')
            duration = video.get('duration', 0)
            try:
                if isinstance(duration, str) and ':' in duration:
                    minutes, seconds = map(int, duration.strip('[]').split(':'))
                    duration = minutes * 60 + seconds
                duration = int(duration)
                duration_str = f'[{duration // 60}:{duration % 60:02d}]' if duration > 0 else '[N/A]'
            except (TypeError, ValueError):
                duration_str = '[N/A]'
            display_title = f'{title} {duration_str}'
            self.add_link(display_title, page_url, 4, thumbnail, self.fanart, context_menu=context_menu)
        if videos:
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
            self.add_dir('Next Page >>', next_page_url, 2, self.icons['default'], self.fanart)
        self.end_directory()

    def add_basic_dirs(self, current_url):
        context_menu = []
        cat_value = (self.addon.getSetting('xhamster_category') or 'Straight').lower()
        filter_url = f'{self.config["base_url"]}/{cat_value}/filter_options' if cat_value else f'{self.config["base_url"]}/filter_options'
        dirs = [
            ('Search xHamster', '', 5, self.icons['search'], self.config['name']),
            ('Categories', self.config['categories_url'], 2, self.icons['categories']),
        ]
        for name, url, mode, icon, *extra in dirs:
            dir_name, dir_url, dir_mode, dir_context_menu, dir_fanart = name, url, mode, context_menu, self.fanart
            dir_name_param = extra[0] if extra else name
            self.add_dir(dir_name, dir_url, dir_mode, icon, dir_fanart, dir_context_menu, name_param=dir_name_param)

    def process_categories(self, url):
        content = self.make_request(url, headers=self.get_headers(url))
        if not content:
            self.notify_error('Failed to load categories')
            self.end_directory()
            return
        categories_dict = {}
        json_match = re.search(r'window\.initials\s*=\s*({.*?});</script>', content, re.DOTALL)
        if json_match:
            try:
                jdata = json.loads(json_match.group(1))
                trending_items = jdata.get('layoutPage', {}).get('store', {}).get('popular', {}).get('trending', {}).get('items', [])
                for item in trending_items:
                    if isinstance(item, dict) and 'url' in item and 'name' in item:
                        cat_url = item['url']
                        if 'categories' in cat_url:
                            categories_dict[cat_url] = (item['name'], item.get('thumb', '') or item.get('thumbnail', ''))
                assignable_groups = jdata.get('layoutPage', {}).get('store', {}).get('popular', {}).get('assignable', [])
                for group in assignable_groups:
                    if isinstance(group, dict) and 'items' in group:
                        for item in group.get('items', []):
                            if isinstance(item, dict) and 'url' in item and 'name' in item:
                                cat_url = item['url']
                                if 'categories' in cat_url:
                                    categories_dict[cat_url] = (item['name'], item.get('thumb', '') or item.get('thumbnail', ''))
            except json.JSONDecodeError:
                pass
        if not categories_dict:
            html_pattern = r'<a\s+href="(https://(?:ge\.)?xhamster\.com/categories/[^"]+)"[^>]*>(?:<img[^>]+src="([^"]+)"[^>]*>)?[^<]*(?:<[^>]+>)*([^<]+)(?:</[^>]+>)*</a>'
            html_categories = re.findall(html_pattern, content, re.DOTALL)
            for cat_url, thumbnail, name in html_categories:
                name = re.sub(r'|<[^>]+>', '', name).strip()
                if name and cat_url:
                    categories_dict[cat_url] = (name, thumbnail or '')
        if not categories_dict:
            self.notify_error('No categories found')
            self.end_directory()
            return
        for cat_url, (name, thumbnail) in sorted(categories_dict.items()):
            self.add_dir(name, cat_url, 2, thumbnail or self.icons['categories'], self.fanart)
        self.end_directory()

    def play_video(self, url):
        decoded_url = urllib.parse.unquote_plus(url)
        content = self.make_request(decoded_url, headers=self.get_headers(decoded_url))
        if not content:
            self.notify_error('Failed to load video page')
            return
        stream_url = None
        json_match = re.search(r'window.initials\s*=\s*({.*?});</script>', content, re.DOTALL)
        if json_match:
            try:
                jdata = json.loads(json_match.group(1))
                sources_hls = jdata.get('xplayerSettings', {}).get('sources', {}).get('hls', {})
                stream_url = (
                    sources_hls.get('h264', {}).get('url') or
                    sources_hls.get('av1', {}).get('url') or
                    sources_hls.get('url')
                )
                if not stream_url:
                    sources_standard = jdata.get('xplayerSettings', {}).get('sources', {}).get('standard', {})
                    stream_url = (
                        sources_standard.get('mp4', {}).get('url') or
                        jdata.get('videoModel', {}).get('sources', {}).get('mp4', {}).get('1080p') or
                        jdata.get('videoModel', {}).get('sources', {}).get('mp4', {}).get('720p')
                    )
            except json.JSONDecodeError:
                pass
        if not stream_url:
            patterns = [
                (r'"mp4File":"(.*?)"', 'mp4File'),
                (r'"hlsUrl":"(.*?)"', 'hlsUrl'),
                (r'<source[^>]+src=["\']([^"\']+\.(?:mp4|m3u8))["\']', '<source> tag')
            ]
            for pattern, desc in patterns:
                match = re.search(pattern, content, re.IGNORECASE)
                if match:
                    stream_url = match.group(1).replace('\\/', '/')
                    break
        if not stream_url:
            self.notify_error('No playable stream found')
            return
        stream_url = stream_url.replace('\\/', '/')
        if not stream_url.startswith('http'):
            stream_url = urllib.parse.urljoin(self.base_url, stream_url)
        try:
            request = urllib.request.Request(stream_url, headers=self.get_headers(stream_url))
            with urllib.request.urlopen(request, timeout=30) as response:
                pass
        except urllib.request.HTTPError:
            self.notify_error('Invalid stream URL')
            return
        except urllib.request.URLError:
            self.notify_error('Failed to verify stream')
            return
        headers = self.get_headers(decoded_url)
        header_string = '|'.join([f'{k}={urllib.parse.quote(v)}' for k, v in headers.items()])
        li = xbmcgui.ListItem(path=f'{stream_url}|{header_string}')
        if stream_url.endswith('.m3u8'):
            li.setProperty('inputstream', 'inputstream.adaptive')
            li.setProperty('inputstream.adaptive.manifest_type', 'hls')
            li.setMimeType('application/vnd.apple.mpegurl')
        else:
            li.setMimeType('video/mp4')
        li.setContentLookup(False)
        xbmcplugin.setResolvedUrl(self.addon_handle, True, li)