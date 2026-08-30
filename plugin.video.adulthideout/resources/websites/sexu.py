#!/usr/bin/env python
# -*- coding: utf-8 -*-

import json
import re
import urllib.parse
import html
import xbmcgui
import xbmcplugin
import requests
from resources.lib.base_website import BaseWebsite


class Sexu(BaseWebsite):
    def __init__(self, addon_handle, addon=None):
        super().__init__(
            name="sexu",
            base_url="https://sexu.com",
            search_url="https://sexu.com/search?query={}",
            addon_handle=addon_handle,
            addon=addon,
        )
        self.sort_options = ["Trending", "Newest", "Most Viewed", "Top Rated"]
        self.sort_paths = {
            "Trending": "/trending",
            "Newest": "/newest",
            "Most Viewed": "/most-viewed",
            "Top Rated": "/top-rated",
        }
        self.categories_url = f"{self.base_url}/categories"
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
        try:
            response = self.session.post(
                f"{self.base_url}/search",
                data={"query": query},
                timeout=20,
            )
            response.raise_for_status()
            content = response.text
        except Exception as e:
            self.logger.error(f"Search request failed: {e}")
            self.notify_error("Search failed")
            self.end_directory()
            return
        self._render_video_list(content)
        self._add_next_button(content)
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

        pattern = r'<a class="item" href="(/tag/[a-z0-9-]+)"[^>]*title="([^"]+)"[^>]*data-id="\d+">.*?<div class="item__counter">(\d+)</div>'
        seen = set()
        for cat_url, name, count in re.findall(pattern, content, re.DOTALL):
            if cat_url in seen:
                continue
            seen.add(cat_url)
            full_url = urllib.parse.urljoin(self.base_url, cat_url)
            label = "{} ({})".format(html.unescape(name.strip()), count)
            self.add_dir(label, full_url, 2, self.icons['categories'])

        next_match = re.search(r'href="(/categories\?page=\d+)"[^>]*>\s*<span[^>]*>\s*(?:Next|&gt;)', content, re.IGNORECASE)
        if next_match:
            next_url = urllib.parse.urljoin(self.base_url, html.unescape(next_match.group(1)))
            self.add_dir('[COLOR blue]Next Page >>[/COLOR]', next_url, 8, self.icons['categories'])

        self.end_directory(content_type='files')

    def _render_video_list(self, content):
        pattern = (
            r'<div class="item thumb_item" data-id="(\d+)">\s*'
            r'<a class="item__main" href="(/\d+/)"[^>]*>.*?'
            r'<img[^>]+src="([^"]+\.webp)"[^>]+alt="([^"]+)".*?'
            r'<div class="item__counter">([\d:]+)</div>'
        )
        seen = set()
        for video_id, video_path, thumb, title, duration in re.findall(pattern, content, re.DOTALL):
            if video_id in seen:
                continue
            seen.add(video_id)
            video_url = urllib.parse.urljoin(self.base_url, video_path)
            display_title = html.unescape(title.strip())
            thumb_url = "https:" + thumb if thumb.startswith("//") else thumb
            label = "{} [COLOR lime]({})[/COLOR]".format(display_title, duration)
            info = {"title": display_title, "mediatype": "video"}
            seconds = self.convert_duration(duration)
            if seconds:
                info["duration"] = seconds
            self.add_link(label, video_url, 4, thumb_url, self.fanart, info_labels=info)

    def _add_next_button(self, content, current_url=None):
        match = re.search(r'href="(/[a-z-]+/(\d+)/)"[^>]*class="pagination__arrow pagination__arrow--next"', content)
        if not match and current_url:
            page_match = re.search(r'/([a-z-]+)/(\d+)/?$', current_url)
            if page_match:
                base_path, page_num = page_match.groups()
                next_url = urllib.parse.urljoin(self.base_url, "/{}/{}/".format(base_path, int(page_num) + 1))
                self.add_dir('[COLOR blue]Next Page >>[/COLOR]', next_url, 2, self.icons['default'])
                return
        if match:
            next_url = urllib.parse.urljoin(self.base_url, match.group(1))
            self.add_dir('[COLOR blue]Next Page >>[/COLOR]', next_url, 2, self.icons['default'])

    def play_video(self, url):
        # The video page (and its signed, short-lived stream tokens) can be
        # served from an edge cache; force a fresh render so the token is
        # still valid by the time playback actually starts.
        try:
            sep = '&' if '?' in url else '?'
            response = self.session.get(
                f"{url}{sep}_={int(__import__('time').time() * 1000)}",
                headers={'Cache-Control': 'no-cache', 'Pragma': 'no-cache'},
                timeout=20,
            )
            response.raise_for_status()
            content = response.text
        except Exception as e:
            self.logger.error(f"Request failed for {url}: {e}")
            content = None
        if not content:
            self.notify_error("Failed to load video page")
            return

        config_match = re.search(r'<script type="application/json" id="videojs-config-[^"]*">(\{.*?\})</script>', content, re.DOTALL)
        if not config_match:
            self.notify_error("Could not find video configuration.")
            return

        try:
            config = json.loads(config_match.group(1))
        except Exception as e:
            self.logger.error(f"Failed to parse player config: {e}")
            self.notify_error("Could not read video configuration.")
            return

        sources = config.get("sources") or []
        stream_url = None
        for quality in ("720p", "480p"):
            for src in sources:
                if src.get("quality") == quality and src.get("src"):
                    stream_url = src["src"]
                    break
            if stream_url:
                break
        if not stream_url and sources:
            stream_url = sources[-1].get("src")
        if not stream_url:
            content_url_match = re.search(
                r'["\']contentUrl["\']\s*:\s*["\'](https?://[^"\']+\.mp4[^"\']*)["\']',
                content,
                re.I,
            )
            if content_url_match:
                stream_url = content_url_match.group(1)

        if not stream_url:
            direct_v_match = re.search(r'(https?://v\.sexu\.com/key=[^\s"\'<>]+\.mp4)', content, re.I)
            if direct_v_match:
                stream_url = direct_v_match.group(1)

        if not stream_url:
            self.notify_error("Could not find a playable video stream.")
            return

        if stream_url.startswith("//"):
            stream_url = "https:" + stream_url
        stream_url = stream_url.replace("\\/", "/")

        is_hls = ".m3u8" in stream_url
        if is_hls:
            li = xbmcgui.ListItem(path=stream_url)
            li.setProperty('IsPlayable', 'true')
            li.setMimeType("application/vnd.apple.mpegurl")
            li.setProperty('inputstream', 'inputstream.adaptive')
            li.setProperty('inputstream.adaptive.manifest_type', 'hls')
            headers = f"User-Agent={urllib.parse.quote(self.session.headers['User-Agent'])}&Referer={urllib.parse.quote(self.base_url)}"
            li.setPath(f"{stream_url}|{headers}")
            xbmcplugin.setResolvedUrl(self.addon_handle, True, li)
            return

        # sexu's CDN links are IP-locked to whichever client resolved them.
        # Kodi's own player connects separately and may exit on a different
        # IP, causing a 403 - route playback through the local proxy so the
        # same session (this add-on's requests.Session) both resolves and
        # fetches the stream.
        import xbmc
        from resources.lib.proxy_utils import ProxyController, PlaybackGuard

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
