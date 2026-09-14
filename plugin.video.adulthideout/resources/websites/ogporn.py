#!/usr/bin/env python
# -*- coding: utf-8 -*-

import html
import re
import sys
import urllib.parse

import requests
import xbmc
import xbmcgui
import xbmcplugin

from resources.lib.base_website import BaseWebsite
from resources.lib.proxy_utils import PlaybackGuard, ProxyController


class OGPorn(BaseWebsite):
    label = "OGPorn"
    # The site's current /anal/ taxonomy URL redirects to itself indefinitely.
    skip_directory_titles = {"anal"}

    def __init__(self, addon_handle, addon=None):
        super().__init__(
            name="ogporn",
            base_url="https://ogporn.com/",
            search_url="https://ogporn.com/?s={}",
            addon_handle=addon_handle,
            addon=addon,
        )
        self.session = requests.Session()
        self.ua = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/126.0.0.0 Safari/537.36"
        )

    def _headers(self, referer=None, accept="text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"):
        return {
            "User-Agent": self.ua,
            "Accept": accept,
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "identity",
            "Referer": referer or self.base_url,
        }

    def _get(self, url, referer=None):
        try:
            response = self.session.get(url, headers=self._headers(referer), timeout=25)
            if response.status_code == 200:
                return response.text
            self.logger.warning("OGPorn HTTP %s for %s", response.status_code, url)
        except Exception as exc:
            self.logger.warning("OGPorn request failed for %s: %s", url, exc)
        return ""

    def _absolute(self, value, base=None):
        return urllib.parse.urljoin(base or self.base_url, html.unescape(value or "").strip())

    @staticmethod
    def _clean(value):
        return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", value or ""))).strip()

    def _context_menu(self):
        return []

    def _page_url(self, url, page):
        if page <= 1:
            return url
        parsed = urllib.parse.urlsplit(url)
        query = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
        if any(key == "s" for key, _ in query):
            query = [(key, value) for key, value in query if key != "paged"]
            query.append(("paged", str(page)))
            return urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, parsed.path, urllib.parse.urlencode(query), ""))
        path = re.sub(r"/page/\d+/?$", "/", parsed.path).rstrip("/")
        return urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, path + "/page/{}/".format(page), parsed.query, ""))

    def _video_items(self, content):
        items, seen = [], set()
        # The front page contains navigation grids before the latest-video grid;
        # only links with a duration badge are actual scene entries.
        pattern = re.compile(
            r'<a\b[^>]*class=["\'][^"\']*\bvideo\b[^"\']*["\'][^>]*'
            r'(?:data-bg|style)=["\'][^"\']*["\']?[\s\S]{0,900}?</a>', re.I
        )
        for block_match in pattern.finditer(content or ""):
            block = block_match.group(0)
            if not re.search(r'class=["\'][^"\']*\btime\b', block, re.I):
                continue
            href = re.search(r'\bhref=["\']([^"\']+)["\']', block, re.I)
            title = re.search(r'\btitle=["\']([^"\']+)["\']', block, re.I)
            thumb = re.search(r'(?:data-bg\s*=\s*|background-image\s*:\s*url\()["\']?([^"\')]+)', block, re.I)
            duration = re.search(r'class=["\'][^"\']*\btime\b[^"\']*["\'][^>]*>([^<]+)', block, re.I)
            if not href or not title:
                continue
            video_url = self._absolute(href.group(1))
            if video_url in seen:
                continue
            seen.add(video_url)
            label = self._clean(title.group(1))
            runtime = self._clean(duration.group(1)) if duration else ""
            if runtime:
                label = "{} [COLOR lime]({})[/COLOR]".format(label, runtime)
            image = self._absolute(thumb.group(1)) if thumb else self.icon
            info = {"title": self._clean(title.group(1)), "plot": self._clean(title.group(1))}
            seconds = self.convert_duration(runtime)
            if seconds:
                info["duration"] = seconds
            items.append((label, video_url, image, info))
        return items

    def _add_navigation(self):
        self.add_dir("Search", "", 5, self.icons.get("search", self.icon))
        self.add_dir("Categories", self._absolute("/categories/"), 8, self.icons.get("categories", self.icon))
        self.add_dir("Models", self._absolute("/model/"), 8, self.icons.get("pornstars", self.icon))
        self.add_dir("Series", self._absolute("/series/"), 8, self.icons.get("groups", self.icon))

    def process_content(self, url, page=1):
        root = not url or url in ("BOOTSTRAP", self.base_url, self.base_url.rstrip("/"))
        url = self.base_url if root else url
        if root:
            self._add_navigation()
        target = self._page_url(url, page)
        content = self._get(target)
        if not content:
            self.notify_error("Could not load OGPorn")
            return self.end_directory("videos")
        items = self._video_items(content)
        if not items:
            self.notify_error("No OGPorn videos found")
            return self.end_directory("videos")
        for label, video_url, thumb, info in items:
            self.add_link(label, video_url, 4, thumb, self.fanart, info_labels=info)
        next_url = self._page_url(url, page + 1)
        next_path = urllib.parse.urlsplit(next_url).path
        if re.search(r'href=["\'][^"\']*{}["\']'.format(re.escape(next_path)), content, re.I):
            self.add_dir("Next Page", url, 2, self.icons.get("default", self.icon), page=page + 1)
        self.end_directory("videos")

    def process_categories(self, url):
        content = self._get(url or self._absolute("/categories/"))
        if not content:
            self.notify_error("Could not load OGPorn directory")
            return self.end_directory("videos")
        self.add_dir("Search", "", 5, self.icons.get("search", self.icon))
        seen = set()
        cards = re.findall(
            r'<article\b[^>]*class=["\'][^"\']*taxonomy-card[^"\']*["\'][^>]*>'
            r'([\s\S]*?)</article>', content, re.I
        )
        for card in cards:
            link = re.search(r'<a\b[^>]*href=["\']([^"\']+)["\']', card, re.I)
            heading = re.search(r'<h2\b[^>]*>([\s\S]*?)</h2>', card, re.I)
            if not link or not heading:
                continue
            href, title = link.group(1), heading.group(1)
            target = self._absolute(href)
            path = urllib.parse.urlsplit(target).path.rstrip("/")
            if path in ("", "/categories", "/model", "/series") or target in seen:
                continue
            clean_title = self._clean(title)
            if not clean_title:
                continue
            if clean_title.lower() in self.skip_directory_titles:
                continue
            seen.add(target)
            icon = self.icons.get("pornstars" if "/model/" in path else "categories", self.icon)
            self.add_dir(clean_title, target, 2, icon, self.fanart)
        self.end_directory("videos")

    def process_pornstars(self, url):
        self.process_categories(url or self._absolute("/model/"))

    def search(self, query):
        if query:
            self.process_content(self.search_url.format(urllib.parse.quote_plus(query.strip())))

    def resolve_recording_stream(self, url):
        content = self._get(url, referer=self.base_url)
        match = re.search(r'<source\b[^>]*\bsrc=["\']([^"\']+\.mp4[^"\']*)["\']', content, re.I)
        if not match:
            return None
        return {"url": html.unescape(match.group(1)), "headers": self._headers(url, accept="*/*"), "extension": "mp4"}

    def play_video(self, url):
        resolved = self.resolve_recording_stream(url)
        if not resolved:
            self.notify_error("Could not resolve OGPorn stream")
            return xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
        try:
            # This CDN keeps the MP4 index at the end. The local proxy preserves
            # the range requests while committing its headers promptly.
            controller = ProxyController(
                resolved["url"], upstream_headers=resolved["headers"],
                use_urllib=True, probe_size=True, fast_wait=1.5,
                emulate_ignored_ranges=True,
            )
            play_url = controller.start()
            PlaybackGuard(xbmc.Player(), xbmc.Monitor(), play_url, controller).start()
            item = xbmcgui.ListItem(path=play_url)
            item.setProperty("IsPlayable", "true")
            item.setMimeType("video/mp4")
            item.setContentLookup(False)
            xbmcplugin.setResolvedUrl(self.addon_handle, True, item)
        except Exception as exc:
            self.logger.error("OGPorn playback failed: %s", exc)
            self.notify_error("OGPorn playback failed")
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
