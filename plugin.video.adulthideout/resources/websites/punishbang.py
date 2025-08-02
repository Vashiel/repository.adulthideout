#!/usr/bin/env python
# -*- coding: utf-8 -*-

import re
import urllib.parse
import urllib.request
from http.cookiejar import CookieJar
import gzip
from io import BytesIO
import xbmc
import xbmcgui
import xbmcplugin
import xbmcvfs
import html
import os
from resources.lib.base_website import BaseWebsite

class PunishbangWebsite(BaseWebsite):
    config = {
        "name": "punishbang",
        "base_url": "https://www.punishbang.com",
        "search_url": "https://www.punishbang.com/search/?q={}"
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
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate'
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
                    content = response.read()
                    content_encoding = response.info().get('Content-Encoding')
                    if content_encoding == 'gzip':
                        try:
                            content = gzip.GzipFile(fileobj=BytesIO(content)).read()
                        except Exception as e:
                            self.logger.error(f"Gzip decompression failed for {url}: {e}")
                            self.notify_error(f"Gzip decompression failed: {e}")
                            return ""
                    try:
                        content = content.decode('utf-8')
                    except UnicodeDecodeError:
                        self.logger.warning(f"UTF-8 decoding failed for {url}, trying latin-1")
                        content = content.decode('latin-1', errors='ignore')
                    self._save_debug_file(f'punishbang_response_{url.replace("/", "_").replace(":", "_")}.html', content)
                    return content.replace('\n', '').replace('\r', '')
            except urllib.request.HTTPError as e:
                self.logger.error(f"HTTP error {e.code} for {url}: {e.reason} (attempt {attempt + 1}/{max_retries})")
                if hasattr(e, 'read'):
                    error_content = e.read().decode('utf-8', errors='ignore')
                    self._save_debug_file(f'punishbang_error_{url.replace("/", "_").replace(":", "_")}.html', error_content)
                if attempt < max_retries - 1:
                    xbmc.sleep(retry_wait)
            except Exception as e:
                self.logger.error(f"Request failed for {url}: {e}")
                if attempt < max_retries - 1:
                    xbmc.sleep(retry_wait)
        self.notify_error(f"Failed to fetch URL: {url}")
        return ""

    def process_content(self, url):
        if "videos" not in url and "search" not in url and "channels" not in url:
            url = url + "/videos/?from=1"

        if url == 'https://www.punishbang.com/channels/':
            self.process_categories(url)
        else:
            content = self.make_request(url)
            if not content:
                self.notify_error("Failed to load content")
                self.add_basic_dirs(url)
                self.end_directory()
                return

            self.add_basic_dirs(url)

            matches = re.compile('<a href="([^"]+)".+?data-src="([^"]+)".+?alt="([^"]+)"', re.DOTALL).findall(content)
            for video_url, thumb, name in matches:
                name = html.unescape(name)
                if not video_url.startswith('http'):
                    video_url = self.base_url + video_url
                if not thumb.startswith('http'):
                    thumb = self.base_url + thumb
                self.add_link(name, video_url, 4, thumb, self.fanart)

            parsed_url = urllib.parse.urlparse(url)
            query_params = urllib.parse.parse_qs(parsed_url.query)
            current_from = int(query_params.get('from', [1])[0])
            next_from = current_from + 1
            base_url = f"{parsed_url.scheme}://{parsed_url.netloc}{parsed_url.path}"
            next_query_params = query_params
            next_query_params['from'] = [str(next_from)]
            next_url = f"{base_url}?{urllib.parse.urlencode(next_query_params, doseq=True)}"
            self.add_dir('[COLOR blue]Next Page >>>>[/COLOR]', next_url, 2, self.icons['default'], self.fanart)

        self.end_directory()

    def add_basic_dirs(self, current_url):
        context_menu = []
        dirs = [
            ('Search Punishbang', '', 5, self.icons['search'], self.config['name']),
            ('Categories', 'https://www.punishbang.com/channels/', 2, self.icons['categories']),
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
            self.notify_error("Failed to load categories")
            self.end_directory()
            return

        matches = re.compile('<a href="([^"]+)".+?data-src="([^"]+)".+?alt="([^"]+)"', re.DOTALL).findall(content)
        for cat_url, thumb, name in matches:
            if not cat_url.startswith('http'):
                cat_url = self.base_url + cat_url
            if not thumb.startswith('http'):
                thumb = self.base_url + thumb
            self.add_dir(name, cat_url, 2, self.icons['categories'], self.fanart)

        self.end_directory()

    def play_video(self, url):
        content = self.make_request(url)
        if not content:
            self.notify_error("Failed to load video page")
            return

        try:
            media_url = re.compile("video_url: '([^']+)'").findall(content)[0]
            media_url = media_url.replace('amp;', '')
            list_item = xbmcgui.ListItem(path=media_url)
            xbmcplugin.setResolvedUrl(self.addon_handle, True, list_item)
        except IndexError:
            self.logger.error(f"Failed to extract video URL for {url}")
            self._save_debug_file(f'punishbang_error_{url.replace("/", "_").replace(":", "_")}.html', content)
            self.notify_error("Failed to extract video URL")
        except Exception as e:
            self.logger.error(f"Error playing video {url}: {e}")
            self.notify_error(f"Error playing video: {e}")