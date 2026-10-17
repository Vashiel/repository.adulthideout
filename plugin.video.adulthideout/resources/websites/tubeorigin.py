#!/usr/bin/env python
# -*- coding: utf-8 -*-

import html
import os
import re
import urllib.parse
import urllib.request

import requests
import xbmcgui
import xbmcplugin

from resources.lib.base_website import BaseWebsite
from resources.lib.proxy_utils import HlsProxyController, PlaybackGuard


class TubeOrigin(BaseWebsite):
    def __init__(self, addon_handle, addon=None):
        super().__init__("tubeorigin", "https://www.tubeorigin.com/", "https://www.tubeorigin.com/search?q={}", addon_handle, addon)
        self.session = requests.Session()
        self.ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131 Safari/537.36"
        self.icon = os.path.join(self.addon.getAddonInfo("path"), "resources", "logos", "tubeorigin.png")
        self.icons["default"] = self.icon

    def _headers(self, referer=None):
        return {"User-Agent": self.ua, "Referer": referer or self.base_url, "Accept-Encoding": "identity"}

    def _get(self, url, referer=None):
        try:
            response = self.session.get(url, headers=self._headers(referer), timeout=20)
            if response.status_code == 200:
                return response.text
            if response.status_code == 403:
                headers = self._headers(referer)
                headers["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36"
                with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=12) as result:
                    return result.read().decode("utf-8", "replace")
            return ""
        except Exception as exc:
            self.logger.warning("TubeOrigin request failed: %s", exc)
            return ""

    def get_start_url_and_label(self):
        return self.base_url, "TubeOrigin [COLOR yellow]Latest[/COLOR]"

    def _items(self, content):
        items, seen = [], set()
        for attrs, body in re.findall(r'<a\b([^>]*)>([\s\S]*?)</a>', content or "", re.I):
            link = re.search(r'\bhref=["\'](/@[^"\']+/video/[^"\']+)["\']', attrs, re.I)
            image = re.search(r'<img\b[^>]*>', body, re.I)
            if not link or not image:
                continue
            title = re.search(r'\balt=["\']([^"\']+)["\']', image.group(0), re.I)
            thumb = re.search(r'\bdata-src=["\'](https://b-cdn\.tubeorigin\.com/[^"\']+\.jpg)["\']', image.group(0), re.I)
            if not title or not thumb:
                continue
            target = urllib.parse.urljoin(self.base_url, html.unescape(link.group(1)))
            if target not in seen:
                seen.add(target)
                items.append((html.unescape(title.group(1)), target, html.unescape(thumb.group(1))))
        if items:
            return items
        # Cards now expose the title on the first link and the Kodi-friendly
        # JPEG in img[data-src]; img[src] is WebP for browsers.
        pattern = (
            r'<a\b[^>]+href=["\'](/@[^"\']+/video/[^"\']+)["\'][^>]*'
            r'\btitle=["\']([^"\']+)["\'][\s\S]{0,1800}?'
            r'<img\b[^>]*\bdata-src=["\'](https://b-cdn\.tubeorigin\.com/[^"\']+\.jpg)["\']'
        )
        for path, title, thumb in re.findall(pattern, content or "", re.I):
            item_url = urllib.parse.urljoin(self.base_url, html.unescape(path))
            if item_url not in seen:
                seen.add(item_url)
                items.append((html.unescape(title), item_url, html.unescape(thumb)))
        if not items:
            for path in re.findall(r'["\'](/@[^"\']+/video/[^"\']+)["\']', content or "", re.I):
                item_url = urllib.parse.urljoin(self.base_url, path)
                if item_url in seen:
                    continue
                seen.add(item_url)
                slug = path.rsplit("/", 1)[-1]
                items.append(("TubeOrigin " + slug, item_url, self.icon))
        return items

    def process_content(self, url, page=1):
        if not url or url == "BOOTSTRAP":
            url = self.base_url
        content = self._get(url)
        if page == 1:
            self.add_dir("Search", "", 5, self.icons.get("search", self.icon))
        items = self._items(content)
        for title, item_url, thumb in items:
            self.add_link(title, item_url, 4, thumb, self.fanart, info_labels={"title": title, "plot": title})
        continuations = re.findall(r'continuation=([A-Za-z0-9_-]+)', content or "")
        if continuations:
            parsed = urllib.parse.urlparse(url)
            query = urllib.parse.parse_qs(parsed.query)
            # The loaded page retains its incoming token in client state and
            # appends the next one afterwards.  The final token is the only
            # one that advances the list.
            query["continuation"] = [continuations[-1]]
            query["hl"] = ["en"]
            next_url = urllib.parse.urlunparse((
                parsed.scheme, parsed.netloc, parsed.path, parsed.params,
                urllib.parse.urlencode(query, doseq=True), parsed.fragment,
            ))
            self.add_dir("Next Page", next_url, 2, self.icons.get("default", self.icon))
        if not items:
            self.notify_error("No TubeOrigin videos found")
        self.end_directory("videos")

    def search(self, query):
        if query:
            self.process_content(self.search_url.format(urllib.parse.quote_plus(query)))

    def resolve_recording_stream(self, url):
        content = self._get(url, self.base_url)
        match = re.search(r'https://b-cdn\.tubeorigin\.com/[^"\'\\]+/playlist\.m3u8', content or "", re.I)
        if not match:
            return None
        return {"url": html.unescape(match.group(0)), "headers": self._headers(url), "extension": "ts"}

    def play_video(self, url):
        resolved = self.resolve_recording_stream(url)
        if not resolved:
            self.notify_error("No TubeOrigin stream found")
            return xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
        # An HLS manifest is not a byte-range media file.  Sending it through
        # the MP4 Range proxy makes Kodi repeatedly reload the master playlist
        # and eventually abort its demuxer.  The HLS proxy rewrites child URLs
        # while retaining the required TubeOrigin browser headers.
        controller = HlsProxyController(resolved["url"], headers=resolved["headers"], session=self.session)
        local_url = controller.start()
        item = xbmcgui.ListItem(path=local_url)
        item.setProperty("IsPlayable", "true")
        item.setMimeType("application/vnd.apple.mpegurl")
        item.setContentLookup(False)
        xbmcplugin.setResolvedUrl(self.addon_handle, True, item)
        PlaybackGuard(__import__("xbmc").Player(), __import__("xbmc").Monitor(), local_url, controller).start()
