#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Changelog:
# - Maintained urllib implementation for best Cloudflare bypass
# - Added select_sort for correct URL routing
# - Removed duplicate context menu entries
# - Cleaned up code and imports

import re
import urllib.parse
import urllib.request
from http.cookiejar import CookieJar
from io import BytesIO
import gzip
import html
import sys
import xbmc
import xbmcaddon
import xbmcgui
import xbmcplugin
from resources.lib.base_website import BaseWebsite

class LuxuretvWebsite(BaseWebsite):
    config = {
        "name": "luxuretv",
        "base_url": "https://en.luxuretv.com",
        "search_url": "https://en.luxuretv.com/searchgate.php?q={}&type=videos",
        "categories_url": "https://en.luxuretv.com/channels/"
    }

    def __init__(self, addon_handle):
        super().__init__(
            name=self.config["name"],
            base_url=self.config["base_url"],
            search_url=self.config["search_url"],
            addon_handle=addon_handle
        )
        self.sort_options = ["Newest", "Top rated", "Most viewed", "Longest", "Most discussed"]
        self.sort_paths = {
            "Newest": "/",
            "Top rated": "/top-rated/",
            "Most viewed": "/most-viewed/",
            "Longest": "/longest/",
            "Most discussed": "/most-discussed/"
        }

    def get_headers(self, url=None):
        return {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
            "Accept-Encoding": "gzip, deflate, br",
            "Accept-Language": "en-US,en;q=0.9",
            "Connection": "keep-alive",
            "Referer": "https://en.luxuretv.com/",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "same-origin",
            "Sec-Fetch-User": "?1"
        }

    def fetch_cookies(self, url):
        try:
            headers = self.get_headers()
            cookie_jar = CookieJar()
            handler = urllib.request.HTTPCookieProcessor(cookie_jar)
            opener = urllib.request.build_opener(handler)
            request = urllib.request.Request(url, headers=headers)
            with opener.open(request, timeout=30) as response:
                cookies = "; ".join([f"{cookie.name}={cookie.value}" for cookie in cookie_jar])
                return cookies
        except Exception as e:
            self.logger.error(f"Failed to fetch cookies from {url}: {e}")
            return ""

    def make_request(self, url, headers=None, post_data=None, max_retries=3, retry_wait=5000):
        headers = headers or self.get_headers(url)
        cookie_jar = CookieJar()
        handler = urllib.request.HTTPCookieProcessor(cookie_jar)
        opener = urllib.request.build_opener(handler)

        if "cookie" not in headers or not headers["cookie"]:
            headers["cookie"] = self.fetch_cookies(self.config["base_url"])

        if post_data:
            post_data = urllib.parse.urlencode(post_data).encode('utf-8')

        for attempt in range(max_retries):
            try:
                request = urllib.request.Request(url, data=post_data, headers=headers)
                with opener.open(request, timeout=60) as response:
                    encoding = response.info().get('Content-Encoding')
                    raw_data = response.read()
                    if encoding == 'gzip':
                        data = gzip.GzipFile(fileobj=BytesIO(raw_data)).read()
                    else:
                        data = raw_data
                    content = data.decode('utf-8', errors='ignore')
                    if cookie_jar:
                        headers["cookie"] = "; ".join([f"{cookie.name}={cookie.value}" for cookie in cookie_jar])
                    return content, response.geturl()
            except urllib.error.HTTPError as e:
                self.logger.error(f"HTTP Error {e.code} fetching {url} (attempt {attempt + 1}/{max_retries}): {e}")
                if e.code == 403 and attempt < max_retries - 1:
                    headers["cookie"] = self.fetch_cookies(self.config["base_url"])
                    xbmc.sleep(retry_wait)
            except Exception as e:
                self.logger.error(f"Error fetching {url} (attempt {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    xbmc.sleep(retry_wait)
        self.notify_error(f"Failed to fetch URL: {url}")
        return None, url

    def process_content(self, url):
        start_url, _ = self.get_start_url_and_label()
        if url == self.config["base_url"] or url == "BOOTSTRAP":
             url = start_url

        self.add_basic_dirs(url)
        
        content, final_url = self.make_request(url)
        if content:
            self.process_content_matches(content, final_url)
            self.add_next_button(content, final_url)
        
        self.end_directory()

    def add_basic_dirs(self, current_url):
        self.add_dir('[COLOR blue]Search[/COLOR]', '', 5, self.icons['search'], self.fanart, name_param=self.name)
        self.add_dir('Categories', self.config['categories_url'], 8, self.icons['categories'], self.fanart)

    def process_categories(self, url):
        self.add_basic_dirs(url)
        content, _ = self.make_request(url)
        if not content:
            self.end_directory()
            return
        
        pattern = r'<a href="([^"]*)">.+?src="([^"]*)" alt="([^"]*)"'
        matches = re.findall(pattern, content, re.DOTALL)

        for category_url, thumb, name in matches:
            if "/out/" in category_url or "javascript:;" in category_url:
                continue
            full_url = urllib.parse.urljoin(self.base_url, category_url)
            self.add_dir(html.unescape(name), full_url, 2, thumb, self.fanart)
        
        self.end_directory()

    def process_content_matches(self, content, current_url):
        item_blocks = re.findall(r'<div class="content">.*?<div class="views">.*?</div>\s*</div>', content, re.DOTALL)
        if not item_blocks:
            self.logger.error(f"PARSER: No video item blocks found on {current_url}")
            return

        for block in item_blocks:
            url_thumb_match = re.search(r'<a href="([^"]+)" title="[^"]*"><img[^>]+data-src="([^"]+)"', block, re.DOTALL)
            title_match = re.search(r'<div class="vtitle"><a[^>]+>([^<]+)</a></div>', block, re.DOTALL)
            duration_match = re.search(r'<div class="time"><b>([^<]+)</b></div>', block, re.DOTALL)
            
            if url_thumb_match and title_match and duration_match:
                video_url = url_thumb_match.group(1)
                thumb = url_thumb_match.group(2)
                title = title_match.group(1)
                duration = duration_match.group(1)

                full_url = urllib.parse.urljoin(self.base_url, video_url)
                title_with_duration = f"{html.unescape(title)} [COLOR gray]({duration})[/COLOR]"
                self.add_link(title_with_duration, full_url, 4, thumb, self.fanart)

    def add_next_button(self, content, current_url):
        next_page_match = re.search(r'<link rel="next" href="([^"]+)"', content)
        if not next_page_match:
            next_page_match = re.search(r"<a href='([^']+)'>Next &raquo;</a>", content)

        if next_page_match:
            next_url = urllib.parse.urljoin(current_url, html.unescape(next_page_match.group(1)))
            self.add_dir('[COLOR blue]Next Page >>>>[/COLOR]', next_url, 2, self.icons['default'], self.fanart)

    def play_video(self, url):
        content, _ = self.make_request(url)
        if not content: return
        
        match = re.search(r'source src="([^"]+)"', content)
        if not match:
            match = re.search(r'<video[^>]+src="([^"]+)"', content)
        if not match:
            match = re.search(r'["\']file["\']\s*:\s*["\']([^"]+\.(?:mp4|m3u8))', content, re.IGNORECASE)
        
        if not match:
            self.logger.error(f"No video source found for URL: {url}")
            self.notify_error("Could not find valid stream URL")
            return
            
        video_url = match.group(1).replace('amp;', '')
        li = xbmcgui.ListItem(path=video_url)
        li.setProperty("IsPlayable", "true")
        li.setMimeType("video/mp4" if video_url.endswith(".mp4") else "application/x-mpegURL")
        xbmcplugin.setResolvedUrl(self.addon_handle, True, li)

    def search(self, query):
        if not query: return
        post_data = {'q': query, 'type': 'videos'}
        content, final_url = self.make_request(
            self.config['search_url'], 
            post_data=post_data, 
            referer=self.config['base_url']
        )
        
        self.add_basic_dirs(final_url)
        if content:
            self.process_content_matches(content, final_url)
            self.add_next_button(content, final_url)
        self.end_directory()

    def select_sort(self, original_url=None):
        if not original_url: return self.notify_error("Cannot sort, original URL not provided.")
        
        if original_url.startswith('plugin://'):
            try:
                params = dict(urllib.parse.parse_qsl(urllib.parse.urlparse(original_url).query))
                if 'url' in params and params['url'] != 'BOOTSTRAP':
                    original_url = params['url']
                elif params.get('url') == 'BOOTSTRAP':
                    start_url, _ = self.get_start_url_and_label()
                    original_url = start_url
            except:
                pass

        dialog = xbmcgui.Dialog()
        preselect = -1
        
        # Try to match current URL to sort options
        for i, option in enumerate(self.sort_options):
            if self.sort_paths[option] in original_url:
                preselect = i
                break
        
        idx = dialog.select("Sort by...", self.sort_options, preselect=preselect)
        if idx != -1:
            sort_key = self.sort_options[idx]
            path = self.sort_paths[sort_key]
            new_url = urllib.parse.urljoin(self.config['base_url'], path)
            xbmc.executebuiltin(f'Container.Update({sys.argv[0]}?mode=2&url={urllib.parse.quote_plus(new_url)}&website={self.name},replace)')