#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Changelog:
# - Final release version
# - Added full sorting support
# - Categories and search support

import re
import sys
import urllib.parse
import urllib.request
from http.cookiejar import CookieJar
import gzip
from io import BytesIO
import xbmc
import xbmcgui
import xbmcplugin
import html
from resources.lib.base_website import BaseWebsite

class PunishbangWebsite(BaseWebsite):
    def __init__(self, addon_handle):
        super().__init__(
            name='punishbang',
            base_url='https://www.punishbang.com',
            search_url='https://www.punishbang.com/search/?q={}',
            addon_handle=addon_handle
        )
        self.sort_options = ["Recently Featured", "Latest", "Most Popular", "Top Rated", "Longest", "Most Commented", "Most Favourited"]
        self.sort_paths = {
            "Recently Featured": "/videos/",
            "Latest": "/videos/?sort_by=post_date",
            "Most Popular": "/videos/?sort_by=video_viewed",
            "Top Rated": "/videos/?sort_by=rating",
            "Longest": "/videos/?sort_by=duration",
            "Most Commented": "/videos/?sort_by=most_commented",
            "Most Favourited": "/videos/?sort_by=most_favourited"
        }

    def get_headers(self):
        return {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
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
                return content.decode('utf-8', errors='ignore').replace('\n', '').replace('\r', '')
        except Exception:
            return None

    def process_content(self, url):
        if not url or url == "BOOTSTRAP":
            url = self.base_url + "/videos/"
            
            saved_sort_idx = int(self.addon.getSetting('punishbang_sort_by') or '0')
            if 0 <= saved_sort_idx < len(self.sort_options):
                sort_option = self.sort_options[saved_sort_idx]
                path = self.sort_paths.get(sort_option)
                if path:
                    url = self.base_url + path

        if url == 'https://www.punishbang.com/channels/':
            self.process_categories(url)
            return

        self.add_basic_dirs(url)
        content = self.make_request(url)
        
        if not content:
            self.notify_error("Failed to load content")
            self.end_directory()
            return

        pattern = re.compile(r'<a href="([^"]+)"[^>]*class="card[^"]*"[^>]*>.*?data-src="([^"]+)"[^>]*alt="([^"]+)"', re.DOTALL)
        matches = pattern.findall(content)
        
        if not matches:
            pattern = re.compile(r'<a href="([^"]+)".+?data-src="([^"]+)".+?alt="([^"]+)"', re.DOTALL)
            matches = pattern.findall(content)

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
        query_params['from'] = [str(next_from)]
        next_url = f"{base_url}?{urllib.parse.urlencode(query_params, doseq=True)}"
        self.add_dir('[COLOR blue]Next Page >>>>[/COLOR]', next_url, 2, self.icons['default'], self.fanart)

        self.end_directory()

    def add_basic_dirs(self, current_url):
        self.add_dir('[COLOR blue]Search[/COLOR]', '', 5, self.icons['search'], self.fanart)
        self.add_dir('Categories', 'https://www.punishbang.com/channels/', 8, self.icons['categories'], self.fanart)

    def process_categories(self, url):
        content = self.make_request(url)
        if not content:
            self.notify_error("Failed to load categories")
            self.end_directory()
            return

        pattern = re.compile(r'<a href="([^"]+)".+?data-src="([^"]+)".+?alt="([^"]+)"', re.DOTALL)
        matches = pattern.findall(content)
        
        for cat_url, thumb, name in matches:
            if not cat_url.startswith('http'):
                cat_url = self.base_url + cat_url
            if not thumb.startswith('http'):
                thumb = self.base_url + thumb
            self.add_dir(html.unescape(name), cat_url, 2, thumb, self.fanart)

        self.end_directory()

    def play_video(self, url):
        content = self.make_request(url)
        if not content:
            self.notify_error("Failed to load video page")
            return

        match = re.search(r"video_url:\s*'([^']+)'", content)
        if match:
            media_url = match.group(1).replace('amp;', '')
            li = xbmcgui.ListItem(path=media_url)
            xbmcplugin.setResolvedUrl(self.addon_handle, True, li)
        else:
            xbmc.log(f"[Punishbang] No video URL found for: {url}", xbmc.LOGERROR)
            self.notify_error("Failed to extract video URL")

    def select_sort(self, original_url=None):
        dialog = xbmcgui.Dialog()
        idx = dialog.select("Sort by...", self.sort_options)
        
        if idx != -1:
            sort_key = self.sort_options[idx]
            self.addon.setSetting('punishbang_sort_by', str(idx))
            path = self.sort_paths[sort_key]
            new_url = self.base_url + path
            xbmc.executebuiltin(f'Container.Update({sys.argv[0]}?mode=2&url={urllib.parse.quote_plus(new_url)}&website={self.name},replace)')