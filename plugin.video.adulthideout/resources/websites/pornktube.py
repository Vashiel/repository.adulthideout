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
from resources.lib.resilient_http import fetch_text


class Pornktube(BaseWebsite):
    # highest first; the no-suffix base file is the 720p variant, all others
    # use a "_{quality}" suffix. Each quality carries its own token/expiry.
    QUALITY_ORDER = ["1080p", "720p", "480p", "360p", "240p"]

    def __init__(self, addon_handle, addon=None):
        super().__init__(
            name="pornktube",
            base_url="https://www.pornktube.com",
            search_url="https://www.pornktube.com/s/?q={}",
            addon_handle=addon_handle,
            addon=addon,
        )
        self.sort_options = ["Latest", "Top Rated"]
        self.sort_paths = {
            "Latest": "/",
            "Top Rated": "/vrat/",
        }
        self.categories_url = f"{self.base_url}/pcat/"
        self.ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        # PornKTube is behind Cloudflare; cloudscraper solves the challenge.
        # A plain requests.Session is kept only for the (non-CF) vstor.top proxy.
        self._scraper = None
        try:
            import cloudscraper
            self._scraper = cloudscraper.create_scraper(
                browser={"browser": "chrome", "platform": "windows", "mobile": False}
            )
        except Exception:
            self._scraper = None
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": self.ua, "Referer": self.base_url})

    def _thumb(self, thumb):
        # i.pornktube.com is Cloudflare-protected (blocks Kodi's internal image
        # loader by TLS fingerprint, 403/error 1034), so route artwork through
        # the local cloudscraper-backed thumb proxy from the service.
        if not thumb or not thumb.startswith("http"):
            return thumb or self.icons['default']
        try:
            from resources.lib.thumb_proxy import build_thumb_url
            return build_thumb_url(thumb, referer=self.base_url + "/")
        except Exception:
            return thumb

    def make_request(self, url):
        headers = {
            "User-Agent": self.ua,
            "Referer": self.base_url + "/",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }
        content = fetch_text(
            url=url,
            headers=headers,
            scraper=self._scraper,
            logger=self.logger,
            timeout=20,
            use_windows_curl_fallback=True,
            prefer_ipv4=True,
        )
        if not content:
            self.notify_error("Failed to fetch URL")
        return content

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
            # the dedicated /pcat/ page occasionally 403s hotlinked requests;
            # the sidebar category list on the homepage is an equivalent source.
            content = self.make_request(self.base_url)
        if not content:
            self.end_directory()
            return

        pattern = r'<a href="(https://www\.pornktube\.com/c/\d+/)">\s*([^<]{2,40}?)\s*</a>'
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
            r'<a href="(https://www\.pornktube\.com/view/\d+/)"><img src="([^"]+\.jpg)"'
            r'[^>]*alt="([^"]*)"[\s\S]*?<div class="vlength">\s*([\d:]+)'
        )
        seen = set()
        for video_url, thumb, title, duration in re.findall(pattern, content):
            if video_url in seen:
                continue
            seen.add(video_url)
            display_title = html.unescape(title.strip()) or "Untitled"
            thumb = self._thumb(html.unescape(thumb))
            label = "{} [COLOR lime]({})[/COLOR]".format(display_title, duration)
            info = {"title": display_title, "mediatype": "video"}
            seconds = self.convert_duration(duration)
            if seconds:
                info["duration"] = seconds
            self.add_link(label, video_url, 4, thumb, self.fanart, info_labels=info)

    def _add_next_button(self, content, current_url):
        if content.count('pornkvideos') < 20:
            return
        parsed = urllib.parse.urlparse(current_url)
        path = parsed.path.rstrip('/')
        page_match = re.search(r'/(\d+)$', path)
        if page_match:
            current_page = int(page_match.group(1))
            path = path[:page_match.start()]
        else:
            current_page = 1
        new_path = "{}/{}/".format(path, current_page + 1) if path else "/{}/".format(current_page + 1)
        next_url = urllib.parse.urlunparse(parsed._replace(path=new_path))
        self.add_dir('[COLOR blue]Next Page >>[/COLOR]', next_url, 2, self.icons['default'])

    def _build_stream_url(self, content):
        player_match = re.search(r'<div id="player"([^>]*)>', content)
        if not player_match:
            return None
        attrs = player_match.group(1)

        def attr(name):
            m = re.search(name + r'="([^"]*)"', attrs)
            return m.group(1) if m else None

        video_id = attr('data-id')
        server = attr('data-n')
        data_q = attr('data-q')
        if not (video_id and server and data_q):
            return None

        # the HTML entity in each quality label (e.g. "FHD&nbsp;1080p") carries a
        # semicolon, so unescape before splitting the ';'-delimited fields.
        data_q = html.unescape(data_q)
        folder = 1000 * (int(video_id) // 1000)

        entries = {}
        for entry in data_q.split(','):
            fields = entry.split(';')
            if len(fields) >= 6:
                entries[fields[0]] = fields

        for quality in self.QUALITY_ORDER:
            fields = entries.get(quality)
            if not fields:
                continue
            expiry, token = fields[4], fields[5]
            suffix = "" if quality == "720p" else "_" + quality
            return "https://{}.vstor.top/whpvid/{}/{}/{}/{}/{}{}.mp4".format(
                server, expiry, token, folder, video_id, video_id, suffix
            )
        return None

    def play_video(self, url):
        content = self.make_request(url)
        if not content:
            self.notify_error("Failed to load video page")
            return

        stream_url = self._build_stream_url(content)
        if not stream_url:
            self.notify_error("Could not find a playable video stream.")
            return

        # vstor.top links are token/expiry (and IP) bound to whoever resolved
        # them; route playback through the local proxy so this add-on's session
        # both resolves and fetches the stream (same pattern as anyporn/sexvid).
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
