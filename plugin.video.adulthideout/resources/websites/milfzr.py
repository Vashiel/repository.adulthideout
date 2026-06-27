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


class Milfzr(BaseWebsite):
    def __init__(self, addon_handle, addon=None):
        super().__init__("milfzr", "https://milfzr.com/", "https://milfzr.com/?s={}", addon_handle, addon)
        self.label = "Milfzr"
        self.session = requests.Session()
        self.ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"

    def _headers(self, referer=None, accept="text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"):
        return {
            "User-Agent": self.ua,
            "Accept": accept,
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": referer or self.base_url
        }

    def _get(self, url, referer=None):
        try:
            response = self.session.get(url, headers=self._headers(referer), timeout=25, allow_redirects=True)
            if response.status_code == 200:
                return response.text
            self.logger.warning("Milfzr HTTP %s for %s", response.status_code, url)
        except Exception as exc:
            self.logger.warning("Milfzr request failed for %s: %s", url, exc)
            self.session = requests.Session()
        return fetch_text(url, headers=self._headers(referer), logger=self.logger, timeout=25, use_windows_curl_fallback=True) or ""

    def _absolute(self, value, base=None):
        value = html.unescape(value or "").strip()
        if value.startswith("//"):
            value = "https:" + value
        return urllib.parse.urljoin(base or self.base_url, value)

    def _clean(self, value):
        return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", value or ""))).strip()

    def get_page_url(self, base_url, page_num):
        if page_num <= 1:
            return base_url
        parsed = urllib.parse.urlparse(base_url)
        if parsed.query:
            # Query parameter paging, e.g. ?s=milf&paged=2
            query_dict = urllib.parse.parse_qs(parsed.query)
            query_dict['paged'] = [str(page_num)]
            new_query = urllib.parse.urlencode(query_dict, doseq=True)
            return urllib.parse.urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, new_query, parsed.fragment))
        else:
            # Path paging, e.g. /page/2/
            path = re.sub(r"/page/\d+/?$", "/", parsed.path).rstrip("/") + "/page/{}/".format(page_num)
            return urllib.parse.urlunparse((parsed.scheme, parsed.netloc, path, parsed.params, parsed.query, parsed.fragment))

    def _items(self, content):
        items, seen = [], set()
        blocks = re.findall(r'<div id="post-\d+" class="item\b[^>]*>([\s\S]*?)</div>\s*</div>', content or "", re.I)
        for block in blocks:
            link_match = re.search(r'href=["\'](https://milfzr\.com/[^"\']+)["\']', block, re.I)
            if not link_match:
                continue
            item_url = link_match.group(1)
            
            title_match = re.search(r'title=["\']([^"\']+)["\']', block, re.I)
            title = self._clean(title_match.group(1) if title_match else "")
            if not title or item_url in seen:
                continue
            
            img_match = re.search(r'<img\b[^>]*src=["\']([^"\']+)["\']', block, re.I)
            thumb = img_match.group(1) if img_match else ""
            
            seen.add(item_url)
            items.append((title, item_url, thumb or self.icon, {"title": title, "plot": title}))
        return items

    def process_content(self, url, page=1):
        if not url or url == "BOOTSTRAP":
            url = self.base_url
        content = self._get(self.get_page_url(url, page))
        if not content:
            self.notify_error("Could not load Milfzr")
            return self.end_directory("videos")
            
        self.add_dir("Search", "", 5, self.icons.get("search", self.icon))
        if not urllib.parse.urlparse(url).query:
            self.add_dir("Categories", self.base_url, 8, self.icons.get("categories", self.icon))
            
        items = self._items(content)
        if not items:
            self.notify_error("No Milfzr videos found")
            return self.end_directory("videos")
            
        for title, item_url, thumb, info in items:
            self.add_link(title, item_url, 4, thumb, self.fanart, info_labels=info)
            
        if re.search(r'href=["\'][^"\']*/page/{}/?["\']'.format(page + 1), content, re.I) or re.search(r'[&?]paged={}\b'.format(page + 1), content, re.I):
            self.add_dir("Next Page", url, 2, self.icons.get("default", self.icon), page=page + 1)
        self.end_directory("videos")

    def process_categories(self, url):
        content = self._get(url or self.base_url)
        if not content:
            self.notify_error("Could not load Milfzr categories")
            return self.end_directory("videos")
            
        self.add_dir("Search", "", 5, self.icons.get("search", self.icon))
        seen = set()
        pattern = r'<a\b[^>]+href=["\'](https://milfzr\.com/category/[^"\']+)["\'][^>]*>([\s\S]*?)</a>'
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
        # Match <source src="...mp4">
        matches = re.findall(r'<source\b[^>]*src=["\']([^"\']+\.mp4[^"\']*)["\']', content or "", re.I)
        for s in matches:
            streams.append(self._absolute(s))
        return streams

    def resolve_recording_stream(self, url):
        content = self._get(url, referer=self.base_url)
        streams = self._streams(content)
        if streams:
            # Prefer /media/imported/ path if present (since /media/videos/ is deprecated/404), otherwise first available
            pref_streams = [s for s in streams if "/media/imported/" in s]
            final_stream = pref_streams[0] if pref_streams else streams[0]
            return {"url": final_stream, "headers": self._headers(url), "extension": "mp4"}
        return None

    def play_video(self, url):
        resolved = self.resolve_recording_stream(url)
        if not resolved:
            self.notify_error("Could not resolve Milfzr stream")
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
            self.logger.error("Milfzr playback failed: %s", exc)
            self.notify_error("Milfzr playback failed")
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
