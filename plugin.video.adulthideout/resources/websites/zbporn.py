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


class Zbporn(BaseWebsite):
    def __init__(self, addon_handle, addon=None):
        super().__init__(
            name="zbporn",
            base_url="https://zbporn.com",
            search_url="https://zbporn.com/search/{}/",
            addon_handle=addon_handle,
            addon=addon,
        )
        self.session = requests.Session()
        self.ua = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/126.0.0.0 Safari/537.36"
        )
        self.sort_options = ["Latest", "Popular", "Top Rated", "Longest"]
        self.sort_paths = {
            "Latest": "/latest-updates/",
            "Popular": "/most-popular/",
            "Top Rated": "/top-rated/",
            "Longest": "/longest/",
        }

    def make_request(self, url, referer=None):
        try:
            headers = {
                "User-Agent": self.ua,
                "Referer": referer or (self.base_url + "/"),
            }
            response = self.session.get(url, headers=headers, timeout=20)
            if response.status_code == 200:
                return response.text
            self.logger.error("[ZBPorn] HTTP %s for %s", response.status_code, url)
        except Exception as exc:
            self.logger.error("[ZBPorn] Request error: %s", exc)
        return None

    def _get_sort_key(self):
        try:
            idx = int(self.addon.getSetting("zbporn_sort_by") or "0")
        except Exception:
            idx = 0
        if not 0 <= idx < len(self.sort_options):
            idx = 0
        return self.sort_options[idx]

    def get_start_url_and_label(self):
        sort_key = self._get_sort_key()
        return urllib.parse.urljoin(self.base_url, self.sort_paths.get(sort_key, "/latest-updates/")), (
            f"ZBPorn [COLOR yellow]{sort_key}[/COLOR]"
        )

    def _get_context_menu(self):
        return [
            (
                "Sort by...",
                f"RunPlugin({sys.argv[0]}?mode=7&action=select_sort_order&website={self.name})",
            )
        ]

    def select_sort_order(self, original_url=None):
        try:
            preselect_idx = self.sort_options.index(self._get_sort_key())
        except ValueError:
            preselect_idx = 0

        idx = xbmcgui.Dialog().select("Sort by...", self.sort_options, preselect=preselect_idx)
        if idx == -1:
            return

        self.addon.setSetting("zbporn_sort_by", str(idx))
        new_url, _ = self.get_start_url_and_label()
        xbmc.executebuiltin(
            f"Container.Update({sys.argv[0]}?mode=2&website={self.name}&url={urllib.parse.quote_plus(new_url)})"
        )

    def process_content(self, url):
        if not url or url == "BOOTSTRAP":
            url, _ = self.get_start_url_and_label()

        context_menu = self._get_context_menu()
        self.add_dir("Search", "", 5, self.icons.get("search", self.icon), context_menu=context_menu)
        self.add_dir(
            "Categories",
            urllib.parse.urljoin(self.base_url, "/categories/"),
            8,
            self.icons.get("categories", self.icon),
            context_menu=context_menu,
        )
        self._render_listing(url, context_menu=context_menu)

    def _render_listing(self, url, context_menu=None):
        html_content = self.make_request(url)
        if not html_content:
            return self.end_directory("videos")

        seen = set()
        item_pattern = re.compile(
            r'<a class="th-image-link" href="(https://zbporn\.com/videos/[^"]+/)"[^>]*title="([^"]+)"[^>]*>.*?'
            r'<img[^>]+src="([^"]+)"[^>]+alt="([^"]+)".*?>.*?'
            r'<span class="th-duration">([^<]+)</span>.*?'
            r'<a class="th-row-title" href="https://zbporn\.com/videos/[^"]+/"[^>]*>([^<]+)</a>',
            re.IGNORECASE | re.DOTALL,
        )

        for video_url, title_attr, thumb, img_alt, duration, row_title in item_pattern.findall(html_content):
            if video_url in seen:
                continue
            seen.add(video_url)

            title = html.unescape((row_title or title_attr or img_alt).strip())
            thumb = thumb.strip() if thumb else self.icon
            if thumb.startswith("//"):
                thumb = "https:" + thumb
            elif thumb.startswith("/"):
                thumb = urllib.parse.urljoin(self.base_url, thumb)

            info = {"title": title, "plot": title}
            duration_seconds = self.convert_duration(duration.strip() if duration else "")
            if duration_seconds:
                info["duration"] = duration_seconds

            self.add_link(title, video_url, 4, thumb, self.fanart, context_menu=context_menu, info_labels=info)

        next_match = re.search(
            r'<div class="page next">\s*<a[^>]+href="([^"]+)"',
            html_content,
            re.IGNORECASE,
        )
        if next_match:
            next_url = urllib.parse.urljoin(self.base_url, html.unescape(next_match.group(1)))
            self.add_dir("Next Page", next_url, 2, self.icons.get("default", self.icon), context_menu=context_menu)

        self.end_directory("videos")

    def process_categories(self, url):
        html_content = self.make_request(url)
        if not html_content:
            return self.end_directory("videos")

        seen = set()
        pattern = re.compile(
            r'<a class="th-title" href="(https://zbporn\.com/categories/[^"]+/)" title="([^"]+)">([^<]+)</a>',
            re.IGNORECASE,
        )
        for cat_url, title_attr, title_text in pattern.findall(html_content):
            if cat_url in seen:
                continue
            seen.add(cat_url)
            label = html.unescape((title_text or title_attr).strip())
            self.add_dir(label, cat_url, 2, self.icons.get("categories", self.icon))

        self.end_directory("videos")

    def search(self, query):
        if not query:
            return
        self.process_content(self.search_url.format(urllib.parse.quote_plus(query)))

    def _build_header_url(self, stream_url, headers):
        parts = []
        for key, value in headers.items():
            parts.append(
                "{}={}".format(
                    urllib.parse.quote(str(key), safe=""),
                    urllib.parse.quote(str(value), safe=""),
                )
            )
        return stream_url + "|" + "&".join(parts)

    def play_video(self, url):
        html_content = self.make_request(url)
        if not html_content:
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
            return

        source_map = {}
        for key in ("video_url", "video_alt_url"):
            match = re.search(r"%s:\s*'([^']+\.mp4[^']*)'" % key, html_content, re.IGNORECASE)
            if match:
                source_map[key] = html.unescape(match.group(1).strip())

        best_url = None
        best_quality = -1
        for key, src in source_map.items():
            quality = 0
            quality_match = re.search(r'_(\d{3,4})p\.mp4', src, re.IGNORECASE)
            if quality_match:
                quality = int(quality_match.group(1))
            elif key == "video_url":
                quality = 1000
            else:
                quality = 360
            if quality >= best_quality:
                best_quality = quality
                best_url = src

        if not best_url:
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
            return

        stream_headers = {
            "User-Agent": self.ua,
            "Referer": url,
            "Accept": "*/*",
            "Accept-Language": "en-US,en;q=0.9",
            "Connection": "keep-alive",
        }
        list_item = xbmcgui.ListItem(path=self._build_header_url(best_url, stream_headers))
        list_item.setProperty("IsPlayable", "true")
        list_item.setMimeType("video/mp4")
        list_item.setContentLookup(False)
        xbmcplugin.setResolvedUrl(self.addon_handle, True, list_item)
