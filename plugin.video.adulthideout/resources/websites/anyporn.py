#!/usr/bin/env python
# -*- coding: utf-8 -*-

import re
import urllib.parse
import html
import xbmcgui
import xbmcplugin
import requests
from resources.lib.base_website import BaseWebsite


class Anyporn(BaseWebsite):
    def __init__(self, addon_handle, addon=None):
        super().__init__(
            name="anyporn",
            base_url="https://anyporn.com",
            search_url="https://anyporn.com/search/{}/",
            addon_handle=addon_handle,
            addon=addon,
        )
        self.sort_options = ["Newest", "Most Viewed"]
        self.sort_paths = {
            "Newest": "/newest/",
            "Most Viewed": "/popular/",
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

        patterns = [
            r'<a class="item" href="(/categories/[a-z0-9-]+/)"\s*title="([^"]+)">',
            r'<a href="(/categories/[a-z0-9-]+/)" title="([^"]+)">\s*<h3>',
        ]
        seen = set()
        for pattern in patterns:
            for cat_url, name in re.findall(pattern, content, re.DOTALL):
                if cat_url in seen:
                    continue
                seen.add(cat_url)
                full_url = urllib.parse.urljoin(self.base_url, cat_url)
                label = html.unescape(name.strip())
                self.add_dir(label, full_url, 2, self.icons['categories'])

        self.end_directory(content_type='files')

    def _render_video_list(self, content):
        matches = re.findall(
            r'<a\s+[^>]*href=["\'](/(\d+)/)["\'][^>]*>\s*'
            r'<img\s+[^>]*data-original=["\']([^"\']+)["\'][^>]*alt=["\']([^"\']+)["\']',
            content,
            re.IGNORECASE
        )
        duration_pattern = r'durationid_(\d+)"><script>var element = document\.getElementById\("durationid_\d+"\);element\.innerHTML = "([^"]+)";'
        durations = dict(re.findall(duration_pattern, content))

        seen = set()
        for rel_url, vid_id, thumb, title in matches:
            if rel_url in seen:
                continue
            seen.add(rel_url)
            full_url = urllib.parse.urljoin(self.base_url, rel_url)
            display_title = html.unescape(title.strip())
            thumb_url = "https:" + thumb if thumb.startswith("//") else thumb
            dur_str = durations.get(vid_id, "").replace("m:", ":").replace("s", "")
            label = display_title
            if dur_str:
                label = f"{display_title} [COLOR lime]({dur_str})[/COLOR]"
            info = {"title": display_title, "mediatype": "video"}
            if dur_str:
                sec = self.convert_duration(dur_str)
                if sec: info["duration"] = sec
            self.add_link(label, full_url, 4, thumb_url, self.fanart, info_labels=info)

    def _add_next_button(self, content, current_url):
        match = re.search(r'href="(/[a-z-]+/\d+/)" data-action="ajax"[^>]*data-container-id="[^"]*pagination"', content)
        if match:
            next_url = urllib.parse.urljoin(self.base_url, html.unescape(match.group(1)))
            self.add_dir('[COLOR blue]Next Page >>[/COLOR]', next_url, 2, self.icons['default'])
            return
        page_match = re.search(r'/([a-z-]+)/(\d+)/?$', current_url)
        if page_match:
            base_path, page_num = page_match.groups()
            next_url = urllib.parse.urljoin(self.base_url, "/{}/{}/".format(base_path, int(page_num) + 1))
            self.add_dir('[COLOR blue]Next Page >>[/COLOR]', next_url, 2, self.icons['default'])

    def play_video(self, url):
        content = self.make_request(url)
        if not content:
            self.notify_error("Failed to load video page")
            return

        sources_match = re.search(r'const sources = \{(.*?)\};', content, re.DOTALL)
        if not sources_match:
            self.notify_error("Could not find video configuration.")
            return

        pairs = re.findall(r'(\d+)\s*:\s*\'([^\']+)\'', sources_match.group(1))
        if not pairs:
            self.notify_error("Could not find a playable video stream.")
            return

        pairs.sort(key=lambda p: int(p[0]), reverse=True)
        stream_url = None
        for quality, src in pairs:
            if int(quality) <= 720:
                stream_url = src
                break
        if not stream_url:
            stream_url = pairs[-1][1]

        stream_url = stream_url.replace("&amp;", "&")
        if stream_url.startswith("//"):
            stream_url = "https:" + stream_url

        # anyporn's CDN links are IP-locked to whichever client resolved them.
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
            skip_resolve=False,
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
