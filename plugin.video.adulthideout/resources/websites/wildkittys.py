# -*- coding: utf-8 -*-
import html
import json
import re
import urllib.parse

import xbmcgui
import xbmcplugin

from resources.lib.base_website import BaseWebsite
from resources.lib.resilient_http import fetch_text

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36"


class WildKittys(BaseWebsite):
    """ASMR / creator clips. Video pages carry a signed Bunny CDN HLS session in their Next.js data."""

    label = "WildKittys"

    def __init__(self, addon_handle, addon=None):
        super().__init__(
            name="wildkittys",
            base_url="https://wildkittys.com",
            search_url="https://wildkittys.com/search?q={}",
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
            self.add_dir("Categories", self.base_url + "/", 8, self.icons["categories"], self.fanart)
        seen = set()
        # Each card: <a href="/videos/<creator>/<slug>"><img src="thumb"><span class="dur">mm:ss</span> ... <div class="title">
        for block in re.split(r'<div class="card\b', content)[1:]:
            link = re.search(r'href="(/videos/[^"]+)"', block)
            title = re.search(r'<div class="title">([^<]+)</div>', block)
            if not link or not title or link.group(1) in seen:
                continue
            seen.add(link.group(1))
            thumb = re.search(r'<img[^>]+src="([^"]+)"', block)
            duration = re.search(r'class="dur">([\d:]+)<', block)
            name = html.unescape(title.group(1).strip())
            label = "{} [COLOR lime]({})[/COLOR]".format(name, duration.group(1)) if duration else name
            self.add_link(label, self.base_url + link.group(1), 4,
                          html.unescape(thumb.group(1)) if thumb else self.icon, self.fanart,
                          info_labels={"title": name, "duration": self.convert_duration(duration.group(1)) if duration else 0})
        if seen and re.search(r'[?&]page={}\b'.format(page + 1), content):
            self.add_dir("[COLOR blue]Next Page >>>>[/COLOR]", url, 2, self.icons["default"], self.fanart, page=page + 1)
        if not seen:
            self.notify_error("No WildKittys videos found")
        self.end_directory()

    def process_categories(self, url):
        content = self._get(self.base_url + "/")
        for slug, name in dict.fromkeys(re.findall(r'<a[^>]+href="/c/([a-z0-9-]+)"[^>]*>([^<]{2,40})<', content)):
            self.add_dir(html.unescape(name.strip()), "{}/c/{}".format(self.base_url, slug), 2, self.icons["categories"], self.fanart)
        self.end_directory("files")

    def search(self, query):
        if query:
            self.process_content(self.search_url.format(urllib.parse.quote_plus(query)))

    def resolve_recording_stream(self, url):
        page = self._get(url)
        # Next.js data is a JSON string inside the page, so quotes arrive as \" and & as &.
        session = re.search(r'\\"playbackSession\\":\{.*?\\"sources\\":(\[.*?\])', page)
        stream_url = None
        if session:
            try:
                sources = json.loads(session.group(1).replace('\\"', '"'))
                best = max(sources, key=lambda source: source.get("quality") or 0)
                stream_url = best.get("url")
            except (ValueError, TypeError):
                stream_url = None
        if not stream_url:
            hls = re.search(r'\\"hlsUrl\\":\\"(https://[^"\\]+(?:\\u0026[^"\\]+)*)', page)
            stream_url = hls.group(1).replace("\\u0026", "&") if hls else None
        if not stream_url:
            return None
        return {"url": stream_url.replace("\\u0026", "&").replace("&", "&"),
                "headers": {"User-Agent": UA, "Referer": self.base_url + "/", "Origin": self.base_url},
                "extension": "m3u8"}

    def play_video(self, url):
        resolved = self.resolve_recording_stream(url)
        if not resolved:
            self.notify_error("No WildKittys stream found")
            return xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
        headers = urllib.parse.urlencode(resolved["headers"])
        item = xbmcgui.ListItem(path=resolved["url"] + "|" + headers)
        item.setMimeType("application/vnd.apple.mpegurl")
        item.setContentLookup(False)
        item.setProperty("inputstream", "inputstream.adaptive")
        item.setProperty("inputstream.adaptive.manifest_type", "hls")
        item.setProperty("inputstream.adaptive.manifest_headers", headers)
        item.setProperty("inputstream.adaptive.stream_headers", headers)
        item.setProperty("IsPlayable", "true")
        xbmcplugin.setResolvedUrl(self.addon_handle, True, item)
