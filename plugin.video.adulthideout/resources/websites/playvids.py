# -*- coding: utf-8 -*-
import html
import re
import urllib.parse

import xbmcgui
import xbmcplugin

from resources.lib.base_website import BaseWebsite
from resources.lib.resilient_http import fetch_text

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36"


class PlayVids(BaseWebsite):
    label = "PlayVids"

    def __init__(self, addon_handle, addon=None):
        super().__init__(
            name="playvids",
            base_url="https://www.playvids.com",
            search_url="https://www.playvids.com/videos?qry={}",
            addon_handle=addon_handle,
            addon=addon,
        )

    def _get(self, url, referer=None):
        return fetch_text(url, headers={"User-Agent": UA, "Referer": referer or self.base_url + "/"},
                          logger=self.logger, timeout=20) or ""

    def _page_url(self, url, page):
        parts = urllib.parse.urlsplit(url)
        query = dict(urllib.parse.parse_qsl(parts.query))
        query["page"] = str(page)
        return urllib.parse.urlunsplit(parts._replace(query=urllib.parse.urlencode(query)))

    def process_content(self, url, page=1):
        if not url or url == "BOOTSTRAP":
            url = self.base_url + "/"
        page = int(page or 1)
        content = self._get(self._page_url(url, page) if page > 1 else url)
        if page == 1:
            self.add_dir("[COLOR blue]Search[/COLOR]", "", 5, self.icons["search"], self.fanart)
        seen = set()
        # <div class="card ... itemVideo"><a href="/<id>/<slug>"><img src="thumb" alt="title"> ... <span class="duration">
        for block in re.split(r'<div class="card\b[^"]*itemVideo', content)[1:]:
            link = re.search(r'<a href="(/[A-Za-z0-9_-]{9,13}/[a-z0-9-]+)"', block)
            image = re.search(r'<img[^>]+src="([^"]+)"[^>]*alt="([^"]*)"', block)
            if not link or not image or link.group(1) in seen:
                continue
            seen.add(link.group(1))
            duration = re.search(r'class="duration">([\d:]+)<', block)
            title = html.unescape(image.group(2)).strip()
            label = "{} [COLOR lime]({})[/COLOR]".format(title, duration.group(1)) if duration else title
            self.add_link(label, self.base_url + link.group(1), 4, image.group(1), self.fanart,
                          info_labels={"title": title, "duration": self.convert_duration(duration.group(1)) if duration else 0})
        if seen and re.search(r'[?&]page={}\b'.format(page + 1), content):
            self.add_dir("[COLOR blue]Next Page >>>>[/COLOR]", url, 2, self.icons["default"], self.fanart, page=page + 1)
        if not seen:
            self.notify_error("No PlayVids videos found")
        self.end_directory()

    def search(self, query):
        if query:
            self.process_content(self.search_url.format(urllib.parse.quote_plus(query)))

    def resolve_recording_stream(self, url):
        page = self._get(url)
        source = re.search(r'<video[^>]+id="player"[\s\S]*?<source[^>]+src="([^"]+)"', page)
        if not source:
            return None
        stream = html.unescape(source.group(1))
        return {"url": stream, "headers": {"User-Agent": UA, "Referer": url},
                "extension": "m3u8" if ".m3u8" in stream else "mp4"}

    def play_video(self, url):
        resolved = self.resolve_recording_stream(url)
        if not resolved:
            self.notify_error("No PlayVids stream found")
            return xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
        headers = urllib.parse.urlencode(resolved["headers"])
        item = xbmcgui.ListItem(path=resolved["url"] + "|" + headers)
        if resolved["extension"] == "m3u8":
            item.setMimeType("application/vnd.apple.mpegurl")
            item.setProperty("inputstream", "inputstream.adaptive")
            item.setProperty("inputstream.adaptive.manifest_type", "hls")
            item.setProperty("inputstream.adaptive.manifest_headers", headers)
            item.setProperty("inputstream.adaptive.stream_headers", headers)
        else:
            item.setMimeType("video/mp4")
        item.setContentLookup(False)
        item.setProperty("IsPlayable", "true")
        xbmcplugin.setResolvedUrl(self.addon_handle, True, item)
