#!/usr/bin/env python
# -*- coding: utf-8 -*-

import re
import json
import urllib.parse as urllib_parse
import urllib.request as urllib_request
from http.cookiejar import CookieJar
import xbmc
import xbmcgui
import xbmcplugin
import xbmcvfs
import os
from resources.lib.base_website import BaseWebsite

class UflashWebsite(BaseWebsite):
    config = {
        "name": "uflash",
        "base_url": "http://www.uflash.tv/",
        "search_url": "http://www.uflash.tv/search?q={}"
    }

    def __init__(self, addon_handle):
        super().__init__(
            name=self.config["name"],
            base_url=self.config["base_url"],
            search_url=self.config["search_url"],
            addon_handle=addon_handle
        )

    def get_headers(self, referer=None, is_json=False):
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/javascript, */*; q=0.01' if is_json else 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': 'de-DE,de;q=0.9',
            'Accept-Encoding': 'identity'
        }
        if referer:
            headers['Referer'] = referer
        if is_json:
            headers['X-Requested-With'] = 'XMLHttpRequest'
            headers['User-Agent'] = 'iPad'
        return headers

    def _save_debug_file(self, filename, content):
        try:
            debug_path = xbmcvfs.translatePath(os.path.join('special://temp', filename))
            with xbmcvfs.File(debug_path, 'w') as f:
                f.write(content)
            self.logger.debug(f"Saved debug data to: {debug_path}")
        except Exception as e:
            self.logger.error(f"Failed to save debug file {filename}: {e}")

    def make_request(self, url, headers=None, data=None, max_retries=3, retry_wait=5000):
        is_json = 'json' in url.lower()
        headers = headers or self.get_headers(url, is_json=is_json)
        cookie_jar = CookieJar()
        handler = urllib_request.HTTPCookieProcessor(cookie_jar)
        opener = urllib_request.build_opener(handler)
        if data and not isinstance(data, bytes):
            data = urllib_parse.urlencode(data).encode('utf-8')
        for attempt in range(max_retries):
            try:
                request = urllib_request.Request(url, data=data, headers=headers)
                with opener.open(request, timeout=60) as response:
                    content = response.read().decode('utf-8', errors='ignore')
                    self._save_debug_file(f'uflash_response_{url.replace("/", "_").replace(":", "_")}.json' if is_json else f'uflash_response_{url.replace("/", "_").replace(":", "_")}.html', content)
                    return content
            except urllib_request.HTTPError as e:
                self.logger.error(f"HTTP error fetching {url} (attempt {attempt + 1}/{max_retries}): {e}")
                if hasattr(e, 'read'):
                    error_content = e.read().decode('utf-8', errors='ignore')
                    self._save_debug_file(f'uflash_error_{url.replace("/", "_").replace(":", "_")}.json' if is_json else f'uflash_error_{url.replace("/", "_").replace(":", "_")}.html', error_content)
                if attempt < max_retries - 1:
                    xbmc.sleep(retry_wait)
            except urllib_request.URLError as e:
                self.logger.error(f"URL error fetching {url}: {e}")
                if attempt < max_retries - 1:
                    xbmc.sleep(retry_wait)
        self.logger.error(f"Failed to fetch URL: {url}")
        self.notify_error(f"Failed to fetch URL: {url}")
        return ""

    def process_content(self, url):
        parsed_url = urllib_parse.urlparse(url)
        base_path = parsed_url.path.strip('/')

        if base_path == 'categories':
            self.process_categories(url)
            return

        if not base_path:
            url = self.base_url

        content = self.make_request(url, headers=self.get_headers(url))
        if not content:
            self.notify_error(f"Failed to fetch URL: {url}")
            return

        if base_path not in ['categories', 'search']:
            self.add_basic_dirs(url)

        pattern = r'<a\s+href="(/video/\d+/[^"]+)"[^>]*>.*?<img[^>]+src="([^"]+)"[^>]+alt="([^"]+)"[^>]*>.*?(?:<span[^>]+class="duration">([:\d]+)</span>|)'
        matches = re.findall(pattern, content, re.DOTALL)
        videos = []
        for video_url, thumbnail, title, duration in matches:
            video_url = urllib_parse.urljoin(self.base_url, video_url)
            title = urllib_parse.unquote(title)
            duration_str = f'[{duration}]' if duration else '[N/A]'
            videos.append({
                'pageURL': video_url,
                'title': title,
                'thumbURL': thumbnail,
                'duration': duration_str
            })

        if not videos:
            self.logger.error(f"No videos found for URL: {url}")
            self._save_debug_file(f'uflash_no_videos_{url.replace("/", "_").replace(":", "_")}.html', content)
            self.notify_error("No videos found for this request")
            return

        for video in videos:
            title = video.get('title', 'No Title')
            page_url = video.get('pageURL')
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
            self.add_link(display_title, page_url, 4, thumbnail, self.fanart)

        next_page_pattern = r'<a[^>]+class="next"[^>]+href="([^"]+)"'
        next_page_match = re.search(next_page_pattern, content)
        if next_page_match:
            next_url = urllib_parse.urljoin(self.base_url, next_page_match.group(1))
            self.add_dir('Next Page', next_url, 2, self.icons['default'], self.fanart)

        self.end_directory()

    def add_basic_dirs(self, current_url):
        context_menu = []
        dirs = [
            ('Search Uflash', '', 5, self.icons['search'], self.config['name']),
            ('Categories', f'{self.base_url}categories', 2, self.icons['categories']),
        ]
        for name, url, mode, icon, *extra in dirs:
            dir_name = name
            dir_url = url
            dir_mode = mode
            dir_context_menu = context_menu
            dir_fanart = self.fanart
            dir_name_param = extra[0] if extra else name
            self.add_dir(dir_name, dir_url, dir_mode, icon, dir_fanart, dir_context_menu, name_param=dir_name_param)

    def process_categories(self, url):
        content = self.make_request(url, headers=self.get_headers(url))
        if not content:
            self.notify_error("Failed to load categories")
            return

        categories_dict = {}
        html_pattern = r'<a\s+href="(/category/[^"]+)"[^>]*>.*?<img[^>]+src="([^"]+)"[^>]*>.*?<span[^>]+class="category-name">([^<]+)</span>'
        html_categories = re.findall(html_pattern, content, re.DOTALL)
        for cat_url, thumbnail, name in html_categories:
            name = re.sub(r'<[^>]+>', '', name).strip()
            cat_url = urllib_parse.urljoin(self.base_url, cat_url)
            categories_dict[cat_url] = (name, thumbnail)

        if not categories_dict:
            self.logger.error(f"No categories found for URL: {url}")
            self._save_debug_file(f'uflash_no_categories_{url.replace("/", "_").replace(":", "_")}.html', content)
            self.notify_error("No categories found")
            return

        for cat_url, (name, thumbnail) in sorted(categories_dict.items()):
            self.add_dir(name, cat_url, 2, self.icons['categories'], self.fanart)
        self.end_directory()

    def play_video(self, url):
        decoded_url = urllib_parse.unquote_plus(url)
        try:
            video_id = re.search(r'/video/(\d+)/', decoded_url).group(1)
        except AttributeError:
            self.logger.error(f"Failed to extract video ID from URL: {decoded_url}")
            self.notify_error("Invalid video URL")
            return

        video_info_url = f"{self.base_url}ajax/getvideo"
        data = {'vid': video_id}
        content = self.make_request(video_info_url, headers=self.get_headers(decoded_url, is_json=True), data=data)
        if not content:
            self.logger.error(f"Failed to fetch video info from {video_info_url}")
            self.notify_error("Failed to load video info")
            return

        stream_url = None
        try:
            jdata = json.loads(content)
            stream_url = jdata.get('video_src')
        except json.JSONDecodeError as e:
            self.logger.error(f"JSON parsing failed for video info: {e}")
            self._save_debug_file(f'uflash_error_{decoded_url.replace("/", "_").replace(":", "_")}.json', content)
            self.notify_error("Invalid video data")

        if not stream_url:
            content = self.make_request(decoded_url, headers=self.get_headers(decoded_url))
            if content:
                patterns = [
                    (r'<source[^>]+src=["\']([^"\']+\.(?:mp4|m3u8))["\']', '<source> tag'),
                    (r'data-video-src=["\']([^"\']+\.(?:mp4|m3u8))["\']', 'data-video-src'),
                    (r'src=["\']([^"\']+\.(?:mp4|m3u8))["\']', 'generic src'),
                    (r'"file":"([^"]+\.(?:mp4|m3u8))"', 'file JSON')
                ]
                for pattern, desc in patterns:
                    match = re.search(pattern, content, re.IGNORECASE)
                    if match:
                        stream_url = match.group(1).replace('\\/', '/')
                        break

        if not stream_url:
            self.logger.error(f"No stream URL available for: {decoded_url}")
            self._save_debug_file(f'uflash_error_{decoded_url.replace("/", "_").replace(":", "_")}.html', content)
            self.notify_error("No playable stream found")
            return

        stream_url = stream_url.replace('\\/', '/')
        if not stream_url.startswith('http'):
            stream_url = urllib_parse.urljoin(self.base_url, stream_url)

        try:
            request = urllib_request.Request(stream_url, headers=self.get_headers(decoded_url))
            with urllib_request.urlopen(request, timeout=30) as response:
                pass
        except urllib_request.HTTPError as e:
            self.logger.error(f"Invalid stream URL: {stream_url}, status: {e.code}")
            self.notify_error("Invalid stream URL")
            return
        except urllib_request.URLError as e:
            self.logger.error(f"Failed to verify stream URL: {e}")
            self.notify_error("Failed to verify stream")
            return

        headers = self.get_headers(decoded_url)
        header_string = '|'.join([f'{k}={urllib_parse.quote(v)}' for k, v in headers.items()])
        li = xbmcgui.ListItem(path=f'{stream_url}|{header_string}')
        if stream_url.endswith('.m3u8'):
            li.setProperty('inputstream', 'inputstream.adaptive')
            li.setProperty('inputstream.adaptive.manifest_type', 'hls')
            li.setMimeType('application/vnd.apple.mpegurl')
        else:
            li.setMimeType('video/mp4')
        li.setContentLookup(False)
        xbmcplugin.setResolvedUrl(self.addon_handle, True, li)