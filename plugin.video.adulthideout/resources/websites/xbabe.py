# -*- coding: utf-8 -*-
import html
import os
import re
import sys
import urllib.parse

import xbmcgui
import xbmcplugin

from resources.lib.base_website import BaseWebsite


class XBabe(BaseWebsite):
    def __init__(self, addon_handle, addon=None):
        super().__init__(
            name="xbabe",
            base_url="https://xbabe.com",
            search_url="https://xbabe.com/search/?q={}",
            addon_handle=addon_handle,
            addon=addon
        )

        try:
            import xbmcaddon

            addon_path = xbmcaddon.Addon().getAddonInfo("path")
            vendor_path = os.path.join(addon_path, "resources", "lib", "vendor")
            if vendor_path not in sys.path:
                sys.path.insert(0, vendor_path)
        except Exception:
            pass

        import cloudscraper

        self._scraper = cloudscraper.create_scraper(
            browser={"browser": "chrome", "platform": "windows", "mobile": False}
        )

    def make_request(self, url):
        try:
            self.logger.info(f"[XBabe] GET {url}")
            response = self._scraper.get(
                url,
                timeout=20,
                headers={"Referer": self.base_url, "User-Agent": "Mozilla/5.0"},
            )
            if response.status_code == 200:
                return response.text
            self.logger.error(f"[XBabe] HTTP {response.status_code} for {url}")
        except Exception as exc:
            self.logger.error(f"[XBabe] Request error: {exc}")
        return None

    def process_content(self, url):
        if url == "BOOTSTRAP":
            url = self.base_url + "/"

        self.add_dir("Search", "", 5, self.icons.get("search", self.icon))
        self.add_dir(
            "Categories",
            urllib.parse.urljoin(self.base_url, "/categories/"),
            8,
            self.icons.get("categories", self.icon),
        )

        self._render_listing(url)

    def _render_listing(self, url):
        html_content = self.make_request(url)
        if not html_content:
            return self.end_directory("videos")

        item_pattern = re.compile(
            r'<div class="thumb"><a[^>]+href="(https://xbabe\.com/videos/[^"]+)"[^>]*>'
            r'<span class="title">([^<]+)</span>.*?'
            r'<img[^>]+(?:data-original|src)="([^"]+)".*?'
            r'<span class="duration">([^<]+)</span>',
            re.IGNORECASE | re.DOTALL,
        )

        seen = set()
        for video_url, title, thumb, duration in item_pattern.findall(html_content):
            if video_url in seen:
                continue
            seen.add(video_url)

            title = html.unescape(title.strip())
            thumb = thumb.strip()
            if thumb.startswith("//"):
                thumb = "https:" + thumb

            info = {"title": title, "plot": title}
            duration_seconds = self.convert_duration(duration.strip())
            if duration_seconds:
                info["duration"] = duration_seconds

            self.add_link(title, video_url, 4, thumb, self.fanart, info_labels=info)

        next_match = re.search(
            r'<a href="([^"]+)" class="next">Next',
            html_content,
            re.IGNORECASE,
        )
        if next_match:
            next_url = urllib.parse.urljoin(self.base_url, next_match.group(1))
            self.add_dir("Next Page", next_url, 2, self.icons.get("default", self.icon))

        self.end_directory("videos")

    def process_categories(self, url):
        html_content = self.make_request(url)
        if not html_content:
            return self.end_directory("videos")

        cat_pattern = re.compile(
            r'<a\s+href="(https://xbabe\.com/categories/videos/[^"]+)"[^>]*>([^<]+)</a>',
            re.IGNORECASE,
        )

        seen = set()
        for cat_url, title in cat_pattern.findall(html_content):
            if cat_url in seen:
                continue
            seen.add(cat_url)
            title = html.unescape(title.strip())
            self.add_dir(title, cat_url, 2, self.icons.get("categories", self.icon))

        self.end_directory("videos")

    def play_video(self, url):
        html_content = self.make_request(url)
        if not html_content:
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
            return

        sources = re.findall(
            r'<source[^>]+src="([^"]+)"[^>]*title="([^"]+)"',
            html_content,
            re.IGNORECASE,
        )

        best_url = None
        best_quality = -1
        for src, label in sources:
            quality = 0
            match = re.search(r"(\d{3,4})", label)
            if match:
                quality = int(match.group(1))
            if quality >= best_quality:
                best_quality = quality
                best_url = src

        if not best_url and sources:
            best_url = sources[0][0]

        if not best_url:
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
            return

        if best_url.startswith("//"):
            best_url = "https:" + best_url

        list_item = xbmcgui.ListItem(path=best_url)
        list_item.setProperty("IsPlayable", "true")
        list_item.setMimeType("video/mp4")
        list_item.setContentLookup(False)
        xbmcplugin.setResolvedUrl(self.addon_handle, True, list_item)
