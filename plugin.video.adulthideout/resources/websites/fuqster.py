#!/usr/bin/env python
# -*- coding: utf-8 -*-

import re
import urllib.parse
import html
import xbmc
import xbmcgui
import xbmcplugin
import requests
from resources.lib.base_website import BaseWebsite
from resources.lib.proxy_utils import ProxyController, PlaybackGuard


class Fuqster(BaseWebsite):
    def __init__(self, addon_handle, addon=None):
        super().__init__(
            name="fuqster",
            base_url="https://fuqster.com",
            search_url="https://fuqster.com/search/{}/",
            addon_handle=addon_handle,
            addon=addon,
        )
        self.sort_options = ["Latest", "Most Viewed", "Top Rated"]
        self.sort_paths = {
            "Latest": "/latest-updates/",
            "Most Viewed": "/most-popular/",
            "Top Rated": "/top-rated/",
        }
        self.categories_url = f"{self.base_url}/categories/"
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": self.base_url,
        })

    def make_request(self, url):
        try:
            response = self.session.get(url, timeout=20)
            response.raise_for_status()
            return response.text
        except Exception as e:
            self.logger.error(f"Request failed for {url}: {e}")
            self.notify_error("Failed to fetch URL")
            return None

    def search(self, query):
        if not query:
            return
        url = self.search_url.format(urllib.parse.quote(query))
        content = self.make_request(url)
        if not content:
            self.notify_error("Search failed")
            self.end_directory()
            return
        self._render_video_list(content)
        self._add_next_button(content, url)
        self.end_directory()

    def process_content(self, url):
        if not url or url == "BOOTSTRAP":
            url, _ = self.get_start_url_and_label()

        content = self.make_request(url)

        self.add_dir('[COLOR blue]Search[/COLOR]', '', 5, self.icons['search'])
        self.add_dir('[COLOR yellow]Categories[/COLOR]', self.categories_url, 8, self.icons['categories'])

        if content:
            self._render_video_list(content)
            self._add_next_button(content, url)

        self.end_directory()

    def process_categories(self, url):
        content = self.make_request(url)
        if not content:
            self.end_directory()
            return

        pattern = r'href="(https://fuqster\.com/categories/[a-z0-9-]+/)"\s+title="([^"]+)"'
        seen = set()
        for cat_url, name in re.findall(pattern, content):
            if cat_url in seen:
                continue
            seen.add(cat_url)
            label = html.unescape(name.strip())
            self.add_dir(label, cat_url, 2, self.icons['categories'])

        self.end_directory(content_type='files')

    def _render_video_list(self, content):
        pattern = (
            r'href="(https://fuqster\.com/video/\d+/[a-z0-9-]+/)"\s+title="([^"]+)"\s*>\s*'
            r'<div class="card-img">\s*<img[^>]*data-original="([^"]+)"'
        )
        seen = set()
        for video_url, title, thumb in re.findall(pattern, content):
            if video_url in seen:
                continue
            seen.add(video_url)
            display_title = html.unescape(title.strip())
            thumb = html.unescape(thumb)
            if thumb.startswith("//"):
                thumb = "https:" + thumb
            elif thumb.startswith("http://"):
                thumb = thumb.replace("http://", "https://")
            if thumb.endswith(".jpg"):
                thumb += "?fmt=webp"
            info = {"title": display_title, "mediatype": "video"}
            self.add_link(display_title, video_url, 4, thumb, self.fanart, info_labels=info)

    def _add_next_button(self, content, current_url):
        base = current_url.rstrip('/')
        page_num = re.search(r'/(\d+)$', base)
        if page_num:
            current_page = int(page_num.group(1))
            base = base[:page_num.start()]
        else:
            current_page = 1
        next_url = "{}/{}/".format(base.rstrip('/'), current_page + 1)
        # only add if the page looks full
        if content.count('class="card-img"') >= 20:
            self.add_dir('[COLOR blue]Next Page >>[/COLOR]', next_url, 2, self.icons['default'])

    def play_video(self, url):
        content = self.make_request(url)
        if not content:
            self.notify_error("Failed to load video page")
            return

        source_match = re.search(r'<source src="([^"]+\.mp4[^"]*)"', content)
        if not source_match:
            self.notify_error("Could not find a playable video stream.")
            return

        stream_url = html.unescape(source_match.group(1))
        if stream_url.startswith("//"):
            stream_url = "https:" + stream_url

        # fuqster CDN links are IP-locked to whichever client resolved them;
        # route playback through the local proxy so the same session both
        # resolves and fetches the stream.
        controller = ProxyController(
            stream_url,
            upstream_headers={
                'User-Agent': self.session.headers['User-Agent'],
                'Referer': self.base_url,
            },
            session=self.session,
            skip_resolve=True,
        )
        local_url = controller.start()

        guard = PlaybackGuard(xbmc.Player(), xbmc.Monitor(), local_url, controller)
        guard.start()

        li = xbmcgui.ListItem(path=local_url)
        li.setProperty('IsPlayable', 'true')
        li.setMimeType('video/mp4')
        li.setContentLookup(False)

        xbmcplugin.setResolvedUrl(self.addon_handle, True, li)
        guard.join()
