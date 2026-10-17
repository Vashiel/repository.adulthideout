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
from resources.lib.proxy_utils import HlsProxyController, PlaybackGuard, ProxyController
from resources.lib.resilient_http import fetch_text
from resources.lib.resolvers import resolver


class DaysNetworkWebsite(BaseWebsite):
    label = ""
    sort_options = ["Newest", "Popular"]
    sort_paths = {"Newest": "/newest", "Popular": "/popullar"}
    categories_path = "/tags"
    category_markers = ("/tag/",)
    direct_mp4 = False
    proxy_mp4 = True

    def __init__(self, name, base_url, addon_handle, addon=None):
        super().__init__(name, base_url, base_url + "search/?s={}", addon_handle, addon)
        self.session = requests.Session()
        self.ua = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/136.0.0.0 Safari/537.36"
        )

    def _headers(self, referer=None, accept="text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"):
        return {
            "User-Agent": self.ua,
            "Referer": referer or self.base_url,
            "Accept": accept,
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "identity",
        }

    def _get(self, url, referer=None):
        try:
            response = self.session.get(
                url,
                headers=self._headers(referer),
                timeout=25,
                allow_redirects=True,
            )
            if response.status_code == 200:
                return response.text
            self.logger.warning("%s HTTP %s for %s", self.label, response.status_code, url)
        except Exception as exc:
            self.logger.warning("%s request failed for %s: %s", self.label, url, exc)
            self.session = requests.Session()
        return fetch_text(
            url,
            headers=self._headers(referer),
            logger=self.logger,
            timeout=25,
            use_windows_curl_fallback=True,
        ) or ""

    def _absolute(self, value, base=None):
        value = html.unescape(value or "").strip()
        if value.startswith("//"):
            value = "https:" + value
        return urllib.parse.urljoin(base or self.base_url, value)

    @staticmethod
    def _clean(value):
        value = re.sub(r"<[^>]+>", " ", value or "")
        return re.sub(r"\s+", " ", html.unescape(value)).strip()

    def _context_menu(self):
        return [
            (
                "Sort by...",
                "RunPlugin({}?mode=7&action=select_sort&website={})".format(sys.argv[0], self.name),
            )
        ]

    def get_page_url(self, base_url, page_num):
        if page_num <= 1:
            return base_url
        parsed = urllib.parse.urlparse(base_url)
        path = re.sub(r"/page\d+/?$", "", parsed.path).rstrip("/")
        path += "/page{}/".format(page_num)
        return urllib.parse.urlunparse(
            (parsed.scheme, parsed.netloc, path, parsed.params, parsed.query, parsed.fragment)
        )

    def _items(self, content):
        items, seen = [], set()
        host = urllib.parse.urlparse(self.base_url).netloc.lower()
        pattern = r'<a\b[^>]+href=["\']([^"\']*video/[^"\']+)["\'][^>]*>([\s\S]{0,700}?)</a>'
        for href, body in re.findall(pattern, content or "", re.I):
            item_url = self._absolute(href)
            if urllib.parse.urlparse(item_url).netloc.lower() != host or item_url in seen:
                continue
            image = re.search(r"<img\b[^>]*>", body, re.I)
            if not image:
                continue
            image_tag = image.group(0)
            title_match = re.search(r'\b(?:alt|title)=["\']([^"\']+)["\']', image_tag, re.I)
            title = self._clean(title_match.group(1) if title_match else "")
            thumb_match = re.search(r'\b(?:data-src|src)=["\']([^"\']+)["\']', image_tag, re.I)
            if not title or not thumb_match:
                continue
            seen.add(item_url)
            thumb = self._absolute(thumb_match.group(1), item_url)
            items.append((title, item_url, thumb, {"title": title, "plot": title}))
        return items

    def process_content(self, url, page=1):
        if not url or url == "BOOTSTRAP":
            url, _ = self.get_start_url_and_label()
        target = self.get_page_url(url, page)
        content = self._get(target)
        if not content:
            self.notify_error("Could not load {}".format(self.label))
            return self.end_directory("videos")

        menu = self._context_menu()
        self.add_dir("Search", "", 5, self.icons.get("search", self.icon), context_menu=menu)
        if page == 1 and "/search/" not in target:
            self.add_dir(
                "Categories",
                self._absolute(self.categories_path),
                8,
                self.icons.get("categories", self.icon),
                context_menu=menu,
            )
        items = self._items(content)
        if not items:
            self.notify_error("No {} videos found".format(self.label))
            return self.end_directory("videos")
        for title, item_url, thumb, info in items:
            self.add_link(title, item_url, 4, thumb, self.fanart, context_menu=menu, info_labels=info)
        next_page = self.get_page_url(url, page + 1)
        next_path = urllib.parse.urlparse(next_page).path
        if re.search(r'href=["\'][^"\']*{}[^"\']*["\']'.format(re.escape(next_path)), content, re.I):
            self.add_dir(
                "Next Page",
                url,
                2,
                self.icons.get("default", self.icon),
                context_menu=menu,
                page=page + 1,
            )
        self.end_directory("videos")

    def process_categories(self, url):
        target = url or self._absolute(self.categories_path)
        content = self._get(target)
        if not content:
            self.notify_error("Could not load {} categories".format(self.label))
            return self.end_directory("videos")
        self.add_dir("Search", "", 5, self.icons.get("search", self.icon))
        seen = set()
        for href, body in re.findall(
            r'<a\b[^>]+href=["\']([^"\']+)["\'][^>]*>([\s\S]{0,250}?)</a>',
            content,
            re.I,
        ):
            category_url = self._absolute(href)
            path = urllib.parse.urlparse(category_url).path.lower()
            if not any(marker in path for marker in self.category_markers):
                continue
            title = self._clean(body)
            if not title or category_url in seen:
                continue
            seen.add(category_url)
            self.add_dir(title, category_url, 2, self.icons.get("categories", self.icon), self.fanart)
        self.end_directory("videos")

    def search(self, query):
        if query:
            self.process_content(self.search_url.format(urllib.parse.quote_plus(query.strip())))

    def _resolve_stream(self, url):
        content = self._get(url, referer=self.base_url)
        if not content:
            return None

        # 1. Check for direct m3u8 playlist directly in the page (e.g. amateur4days.com/hls/...)
        m3u8_matches = re.findall(r'https?://[^"\'<>\s]+\.m3u8[^"\'<>\s]*', content, re.I)
        for m3u8 in m3u8_matches:
            m3u8 = html.unescape(m3u8).replace("\\/", "/")
            if "preview" not in m3u8.lower():
                return m3u8, self._headers(url, accept="*/*"), "m3u8"

        # 2. Check for direct mp4 if configured or present
        if self.direct_mp4:
            streams = re.findall(r'https?://[^"\'<>\s]+\.mp4[^"\'<>\s]*', content, re.I)
            for stream in streams:
                stream = html.unescape(stream).replace("\\/", "/")
                if "preview" not in stream.lower():
                    return stream, self._headers(url, accept="*/*"), "mp4"

        # 3. Collect hoster links & iframes
        links, seen = [], set()
        host_pattern = r'https?://(?:[^"\'<>\s]*(?:streamtape|dood|playmogo|luluvido|doply|mixdrop|voe|turbovid)[^"\'<>\s]*)'
        for match in re.finditer(host_pattern, content, re.I):
            h_url = html.unescape(match.group(0)).replace("\\/", "/")
            if h_url not in seen:
                seen.add(h_url)
                links.append(h_url)

        # Also check all iframes
        for iframe_src in re.findall(r'<iframe\b[^>]+src=["\']([^"\']+)["\']', content, re.I):
            h_url = self._absolute(iframe_src, url)
            if h_url not in seen:
                seen.add(h_url)
                links.append(h_url)

        # 4. Try resolving through AdultHideout resolver stack
        if links:
            stream_url, headers, _ = resolver.resolve_first_working(
                links,
                referer=url,
                headers={"User-Agent": self.ua, "Referer": url},
                addon=self.addon,
            )
            if stream_url:
                kind = "m3u8" if ".m3u8" in stream_url.lower() else "mp4"
                return stream_url, headers, kind

        # 5. Fallback: inspect any embedded player page for m3u8/mp4
        embed_match = re.search(r'<iframe\b[^>]+src=["\']([^"\']+)["\']', content, re.I)
        if not embed_match:
            embed_match = re.search(
                r'["\'](https?://(?:www\.)?turbovidhls\.com/[^"\']+)["\']',
                content,
                re.I,
            )
        if embed_match:
            embed_url = self._absolute(embed_match.group(1), url)
            embed = self._get(embed_url, referer=url)
            streams = re.findall(r'https?://[^"\'<>\s]+\.m3u8[^"\'<>\s]*', embed or "", re.I)
            headers = self._headers(embed_url, accept="*/*")
            if streams:
                return html.unescape(streams[0]).replace("\\/", "/"), headers, "m3u8"
            streams = re.findall(r'https?://[^"\'<>\s]+\.mp4[^"\'<>\s]*', embed or "", re.I)
            if streams:
                return html.unescape(streams[0]).replace("\\/", "/"), headers, "mp4"
        return None

    def resolve_recording_stream(self, url):
        resolved = self._resolve_stream(url)
        if not resolved:
            return None
        stream, headers, kind = resolved
        return {"url": stream, "headers": headers, "extension": "mp4", "stream_type": kind}

    def play_video(self, url):
        resolved = self.resolve_recording_stream(url)
        if not resolved:
            self.notify_error("Could not resolve {} stream".format(self.label))
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
            return
        stream, headers = resolved["url"], resolved["headers"]
        if resolved.get("stream_type") == "m3u8":
            controller = HlsProxyController(stream, headers=headers, session=self.session)
            play_url = controller.start()
            PlaybackGuard(xbmc.Player(), xbmc.Monitor(), play_url, controller).start()
            item = xbmcgui.ListItem(path=play_url)
            item.setProperty("IsPlayable", "true")
            item.setMimeType("application/vnd.apple.mpegurl")
            item.setContentLookup(False)
            xbmcplugin.setResolvedUrl(self.addon_handle, True, item)
            return
        if not self.proxy_mp4:
            play_url = "{}|{}".format(stream, urllib.parse.urlencode(headers))
            item = xbmcgui.ListItem(path=play_url)
            item.setProperty("IsPlayable", "true")
            item.setMimeType("video/mp4")
            item.setContentLookup(False)
            xbmcplugin.setResolvedUrl(self.addon_handle, True, item)
            return
        try:
            controller = ProxyController(
                stream,
                upstream_headers=headers,
                session=self.session,
                use_urllib=True,
                probe_size=True,
            )
            play_url = controller.start()
            PlaybackGuard(xbmc.Player(), xbmc.Monitor(), play_url, controller).start()
            item = xbmcgui.ListItem(path=play_url)
            item.setProperty("IsPlayable", "true")
            item.setMimeType("video/mp4")
            item.setContentLookup(False)
            xbmcplugin.setResolvedUrl(self.addon_handle, True, item)
        except Exception as exc:
            self.logger.error("%s playback failed: %s", self.label, exc)
            self.notify_error("{} playback failed".format(self.label))
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
