#!/usr/bin/env python
# -*- coding: utf-8 -*-

import re
import urllib.parse
import urllib.request
from http.cookiejar import CookieJar
import html
import xbmc
import xbmcaddon
import xbmcgui
import xbmcplugin
import xbmcvfs
import os
from resources.lib.base_website import BaseWebsite

class RealcuckoldsexWebsite(BaseWebsite):
    config = {
        "name": "realcuckoldsex",
        "base_url": "https://realcuckoldsex.com",
        "search_url": "https://realcuckoldsex.com/search/?q={}",
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
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': 'de-DE,de;q=0.9'
        }
        if referer:
            headers['Referer'] = referer
        if is_json:
            headers['Accept'] = 'application/json, text/javascript, */*; q=0.01'
            headers['X-Requested-With'] = 'XMLHttpRequest'
            headers['Sec-Fetch-Dest'] = 'empty'
            headers['Sec-Fetch-Mode'] = 'cors'
            headers['Sec-Fetch-Site'] = 'same-origin'
        return headers

    def _save_debug_file(self, filename, content):
        try:
            debug_path = xbmcvfs.translatePath(os.path.join('special://temp', filename))
            with xbmcvfs.File(debug_path, 'w') as f:
                f.write(content)
            self.logger.debug(f"Saved debug data to: {debug_path}")
        except Exception as e:
            self.logger.error(f"Failed to save debug file {filename}: {e}")

    def make_request(self, url, headers=None, post_data=None, max_retries=3, retry_wait=5000):
        is_json = 'json' in url.lower()
        headers = headers or self.get_headers(url, is_json=is_json)
        cookie_jar = CookieJar()
        handler = urllib.request.HTTPCookieProcessor(cookie_jar)
        opener = urllib.request.build_opener(handler)
        if post_data:
            post_data = urllib.parse.urlencode(post_data).encode('utf-8')
        for attempt in range(max_retries):
            try:
                request = urllib.request.Request(url, data=post_data, headers=headers)
                with urllib.request.urlopen(request, timeout=60) as response:
                    content = response.read().decode('utf-8', errors='ignore')
                    self._save_debug_file(f'realcuckoldsex_response_{url.replace("/", "_").replace(":", "_")}.html', content)
                    return content
            except urllib.error.HTTPError as e:
                self.logger.error(f"HTTP error fetching {url} (attempt {attempt + 1}/{max_retries}): {e}")
                if hasattr(e, 'read'):
                    error_content = e.read().decode('utf-8', errors='ignore')
                    self._save_debug_file(f'realcuckoldsex_error_{url.replace("/", "_").replace(":", "_")}.html', error_content)
                if attempt < max_retries - 1:
                    xbmc.sleep(retry_wait)
            except urllib.error.URLError as e:
                self.logger.error(f"URL error fetching {url}: {e}")
                if attempt < max_retries - 1:
                    xbmc.sleep(retry_wait)
        self.logger.error(f"Failed to fetch URL: {url}")
        self.notify_error(f"Failed to fetch URL: {url}")
        return None

    def process_content(self, url):
        parsed_url = urllib.parse.urlparse(url)
        base_path = parsed_url.path.strip('/')
        query_params = urllib.parse.parse_qs(parsed_url.query)

        if url == self.config["base_url"] or not base_path:
            url = f"{self.config['base_url']}/latest-updates/"
        if query_params.get('q'):
            search_query = query_params.get('q', [''])[0]
            url = self.config["search_url"].format(urllib.parse.quote_plus(search_query))

        content = self.make_request(url, headers=self.get_headers(url))
        if content:
            self.add_basic_dirs(url)
            self.process_content_matches(content, url)
        else:
            self.notify_error("Failed to load page")
        self.end_directory()

    def add_basic_dirs(self, current_url):
        context_menu = []
        dirs = [
            ('[COLOR blue]Search[/COLOR]', '', 5, self.icons['search'], self.config['name']),
        ]
        for name, url, mode, icon, *extra in dirs:
            dir_name = name
            dir_url = url
            dir_mode = mode
            dir_context_menu = context_menu
            dir_fanart = self.fanart
            dir_name_param = extra[0] if extra else name
            self.add_dir(dir_name, dir_url, dir_mode, icon, dir_fanart, dir_context_menu, name_param=dir_name_param)

    def process_content_matches(self, content, current_url):
        pattern = r'<a target="_blank" href="([^"]+)">.+?data-original="([^"]+)" alt="([^"]+)"'
        matches = re.findall(pattern, content, re.DOTALL)
        if not matches:
            pattern_alt = r'<a[^>]*href="([^"]+)"[^>]*>.*?<img[^>]+src="([^"]+)"[^>]*alt="([^"]+)"'
            matches = re.findall(pattern_alt, content, re.DOTALL)
        for video_url, thumbnail, title in matches:
            if "out.php" in video_url:
                continue
            full_url = urllib.parse.urljoin(self.config['base_url'], video_url)
            thumb_url = urllib.parse.urljoin(self.config['base_url'], thumbnail)
            title = html.unescape(title)
            self.add_link(title, full_url, 4, thumb_url, self.fanart)
        next_page_match = re.search(r'<a href="([^"]+)"[^>]*>Next<', content)
        if next_page_match:
            next_url = urllib.parse.urljoin(self.config['base_url'], next_page_match.group(1))
            self.add_dir('[COLOR blue]Next Page >>>>[/COLOR]', next_url, 2, self.icons['default'], self.fanart)

    def play_video(self, url):
        content = self.make_request(url, headers=self.get_headers(url))
        if not content:
            self.notify_error("Failed to load video page")
            return
        try:
            match = None
            patterns = [
                (r"video_url:\s*'([^']+\.mp4)'", "Original video_url pattern"),
                (r'<source[^>]+src=["\']([^"\']+)', "<source> tag"),
                (r'<video[^>]+src=["\']([^"\']+)', "<video> tag"),
                (r'["\']file["\']\s*:\s*["\']([^"]+\.(?:mp4|m3u8))', "JavaScript file variable"),
                (r'src=["\']([^"\']+\.(?:mp4|m3u8))["\']', "Generic src attribute"),
                (r'data-src=["\']([^"\']+\.(?:mp4|m3u8))["\']', "Data-src attribute"),
                (r'videoSrc\s*=\s*["\']([^"\']+\.(?:mp4|m3u8))["\']', "videoSrc variable"),
                (r'url:\s*["\']([^"\']+\.(?:mp4|m3u8))["\']', "Generic URL pattern"),
                (r'["\']video["\']\s*:\s*["\']([^"\']+\.(?:mp4|m3u8))["\']', "Generic video variable"),
                (r'data-video=["\']([^"\']+\.(?:mp4|m3u8))["\']', "Data-video attribute")
            ]
            for pattern, description in patterns:
                match = re.search(pattern, content, re.IGNORECASE)
                if match:
                    break
            if not match:
                self.logger.error(f"No video source found for URL: {url}")
                self._save_debug_file(f'realcuckoldsex_error_{url.replace("/", "_").replace(":", "_")}.html', content)
                self.notify_error("Could not find valid stream URL")
                return
            video_url = match.group(1).replace('amp;', '')
            video_url = urllib.parse.urljoin(self.config['base_url'], video_url) if not video_url.startswith('http') else video_url
            try:
                request = urllib.request.Request(video_url, headers=self.get_headers(video_url))
                with urllib.request.urlopen(request, timeout=30) as response:
                    pass
            except urllib.error.HTTPError as e:
                self.logger.error(f"Failed to verify video URL {video_url}: {e}")
                self.notify_error(f"Invalid video URL: {video_url}")
                return
            li = xbmcgui.ListItem(path=video_url)
            li.setProperty("IsPlayable", "true")
            li.setMimeType("video/mp4" if video_url.endswith(".mp4") else "application/x-mpegURL")
            li.setContentLookup(False)
            xbmcplugin.setResolvedUrl(self.addon_handle, True, li)
        except Exception as e:
            self.logger.error(f"Error processing video for URL {url}: {str(e)}")
            self._save_debug_file(f'realcuckoldsex_error_{url.replace("/", "_").replace(":", "_")}.html', content)
            self.notify_error(f"Error processing video: {str(e)}")

    def handle_search_entry(self, url, mode, name, action=None):
        if action == 'new_search':
            query = self.get_search_query()
            if query:
                search_url = self.search_url.format(urllib.parse.quote(query))
                self.process_content(search_url)
        elif action == 'history_search' and url:
            query = urllib.parse.quote(url)
            search_url = self.search_url.format(query)
            self.process_content(search_url)
        elif action == 'edit_search':
            self.edit_query()
        elif action == 'clear_history':
            self.clear_search_history()
        elif url:
            query = urllib.parse.quote(url)
            search_url = self.search_url.format(query)
            self.process_content(search_url)
        else:
            query = self.get_search_query()
            if query:
                search_url = self.search_url.format(urllib.parse.quote(query))
                self.process_content(search_url)