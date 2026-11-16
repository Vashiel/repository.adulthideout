#!/usr/bin/env python
# -*- coding: utf-8 -*-

import html
import os
import re
import urllib.parse
from concurrent.futures import ThreadPoolExecutor

import requests
import xbmc
import xbmcgui
import xbmcplugin

from resources.lib.base_website import BaseWebsite
from resources.lib.proxy_utils import PlaybackGuard, ProxyController


class Taxi69(BaseWebsite):
    def __init__(self, addon_handle, addon=None):
        super().__init__("taxi69", "https://taxi69.com/", "https://taxi69.com/search/{}", addon_handle, addon)
        self.session = requests.Session()
        self.ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131 Safari/537.36"
        self.icon = os.path.join(self.addon.getAddonInfo("path"), "resources", "logos", "taxi69.png")
        self.icons["default"] = self.icon

    def _headers(self, referer=None):
        return {"User-Agent": self.ua, "Referer": referer or self.base_url, "Accept-Encoding": "identity"}

    def _get(self, url, referer=None):
        try:
            response = self.session.get(url, headers=self._headers(referer), timeout=20)
            return response.text if response.status_code == 200 else ""
        except Exception as exc:
            self.logger.warning("Taxi69 request failed: %s", exc)
            return ""

    def get_start_url_and_label(self):
        return self.base_url, "Taxi69 [COLOR yellow]Latest[/COLOR]"

    def _items(self, content):
        items, seen = [], set()
        blocks = re.findall(r'<div\b[^>]*class=["\'][^"\']*videoBlock[^"\']*["\'][^>]*>([\s\S]*?)</div>', content or "", re.I)
        for block in blocks:
            link = re.search(r'<a\b[^>]*href=["\'](/video/[^"\']+)["\']', block, re.I)
            image = re.search(r'<img\b[^>]*>', block, re.I)
            if not link or not image:
                continue
            thumb_match = re.search(r'\ssrc=["\']([^"\']+)["\']', image.group(0), re.I)
            title_match = re.search(r'\salt=["\']([^"\']+)["\']', image.group(0), re.I)
            if not thumb_match:
                continue
            path = link.group(1)
            thumb = thumb_match.group(1)
            title = title_match.group(1) if title_match else path.rsplit("/", 1)[-1].replace("-", " ").title()
            url = urllib.parse.urljoin(self.base_url, path)
            if url not in seen:
                seen.add(url)
                items.append((html.unescape(title), url, html.unescape(thumb)))
        return items

    def _is_live(self, item):
        try:
            response = requests.head(item[1], headers=self._headers(), timeout=8, allow_redirects=True)
            return response.status_code == 200 and urllib.parse.urlparse(response.url).path.startswith("/video/")
        except Exception:
            return False

    def process_content(self, url, page=1):
        if not url or url == "BOOTSTRAP":
            url = self.base_url
        parsed = urllib.parse.urlparse(url)
        query = urllib.parse.parse_qs(parsed.query)
        current_page = max(1, int(query.get("page", [page])[0] or page or 1))
        query["page"] = [str(current_page)]
        target = urllib.parse.urlunparse((
            parsed.scheme,
            parsed.netloc,
            parsed.path or "/",
            parsed.params,
            urllib.parse.urlencode(query, doseq=True),
            parsed.fragment,
        ))
        content = self._get(target)
        if page == 1:
            self.add_dir("Search", "", 5, self.icons.get("search", self.icon))
        items = self._items(content)
        if items:
            with ThreadPoolExecutor(max_workers=8) as executor:
                items = [item for item, live in zip(items, executor.map(self._is_live, items)) if live]
        for title, item_url, thumb in items:
            self.add_link(title, item_url, 4, thumb, self.fanart, info_labels={"title": title, "plot": title})
        if len(items) >= 6:
            next_query = dict(query)
            next_query["page"] = [str(current_page + 1)]
            next_url = urllib.parse.urlunparse((
                parsed.scheme,
                parsed.netloc,
                parsed.path or "/",
                parsed.params,
                urllib.parse.urlencode(next_query, doseq=True),
                parsed.fragment,
            ))
            self.add_dir("Next Page", next_url, 2, self.icon)
        if not items:
            self.notify_error("No Taxi69 videos found")
        self.end_directory("videos")

    def search(self, query):
        if query:
            self.process_content(self.search_url.format(urllib.parse.quote_plus(query)))

    def resolve_recording_stream(self, url):
        content = self._get(url, self.base_url)
        match = re.search(r'https://videos\.rubias19\.com/[^"\'\\]+\.mp4', content or "", re.I)
        return {"url": html.unescape(match.group(0)), "headers": self._headers(url), "extension": "mp4"} if match else None

    def _pornhub_view_url(self, url):
        """Newer Taxi69 pages embed Pornhub's player instead of hosting the file themselves."""
        content = self._get(url, self.base_url)
        match = re.search(r'pornhub\.com/embed/([A-Za-z0-9]+)', content or "", re.I)
        return "https://www.pornhub.com/view_video.php?viewkey={}".format(match.group(1)) if match else None

    def play_video(self, url):
        resolved = self.resolve_recording_stream(url)
        if not resolved:
            view_url = self._pornhub_view_url(url)
            if view_url:
                from resources.websites.pornhub import PornhubWebsite
                return PornhubWebsite(self.addon_handle).play_video(view_url)
            self.notify_error("No Taxi69 stream found")
            return xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
        controller = ProxyController(resolved["url"], upstream_headers=resolved["headers"], session=self.session, skip_resolve=True, probe_size=True, use_urllib=True)
        local_url = controller.start()
        item = xbmcgui.ListItem(path=local_url)
        item.setProperty("IsPlayable", "true")
        item.setMimeType("video/mp4")
        item.setContentLookup(False)
        xbmcplugin.setResolvedUrl(self.addon_handle, True, item)
        PlaybackGuard(xbmc.Player(), xbmc.Monitor(), local_url, controller).start()
