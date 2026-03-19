#!/usr/bin/env python

import re
import urllib.parse
import urllib.request
from http.cookiejar import CookieJar
from concurrent.futures import ThreadPoolExecutor, as_completed
import html
import hashlib
import xbmc
import xbmcaddon
import xbmcgui
import xbmcplugin
import xbmcvfs
import os
import sys
from resources.lib.base_website import BaseWebsite


class VikipornWebsite(BaseWebsite):
    config = {
        "name": "vikiporn",
        "base_url": "https://www.vikiporn.com",
        "search_url": "https://www.vikiporn.com/search/?q={}"
    }

    sort_options = ["Latest", "Top Rated", "Most Popular"]
    sort_paths = {
        "Latest": "/latest-updates/",
        "Top Rated": "/top-rated/",
        "Most Popular": "/most-popular/",
    }

    # Max parallel thumbnail downloads
    THUMB_WORKERS = 10
    THUMB_TIMEOUT = 10

    def __init__(self, addon_handle):
        super().__init__(
            name=self.config["name"],
            base_url=self.config["base_url"],
            search_url=self.config["search_url"],
            addon_handle=addon_handle
        )
        self._thumb_cache_dir = self._init_thumb_cache()

    # ------------------------------------------------------------------
    # Thumbnail cache – threaded batch download
    # ------------------------------------------------------------------
    def _init_thumb_cache(self):
        addon_profile = xbmcvfs.translatePath(self.addon.getAddonInfo('profile'))
        thumb_dir = os.path.join(addon_profile, 'thumbs', self.name)
        if not xbmcvfs.exists(thumb_dir):
            xbmcvfs.mkdirs(thumb_dir)
        return thumb_dir

    def _download_single_thumb(self, url):
        """Download one thumbnail with correct Referer header.
        Returns local file path on success, or None on failure.
        Called from thread pool – must be thread-safe."""
        if not url or not url.startswith('http'):
            return None

        try:
            hashed = hashlib.md5(url.encode('utf-8')).hexdigest()

            # Check cache first
            for ext in ('.jpg', '.png', '.gif', '.webp', '.bmp'):
                cached = os.path.join(self._thumb_cache_dir, hashed + ext)
                if xbmcvfs.exists(cached):
                    return cached

            # Download with Referer to bypass CDN hotlink protection
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                              'AppleWebKit/537.36 (KHTML, like Gecko) '
                              'Chrome/129.0.0.0 Safari/537.36',
                'Referer': self.config['base_url'] + '/',
                'Accept': 'image/avif,image/webp,image/apng,image/*,*/*;q=0.8',
            }
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=self.THUMB_TIMEOUT) as resp:
                data = resp.read()

            # Detect actual image format via magic bytes
            signatures = {
                b'\xFF\xD8\xFF':       '.jpg',
                b'\x89PNG\r\n\x1a\n':  '.png',
                b'GIF89a':             '.gif',
                b'GIF87a':             '.gif',
                b'BM':                 '.bmp',
            }
            ext = None
            for sig, e in signatures.items():
                if data.startswith(sig):
                    ext = e
                    break
            if ext is None and data[:4] == b'RIFF' and data[8:12] == b'WEBP':
                ext = '.webp'

            if ext is None:
                return None

            local_path = os.path.join(self._thumb_cache_dir, hashed + ext)
            with xbmcvfs.File(local_path, 'wb') as f:
                f.write(data)
            return local_path

        except Exception:
            return None

    def _batch_download_thumbs(self, urls):
        """Download multiple thumbnails in parallel via ThreadPoolExecutor.
        Returns dict  {original_url: local_path_or_None}."""
        results = {}
        unique_urls = list(set(u for u in urls if u and u.startswith('http')))
        if not unique_urls:
            return results

        with ThreadPoolExecutor(max_workers=self.THUMB_WORKERS) as pool:
            future_map = {
                pool.submit(self._download_single_thumb, u): u
                for u in unique_urls
            }
            for future in as_completed(future_map):
                orig_url = future_map[future]
                try:
                    results[orig_url] = future.result()
                except Exception:
                    results[orig_url] = None

        return results

    def _resolve_thumb(self, thumb_map, url):
        """Look up a downloaded thumbnail, fall back to default icon."""
        path = thumb_map.get(url)
        if path and xbmcvfs.exists(path):
            return path
        return self.icons.get('default', self.icon)

    # ------------------------------------------------------------------
    # HTTP helpers
    # ------------------------------------------------------------------
    def get_extended_headers(self, referer=None):
        headers = {
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Cache-Control': 'no-cache',
            'Pragma': 'no-cache',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                          'AppleWebKit/537.36 (KHTML, like Gecko) '
                          'Chrome/129.0.0.0 Safari/537.36',
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
                    return response.read().decode('utf-8', errors='ignore')
            except (urllib.error.HTTPError, urllib.error.URLError) as e:
                self.logger.warning(f"Request attempt {attempt+1} failed for {url}: {e}")
                if attempt < max_retries - 1:
                    xbmc.sleep(retry_wait)
        self.notify_error(f"Failed to fetch URL after {max_retries} attempts")
        return ""

    # ------------------------------------------------------------------
    # Content routing
    # ------------------------------------------------------------------
    def process_content(self, url):
        content = self.make_request(url)
        if not content:
            self.notify_error("Failed to load page")
            self.end_directory()
            return

        self.add_basic_dirs(url)

        parsed_url = urllib.parse.urlparse(url)
        path = parsed_url.path.rstrip('/')

        if path.endswith('/pornstars') or '<div class="models-thumbs">' in content:
            self.process_pornstar_list(content)
        elif path.endswith('/categories') or '<div class="categories-thumbs">' in content:
            self.process_category_list(content)
        else:
            self.process_video_list(content)

        self.add_next_button(content, url)
        self.end_directory()

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------
    def add_basic_dirs(self, current_url):
        dirs = [
            ('[COLOR blue]Search[/COLOR]', '', 5, self.icons['search'],
             self.config['name']),
            ('Categories', f"{self.config['base_url']}/categories/", 2,
             self.icons['categories']),
            ('Pornstars', f"{self.config['base_url']}/pornstars/", 2,
             self.icons['pornstars']),
        ]
        for name, url, mode, icon, *extra in dirs:
            dir_name_param = extra[0] if extra else name
            self.add_dir(name, url, mode, icon, self.fanart,
                         name_param=dir_name_param)

    # ------------------------------------------------------------------
    # Parsers – all use parallel batch thumbnail download
    # ------------------------------------------------------------------
    def process_category_list(self, content):
        pattern = (r'<div class="thumb">\s*<a[^>]*href="([^"]+)"[^>]*>\s*'
                   r'<img[^>]*src="([^"]+)"[^>]*>\s*<span>([^<]+)</span>')
        matches = re.findall(pattern, content, re.DOTALL)
        if not matches:
            pattern = (r'<a[^>]*class="ponn"[^>]*href="([^"]+)"[^>]*>\s*'
                       r'<img[^>]*src="([^"]+)"[^>]*>.*?<span>([^<]+)</span>')
            matches = re.findall(pattern, content, re.DOTALL)
        if not matches:
            return

        thumb_map = self._batch_download_thumbs(
            [thumb for _, thumb, _ in matches])

        for item_url, thumb, name in matches:
            name = html.unescape(name.strip())
            full_url = urllib.parse.urljoin(self.config['base_url'], item_url)
            local_thumb = self._resolve_thumb(thumb_map, thumb)
            self.add_dir(name, full_url, 2, local_thumb, self.fanart)

    def process_pornstar_list(self, content):
        pattern = (r'<div class="thumb">\s*<a[^>]*href="([^"]+)"[^>]*'
                   r'title="([^"]*)"[^>]*>.*?<img[^>]*src="([^"]+)"[^>]*>'
                   r'.*?<span>([^<]+)</span>')
        matches = re.findall(pattern, content, re.DOTALL)
        if not matches:
            pattern = (r'<div class="thumb">.*?<a[^>]*href="([^"]+)"[^>]*>'
                       r'.*?<img[^>]*src="([^"]+)"[^>]*>'
                       r'.*?<span>([^<]+)</span>')
            matches = re.findall(pattern, content, re.DOTALL)
            matches = [(url, "", thumb, name) for url, thumb, name in matches]
        if not matches:
            return

        thumb_map = self._batch_download_thumbs(
            [thumb for _, _, thumb, _ in matches])

        for item_url, title, thumb, name in matches:
            name = html.unescape(name.strip())
            full_url = urllib.parse.urljoin(self.config['base_url'], item_url)
            local_thumb = self._resolve_thumb(thumb_map, thumb)
            self.add_dir(name, full_url, 2, local_thumb, self.fanart)

    def process_video_list(self, content):
        pattern = (r'<div class="thumb"[^>]*>.*?<a[^>]*class="ponn"[^>]*'
                   r'href="([^"]+)"[^>]*>.*?'
                   r'(?:data-poster|data-original|src)="([^"]+)".*?'
                   r'<span class="title"[^>]*>(?:<a[^>]*>)?([^<]+)'
                   r'(?:</a>)?</span>')
        matches = re.findall(pattern, content, re.DOTALL)
        if not matches:
            pattern = (r'<div class="thumb"[^>]*>.*?<a[^>]*href="([^"]+)"'
                       r'[^>]*>.*?<img[^>]*'
                       r'(?:data-poster|data-original|src)="([^"]+)"[^>]*>'
                       r'.*?<span[^>]*class="title"[^>]*>'
                       r'(?:<a[^>]*>)?([^<]+)(?:</a>)?</span>')
            matches = re.findall(pattern, content, re.DOTALL)
        if not matches:
            pattern = (r'<a[^>]*href="(/videos/[^"]+)"[^>]*>.*?'
                       r'<img[^>]*src="([^"]+)"[^>]*>.*?'
                       r'<span[^>]*>([^<]+)</span>')
            matches = re.findall(pattern, content, re.DOTALL)
        if not matches:
            return

        # Parallel batch download of all thumbnails
        thumb_map = self._batch_download_thumbs(
            [thumb for _, thumb, _ in matches])

        for video_url, thumb, name in matches:
            name = html.unescape(name.strip())
            full_url = urllib.parse.urljoin(self.config['base_url'], video_url)
            local_thumb = self._resolve_thumb(thumb_map, thumb)
            self.add_link(name, full_url, 4, local_thumb, self.fanart)

    # ------------------------------------------------------------------
    # Pagination
    # ------------------------------------------------------------------
    def add_next_button(self, content, current_url):
        match = re.search(
            r'<li class="next">\s*<a[^>]*href="([^"]+)"[^>]*>', content)
        if not match:
            match = re.search(
                r'<a[^>]*class="[^"]*next[^"]*"[^>]*href="([^"]+)"[^>]*>',
                content)
        if not match:
            match = re.search(
                r'<a[^>]*rel="next"[^>]*href="([^"]+)"[^>]*>', content)
        if match:
            next_url = urllib.parse.urljoin(
                self.config['base_url'], match.group(1))
            self.add_dir('[COLOR blue]Next Page >>>>[/COLOR]', next_url, 2,
                         self.icons['default'], self.fanart)

    # ------------------------------------------------------------------
    # Playback – ProxyController for seek/range support
    # ------------------------------------------------------------------
    def play_video(self, url):
        content = self.make_request(url)
        if not content:
            self.notify_error("Failed to load video page")
            return

        media_url = None

        # Pattern 1: meta itemprop contentUrl
        match = re.search(
            r'<meta\s+itemprop="contentUrl"\s+content="([^"]+)"', content)
        if match:
            media_url = match.group(1)

        # Pattern 2: video_url in JS
        if not media_url:
            match = re.search(
                r"video_url\s*[:=]\s*['\"]([^'\"]+)['\"]", content)
            if match:
                media_url = match.group(1)

        # Pattern 3: <source> tag
        if not media_url:
            match = re.search(
                r'<source[^>]*src="([^"]+)"[^>]*type="video/mp4"', content)
            if match:
                media_url = match.group(1)

        # Pattern 4: any mp4 URL
        if not media_url:
            match = re.search(
                r'(https?://[^\s"\'<>]+\.mp4[^\s"\'<>]*)', content)
            if match:
                media_url = match.group(1)

        if not media_url:
            self.notify_error("No video source found")
            return

        media_url = html.unescape(media_url)
        if not media_url.startswith('http'):
            media_url = urllib.parse.urljoin(self.config['base_url'], media_url)

        # Use ProxyController for proper Range/Seek support
        try:
            from resources.lib.proxy_utils import ProxyController, PlaybackGuard

            upstream_headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                              'AppleWebKit/537.36 (KHTML, like Gecko) '
                              'Chrome/129.0.0.0 Safari/537.36',
                'Referer': url,
                'Accept-Encoding': 'identity',
            }

            ctrl = ProxyController(
                upstream_url=media_url,
                upstream_headers=upstream_headers,
                use_urllib=True,
            )
            local_url = ctrl.start()

            li = xbmcgui.ListItem(path=local_url)
            li.setProperty('IsPlayable', 'true')
            li.setMimeType('video/mp4')
            xbmcplugin.setResolvedUrl(self.addon_handle, True, li)

            # Guard thread stops proxy when playback ends
            player = xbmc.Player()
            monitor = xbmc.Monitor()
            guard = PlaybackGuard(player, monitor, local_url, ctrl)
            guard.start()

        except Exception as e:
            self.logger.error(f"Proxy failed ({e}), falling back to direct")
            li = xbmcgui.ListItem(path=media_url)
            li.setProperty('IsPlayable', 'true')
            li.setMimeType('video/mp4')
            xbmcplugin.setResolvedUrl(self.addon_handle, True, li)