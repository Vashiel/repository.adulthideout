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
from resources.lib.resilient_http import fetch_text
from resources.lib.resolvers import resolver


class MangoPorn(BaseWebsite):
    def __init__(self, addon_handle, addon=None):
        super().__init__("mangoporn", "https://mangoporn.net/", "https://mangoporn.net/?s={}", addon_handle, addon)
        self.label = "MangoPorn"
        self.session = requests.Session()
        self.ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
        self.sort_options = ["Latest", "Trending", "Ratings"]
        self.sort_paths = {"Latest": "/movies/", "Trending": "/trending/", "Ratings": "/ratings/"}

    def _headers(self, referer=None, accept="text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"):
        return {"User-Agent": self.ua, "Accept": accept, "Accept-Language": "en-US,en;q=0.9", "Accept-Encoding": "identity", "Referer": referer or self.base_url}

    def _get(self, url, referer=None):
        try:
            response = self.session.get(url, headers=self._headers(referer), timeout=25, allow_redirects=True)
            if response.status_code == 200:
                return response.text
            self.logger.warning("MangoPorn HTTP %s for %s", response.status_code, url)
        except Exception as exc:
            self.logger.warning("MangoPorn request failed for %s: %s", url, exc)
            self.session = requests.Session()
        return fetch_text(url, headers=self._headers(referer), logger=self.logger, timeout=25, use_windows_curl_fallback=True) or ""

    def _absolute(self, value, base=None):
        value = html.unescape(value or "").strip()
        if value.startswith("//"):
            value = "https:" + value
        return urllib.parse.urljoin(base or self.base_url, value)

    def _clean(self, value):
        return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", value or ""))).strip()

    def get_start_url_and_label(self):
        try:
            index = int(self.addon.getSetting("mangoporn_sort_by") or "0")
        except Exception:
            index = 0
        index = index if 0 <= index < len(self.sort_options) else 0
        key = self.sort_options[index]
        return self._absolute(self.sort_paths[key]), "{} [COLOR yellow]{}[/COLOR]".format(self.label, key)

    def _context_menu(self):
        return [("Sort by...", "RunPlugin({}?mode=7&action=select_sort&website={})".format(sys.argv[0], self.name))]

    def get_page_url(self, base_url, page_num):
        if page_num <= 1:
            return base_url
        parsed = urllib.parse.urlparse(base_url)
        path = re.sub(r"/page/\d+/?$", "/", parsed.path).rstrip("/") + "/page/{}/".format(page_num)
        return urllib.parse.urlunparse((parsed.scheme, parsed.netloc, path, parsed.params, parsed.query, parsed.fragment))

    def _items(self, content):
        items, seen = [], set()
        blocks = re.findall(r"<article\b[^>]*>([\s\S]*?)</article>", content or "", re.I)
        for block in blocks:
            link = re.search(r"href=[\"']([^\"']+/(?:movies|xxxclips)/[^\"']+/)[\"']", block, re.I)
            if not link:
                continue
            item_url = self._absolute(link.group(1))
            title_match = re.search(r"<h3\b[^>]*class=[\"'][^\"']*\btitle\b[^\"']*[\"'][^>]*>([\s\S]*?)</h3>", block, re.I)
            if not title_match:
                title_match = re.search(r"<img\b[^>]*(?:alt|title)=[\"']([^\"']+)[\"']", block, re.I)
            title = self._clean(title_match.group(1) if title_match else "")
            if not title or item_url in seen:
                continue
            image_match = re.search(r"<img\b[^>]*>", block, re.I)
            image_tag, thumb = image_match.group(0) if image_match else "", ""
            for attr in ("data-wpfc-original-src", "data-src", "data-original", "src"):
                found = re.search(r"\b{}=[\"']([^\"']+)[\"']".format(attr), image_tag, re.I)
                if found and found.group(1):
                    thumb = self._absolute(found.group(1), item_url)
                    break
            seen.add(item_url)
            items.append((title, item_url, thumb or self.icon, {"title": title, "plot": title}))
        return items

    def process_content(self, url, page=1):
        if not url or url == "BOOTSTRAP":
            url, _ = self.get_start_url_and_label()
        content = self._get(self.get_page_url(url, page))
        if not content:
            self.notify_error("Could not load MangoPorn")
            return self.end_directory("videos")

        # Remove featured slider to prevent duplicate videos without thumbnails
        slider_match = re.search(r'<div\b[^>]*(?:id=["\']slider-[^"\']*["\']|class=["\'][^"\']*\bslider\b[^"\']*["\'])[^>]*>', content, re.I)
        if slider_match:
            start_idx = slider_match.start()
            next_section = re.search(r'(?:<header class="archive_post"|<div id="archive-content"|<div class="content|<div class="items)', content[start_idx:], re.I)
            if next_section:
                end_idx = start_idx + next_section.start()
                content = content[:start_idx] + content[end_idx:]

        menu = self._context_menu()
        self.add_dir("Search", "", 5, self.icons.get("search", self.icon), context_menu=menu)
        if not urllib.parse.urlparse(url).query:
            self.add_dir("Categories", self.base_url, 8, self.icons.get("categories", self.icon), context_menu=menu)
            self.add_dir("XXX Movies", self.base_url + "movies/", 2, self.icons.get("videos", self.icon), context_menu=menu)
            self.add_dir("XXX Clips", self.base_url + "xxxclips/", 2, self.icons.get("videos", self.icon), context_menu=menu)
        items = self._items(content)
        if not items:
            self.notify_error("No MangoPorn videos found")
            return self.end_directory("videos")
        for title, item_url, thumb, info in items:
            self.add_link(title, item_url, 4, thumb, self.fanart, context_menu=menu, info_labels=info)
        if re.search(r'href=["\'][^"\']*/page/{}/?["\']'.format(page + 1), content, re.I):
            self.add_dir("Next Page", url, 2, self.icons.get("default", self.icon), context_menu=menu, page=page + 1)
        self.end_directory("videos")

    def process_categories(self, url):
        content = self._get(url or self.base_url)
        if not content:
            self.notify_error("Could not load MangoPorn categories")
            return self.end_directory("videos")
        self.add_dir("Search", "", 5, self.icons.get("search", self.icon))
        seen = set()
        pattern = r'<a\b[^>]+href=["\']([^"\']+/(?:adult/)?genres/[^"\']+/)["\'][^>]*>([\s\S]*?)</a>'
        for href, body in re.findall(pattern, content, re.I):
            category_url, title = self._absolute(href), self._clean(body)
            if title and category_url not in seen:
                seen.add(category_url)
                self.add_dir(title, category_url, 2, self.icons.get("categories", self.icon), self.fanart)
        self.end_directory("videos")

    def search(self, query):
        if query:
            self.process_content(self.search_url.format(urllib.parse.quote_plus(query.strip())))

    def _streams(self, content):
        streams = []
        for tag in re.findall(r"<source\b[^>]*>", content or "", re.I):
            match = re.search(r"\bsrc=[\"']([^\"']+\.mp4[^\"']*)[\"']", tag, re.I)
            if match:
                quality_match = re.search(r"(\d{3,4})p", tag + match.group(1), re.I)
                streams.append((int(quality_match.group(1)) if quality_match else 0, self._absolute(match.group(1))))
        if not streams:
            pattern = r"https?://[^\"'\\]+\.(?:bkcdn|bxcdn)\.net/[^\"'\\<\s]+\.mp4[^\"'\\<\s]*"
            streams = [(0, html.unescape(m.group(0))) for m in re.finditer(pattern, content or "", re.I)]
        result, seen = [], set()
        for _, stream in sorted(streams, key=lambda item: item[0], reverse=True):
            if stream not in seen:
                seen.add(stream)
                result.append(stream)
        return result

    def resolve_recording_stream(self, url):
        content = self._get(url, referer=self.base_url)
        streams = self._streams(content)
        if streams:
            return {"url": streams[0], "headers": self._headers(url, accept="*/*"), "extension": "mp4"}

        links, seen = [], set()
        host_pattern = r'href=["\'](https?://(?:[^/]*dood[^/]*|doply\.net|[^/]*mixdrop[^/]*)/[^"\']+)["\']'
        for match in re.finditer(host_pattern, content or "", re.I):
            host_url = html.unescape(match.group(1))
            if host_url not in seen:
                seen.add(host_url)
                links.append(host_url)
        for host_url in resolver.sort_urls_by_resolver_preference(links, self.addon):
            try:
                result = resolver.resolve(host_url, referer=url, headers={"User-Agent": self.ua, "Referer": url})
                if isinstance(result, tuple):
                    stream_url, headers = result
                else:
                    stream_url, headers = result, {}
                if stream_url and stream_url.startswith("http"):
                    if resolver.resolver_preflight_enabled(self.addon) and not resolver.probe_resolved_stream(stream_url, headers):
                        continue
                    return {"url": stream_url, "headers": headers or {}, "extension": "mp4"}
            except Exception as exc:
                self.logger.warning("MangoPorn resolver failed for %s: %s", host_url, exc)
        return None

    def play_video(self, url):
        resolved = self.resolve_recording_stream(url)
        if not resolved:
            self.notify_error("Could not resolve MangoPorn stream")
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
            return
        try:
            controller = ProxyController(resolved["url"], upstream_headers=resolved["headers"], use_urllib=True, probe_size=True)
            play_url = controller.start()
            PlaybackGuard(xbmc.Player(), xbmc.Monitor(), play_url, controller).start()
            item = xbmcgui.ListItem(path=play_url)
            item.setProperty("IsPlayable", "true")
            item.setMimeType("video/mp4")
            item.setContentLookup(False)
            xbmcplugin.setResolvedUrl(self.addon_handle, True, item)
        except Exception as exc:
            self.logger.error("MangoPorn playback failed: %s", exc)
            self.notify_error("MangoPorn playback failed")
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
