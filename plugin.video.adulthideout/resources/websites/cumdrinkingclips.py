#!/usr/bin/env python
# -*- coding: utf-8 -*-

import html
import re
import urllib.parse

import requests
import xbmc
import xbmcgui
import xbmcplugin

from resources.lib.base_website import BaseWebsite
from resources.lib.proxy_utils import PlaybackGuard, ProxyController


class CumDrinkingClips(BaseWebsite):
    label = "CumDrinkingClips"
    sort_options = ["Newest", "Best", "Most Viewed", "Longest"]
    sort_paths = {
        "Newest": "/?filter=latest",
        "Best": "/?filter=popular",
        "Most Viewed": "/?filter=most-viewed",
        "Longest": "/?filter=longest",
    }

    def __init__(self, addon_handle, addon=None):
        super().__init__(
            name="cumdrinkingclips",
            base_url="https://cumdrinkingclips.com/",
            search_url="https://cumdrinkingclips.com/?s={}",
            addon_handle=addon_handle,
            addon=addon,
        )
        self.session = requests.Session()
        self.ua = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/127.0.0.0 Safari/537.36"
        )

    def _headers(self, referer=None, accept=None):
        return {
            "User-Agent": self.ua,
            "Referer": referer or self.base_url,
            "Accept": accept or "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "identity",
        }

    def _get(self, url, referer=None):
        try:
            response = self.session.get(url, headers=self._headers(referer), timeout=20)
            if response.status_code == 200:
                return response.text
            self.logger.warning("CumDrinkingClips HTTP %s for %s", response.status_code, url)
        except Exception as exc:
            self.logger.warning("CumDrinkingClips request failed for %s: %s", url, exc)
            self.session = requests.Session()
        return ""

    def _absolute(self, value, base=None):
        return urllib.parse.urljoin(base or self.base_url, html.unescape(value or "").strip())

    def _clean(self, value):
        return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", value or ""))).strip()

    def _sort_index(self):
        try:
            return max(0, min(int(self.addon.getSetting("cumdrinkingclips_sort_by") or "0"), len(self.sort_options) - 1))
        except (TypeError, ValueError):
            return 0

    def get_start_url_and_label(self):
        option = self.sort_options[self._sort_index()]
        return self._absolute(self.sort_paths[option]), "{} [COLOR yellow]{}[/COLOR]".format(self.label, option)

    def get_page_url(self, url, page):
        if page <= 1:
            return url
        parsed = urllib.parse.urlparse(url)
        path = re.sub(r"/page/\d+/?$", "/", parsed.path)
        path = path.rstrip("/") + "/page/{}/".format(page)
        return urllib.parse.urlunparse((parsed.scheme, parsed.netloc, path, parsed.params, parsed.query, parsed.fragment))

    def _extract_videos(self, content):
        items = []
        seen = set()
        for block in re.findall(
            r'<article\b[^>]*class=["\'][^"\']*\bvideo-preview-item\b[^"\']*["\'][^>]*>[\s\S]{0,2600}?</article>',
            content or "",
            re.IGNORECASE,
        ):
            link = re.search(r'<a\b[^>]+href=["\']([^"\']+)["\'][^>]+title=["\']([^"\']+)["\']', block, re.IGNORECASE)
            if not link:
                continue
            target = self._absolute(link.group(1))
            if target in seen:
                continue
            clean_title = self._clean(link.group(2))
            thumb = re.search(r'\bdata-main-thumb=["\']([^"\']+)["\']', block, re.IGNORECASE)
            if not thumb:
                thumb = re.search(r'<img\b[^>]+\bsrc=["\']([^"\']+)["\']', block, re.IGNORECASE)
            duration = re.search(r'class=["\'][^"\']*duration[^"\']*["\'][^>]*>[\s\S]*?(\d{1,2}:\d{2}(?::\d{2})?)', block, re.IGNORECASE)
            duration_text = duration.group(1) if duration else ""
            if not clean_title:
                continue
            seen.add(target)
            info = {"title": clean_title, "plot": clean_title}
            seconds = self.convert_duration(duration_text)
            if seconds:
                info["duration"] = seconds
            label = "{} [COLOR lime]({})[/COLOR]".format(clean_title, duration_text) if duration_text else clean_title
            items.append({
                "label": label,
                "url": target,
                "thumb": self._absolute(thumb.group(1)) if thumb else self.icon,
                "info": info,
            })
        return items

    def process_content(self, url, page=1):
        if not url or url == "BOOTSTRAP":
            url, _ = self.get_start_url_and_label()
        target = self.get_page_url(url, page)
        content = self._get(target)
        if self.is_primary_listing_url(url):
            self.add_dir("Search", "", 5, self.icons.get("search", self.icon))
            self.add_dir("Categories", self._absolute("/categories/"), 8, self.icons.get("categories", self.icon))
            self.add_dir("Models", self._absolute("/actors/"), 9, self.icons.get("pornstars", self.icon))
        items = self._extract_videos(content)
        for item in items:
            self.add_link(item["label"], item["url"], 4, item["thumb"], self.fanart, info_labels=item["info"])
        marker = "/page/{}/".format(page + 1)
        if items and marker in (content or ""):
            self.add_dir("Next Page", url, 2, self.icons.get("default", self.icon), page=page + 1)
        if not items:
            self.notify_error("No CumDrinkingClips videos found")
        self.end_directory("videos")

    def _directory(self, taxonomy, url, mode):
        try:
            page = max(1, int(urllib.parse.parse_qs(urllib.parse.urlparse(url or "").query).get("page", [1])[0]))
        except (TypeError, ValueError):
            page = 1
        endpoint = self._absolute(
            "wp-json/wp/v2/{}?{}".format(
                taxonomy,
                urllib.parse.urlencode({
                    "per_page": 100,
                    "page": page,
                    "hide_empty": "true",
                    "orderby": "count",
                    "order": "desc",
                }),
            )
        )
        try:
            response = self.session.get(endpoint, headers=self._headers(self.base_url, "application/json"), timeout=25)
            entries = response.json() if response.status_code == 200 else []
            total_pages = int(response.headers.get("X-WP-TotalPages") or 0)
        except Exception as exc:
            self.logger.warning("CumDrinkingClips %s directory failed: %s", taxonomy, exc)
            entries = []
            total_pages = 0
        icon = self.icons.get("pornstars" if mode == 9 else "categories", self.icon)
        for entry in entries:
            clean_title = self._clean(entry.get("name"))
            target = self._absolute(entry.get("link"))
            if clean_title and target and clean_title.lower() != "uncategorized":
                self.add_dir(clean_title, target, 2, icon)
        if page < total_pages:
            self.add_dir(
                "Next Page",
                "{}?page={}".format(taxonomy.upper(), page + 1),
                mode,
                self.icons.get("default", self.icon),
            )
        self.end_directory("videos")

    def process_categories(self, url):
        self._directory("categories", url, 8)

    def process_pornstars(self, url):
        self._directory("actors", url, 9)

    def search(self, query):
        if query:
            self.process_content(self.search_url.format(urllib.parse.quote_plus(query.strip())))

    def resolve_recording_stream(self, url):
        content = self._get(url, referer=self.base_url)
        candidates = []
        for value in re.findall(
            r'https?://cumdrinkingclips\.com/wp-content/uploads/[^"\'<>\s]+\.mp4',
            content or "",
            re.IGNORECASE,
        ):
            stream_url = html.unescape(value).replace("\\/", "/")
            if "preview" not in stream_url.lower() and stream_url not in candidates:
                candidates.append(stream_url)
        if not candidates:
            return None
        return {"url": candidates[0], "headers": self._headers(url, "*/*"), "extension": "mp4"}

    def play_video(self, url):
        resolved = self.resolve_recording_stream(url)
        if not resolved:
            self.notify_error("Could not resolve CumDrinkingClips stream")
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
            return
        controller = ProxyController(
            upstream_url=resolved["url"],
            upstream_headers=resolved["headers"],
            session=self.session,
            skip_resolve=True,
            probe_size=True,
            use_urllib=False,
        )
        proxy_url = controller.start()
        item = xbmcgui.ListItem(path=proxy_url)
        item.setProperty("IsPlayable", "true")
        item.setMimeType("video/mp4")
        item.setContentLookup(False)
        xbmcplugin.setResolvedUrl(self.addon_handle, True, item)
        PlaybackGuard(xbmc.Player(), xbmc.Monitor(), proxy_url, controller).start()
