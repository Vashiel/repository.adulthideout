#!/usr/bin/env python
# -*- coding: utf-8 -*-

import html
import json
import os
import re
import sys
import urllib.parse

vendor_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "lib", "vendor")
if os.path.isdir(vendor_path) and vendor_path not in sys.path:
    sys.path.insert(0, vendor_path)

try:
    import cloudscraper
except Exception:
    cloudscraper = None
import requests
import xbmc
import xbmcgui
import xbmcplugin

from resources.lib.base_website import BaseWebsite
from resources.lib.playback_preferences import select_quality_variant
from resources.lib.proxy_utils import PlaybackGuard, ProxyController


class Iwara(BaseWebsite):
    sort_options = ["Latest", "Most Viewed", "Most Liked", "Trending"]
    sort_values = ("date", "views", "likes", "trending")
    categories = (
        ("HMV", "HMV"),
        ("MikuMikuDance", "MikuMikuDance"),
        ("Koikatsu", "Koikatsu"),
        ("Honey Select", "Honey Select"),
        ("SFM", "SFM"),
        ("Blender", "Blender"),
        ("VR", "VR"),
        ("Futanari", "Futanari"),
    )
    blocked_terms = (
        "loli",
        "lolicon",
        "shota",
        "shotacon",
        "underage",
        "minor",
    )

    def __init__(self, addon_handle, addon=None):
        super().__init__(
            name="iwara",
            base_url="https://www.iwara.tv/",
            search_url="https://api.iwara.tv/search?query={}&type=videos&page=0&limit=32&sort=date",
            addon_handle=addon_handle,
            addon=addon,
        )
        self.label = "Iwara"
        self.api_url = "https://api.iwara.tv/"
        self.ua = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/126.0.0.0 Safari/537.36"
        )
        self.session = self._build_session()

    def _build_session(self):
        if cloudscraper:
            try:
                return cloudscraper.create_scraper(browser={"custom": self.ua})
            except Exception as exc:
                self.logger.warning("Iwara cloudscraper init failed: %s", exc)
        return requests.Session()

    def _headers(self, referer=None, accept="application/json"):
        return {
            "User-Agent": self.ua,
            "Accept": accept,
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "identity",
            "Origin": "https://www.iwara.tv",
            "Referer": referer or self.base_url,
        }

    def _json(self, url, referer=None):
        for attempt in range(3):
            try:
                response = self.session.get(
                    url,
                    headers=self._headers(referer),
                    timeout=25,
                    allow_redirects=True,
                )
                if response.status_code == 200:
                    return response.json()
                self.logger.warning("Iwara HTTP %s for %s", response.status_code, url)
            except Exception as exc:
                self.logger.warning("Iwara request attempt %s failed: %s", attempt + 1, exc)
            self.session = self._build_session()
            if attempt < 2:
                xbmc.sleep(500 * (attempt + 1))
        return {}

    def _sort_index(self):
        try:
            index = int(self.addon.getSetting("iwara_sort_by") or "0")
        except Exception:
            index = 0
        return index if 0 <= index < len(self.sort_options) else 0

    def get_start_url_and_label(self):
        index = self._sort_index()
        return "IWARA_QUERY:*", "{} [COLOR yellow]{}[/COLOR]".format(self.label, self.sort_options[index])

    def _context_menu(self):
        return [
            (
                "Sort by...",
                "RunPlugin({}?mode=7&action=select_sort&website={})".format(sys.argv[0], self.name),
            )
        ]

    def _clean(self, value):
        value = re.sub(r"<[^>]+>", " ", value or "")
        return re.sub(r"\s+", " ", html.unescape(value)).strip()

    def _allowed(self, item):
        if not isinstance(item, dict):
            return False
        if item.get("rating") != "ecchi" or item.get("private") or item.get("status") != "active":
            return False
        if not isinstance(item.get("file"), dict) or item["file"].get("type") != "video":
            return False
        tags = " ".join(str(tag.get("id") or "") for tag in item.get("tags") or [] if isinstance(tag, dict))
        marker = "{} {} {}".format(item.get("title") or "", item.get("body") or "", tags).lower()
        return not any(term in marker for term in self.blocked_terms)

    def _thumb(self, item):
        file_data = item.get("file") or {}
        file_id = file_data.get("id")
        try:
            number = int(item.get("thumbnail") or 0)
        except (TypeError, ValueError):
            number = 0
        if not file_id:
            return self.icon
        image_url = "https://i.iwara.tv/image/thumbnail/{}/thumbnail-{:02d}.jpg".format(file_id, number)
        return "{}|{}".format(
            image_url,
            urllib.parse.urlencode({
                "User-Agent": self.ua,
                "Referer": self.base_url,
            }),
        )

    def _video_url(self, item):
        slug = urllib.parse.quote(str(item.get("slug") or "video").strip("/"))
        return urllib.parse.urljoin(self.base_url, "video/{}/{}".format(item.get("id"), slug))

    def _query_api_url(self, query, page):
        index = self._sort_index()
        params = {
            "query": query or "*",
            "type": "videos",
            "page": max(0, page - 1),
            "limit": 32,
            "sort": self.sort_values[index],
        }
        return urllib.parse.urljoin(self.api_url, "search?{}".format(urllib.parse.urlencode(params)))

    def _add_results(self, query, page, include_navigation):
        payload = self._json(self._query_api_url(query, page))
        raw_results = payload.get("results") if isinstance(payload, dict) else []
        raw_results = raw_results if isinstance(raw_results, list) else []
        context_menu = self._context_menu()
        added = 0
        for item in raw_results:
            if not self._allowed(item):
                continue
            title = self._clean(item.get("title") or "Iwara Video")
            file_data = item.get("file") or {}
            duration = int(file_data.get("duration") or 0)
            label = title
            if duration:
                minutes, seconds = divmod(duration, 60)
                hours, minutes = divmod(minutes, 60)
                duration_text = "{:d}:{:02d}:{:02d}".format(hours, minutes, seconds) if hours else "{:d}:{:02d}".format(minutes, seconds)
                label = "{} [COLOR lime]({})[/COLOR]".format(title, duration_text)
            info = {
                "title": title,
                "plot": self._clean(item.get("body") or title),
                "duration": duration,
            }
            self.add_link(
                label,
                self._video_url(item),
                4,
                self._thumb(item),
                self.fanart,
                context_menu=context_menu,
                info_labels=info,
            )
            added += 1
        if include_navigation and len(raw_results) >= 32:
            self.add_dir(
                "Next Page",
                "IWARA_QUERY:{}".format(query),
                2,
                self.icons.get("default", self.icon),
                context_menu=context_menu,
                page=page + 1,
            )
        return added

    def process_content(self, url, page=1):
        if not url or url == "BOOTSTRAP":
            url = "IWARA_QUERY:*"
        query = url.split(":", 1)[1] if url.startswith("IWARA_QUERY:") else "*"
        if page == 1 and query == "*":
            context_menu = self._context_menu()
            self.add_dir("Search", "", 5, self.icons.get("search", self.icon), context_menu=context_menu)
            self.add_dir("Categories", "IWARA_CATEGORIES", 8, self.icons.get("categories", self.icon), context_menu=context_menu)
        added = self._add_results(query, page, include_navigation=True)
        if not added:
            self.notify_error("No public adult Iwara videos found")
        self.end_directory("videos")

    def process_categories(self, url):
        for label, query in self.categories:
            self.add_dir(
                label,
                "IWARA_QUERY:{}".format(query),
                2,
                self.icons.get("categories", self.icon),
                self.fanart,
            )
        self.end_directory("videos")

    def search(self, query):
        if not query:
            return
        added = self._add_results(query.strip(), 1, include_navigation=True)
        if not added:
            self.notify_error("No public adult Iwara videos found")
        self.end_directory("videos")

    def _video_id(self, url):
        match = re.search(r"/video/([^/?#]+)", url or "", re.IGNORECASE)
        return match.group(1) if match else ""

    def resolve_recording_stream(self, url):
        video_id = self._video_id(url)
        if not video_id:
            return None
        detail = self._json(urllib.parse.urljoin(self.api_url, "video/{}".format(video_id)), referer=url)
        if not self._allowed(detail):
            return None
        file_url = detail.get("fileUrl")
        if not file_url:
            return None
        variants = self._json(file_url, referer=url)
        if not isinstance(variants, list):
            return None
        choices = []
        for variant in variants:
            if not isinstance(variant, dict):
                continue
            name = str(variant.get("name") or "")
            if name.lower() == "preview":
                continue
            source = variant.get("src") or {}
            stream_url = source.get("view") if isinstance(source, dict) else ""
            if stream_url and stream_url.startswith("//"):
                stream_url = "https:" + stream_url
            if not stream_url:
                continue
            quality_match = re.search(r"(\d{3,4})", name)
            quality = int(quality_match.group(1)) if quality_match else (10000 if name.lower() == "source" else 0)
            choices.append((quality, stream_url))
        stream_url = select_quality_variant(choices, addon=self.addon)
        if not stream_url:
            return None
        return {
            "url": stream_url,
            "headers": self._headers(url, accept="*/*"),
            "extension": "mp4",
        }

    def play_video(self, url):
        resolved = self.resolve_recording_stream(url)
        if not resolved:
            self.notify_error("Could not resolve a full public Iwara stream")
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
            return
        controller = ProxyController(
            resolved["url"],
            upstream_headers=resolved["headers"],
            session=self.session,
            skip_resolve=True,
            probe_size=True,
        )
        local_url = controller.start()
        item = xbmcgui.ListItem(path=local_url)
        item.setProperty("IsPlayable", "true")
        item.setMimeType("video/mp4")
        item.setContentLookup(False)
        xbmcplugin.setResolvedUrl(self.addon_handle, True, item)
        PlaybackGuard(xbmc.Player(), xbmc.Monitor(), local_url, controller).start()
