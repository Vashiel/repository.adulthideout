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
import sys
import os
from resources.lib.base_website import BaseWebsite

class XvideosWebsite(BaseWebsite):
    config = {
        "name": "xvideos",
        "base_url": "https://xvideos.com",
        "search_url": "https://xvideos.com/?k={}"
    }

    def __init__(self, addon_handle):
        super().__init__(
            name=self.config["name"],
            base_url=self.config["base_url"],
            search_url=self.config["search_url"],
            addon_handle=addon_handle
        )
        self.category_options = ["Straight", "Gay", "Shemale"]

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
                    return content
            except (urllib.error.HTTPError, urllib.error.URLError):
                if attempt < max_retries - 1:
                    xbmc.sleep(retry_wait)

        self.notify_error(f"Failed to fetch URL: {url}")
        return ""

    def select_category(self, original_url=None):
        idx = xbmcgui.Dialog().select("Select Category", self.category_options)
        if idx == -1:
            return
        category = self.category_options[idx]
        self.addon.setSetting(f"{self.config['name']}_category", category)
        new_url = self.get_category_url(category)
        xbmc.executebuiltin(
            f"Container.Update({sys.argv[0]}?mode=2&url={urllib.parse.quote_plus(new_url)}&website={self.config['name']},replace)"
        )

    def get_category_url(self, category):
        cat_value = category.lower() if category != "Straight" else ""
        return f"{self.config['base_url']}/{cat_value}" if cat_value else self.config["base_url"]

    def process_content(self, url):
        category = self.addon.getSetting(f"{self.config['name']}_category") or "Straight"
        cat_value = category.lower() if category != "Straight" else ""
        
        parsed_url = urllib.parse.urlparse(url)
        query_params = urllib.parse.parse_qs(parsed_url.query)

        if "filter_options" in url:
            self.addon.openSettings()
            category = self.addon.getSetting(f"{self.config['name']}_category") or "Straight"
            new_url = self.get_category_url(category)
            xbmc.executebuiltin(f"Container.Update({sys.argv[0]}?mode=2&url={urllib.parse.quote_plus(new_url)}&website={self.config['name']},replace)")
            return

        search_query = query_params.get('k', [None])[0]
        if search_query:
            search_url = url
        elif parsed_url.path in ["", "/"]:
            search_url = self.get_category_url(category)
        else:
            search_url = url

        content = self.make_request(search_url)
        if content:
            self.add_basic_dirs(search_url, cat_value)
            if "/tags" in url.lower():
                self.process_category_matches(content, search_url)
            else:
                self.process_content_matches(content, search_url, cat_value)
        else:
            self.notify_error("Failed to load content")

        self.end_directory()

    def add_basic_dirs(self, current_url, cat_value):
        context_menu = [
            ('Select Category', f'RunPlugin(plugin://plugin.video.adulthideout/?mode=7&action=select_category&website={self.config["name"]}&original_url={urllib.parse.quote_plus(current_url)})'),
        ]
        dirs = [
            ('[COLOR blue]Search[/COLOR]', '', 5, self.icons['search'], self.config["name"]),
            ('Categories', f"{self.config['base_url']}/tags", 2, self.icons['categories']),
        ]
        for name, url, mode, icon, *extra in dirs:
            dir_name_param = extra[0] if extra else name
            self.add_dir(name, url, mode, icon, self.fanart, context_menu, name_param=dir_name_param)

    def process_content_matches(self, content, current_url, cat_value):
        try:
            pattern = r'<div class="thumb"><a href="([^"]*)"><img[^>]*data-src="([^"]*)"[^>]*>.*?<p class="title"><a[^>]*title="([^"]*)".*?<span class="duration">([^<]*)</span>'
            matches = re.finditer(pattern, content, re.DOTALL)

            base_url = urllib.parse.urlparse(current_url).scheme + "://" + urllib.parse.urlparse(current_url).netloc
            context_menu = [
                ('Select Category', f'RunPlugin(plugin://plugin.video.adulthideout/?mode=7&action=select_category&website={self.config["name"]}&original_url={urllib.parse.quote_plus(current_url)})'),
            ]

            for match in matches:
                relative_url = match.group(1).replace('THUMBNUM/', '')
                thumb = match.group(2).replace('THUMBNUM', '1')
                name = html.unescape(match.group(3)).replace('`', "'")
                duration = match.group(4)
                url = urllib.parse.urljoin(base_url, relative_url)
                listname = f"{name} [COLOR lime]({duration})[/COLOR]"
                self.add_link(listname, url, 4, thumb, self.fanart, context_menu)

            next_page_url = None
            next_pattern = r'<li><a href="([^"]*)" class="no-page next-page">'
            next_match = re.search(next_pattern, content)
            if next_match:
                next_page_url = html.unescape(next_match.group(1))
                if not urllib.parse.urlparse(next_page_url).netloc:
                    next_page_url = urllib.parse.urljoin(base_url, next_page_url)
                if cat_value:
                    parsed_next_url = urllib.parse.urlparse(next_page_url)
                    next_query_params = urllib.parse.parse_qs(parsed_next_url.query)
                    if 'typef' not in next_query_params:
                        next_query_params['typef'] = [cat_value]
                        query_string = urllib.parse.urlencode(next_query_params, doseq=True)
                        next_page_url = f"{parsed_next_url.scheme}://{parsed_next_url.netloc}{parsed_next_url.path}?{query_string}"
            elif 'k=' in current_url:
                parsed_url = urllib.parse.urlparse(current_url)
                query_params = urllib.parse.parse_qs(parsed_url.query)
                current_page = int(query_params.get('p', [0])[0]) + 1 if 'p' in query_params else 1
                next_page = current_page + 1
                query_dict = {k: v[0] for k, v in query_params.items() if k != 'p'}
                if cat_value:
                    query_dict['typef'] = cat_value
                if next_page > 2:
                    query_dict['p'] = str(next_page - 1)
                query_string = urllib.parse.urlencode(query_dict)
                next_page_url = f"{parsed_url.scheme}://{parsed_url.netloc}{parsed_url.path}?{query_string}"

            if next_page_url:
                self.add_dir('[COLOR blue]Next Page >>>>[/COLOR]', next_page_url, 2, self.icons['default'], self.fanart, context_menu)

        except Exception as e:
            self.notify_error(f"Parsing failed: {str(e)}")

    def process_category_matches(self, content, current_url):
        try:
            pattern = r'<li class="dyn (top-cat|topterm)[^"]*"><a href="(/[^"]+)"(?:[^>]+)?>([^<]+)</a></li>'
            matches = re.finditer(pattern, content)

            base_url = urllib.parse.urlparse(current_url).scheme + "://" + urllib.parse.urlparse(current_url).netloc
            context_menu = [
                ('Select Category', f'RunPlugin(plugin://plugin.video.adulthideout/?mode=7&action=select_category&website={self.config["name"]}&original_url={urllib.parse.quote_plus(current_url)})'),
            ]

            for match in matches:
                relative_url = match.group(2)
                name = match.group(3).strip()
                url = urllib.parse.urljoin(base_url, relative_url)
                self.add_dir(name, url, 2, self.icons['categories'], self.fanart, context_menu)
        except Exception as e:
            self.notify_error(f"Parsing failed: {str(e)}")

    def play_video(self, url):
        content = self.make_request(url)
        if content:
            high_quality = re.search(r"html5player\.setVideoHLS\('(.+?)'\)", content)
            med_quality = re.search(r"html5player\.setVideoUrlHigh\('(.+?)'\)", content)
            low_quality = re.search(r"html5player\.setVideoUrlLow\('(.+?)'\)", content)
            
            path = None
            if high_quality:
                path = high_quality.group(1)
            elif med_quality:
                path = med_quality.group(1)
            elif low_quality:
                path = low_quality.group(1)
            
            if path:
                li = xbmcgui.ListItem(path=path)
                li.setProperty('IsPlayable', 'true')
                li.setMimeType('video/mp4')
                xbmcplugin.setResolvedUrl(self.addon_handle, True, li)
            else:
                self.notify_error("No video found")
        else:
            self.notify_error("Failed to load video page")

    def handle_search_entry(self, url, mode, name, action=None):
        category = self.addon.getSetting(f"{self.config['name']}_category") or "Straight"
        cat_value = category.lower() if category != "Straight" else ""
        
        query = None
        if action == 'new_search':
            query = self.get_search_query()
        elif action == 'history_search' and url:
            query = url
        elif url and not action:
             query = url
        else:
             query = self.get_search_query()
        
        if query:
            search_url = f"{self.config['search_url'].format(urllib.parse.quote_plus(query))}"
            if cat_value:
                search_url += f"&typef={cat_value}"
            self.search(query)
            xbmc.executebuiltin(f"Container.Update({sys.argv[0]}?mode=2&url={urllib.parse.quote_plus(search_url)}&website={self.config['name']},replace)")
        elif action == 'edit_search':
            self.edit_query()
        elif action == 'clear_history':
            self.clear_search_history()
        elif action == 'select_category':
            self.select_category(url)