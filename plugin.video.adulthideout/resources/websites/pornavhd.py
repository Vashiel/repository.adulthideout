# -*- coding: utf-8 -*-
import html
import os
import re
import sys
import urllib.parse

import requests
import xbmc
import xbmcgui
import xbmcplugin

from resources.lib.base_website import BaseWebsite
from resources.lib.resolvers import resolver

_VENDOR_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "lib", "vendor"))
if _VENDOR_DIR not in sys.path:
    sys.path.insert(0, _VENDOR_DIR)

try:
    import cloudscraper
except ImportError:
    cloudscraper = None


class PornAVHD(BaseWebsite):
    sort_options = ["Newest", "Best", "Most Viewed", "Longest", "Random"]
    sort_paths = {
        "Newest": "/?filter=latest",
        "Best": "/?filter=popular",
        "Most Viewed": "/?filter=most-viewed",
        "Longest": "/?filter=longest",
        "Random": "/?filter=random",
    }

    def __init__(self, addon_handle, addon=None):
        super().__init__("pornavhd", "https://pornavhd.com/", "https://pornavhd.com/?s={}", addon_handle, addon)
        self.ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
        self.session = self._create_session()
        self.icon = os.path.join(self.addon.getAddonInfo("path"), "resources", "logos", "pornavhd.png")
        self.icons["default"] = self.icon

    def _headers(self, referer=None):
        return {
            "User-Agent": self.ua,
            "Referer": referer or self.base_url,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }

    def _create_session(self):
        if cloudscraper:
            try:
                return cloudscraper.create_scraper(
                    browser={"browser": "chrome", "platform": "windows", "desktop": True}
                )
            except Exception as exc:
                self.logger.warning("PornAVHD cloudscraper init failed: %s", exc)
        return requests.Session()

    def _get(self, url, referer=None):
        if not self.session:
            self.session = self._create_session()
        try:
            response = self.session.get(url, headers=self._headers(referer), timeout=(7, 20))
            if response.status_code == 403 and cloudscraper and not hasattr(self.session, "solveDepth"):
                self.session = self._create_session()
                response = self.session.get(url, headers=self._headers(referer), timeout=(7, 20))
            return response.text if response.status_code == 200 else ""
        except Exception as exc:
            self.logger.warning("PornAVHD request failed: %s", exc)
            return ""

    def _items(self, content):
        for block in re.findall(r'<article\b[^>]*class=["\'][^"\']*video-preview-item[^"\']*["\'][^>]*>([\s\S]*?)</article>', content or "", re.I):
            link = re.search(r'<a\b[^>]*href=["\']([^"\']+)["\'][^>]*title=["\']([^"\']+)', block, re.I)
            image = re.search(r'<img\b[^>]*src=["\']([^"\']+)', block, re.I)
            duration = re.search(r'class=["\']duration["\'][^>]*>([^<]+)', block, re.I)
            if link and image:
                yield html.unescape(link.group(2)).strip(), html.unescape(link.group(1)), html.unescape(image.group(1)), duration.group(1).strip() if duration else ""

    def process_content(self, url, page=1):
        if not url or url == "BOOTSTRAP":
            url = self.base_url
        if self.is_primary_listing_url(url):
            self.add_dir("Search", "", 5, self.icons.get("search", self.icon))
            self.add_dir("Categories", self.base_url, 8, self.icons.get("categories", self.icon))
        content = self._get(url)
        for title, target, thumb, duration in self._items(content):
            info = {"title": title, "plot": title}
            seconds = self.convert_duration(duration)
            if seconds:
                info["duration"] = seconds
            self.add_link(title, target, 4, thumb, self.fanart, info_labels=info)
        next_match = re.search(r'<a\b[^>]*class=["\'][^"\']*next[^"\']*["\'][^>]*href=["\']([^"\']+)', content or "", re.I)
        if not next_match:
            next_match = re.search(r'<a\b[^>]*href=["\']([^"\']+/page/\d+/[^"\']*)["\'][^>]*>\s*(?:Next|&raquo;|›)', content or "", re.I)
        if next_match:
            self.add_dir("Next Page", html.unescape(next_match.group(1)), 2, self.icon)
        self.end_directory("videos")

    def process_categories(self, url):
        content = self._get(self.base_url)
        seen = set()
        for target, label in re.findall(r'<a\b[^>]*href=["\'](https?://pornavhd\.com/category/[^"\']+/)["\'][^>]*>([^<]+)</a>', content or "", re.I):
            label = html.unescape(label).strip()
            if target not in seen and label:
                seen.add(target)
                self.add_dir(label, target, 2, self.icon)
        self.end_directory("videos")

    def search(self, query):
        if query:
            self.process_content(self.search_url.format(urllib.parse.quote_plus(query)))

    def resolve_recording_stream(self, url):
        page = self._get(url, self.base_url)
        embeds = re.findall(r'<iframe\b[^>]*src=["\'](https?://(?:recordplay|playrecord)\.biz/(?:e|embed)/[^"\']+)', page or "", re.I)
        for embed in embeds:
            stream, headers = resolver.resolve(embed, referer=url, headers=self._headers(url))
            if stream:
                return {"url": stream, "headers": headers or {}, "extension": "m3u8"}
        return None


    def play_video(self, url):
        resolved = self.resolve_recording_stream(url)
        if not resolved:
            self.notify_error("Could not resolve PornAVHD stream")
            return xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
        encoded = urllib.parse.urlencode(resolved["headers"])
        item = xbmcgui.ListItem(path=resolved["url"] + "|" + encoded)
        item.setProperty("IsPlayable", "true")
        item.setMimeType("application/vnd.apple.mpegurl")
        item.setContentLookup(False)
        if xbmc.getCondVisibility("System.HasAddon(inputstream.adaptive)"):
            item.setProperty("inputstream", "inputstream.adaptive")
            item.setProperty("inputstream.adaptive.manifest_type", "hls")
            item.setProperty("inputstream.adaptive.manifest_headers", encoded)
            item.setProperty("inputstream.adaptive.stream_headers", encoded)
        xbmcplugin.setResolvedUrl(self.addon_handle, True, item)
