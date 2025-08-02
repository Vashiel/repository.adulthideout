#!/usr/bin/env python
# -*- coding: utf-8 -*-

import re
import urllib.parse
import urllib.request
import sys
import html
import xbmc
import xbmcaddon
import xbmcgui
import xbmcplugin
from resources.lib.base_website import BaseWebsite

class HypnotubeWebsite(BaseWebsite):
    config = {
        "name": "hypnotube",
        "base_url": "https://hypnotube.com",
        "search_url": "https://hypnotube.com/searchgate.php",
    }

    def __init__(self, addon_handle):
        super().__init__(
            name=self.config["name"],
            base_url=self.config["base_url"],
            search_url=self.config["search_url"],
            addon_handle=addon_handle
        )
        self.sort_options = ["Most Recent", "Most Viewed", "Top Rated", "Most Discussed", "Longest"]
        self.sort_paths = {
            "Most Recent": "/videos/",
            "Most Viewed": "/most-viewed/",
            "Top Rated": "/top-rated/",
            "Most Discussed": "/most-discussed/",
            "Longest": "/longest/"
        }
        self.cookie_jar = urllib.request.HTTPCookieProcessor()
        self.opener = urllib.request.build_opener(self.cookie_jar)

    def get_headers(self, url=None):
        return {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "de-DE,de;q=0.9",
            "Referer": url or self.config['base_url'] + "/"
        }

    def make_request(self, url, headers=None, post_data=None, referer=None, max_retries=3, retry_wait=5000):
        headers = self.get_headers(referer)
        
        encoded_post_data = None
        if post_data:
            encoded_post_data = urllib.parse.urlencode(post_data).encode('utf-8')

        for attempt in range(max_retries):
            try:
                request = urllib.request.Request(url, data=encoded_post_data, headers=headers, method='POST' if encoded_post_data else 'GET')
                with self.opener.open(request, timeout=60) as response:
                    return response.read().decode('utf-8', errors='ignore'), response.geturl()
            except Exception as e:
                self.logger.error(f"Error fetching {url} (attempt {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    xbmc.sleep(retry_wait)
        self.notify_error(f"Failed to fetch URL: {url}")
        return None, url

    def process_content(self, url):
        self.add_basic_dirs(url)
        content, final_url = self.make_request(url, referer=self.base_url)
        if content:
            self.process_matches(content, final_url)
            self.add_next_button(content, final_url)
        self.end_directory()

    def add_basic_dirs(self, current_url):
        context_menu = [('Sort by...', f'RunPlugin({sys.argv[0]}?mode=7&action=select_sort&website={self.name}&original_url={urllib.parse.quote_plus(current_url)})')]
        self.add_dir('[COLOR blue]Search[/COLOR]', '', 5, self.icons['search'], self.fanart, name_param=self.config['name'])
        self.add_dir('Categories', f"{self.config['base_url']}/channels/", 8, self.icons['categories'], self.fanart)

    def process_matches(self, content, current_url):
        main_content_match = re.search(r'<main class="main-col">.*?</main>', content, re.DOTALL)
        main_content = main_content_match.group(0) if main_content_match else content

        pattern = r'<div class="item-col col[^"]*"\s*>\s*<div class="item-inner-col inner-col">\s*<a href="([^"]+)" title="([^"]+)".*?<img.*?src="([^"]+)".*?<span class="time">([^<]+)</span>'
        matches = re.findall(pattern, main_content, re.DOTALL)
        if not matches:
             self.logger.error(f"PARSER: No video items found on {current_url}")
             return

        context_menu = [('Sort by...', f'RunPlugin({sys.argv[0]}?mode=7&action=select_sort&website={self.name}&original_url={urllib.parse.quote_plus(current_url)})')]
        for video_url, title, thumbnail, duration in matches:
            title_with_duration = f"{html.unescape(title)} [COLOR gray]({duration.strip()})[/COLOR]"
            full_url = urllib.parse.urljoin(self.config['base_url'], video_url)
            thumb_url = urllib.parse.urljoin(self.config['base_url'], thumbnail)
            self.add_link(title_with_duration, full_url, 4, thumb_url, self.fanart, context_menu=context_menu)

    def process_categories(self, url):
        self.add_basic_dirs(url)
        content, _ = self.make_request(url, referer=self.base_url)
        if not content: self.end_directory(); return
        
        main_content_match = re.search(r'<main class="main-col">.*?</main>', content, re.DOTALL)
        if not main_content_match: self.end_directory(); return
        main_content = main_content_match.group(0)
        
        pattern = r'<div class="item-col item--channel col">.*?<a href="([^"]+)" title="([^"]+)".*?<img src="([^"]+)"'
        matches = re.findall(pattern, main_content, re.DOTALL)
        for category_url, title, thumb in matches:
            full_url = urllib.parse.urljoin(self.config['base_url'], category_url)
            thumb_url = urllib.parse.urljoin(self.config['base_url'], thumb)
            self.add_dir(html.unescape(title), full_url, 2, thumb_url, self.fanart)
        self.end_directory()
            
    def add_next_button(self, content, current_url):
        next_page_match = re.search(r'<a rel=\'next\'[^>]+href=\'([^\']+)\'', content)
        if next_page_match:
            next_page_href = html.unescape(next_page_match.group(1))
            next_url = urllib.parse.urljoin(current_url, next_page_href)
            self.add_dir('[COLOR blue]Next Page >>>>[/COLOR]', next_url, 2, self.icons['default'], self.fanart)

    def play_video(self, url):
        content, _ = self.make_request(url, referer=self.base_url)
        if not content: return
        match = re.search(r'<video id=.+?src="([^"]+)"', content) or re.search(r'<source[^>]+src="([^"]+)"', content)
        if not match: return self.notify_error("Could not find valid stream URL")
        video_url = match.group(1).replace('amp;', '')
        li = xbmcgui.ListItem(path=video_url)
        li.setProperty("IsPlayable", "true")
        li.setMimeType("video/mp4")
        xbmcplugin.setResolvedUrl(self.addon_handle, True, li)

    def search(self, query):
        if not query: return
        post_data = {'q': query, 'type': 'videos'}
        content, final_url = self.make_request(self.config['search_url'], post_data=post_data, referer=self.base_url)
        
        self.add_basic_dirs(final_url)
        if content:
            self.process_matches(content, final_url)
            self.add_next_button(content, final_url)
        self.end_directory()

    def select_sort(self, original_url=None):
        if not original_url: return self.notify_error("Cannot sort, original URL not provided.")
        dialog = xbmcgui.Dialog()
        
        if '/search/' in original_url:
            choices = ["Most Relevant", "Newest", "Top Rated", "Most Viewed"]
            slug_map = {"Most Relevant": "", "Newest": "newest", "Top Rated": "rating", "Most Viewed": "views"}
            choice_map = {v: k for k, v in slug_map.items()}
            
            current_slug_match = re.search(r'/(newest|rating|views)/?$', original_url)
            current_slug = current_slug_match.group(1) if current_slug_match else ""
            preselect = choices.index(choice_map.get(current_slug, "Most Relevant"))

            idx = dialog.select("Sort Search Results by...", choices, preselect=preselect)
            if idx != -1:
                selected_slug = slug_map[choices[idx]]
                base_search_url = re.sub(r'/(newest|rating|views)/?$', '', original_url.rstrip('/'))
                new_url = f"{base_search_url}/{selected_slug}/" if selected_slug else f"{base_search_url}/"
                xbmc.executebuiltin(f'Container.Update({sys.argv[0]}?mode=2&url={urllib.parse.quote_plus(new_url)}&website={self.name},replace)')
        else:
            super().select_sort(original_url)