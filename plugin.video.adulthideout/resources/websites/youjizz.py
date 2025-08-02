#!/usr/bin/env python
# -*- coding: utf-8 -*-

import re
import urllib.parse
import urllib.request
from http.cookiejar import CookieJar
from io import BytesIO
import gzip
import html
import xbmc
import xbmcaddon
import xbmcgui
import xbmcplugin
import xbmcvfs
import os
from resources.lib.base_website import BaseWebsite

class YoujizzWebsite(BaseWebsite):
    config = {
        "name": "youjizz",
        "base_url": "https://www.youjizz.com",
        "search_url": "https://www.youjizz.com/search?q={}",
        "categories_url": "https://www.youjizz.com/sitemap"
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
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/*,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Cache-Control': 'no-cache',
            'Pragma': 'no-cache',
            'Sec-Ch-Ua': '"Google Chrome";v="129", "Not=A?Brand";v="8", "Chromium";v="129"',
            'Sec-Ch-Ua-Mobile': '?0',
            'Sec-Ch-Ua-Platform': '"Windows"',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Upgrade-Insecure-Requests': '1',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36'
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
        except Exception as e:
            self.logger.error(f"Failed to save debug file {filename}: {e}")

    def make_request(self, url, headers=None, max_retries=3, retry_wait=5000):
        is_json = 'json' in url.lower()
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
                    self._save_debug_file(f'youjizz_response_{url.replace("/", "_").replace(":", "_")}.html', content)
                    return content
            except urllib.error.HTTPError as e:
                self.logger.error(f"HTTP error fetching {url} (attempt {attempt + 1}/{max_retries}): {e}")
                if hasattr(e, 'read'):
                    error_content = e.read().decode('utf-8', errors='ignore')
                    self._save_debug_file(f'youjizz_error_{url.replace("/", "_").replace(":", "_")}.html', error_content)
                if attempt < max_retries - 1:
                    xbmc.sleep(retry_wait)
            except urllib.error.URLError as e:
                self.logger.error(f"URL error fetching {url}: {e}")
                if attempt < max_retries - 1:
                    xbmc.sleep(retry_wait)
        self.logger.error(f"Failed to fetch URL: {url}")
        self.notify_error(f"Failed to fetch URL: {url}")
        return ""

    def process_content(self, url):
        parsed_url = urllib.parse.urlparse(url)
        base_path = parsed_url.path.strip('/')
        query_params = urllib.parse.parse_qs(parsed_url.query)

        if url == self.config["base_url"] or not base_path:
            url = f"{self.config['base_url']}/newest-clips/1.html"
        if base_path == "sitemap":
            self.process_categories(url)
            return
        if query_params.get('q'):
            search_query = query_params.get('q', [''])[0]
            url = self.config["search_url"].format(urllib.parse.quote_plus(search_query))

        content = self.make_request(url)
        if content:
            self.add_basic_dirs(url)
            self.process_content_matches(content, url)
        else:
            self.logger.error(f"Failed to load page: {url}")
            self.notify_error("Failed to load page")
        self.end_directory()

    def add_basic_dirs(self, current_url):
        context_menu = []
        dirs = [
            ('[COLOR blue]Search[/COLOR]', '', 5, self.icons['search'], self.config['name']),
            ('Categories', self.config['categories_url'], 2, self.icons['categories']),
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
        content = self.make_request(url)
        if not content:
            self.logger.error("Failed to load categories")
            self.notify_error("Failed to load categories")
            return
        pattern = r'<li><a href="(/categories/[^"]+)">([^<]+)</a></li>'
        matches = re.findall(pattern, content, re.DOTALL)
        for category_url, name in matches:
            full_url = urllib.parse.urljoin(self.config['base_url'], category_url)
            self.add_dir(html.unescape(name), full_url, 2, self.icons['categories'], self.fanart)
        self.end_directory()

    def process_content_matches(self, content, current_url):
        pattern = r'<div class="video-thumb"[^>]*>.*?data-original="([^"]*)".+?<a href=["\']([^"\']+)["\'][^>]*>([^<]+)</a>.+?<span class="time">.*?([0-9:]+)'
        matches = re.findall(pattern, content, re.DOTALL)
        if not matches:
            pattern_alt = r'<a href=["\']([^"\']+)["\'][^>]*>([^<]+)</a>.+?(?:<span class="(?:time|duration)">.*?([0-9:]+)|)'
            matches = re.findall(pattern_alt, content, re.DOTALL)
        if not matches:
            self.logger.error(f"No videos found for URL: {current_url}")
            self._save_debug_file(f'youjizz_no_matches_{current_url.replace("/", "_").replace(":", "_")}.html', content)
            self.notify_error("No videos found")
        for match in matches:
            if len(match) == 4:
                thumbnail, video_url, title, duration = match
            elif len(match) == 3:
                video_url, title, duration = match
                thumbnail = ''
            else:
                continue
            if "out.php" in video_url:
                continue
            full_url = urllib.parse.urljoin(self.config['base_url'], video_url)
            thumb_url = urllib.parse.urljoin('https:', thumbnail) if thumbnail and not thumbnail.startswith('http') else thumbnail or self.icons['default']
            title = html.unescape(title)
            duration = duration if duration else ""
            title_display = f'{title} [COLOR lime]({duration})[/COLOR]' if duration else title
            self.add_link(title_display, full_url, 4, thumb_url, self.fanart)
        next_page_match = re.search(r'<a class="pagination-next" href="([^"]+)"', content)
        if not next_page_match:
            next_page_match = re.search(r'<a href="([^"]+)"[^>]*>Next', content, re.IGNORECASE)
        if next_page_match:
            next_url = urllib.parse.urljoin(self.config['base_url'], next_page_match.group(1))
            self.add_dir('[COLOR blue]Next Page >>>>[/COLOR]', next_url, 2, self.icons['default'], self.fanart)
        self.end_directory()

    def play_video(self, url):
        content = self.make_request(url)
        if not content:
            self.logger.error("Failed to load video page")
            self.notify_error("Failed to load video page")
            return
        try:
            patterns = [
                (r'"filename":"([^"]+\.mp4[^"]*)"', "Original filename pattern"),
                (r'<source[^>]+src=["\']([^"\']+)', "<source> tag"),
                (r'<video[^>]+src=["\']([^"\']+)', "<video> tag"),
                (r'["\']file["\']\s*:\s*["\']([^"]+\.(?:mp4|m3u8))', "JavaScript file variable"),
                (r'src=["\']([^"\']+\.(?:mp4|m3u8))["\']', "Generic src attribute"),
                (r'data-src=["\']([^"\']+\.(?:mp4|m3u8))["\']', "Data-src attribute"),
                (r'videoSrc\s*=\s*["\']([^"\']+\.(?:mp4|m3u8))["\']', "videoSrc variable"),
                (r'url:\s*["\']([^"\']+\.(?:mp4|m3u8))["\']', "Generic URL pattern"),
                (r'["\']video["\']\s*:\s*["\']([^"\']+\.(?:mp4|m3u8))["\']', "Generic video variable"),
                (r'data-video=["\']([^"\']+\.(?:mp4|m3u8))["\']', "Data-video attribute"),
                (r'["\']source["\']\s*:\s*["\']([^"\']+\.(?:mp4|m3u8))["\']', "Generic source variable"),
                (r'data-video-url=["\']([^"\']+\.(?:mp4|m3u8))["\']', "Data-video-url attribute"),
                (r'["\']mediaDefinitions["\']\s*:\s*\[\s*\{\s*["\']src["\']\s*:\s*["\']([^"\']+\.(?:mp4|m3u8))', "mediaDefinitions pattern"),
                (r'data-video-src=["\']([^"\']+\.(?:mp4|m3u8))["\']', "Data-video-src attribute")
            ]
            preferred_qualities = ["1080", "720"]
            found_urls = []
            for pattern, description in patterns:
                matches = re.findall(pattern, content, re.IGNORECASE)
                for match_url in matches:
                    found_urls.append((match_url, description))
            if not found_urls:
                self.logger.error(f"No video source found for URL: {url}")
                self._save_debug_file(f'youjizz_no_source_{url.replace("/", "_").replace(":", "_")}.html', content)
                self.notify_error("No valid stream URL found")
                return
            selected_url = None
            for quality in preferred_qualities:
                for match_url, description in found_urls:
                    if quality.lower() in match_url.lower():
                        selected_url = match_url.replace('amp;', '')
                        break
                if selected_url:
                    break
            if not selected_url:
                selected_url = found_urls[0][0].replace('amp;', '')
            cleaned_url = selected_url.replace('\\', '/').replace('//', '/')
            if cleaned_url.startswith('/'):
                video_url = 'https://' + cleaned_url.lstrip('/')
            else:
                video_url = 'https://' + cleaned_url
            video_url = re.sub(r'https:/+', 'https://', video_url)
            try:
                request = urllib.request.Request(video_url, headers=self.get_headers(video_url))
                with urllib.request.urlopen(request, timeout=30) as response:
                    pass
            except urllib.error.HTTPError as e:
                self.logger.error(f"Error verifying video URL {video_url}: {e}")
                self._save_debug_file(f'youjizz_error_{url.replace("/", "_").replace(":", "_")}.html', content)
                self.notify_error(f"Invalid video URL: {e}")
                return
            except urllib.error.URLError as e:
                self.logger.error(f"URL error for video URL {video_url}: {e}")
                self._save_debug_file(f'youjizz_error_{url.replace("/", "_").replace(":", "_")}.html', content)
                self.notify_error(f"Invalid video URL: {e}")
                return
            li = xbmcgui.ListItem(path=video_url)
            li.setProperty("IsPlayable", "true")
            li.setMimeType("video/mp4" if video_url.endswith(".mp4") else "application/x-mpegURL")
            li.setContentLookup(False)
            xbmcplugin.setResolvedUrl(self.addon_handle, True, li)
        except Exception as e:
            self.logger.error(f"Error processing video for URL {url}: {str(e)}")
            self._save_debug_file(f'youjizz_error_{url.replace("/", "_").replace(":", "_")}.html', content)
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