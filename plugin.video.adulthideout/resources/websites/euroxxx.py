#!/usr/bin/env python
# -*- coding: utf-8 -*-

import html
import os
import re
import urllib.parse

import requests
import xbmc
import xbmcgui
import xbmcplugin

from resources.lib.base_website import BaseWebsite
from resources.lib.resolvers import resolver
from resources.lib.thumb_proxy import build_thumb_url
from resources.lib.proxy_utils import PlaybackGuard, ProxyController


class EuroXXX(BaseWebsite):
    sort_options = ["Latest", "Most Viewed", "Top Rated"]
    sort_values = ["latest", "most-viewed", "top-rated"]

    def __init__(self, addon_handle, addon=None):
        super().__init__("euroxxx", "https://euroxxx.net/", "https://euroxxx.net/?s={}", addon_handle, addon)
        self.session = requests.Session()
        self.ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131 Safari/537.36"
        self.icon = os.path.join(self.addon.getAddonInfo("path"), "resources", "logos", "euroxxx.png")
        self.icons["default"] = self.icon

    def _headers(self, referer=None):
        return {"User-Agent": self.ua, "Referer": referer or self.base_url, "Accept-Encoding": "identity"}

    def _get(self, url, referer=None):
        try:
            response = self.session.get(url, headers=self._headers(referer), timeout=20)
            return response.text if response.status_code == 200 else ""
        except Exception as exc:
            self.logger.warning("EuroXXX request failed: %s", exc)
            return ""

    def get_start_url_and_label(self):
        try:
            index = int(self.addon.getSetting("euroxxx_sort_by") or "0")
        except Exception:
            index = 0
        index = index if 0 <= index < len(self.sort_options) else 0
        return self.base_url + "?filter=" + self.sort_values[index], "EuroXXX [COLOR yellow]{}[/COLOR]".format(self.sort_options[index])

    def _items(self, content):
        items, seen = [], set()
        for block in re.findall(r'<article\b[^>]*>([\s\S]*?)</article>', content or "", re.I):
            link = re.search(r'<a\b[^>]*href=["\'](https://euroxxx\.net/[^"\']+/)["\'][^>]*title=["\']([^"\']+)', block, re.I)
            image = re.search(r'<img\b[^>]*(?:data-src|src)=["\']([^"\']+)["\']', block, re.I)
            if not link or not image or link.group(1) in seen:
                continue
            seen.add(link.group(1))
            duration = re.search(r'class=["\'][^"\']*duration[^"\']*["\'][^>]*>[\s\S]*?(\d{1,2}:\d{2}(?::\d{2})?)', block, re.I)
            title = html.unescape(link.group(2))
            label = "{} [COLOR lime]({})[/COLOR]".format(title, duration.group(1)) if duration else title
            thumb = html.unescape(image.group(1))
            thumb = build_thumb_url(thumb, referer=self.base_url)
            items.append((label, title, link.group(1), thumb))
        return items

    def process_content(self, url, page=1):
        if not url or url == "BOOTSTRAP":
            url, _ = self.get_start_url_and_label()
        if page > 1:
            parsed = urllib.parse.urlparse(url)
            target = urllib.parse.urlunparse((parsed.scheme, parsed.netloc, "/page/{}/".format(page), "", parsed.query, ""))
        else:
            target = url
        content = self._get(target)
        if page == 1:
            self.add_dir("Search", "", 5, self.icons.get("search", self.icon))
        items = self._items(content)
        for label, title, item_url, thumb in items:
            self.add_link(label, item_url, 4, thumb, self.fanart, info_labels={"title": title, "plot": title})
        if len(items) >= 10:
            self.add_dir("Next Page", url, 2, self.icon, page=page + 1)
        if not items:
            self.notify_error("No EuroXXX videos found")
        self.end_directory("videos")

    def search(self, query):
        if query:
            self.process_content(self.search_url.format(urllib.parse.quote_plus(query)))

    def _host_links(self, url):
        content = self._get(url, self.base_url)
        return re.findall(r'<iframe[^>]+src=["\'](https?://(?:[^/]*playmogo[^/]*|[^/]*dood[^/]*)/[^"\']+)', content or "", re.I)

    def resolve_recording_stream(self, url):
        stream, headers, _ = resolver.resolve_first_working(self._host_links(url), referer=url, addon=self.addon)
        return {"url": stream, "headers": headers or {}, "extension": "mp4"} if stream else None

    def play_video(self, url):
        resolved = self.resolve_recording_stream(url)
        if not resolved:
            self.notify_error("No working EuroXXX mirror found")
            return xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
        controller = ProxyController(
            resolved["url"],
            upstream_headers=resolved["headers"],
            skip_resolve=True,
            probe_size=True,
            use_urllib=True,
        )
        local_url = controller.start()
        item = xbmcgui.ListItem(path=local_url)
        item.setProperty("IsPlayable", "true")
        item.setMimeType("video/mp4")
        item.setContentLookup(False)
        xbmcplugin.setResolvedUrl(self.addon_handle, True, item)
        PlaybackGuard(xbmc.Player(), xbmc.Monitor(), local_url, controller).start()
