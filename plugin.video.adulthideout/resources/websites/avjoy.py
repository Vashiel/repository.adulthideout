#!/usr/bin/env python
# -*- coding: utf-8 -*-

import re
import urllib.parse
import urllib.request
import html
import xbmc
import xbmcgui
import xbmcplugin
import sys
from resources.lib.base_website import BaseWebsite

class AvjoyWebsite(BaseWebsite):
    def __init__(self, addon_handle, addon=None):
        super().__init__(
            name="avjoy",
            base_url="https://en.avjoy.me",
            search_url="https://en.avjoy.me/search/videos/{}",
            addon_handle=addon_handle,
            addon=addon
        )
        self.sort_options = ["Most Recent", "Most Viewed", "Top Rated", "Top Favorites", "Longest"]
        self.sort_paths = {
            "Most Recent": "/videos?o=mr",
            "Most Viewed": "/videos?o=mv",
            "Top Rated": "/videos?o=tr",
            "Top Favorites": "/videos?o=tf",
            "Longest": "/videos?o=lg"
        }

    def make_request(self, url):
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req) as response:
            return response.read().decode('utf-8')

    def process_content(self, url):
        self.add_basic_dirs(url)
        content = self.make_request(url)
        if content:
            self.parse_video_list(content, url)
            self.add_next_button(content, url)
        self.end_directory()

    def add_basic_dirs(self, current_url):
        context_menu = [('Sort by...', f'RunPlugin({sys.argv[0]}?mode=7&action=select_sort&website={self.name}&original_url={urllib.parse.quote_plus(current_url)})')]
        self.add_dir('[COLOR blue]Search[/COLOR]', '', 5, self.icons['search'], context_menu=context_menu)
        self.add_dir('Categories', f'{self.base_url}/categories', 8, self.icons['categories'], context_menu=context_menu)

    def parse_video_list(self, content, current_url):
        pattern = r'<div class="col-6 col-sm-6 col-md-4 col-lg-4 col-xl-3"> <a href="([^"]+)"> <div class="thumb-overlay".*?> <img src="([^"]+)" title="([^"]+)"'
        matches = re.findall(pattern, content, re.DOTALL)
        context_menu = [('Sort by...', f'RunPlugin({sys.argv[0]}?mode=7&action=select_sort&website={self.name}&original_url={urllib.parse.quote_plus(current_url)})')]

        for video_url, thumbnail, title in matches:
            full_url = urllib.parse.urljoin(self.base_url, video_url)
            self.add_link(html.unescape(title.strip()), full_url, 4, thumbnail, self.fanart, context_menu=context_menu)

    def add_next_button(self, content, current_url):
        match = re.search(r'<li class="page-item"><a class="page-link" href="([^"]+)" class="prevnext">', content)
        if match:
            next_url = urllib.parse.urljoin(self.base_url, html.unescape(match.group(1)))
            self.add_dir('[COLOR blue]Next Page >>>>[/COLOR]', next_url, 2, self.icons['default'], self.fanart)

    def play_video(self, url):
        content = self.make_request(url)
        if not content:
            self.notify_error("Failed to load video page")
            return

        match = re.search(r'<source src="([^"]+)" type=[\'"]video/mp4[\'"]', content)
        if match:
            video_url = match.group(1)
            video_url_with_referer = f"{video_url}|Referer={self.base_url}/"
            li = xbmcgui.ListItem(path=video_url_with_referer)
            li.setProperty("IsPlayable", "true")
            li.setMimeType("video/mp4")
            xbmcplugin.setResolvedUrl(self.addon_handle, True, li)
        else:
            self.notify_error("No playable stream found")

    def process_categories(self, url):
        content = self.make_request(f"{self.base_url}/categories")
        if content:
            pattern = r'<div class="col-6 col-sm-6 col-md-4 col-lg-4 col-xl-4 m-b-20"> <a href="([^"]+)"> <div class="thumb-overlay"> <img src="([^"]+)" title="([^"]+)"'
            matches = re.findall(pattern, content, re.DOTALL)
            context_menu = [('Sort by...', f'RunPlugin({sys.argv[0]}?mode=7&action=select_sort&website={self.name}&original_url={urllib.parse.quote_plus(url)})')]
            for cat_url, thumb, name in matches:
                full_cat_url = urllib.parse.urljoin(self.base_url, cat_url)
                full_thumb_url = urllib.parse.urljoin(self.base_url, thumb)
                self.add_dir(html.unescape(name.strip()), full_cat_url, 2, icon=full_thumb_url, fanart=self.fanart, context_menu=context_menu)
        self.end_directory()

    def select_sort(self, original_url=None):
        dialog = xbmcgui.Dialog()
        idx = dialog.select("Sort by...", self.sort_options)
        if idx > -1:
            sort_key = self.sort_options[idx]
            sort_path = self.sort_paths[sort_key]
            new_url = urllib.parse.urljoin(self.base_url, sort_path)
            xbmc.executebuiltin(f"Container.Update({sys.argv[0]}?mode=2&url={urllib.parse.quote_plus(new_url)}&website={self.name},replace)")