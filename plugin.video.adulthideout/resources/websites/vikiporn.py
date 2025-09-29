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
import sys
import hashlib
from resources.lib.base_website import BaseWebsite

class VikipornWebsite(BaseWebsite):
    config = {
        "name": "vikiporn",
        "base_url": "https://www.vikiporn.com",
        "search_url": "https://www.vikiporn.com/search/?q={}"
    }

    def __init__(self, addon_handle):
        super().__init__(
            name=self.config["name"],
            base_url=self.config["base_url"],
            search_url=self.config["search_url"],
            addon_handle=addon_handle
        )
        self._thumb_cache_dir = self._initialize_thumb_cache()

    def _initialize_thumb_cache(self):
        addon_profile = xbmcvfs.translatePath(self.addon.getAddonInfo('profile'))
        thumb_dir = os.path.join(addon_profile, 'thumbs', self.name)
        if not xbmcvfs.exists(thumb_dir):
            xbmcvfs.mkdirs(thumb_dir)
        return thumb_dir

    def _download_and_validate_thumb(self, url):
        if not url or not url.startswith('http'):
            return url

        try:
            hashed_url = hashlib.md5(url.encode('utf-8')).hexdigest()
            
            valid_signatures = {
                b'\xFF\xD8\xFF': '.jpg',
                b'\x89PNG\r\n\x1a\n': '.png',
                b'GIF89a': '.gif',
                b'GIF87a': '.gif',
                b'BM': '.bmp',
                b'RIFF': '.webp'
            }

            for ext in set(valid_signatures.values()):
                local_path = os.path.join(self._thumb_cache_dir, hashed_url + ext)
                if xbmcvfs.exists(local_path):
                    return local_path

            headers = self.get_extended_headers(referer=url)
            request = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(request, timeout=15) as response:
                content = response.read()

            file_ext = None
            for signature, ext in valid_signatures.items():
                if content.startswith(signature):
                    if ext == '.webp' and content[8:12] == b'WEBP':
                        file_ext = ext
                        break
                    elif ext != '.webp':
                        file_ext = ext
                        break
            
            if file_ext:
                local_path = os.path.join(self._thumb_cache_dir, hashed_url + file_ext)
                with xbmcvfs.File(local_path, 'wb') as f:
                    f.write(content)
                return local_path
            else:
                self.logger.warning(f"Invalid image from {url}, starts with: {content[:16]}")
                return self.icons['default']

        except Exception as e:
            self.logger.error(f"Failed to process thumb {url}: {e}")
            return self.icons['default']

    def add_dir(self, name, url, mode, icon=None, fanart=None, context_menu=None, name_param=None, info_labels=None, **kwargs):
        processed_icon = self._download_and_validate_thumb(icon) if icon else self.icons.get('default', self.icon)
        fanart = fanart or self.fanart
        u = f"{sys.argv[0]}?url={urllib.parse.quote_plus(str(url))}&mode={mode}&name={urllib.parse.quote_plus(name_param or name)}&website={self.name}"
        if kwargs:
            for key, value in kwargs.items(): u += f"&{key}={urllib.parse.quote_plus(str(value))}"
        
        liz = xbmcgui.ListItem(name)
        liz.setArt({'thumb': processed_icon, 'icon': processed_icon, 'fanart': fanart})
        
        if info_labels:
            liz.setInfo('video', info_labels)

        if context_menu: 
            liz.addContextMenuItems(context_menu)
            
        xbmcplugin.addDirectoryItem(handle=self.addon_handle, url=u, listitem=liz, isFolder=True)

    def add_link(self, name, url, mode, icon, fanart, context_menu=None, info_labels=None):
        processed_icon = self._download_and_validate_thumb(icon) if icon else self.icons.get('default', self.icon)
        u = f"{sys.argv[0]}?url={urllib.parse.quote_plus(url)}&mode={mode}&name={urllib.parse.quote_plus(name)}&website={self.name}"
        liz = xbmcgui.ListItem(name)
        liz.setArt({'thumb': processed_icon, 'icon': processed_icon, 'fanart': fanart})
        liz.getVideoInfoTag().setTitle(name)
        liz.setProperty('IsPlayable', 'true')
        if context_menu: liz.addContextMenuItems(context_menu)
        xbmcplugin.addDirectoryItem(handle=self.addon_handle, url=u, listitem=liz, isFolder=False)

    def get_extended_headers(self, referer=None, is_json=False):
        headers = {
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/*,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Cache-Control': 'no-cache',
            'Pragma': 'no-cache',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36'
        }
        if referer:
            headers['Referer'] = referer
        return headers

    def make_request(self, url, headers=None, max_retries=3, retry_wait=5000):
        headers = headers or self.get_extended_headers(url)
        cookie_jar = CookieJar()
        handler = urllib.request.HTTPCookieProcessor(cookie_jar)
        opener = urllib.request.build_opener(handler)
        for attempt in range(max_retries):
            try:
                request = urllib.request.Request(url, headers=headers)
                with opener.open(request, timeout=60) as response:
                    content = response.read().decode('utf-8', errors='ignore')
                    return content
            except (urllib.error.HTTPError, urllib.error.URLError):
                if attempt < max_retries - 1:
                    xbmc.sleep(retry_wait)
        self.notify_error(f"Failed to fetch URL: {url}")
        return ""

    def process_content(self, url):
        parsed_url = urllib.parse.urlparse(url)
        path = parsed_url.path.rstrip('/')

        content = self.make_request(url)
        if not content:
            self.notify_error("Failed to load page")
            self.end_directory()
            return

        self.add_basic_dirs(url)

        if path.endswith('/pornstars/') or '<div class="models-thumbs">' in content:
            self.process_pornstar_list(content)
        elif path.endswith('/categories/') or '<div class="categories-thumbs">' in content:
            self.process_category_list(content)
        else:
            self.process_video_list(content)

        self.add_next_button(content, url)
        self.end_directory()

    def add_basic_dirs(self, current_url):
        dirs = [
            ('[COLOR blue]Search[/COLOR]', '', 5, self.icons['search'], self.config['name']),
            ('Categories', f"{self.config['base_url']}/categories/", 2, self.icons['categories']),
            ('Pornstars', f"{self.config['base_url']}/pornstars/", 2, self.icons['pornstars']),
        ]
        for name, url, mode, icon, *extra in dirs:
            dir_name_param = extra[0] if extra else name
            self.add_dir(name, url, mode, icon, self.fanart, name_param=dir_name_param)

    def process_category_list(self, content):
        pattern = r'<div class="thumb">\s*<a class="ponn" href="([^"]+)"[^>]*>\s*<img src="([^"]+)"[^>]*>\s*<span>([^<]+)</span>'
        matches = re.findall(pattern, content, re.DOTALL)
        for item_url, thumb, name in matches:
            name = html.unescape(name.strip())
            full_url = urllib.parse.urljoin(self.config['base_url'], item_url)
            self.add_dir(name, full_url, 2, thumb, self.fanart)

    def process_pornstar_list(self, content):
        pattern = r'<div class="thumb">\s*<a href="([^"]+)" title="([^"]*)">.*?<img src="([^"]+)".*?<span>([^<]+)</span>'
        matches = re.findall(pattern, content, re.DOTALL)
        for item_url, title, thumb, name in matches:
            name = html.unescape(name.strip())
            full_url = urllib.parse.urljoin(self.config['base_url'], item_url)
            self.add_dir(name, full_url, 2, thumb, self.fanart)

    def process_video_list(self, content):
        pattern = r'<div class="thumb".*?<a class="ponn" href="([^"]+)".*?data-poster="([^"]+)".*?<span class="title">([^<]+)</span>.*?</div>'
        matches = re.findall(pattern, content, re.DOTALL)

        for video_url, thumb, name in matches:
            name = html.unescape(name.strip())
            full_video_url = urllib.parse.urljoin(self.config['base_url'], video_url)
            self.add_link(name, full_video_url, 4, thumb, self.fanart)

    def add_next_button(self, content, current_url):
        match = re.search(r'<li class="next">\s*<a rel="next" href="([^"]+)">', content)
        if match:
            next_url = urllib.parse.urljoin(self.config['base_url'], match.group(1))
            self.add_dir('[COLOR blue]Next Page >>>>[/COLOR]', next_url, 2, self.icons['default'], self.fanart)

    def play_video(self, url):
        content = self.make_request(url)
        if not content:
            self.notify_error("Failed to load video page")
            return

        match = re.search(r'<meta itemprop="contentUrl" content="([^"]+)">', content)
        
        if match:
            media_url = match.group(1)
            cleaned_url = html.unescape(media_url)
            
            li = xbmcgui.ListItem(path=cleaned_url)
            li.setProperty('IsPlayable', 'true')
            li.setMimeType('video/mp4')
            xbmcplugin.setResolvedUrl(self.addon_handle, True, li)
            return

        self.notify_error("No video source found")