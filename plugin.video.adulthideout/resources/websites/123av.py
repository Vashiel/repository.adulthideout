# -*- coding: utf-8 -*-
import html
import json
import os
import re
import urllib.parse

import requests
import xbmc
import xbmcgui
import xbmcplugin

from resources.lib.base_website import BaseWebsite


class OneTwoThreeAV(BaseWebsite):
    sort_options = ["New", "Hot", "Recent"]
    sort_paths = {
        "New": "/en/new",
        "Hot": "/en/hot",
        "Recent": "/en/recent",
    }

    def __init__(self, addon_handle, addon=None):
        super().__init__(
            "123av",
            "https://123av.com/en/new",
            "https://123av.com/en/search?keyword={}",
            addon_handle,
            addon,
        )
        self.root = "https://123av.com"
        self.session = requests.Session()
        self.ua = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131 Safari/537.36"
        )
        self.icon = os.path.join(
            self.addon.getAddonInfo("path"), "resources", "logos", "123av.png"
        )
        self.icons["default"] = self.icon

    def _headers(self, referer=None):
        return {
            "User-Agent": self.ua,
            "Referer": referer or self.root + "/en",
            "Accept-Encoding": "identity",
        }

    def _get(self, url, referer=None):
        try:
            response = self.session.get(
                url, headers=self._headers(referer), timeout=(7, 20)
            )
            return response.text if response.status_code == 200 else ""
        except Exception as exc:
            self.logger.warning("123AV request failed: %s", exc)
            return ""

    @staticmethod
    def _clean(value):
        return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", value or ""))).strip()

    def _items(self, content):
        seen = set()
        for block in re.findall(
            r'<div\b[^>]*class=["\'][^"\']*\bcard\b[^"\']*["\'][^>]*>([\s\S]*?)(?=<div\b[^>]*class=["\'][^"\']*\bcard\b|</section>)',
            content or "",
            re.I,
        ):
            link = re.search(r'href=["\'](/en/v/[^"\']+)["\']', block, re.I)
            image = re.search(r'<img\b[^>]*class=["\'][^"\']*card__img[^"\']*["\'][^>]*src=["\']([^"\']+)', block, re.I)
            title = re.search(r'class=["\'][^"\']*card__link[^"\']*["\'][^>]*>([\s\S]*?)</a>', block, re.I)
            duration = re.search(r'class=["\'][^"\']*card__dur[^"\']*["\'][^>]*>([^<]+)', block, re.I)
            if not link or not image or link.group(1) in seen:
                continue
            seen.add(link.group(1))
            label = self._clean(title.group(1) if title else link.group(1).rsplit("/", 1)[-1])
            yield (
                label,
                urllib.parse.urljoin(self.root, link.group(1)),
                html.unescape(image.group(1)),
                self._clean(duration.group(1)) if duration else "",
            )

    def process_content(self, url, page=1):
        if not url or url == "BOOTSTRAP":
            url = self.base_url
        if self.is_primary_listing_url(url):
            self.add_dir("Search", "", 5, self.icons.get("search", self.icon))
            self.add_dir("Categories", self.root + "/en", 8, self.icons.get("categories", self.icon))
            self.add_dir("Actresses", self.root + "/en/actresses", 8, self.icons.get("pornstars", self.icon))
        content = self._get(url)
        count = 0
        for title, target, thumb, duration in self._items(content):
            info = {"title": title, "plot": title}
            seconds = self.convert_duration(duration)
            if seconds:
                info["duration"] = seconds
            self.add_link(title, target, 4, thumb, self.fanart, info_labels=info)
            count += 1
        next_match = re.search(
            r'<a\b[^>]*(?:rel=["\']next["\'][^>]*href|href)=["\']([^"\']*(?:\?|&)page=\d+[^"\']*)',
            content or "",
            re.I,
        )
        if next_match:
            self.add_dir("Next Page", urllib.parse.urljoin(url, html.unescape(next_match.group(1))), 2, self.icon)
        if not count:
            self.notify_info("No videos found")
        self.end_directory("videos")

    def process_categories(self, url):
        url = url or self.root + "/en"
        if urllib.parse.urlparse(url).path.rstrip("/") == "/en":
            for label, path in (
                ("Genres", "/en/genres"),
                ("Actresses", "/en/actresses"),
                ("Makers", "/en/makers"),
                ("Series", "/en/series"),
                ("Censored", "/en/censored"),
                ("Uncensored", "/en/uncensored"),
                ("Uncensored Leaked", "/en/uncensored-leaked"),
            ):
                self.add_dir(label, self.root + path, 8, self.icons.get("categories", self.icon))
            return self.end_directory("videos")
        content = self._get(url)
        path = urllib.parse.urlparse(url).path.rstrip("/")
        section = path.rsplit("/", 1)[-1]
        patterns = {
            "genres": r'href=["\'](/en/genres/[^"\']+)["\'][^>]*>([\s\S]*?)</a>',
            "actresses": r'href=["\'](/en/actresses/[^"\']+)["\'][^>]*>([\s\S]*?)</a>',
            "makers": r'href=["\'](/en/makers/[^"\']+)["\'][^>]*>([\s\S]*?)</a>',
            "series": r'href=["\'](/en/series/[^"\']+)["\'][^>]*>([\s\S]*?)</a>',
        }
        pattern = patterns.get(section)
        if not pattern:
            return self.process_content(url)
        seen = set()
        for target, raw_label in re.findall(pattern, content or "", re.I):
            if target in seen:
                continue
            seen.add(target)
            label = self._clean(raw_label)
            if label:
                self.add_dir(label, self.root + target, 2, self.icon)
        self.end_directory("videos")

    def search(self, query):
        if query:
            self.process_content(self.search_url.format(urllib.parse.quote_plus(query)))

    def resolve_recording_stream(self, url):
        page = self._get(url, self.root + "/en")
        embeds = re.findall(r'javplayer\.cc[\\/]+e[\\/]+([A-Za-z0-9_-]+)', page or "", re.I)
        for embed_id in embeds:
            try:
                response = self.session.get(
                    "https://javplayer.cc/stream?id=" + embed_id,
                    headers=self._headers(url),
                    timeout=(7, 20),
                )
                payload = response.json() if response.status_code == 200 else {}
                stream = payload.get("media", {}).get("stream")
                if stream and stream.startswith("http"):
                    return {"url": stream, "headers": self._headers("https://javplayer.cc/"), "extension": "m3u8"}
            except (ValueError, requests.RequestException):
                continue
        return None


    def play_video(self, url):
        resolved = self.resolve_recording_stream(url)
        if not resolved:
            self.notify_error("Could not resolve 123AV stream")
            return xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
        headers = urllib.parse.urlencode(resolved["headers"])
        item = xbmcgui.ListItem(path=resolved["url"] + "|" + headers)
        item.setProperty("IsPlayable", "true")
        item.setMimeType("application/vnd.apple.mpegurl")
        item.setContentLookup(False)
        if xbmc.getCondVisibility("System.HasAddon(inputstream.adaptive)"):
            item.setProperty("inputstream", "inputstream.adaptive")
            item.setProperty("inputstream.adaptive.manifest_type", "hls")
            item.setProperty("inputstream.adaptive.manifest_headers", headers)
            item.setProperty("inputstream.adaptive.stream_headers", headers)
        xbmcplugin.setResolvedUrl(self.addon_handle, True, item)
