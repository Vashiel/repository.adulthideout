#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Changelog:
# - Final Release
# - Integrated Cloudscraper for robust anti-bot protection bypass
# - Fixed sorting URLs and logic matches HTML source
# - Optimized Regex for content parsing (Image -> Title -> Duration)
# - Added hours support for duration parsing
# - Added robust fallback mechanisms for Thumbnails and Requests

import re
import sys
import os
import urllib.parse
import urllib.request
from http.cookiejar import CookieJar
from io import BytesIO
import gzip
import html
import xbmc
import xbmcgui
import xbmcplugin
from resources.lib.base_website import BaseWebsite

current_dir = os.path.dirname(os.path.abspath(__file__))
resources_dir = os.path.dirname(current_dir)
vendor_path = os.path.join(resources_dir, 'lib', 'vendor')

if vendor_path not in sys.path:
    sys.path.append(vendor_path)

try:
    import cloudscraper
    HAS_CLOUDSCRAPER = True
except ImportError:
    HAS_CLOUDSCRAPER = False
    xbmc.log(f"[Youjizz] Cloudscraper not found at {vendor_path}", xbmc.LOGWARNING)

class YoujizzWebsite(BaseWebsite):
    config = {
        "name": "youjizz",
        "base_url": "https://www.youjizz.com",
        "search_url": "https://www.youjizz.com/search/{}-1.html",
        "categories_url": "https://www.youjizz.com/sitemap"
    }

    def __init__(self, addon_handle):
        super().__init__(
            name=self.config["name"],
            base_url=self.config["base_url"],
            search_url=self.config["search_url"],
            addon_handle=addon_handle
        )
        
        if HAS_CLOUDSCRAPER:
            self.scraper = cloudscraper.create_scraper(
                browser={
                    'browser': 'chrome',
                    'platform': 'windows',
                    'mobile': False
                }
            )
        else:
            self.scraper = None
        
        self.sort_options = ['Most Popular', 'Newest', 'Top Rated (Month)', 'Trending']
        self.sort_paths = {
            'Most Popular': 'most-popular',
            'Newest': 'newest-clips',
            'Top Rated (Month)': 'top-rated-month',
            'Trending': 'trending'
        }

    def get_headers(self, referer=None):
        return {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate',
            'Referer': referer if referer else self.config['base_url'] + '/',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1'
        }

    def make_request(self, url):
        content = None
        
        if self.scraper:
            try:
                response = self.scraper.get(url, timeout=60)
                if response.status_code == 200:
                    content = response.text
                else:
                    xbmc.log(f"[Youjizz] Cloudscraper HTTP Error: {response.status_code}", xbmc.LOGWARNING)
            except Exception as e:
                xbmc.log(f"[Youjizz] Cloudscraper failed: {e}", xbmc.LOGWARNING)

        if not content:
            xbmc.log(f"[Youjizz] Fallback to urllib for {url}", xbmc.LOGINFO)
            headers = self.get_headers(url)
            cookie_jar = CookieJar()
            handler = urllib.request.HTTPCookieProcessor(cookie_jar)
            opener = urllib.request.build_opener(handler)
            
            try:
                request = urllib.request.Request(url, headers=headers)
                with opener.open(request, timeout=60) as response:
                    raw = response.read()
                    if response.info().get('Content-Encoding') == 'gzip':
                        content = gzip.GzipFile(fileobj=BytesIO(raw)).read().decode('utf-8', errors='ignore')
                    else:
                        content = raw.decode('utf-8', errors='ignore')
            except Exception as e:
                self.notify_error(f"Connection error: {e}")
                return None

        return content

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

    def select_sort(self, original_url=None):
        self._select_generic("youjizz_sort_by", self.sort_options, "Sort by...")

    def _build_filtered_url(self, page=1):
        sort = self.addon.getSetting("youjizz_sort_by") or self.sort_options[0]
        sort_path = self.sort_paths.get(sort, 'most-popular')
        return f"{self.config['base_url']}/{sort_path}/{int(page)}.html"

    def _format_thumb_url(self, url):
        if not url: 
            return self.icons['default']
        
        if url.startswith('//'): 
            url = 'https:' + url
        
        if not url.startswith('http'): 
            return self.icons['default']
        
        headers = self.get_headers()
        ua_str = urllib.parse.quote(headers['User-Agent'])
        return f"{url}|User-Agent={ua_str}"

    def process_content(self, url):
        parsed_url = urllib.parse.urlparse(url)
        path = parsed_url.path.strip('/')

        if path == 'sitemap':
            self.process_categories(url)
            return

        self.add_basic_dirs(url)
        
        if 'search' in path:
            request_url = url
        elif url == "BOOTSTRAP" or url == self.config["base_url"] or not path:
            request_url = self._build_filtered_url(page=1)
        else:
            if not url.endswith('.html') and not 'search' in url:
                 request_url = f"{url.rstrip('/')}/1.html"
            else:
                 request_url = url

        content = self.make_request(request_url)
        if not content:
            self.notify_error('Failed to fetch content')
            self.end_directory()
            return

        pattern = r'data-original=["\']([^"\']+)["\'].*?class=["\']video-title["\'][^>]*>\s*<a\s+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>.*?class=["\']time["\'][^>]*>.*?(\d+(?::\d+)+)'
        matches = re.findall(pattern, content, re.DOTALL)
        
        if not matches:
            pattern_alt = r'<a href=["\']([^"\']+)["\'][^>]*>([^<]+)</a>.+?(?:<span class="(?:time|duration)">.*?([0-9:]+)|)'
            matches_alt = re.findall(pattern_alt, content, re.DOTALL)
            if matches_alt:
                 matches = [('', m[0], m[1], m[2]) for m in matches_alt if len(m) == 3]

        if not matches:
            self.notify_info('No videos found.')
            self.end_directory()
            return

        for thumbnail, video_path, title, duration in matches:
            if "out.php" in video_path:
                continue
                
            full_url = urllib.parse.urljoin(self.config['base_url'], video_path)
            thumb_url = self._format_thumb_url(thumbnail)
            
            title = html.unescape(title.strip())
            duration = duration.strip() if duration else ""
            
            if duration:
                display_title = f'{title} [COLOR yellow][{duration}][/COLOR]'
            else:
                display_title = title

            context_menu = [
                ('Sort by...', f'RunPlugin({sys.argv[0]}?mode=7&action=select_sort&website={self.config["name"]})')
            ]

            self.add_link(display_title, full_url, 4, thumb_url, self.fanart, context_menu=context_menu)
        
        next_page_match = re.search(r'<a class="pagination-next" href="([^"]+)"', content)
        if next_page_match:
            next_url = urllib.parse.urljoin(self.config['base_url'], next_page_match.group(1))
            self.add_dir('[COLOR blue]Next Page >>>>[/COLOR]', next_url, 2, self.icons['default'], self.fanart)
            
        self.end_directory()

    def add_basic_dirs(self, current_url):
        dirs = [
            ('[COLOR blue]Search[/COLOR]', '', 5, self.icons['search'], self.fanart),
            ('Categories', self.config['categories_url'], 2, self.icons['categories'], self.fanart)
        ]
        for name, url, mode, icon, fanart in dirs:
            dir_name_param = name
            self.add_dir(name, url, mode, icon, fanart, dir_context_menu=[], name_param=dir_name_param)

    def process_categories(self, url):
        content = self.make_request(url)
        if not content:
            self.notify_error('Failed to load categories')
            self.end_directory()
            return
            
        pattern = r'<li><a href="(/categories/[^"]+)">([^<]+)</a></li>'
        matches = re.findall(pattern, content, re.DOTALL)
        
        if not matches:
            self.notify_info('No categories found')
            self.end_directory()
            return

        for cat_url, name in matches:
            full_url = urllib.parse.urljoin(self.config['base_url'], cat_url)
            self.add_dir(html.unescape(name), full_url, 2, self.icons['categories'], self.fanart)
            
        self.end_directory()

    def play_video(self, url):
        content = self.make_request(url)
        if not content:
            self.notify_error('Failed to load video page')
            return

        patterns = [
            r'["\']filename["\']\s*:\s*["\']([^"\']+\.mp4[^"\']*)["\']',
            r'<source[^>]+src=["\']([^"\']+\.mp4[^"\']*)["\']',
            r'data-video-url=["\']([^"\']+)["\']',
            r'videoSrc\s*=\s*["\']([^"\']+)["\']'
        ]
        
        stream_url = None
        for pat in patterns:
            match = re.search(pat, content)
            if match:
                stream_url = match.group(1)
                stream_url = stream_url.replace('\\/', '/')
                break
        
        if not stream_url:
            self.notify_error('No playable stream found')
            return

        if not stream_url.startswith('http'):
            if stream_url.startswith('//'):
                stream_url = 'https:' + stream_url
            else:
                stream_url = urllib.parse.urljoin(self.config['base_url'], stream_url)
        
        li = xbmcgui.ListItem(path=stream_url)
        li.setMimeType('video/mp4')
        li.setContentLookup(False)
        xbmcplugin.setResolvedUrl(self.addon_handle, True, li)

    def handle_search_entry(self, url, mode, name, action=None):
        if action == 'new_search':
            query = self.get_search_query()
            if query:
                search_url = self.config['search_url'].format(urllib.parse.quote(query))
                self.process_content(search_url)
        elif url:
            search_url = self.config['search_url'].format(urllib.parse.quote(url))
            self.process_content(search_url)
        else:
            query = self.get_search_query()
            if query:
                search_url = self.config['search_url'].format(urllib.parse.quote(query))
                self.process_content(search_url)