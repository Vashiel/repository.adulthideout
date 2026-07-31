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


class Feet9(BaseWebsite):
    label = "Feet9"

    def __init__(self, addon_handle, addon=None):
        super().__init__(
            name="feet9",
            base_url="https://www.feet9.com/",
            search_url="https://www.feet9.com/search/video/{}/",
            addon_handle=addon_handle,
            addon=addon,
        )
        self.session = requests.Session()
        self.ua = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
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
            self.logger.warning("Feet9 HTTP %s for %s", response.status_code, url)
        except Exception as exc:
            self.logger.warning("Feet9 request failed for %s: %s", url, exc)
        return ""

    def _absolute(self, value):
        return urllib.parse.urljoin(self.base_url, html.unescape(value or "").strip())

    def _clean(self, value):
        value = re.sub(r"<[^>]+>", " ", value or "")
        return re.sub(r"\s+", " ", html.unescape(value)).strip()

    def get_start_url_and_label(self):
        return self._absolute("/recent/"), self.label

    def get_page_url(self, base_url, page_num):
        if page_num <= 1:
            return base_url
        parsed = urllib.parse.urlparse(base_url)
        path = re.sub(r"/\d+/?$", "/", parsed.path)
        path = path.rstrip("/") + "/{}/".format(page_num)
        return urllib.parse.urlunparse(
            (parsed.scheme, parsed.netloc, path, parsed.params, parsed.query, parsed.fragment)
        )

    def _extract_videos(self, page_html):
        items = []
        seen = set()
        for block in re.findall(
            r'<div\s+id=["\']video-\d+["\'][^>]*class=["\']video-inner["\'][^>]*>([\s\S]{0,5000}?)</div>\s*</div>',
            page_html or "",
            re.IGNORECASE,
        ):
            anchor = re.search(
                r'<a\b[^>]+href=["\'](/\d+/[^"\']+)["\'][^>]*title=["\']([^"\']+)["\']',
                block,
                re.IGNORECASE,
            )
            if not anchor:
                continue
            url = self._absolute(anchor.group(1))
            if url in seen:
                continue
            thumb_match = re.search(r'data-original=["\']([^"\']+)["\']', block, re.IGNORECASE)
            duration_match = re.search(r'class=["\']duration["\'][^>]*>([^<]+)', block, re.IGNORECASE)
            title = self._clean(anchor.group(2))
            duration = self._clean(duration_match.group(1) if duration_match else "")
            seconds = self.convert_duration(duration)
            info = {"title": title, "plot": title}
            if seconds:
                info["duration"] = seconds
            seen.add(url)
            items.append({
                "label": "{} [COLOR lime]({})[/COLOR]".format(title, duration) if duration else title,
                "url": url,
                "thumb": self._absolute(thumb_match.group(1)) if thumb_match else self.icon,
                "info": info,
            })
        return items

    def process_content(self, url, page=1):
        url = self._absolute("/recent/") if not url or url == "BOOTSTRAP" else url
        if self.is_primary_listing_url(url) or "/recent/" in urllib.parse.urlparse(url).path:
            self.add_dir("Search", "", 5, self.icons.get("search", self.icon))
            self.add_dir("Categories", self.base_url, 8, self.icons.get("categories", self.icon))
        target = self.get_page_url(url, page)
        page_html = self._get(target)
        items = self._extract_videos(page_html)
        if not items:
            self.notify_error("No Feet9 videos found")
            return self.end_directory("videos")
        for item in items:
            self.add_link(item["label"], item["url"], 4, item["thumb"], self.fanart, info_labels=item["info"])
        next_path = urllib.parse.urlparse(self.get_page_url(url, page + 1)).path
        if re.search(r'href=["\'](?:https?://[^/]+)?{}["\']'.format(re.escape(next_path)), page_html, re.IGNORECASE):
            self.add_dir("Next Page", url, 2, self.icons.get("default", self.icon), page=page + 1)
        self.end_directory("videos")

    def process_categories(self, url):
        page_html = self._get(self.base_url)
        seen = set()
        blocked = ("recent", "photo", "rss", "sitemap-html", "3d-anime-hentai")
        for href, title in re.findall(r'<a\b[^>]+href=["\'](/[^"\']+/)["\'][^>]*>([^<]{2,80})</a>', page_html, re.IGNORECASE):
            slug = href.strip("/").lower()
            title = self._clean(title)
            if not title or slug in blocked or href in seen or re.match(r"^\d+$", slug):
                continue
            if any(part in slug for part in ("feet", "foot", "shoe", "nylon", "stocking", "trample", "pedal")):
                seen.add(href)
                self.add_dir(title, self._absolute(href), 2, self.icons.get("categories", self.icon), self.fanart)
        self.end_directory("videos")

    def search(self, query):
        if query:
            slug = re.sub(r"[^a-z0-9]+", "-", query.lower()).strip("-")
            self.process_content(self.search_url.format(slug))

    def resolve_recording_stream(self, url):
        page_html = self._get(url, referer=self.base_url)
        match = re.search(r'https://[^"\'\s]+/media/videos/mp4/\d+\.mp4[^"\'\s<]*', page_html, re.IGNORECASE)
        if not match:
            return None
        return {"url": html.unescape(match.group(0)), "headers": self._headers(url, "*/*"), "extension": "mp4"}

    def play_video(self, url):
        resolved = self.resolve_recording_stream(url)
        if not resolved:
            self.notify_error("Could not resolve Feet9 stream")
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
            return
        controller = None
        play_url = resolved["url"]
        try:
            controller = ProxyController(
                upstream_url=play_url,
                upstream_headers=resolved["headers"],
                session=self.session,
                skip_resolve=True,
                probe_size=True,
                use_urllib=True,
            )
            play_url = controller.start()
        except Exception as exc:
            controller = None
            self.logger.warning("Feet9 Range proxy failed, using direct stream: %s", exc)
            play_url = "{}|{}".format(play_url, urllib.parse.urlencode(resolved["headers"]))
        item = xbmcgui.ListItem(path=play_url)
        item.setProperty("IsPlayable", "true")
        item.setMimeType("video/mp4")
        item.setContentLookup(False)
        xbmcplugin.setResolvedUrl(self.addon_handle, True, item)
        if controller:
            PlaybackGuard(xbmc.Player(), xbmc.Monitor(), play_url, controller).start()
