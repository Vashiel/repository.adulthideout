#!/usr/bin/env python
# -*- coding: utf-8 -*-

import html
import os
import re
import urllib.parse

import requests
import xbmcgui
import xbmcplugin

from resources.lib.base_website import BaseWebsite
from resources.lib.resolvers import resolver


class InternetChicks(BaseWebsite):
    sort_options = ["Latest", "Trending"]

    def __init__(self, addon_handle, addon=None):
        super().__init__("internetchicks", "https://internetchicks.com/", "https://internetchicks.com/?s={}", addon_handle, addon)
        self.ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131 Safari/537.36"
        self.session = requests.Session()
        self.icon = os.path.join(self.addon.getAddonInfo("path"), "resources", "logos", "internetchicks.png")
        self.icons["default"] = self.icon

    def get_start_url_and_label(self):
        try:
            index = int(self.addon.getSetting("internetchicks_sort_by") or "0")
        except Exception:
            index = 0
        index = index if 0 <= index < len(self.sort_options) else 0
        label = self.sort_options[index]
        return (self.base_url if index == 0 else urllib.parse.urljoin(self.base_url, "trending/"),
                "InternetChicks [COLOR yellow]{}[/COLOR]".format(label))

    def _headers(self, referer=None):
        return {"User-Agent": self.ua, "Referer": referer or self.base_url, "Accept-Language": "en-US,en;q=0.9"}

    def _get(self, url, referer=None):
        try:
            response = self.session.get(url, headers=self._headers(referer), timeout=(7, 20))
            return response.text if response.status_code == 200 else ""
        except Exception as exc:
            self.logger.warning("InternetChicks request failed: %s", exc)
            return ""

    @staticmethod
    def _clean(value):
        return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", value or ""))).strip()

    def _items(self, content):
        seen = set()
        for article in re.findall(r'<article\b[^>]*class=["\'][^"\']*\bpost\b[^"\']*["\'][^>]*>([\s\S]*?)</article>', content or "", re.I):
            link = re.search(r'<a\b[^>]*href=["\'](https?://internetchicks\.com/[^"\']+/)["\'][^>]*>([\s\S]*?)</a>', article, re.I)
            image_tag = re.search(r'<img\b[^>]*>', article, re.I)
            heading = re.search(r'<h[23]\b[^>]*>([\s\S]*?)</h[23]>', article, re.I)
            if not link or not image_tag or link.group(1) in seen:
                continue
            seen.add(link.group(1))
            title = self._clean(heading.group(1) if heading else "")
            thumb_match = re.search(r'\sdata-src=["\']([^"\']+)', image_tag.group(0), re.I)
            if not thumb_match:
                thumb_match = re.search(r'\ssrc=["\']([^"\']+)', image_tag.group(0), re.I)
            thumb = html.unescape(thumb_match.group(1)) if thumb_match else ""
            if title and not thumb.startswith("data:image/"):
                yield title, link.group(1), thumb

    def _listing_url(self, url, page):
        if page <= 1:
            return url
        parsed = urllib.parse.urlparse(url)
        if parsed.query:
            query = urllib.parse.parse_qs(parsed.query)
            query["paged"] = [str(page)]
            return urllib.parse.urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", urllib.parse.urlencode(query, doseq=True), ""))
        return urllib.parse.urljoin(url.rstrip("/") + "/", "page/{}/".format(page))

    def process_content(self, url, page=1):
        if not url or url == "BOOTSTRAP":
            url = self.base_url
        path = urllib.parse.urlparse(url).path.rstrip("/")
        if path in ("", "/trending") and page == 1:
            self.add_dir("Search", "", 5, self.icons.get("search", self.icon))
            self.add_dir("Categories", self.base_url, 8, self.icons.get("categories", self.icon))
            self.add_dir("Models", self.base_url, 8, self.icons.get("pornstars", self.icon))
        target = self._listing_url(url, page)
        content = self._get(target)
        items = list(self._items(content))
        for title, target_url, thumb in items:
            self.add_link(title, target_url, 4, thumb, self.fanart, info_labels={"title": title, "plot": title})
        if re.search(r'(?:page/{}/|[?&]paged={})'.format(page + 1, page + 1), content or "", re.I):
            self.add_dir("Next Page", url, 2, self.icon, page=page + 1)
        self.end_directory("videos")

    def process_categories(self, url):
        content = self._get(self.base_url)
        mode_models = "models" in (url or "").lower()
        marker = "actress" if mode_models else "category"
        seen = set()
        for target, label in re.findall(r'<a\b[^>]*href=["\'](https?://internetchicks\.com/{}/[^"\']+/)["\'][^>]*>([\s\S]*?)</a>'.format(marker), content or "", re.I):
            title = self._clean(label)
            if target not in seen and title:
                seen.add(target)
                self.add_dir(title, target, 2, self.icon)
        self.end_directory("videos")

    def process_pornstars(self, url):
        self.process_categories("models")

    def search(self, query):
        if query:
            self.process_content(self.search_url.format(urllib.parse.quote_plus(query)))

    def resolve_recording_stream(self, url):
        page = self._get(url, self.base_url)
        mirrors = re.findall(r"playEmbed\(['\"]([^'\"]+)", page or "", re.I)
        for mirror in mirrors:
            stream, headers = resolver.resolve(html.unescape(mirror), referer=url, headers=self._headers(url))
            if stream:
                return {"url": stream, "headers": headers or {}, "extension": "m3u8" if ".m3u8" in stream else "mp4"}
        return None

    def play_video(self, url):
        resolved = self.resolve_recording_stream(url)
        if not resolved:
            self.notify_error("Could not resolve InternetChicks stream")
            return xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
        encoded = urllib.parse.urlencode(resolved["headers"])
        item = xbmcgui.ListItem(path=resolved["url"] + ("|" + encoded if encoded else ""))
        item.setProperty("IsPlayable", "true")
        item.setContentLookup(False)
        xbmcplugin.setResolvedUrl(self.addon_handle, True, item)
