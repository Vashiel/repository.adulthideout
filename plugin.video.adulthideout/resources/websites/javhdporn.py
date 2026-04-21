# -*- coding: utf-8 -*-
import html
import json
import os
import re
import sys
import urllib.parse

import xbmcaddon
import xbmcgui
import xbmcplugin

from resources.lib.base_website import BaseWebsite
from resources.lib.resolvers import javhdporn_resolver

try:
    current_dir = os.path.dirname(os.path.abspath(__file__))
    vendor_path = os.path.abspath(os.path.join(current_dir, "..", "lib", "vendor"))
    if os.path.isdir(vendor_path) and vendor_path not in sys.path:
        sys.path.insert(0, vendor_path)
except Exception:
    vendor_path = ""

import requests
import cloudscraper


class JavhdpornWebsite(BaseWebsite):
    """
    Research scaffold for https://www.javhdporn.net/

    Important:
    - This file intentionally uses only vendored libraries already bundled with AdultHideout.
    - With the updated vendored cloudscraper stack, root HTML, search and categories are now fetchable.
    - Playback is still documented and partially prepared, but the final host resolver is not finished yet.
    """

    def __init__(self, addon_handle):
        addon = xbmcaddon.Addon()
        super().__init__(
            name="javhdporn",
            base_url="https://www.javhdporn.net/",
            search_url="https://www.javhdporn.net/?s={}",
            addon_handle=addon_handle,
            addon=addon,
        )
        self.ua = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/123.0.0.0 Safari/537.36"
        )
        self.session = requests.Session()
        self.cf_session = cloudscraper.create_scraper(
            browser={"browser": "chrome", "platform": "windows", "desktop": True},
            interpreter="native",
            enable_stealth=False,
            rotate_tls_ciphers=True,
            min_request_interval=0.0,
            auto_refresh_on_403=False,
        )
        self.category_links = [
            ("Censored", "https://www.javhdporn.net/category/censored/"),
            ("English Subtitle", "https://www.javhdporn.net/category/censored/english-subtitle/"),
            ("Chinese Subtitle", "https://www.javhdporn.net/category/chinese-subtitle/"),
            ("Subtitle Indonesia", "https://www.javhdporn.net/category/subtitle-indonesia/"),
            ("Uncensored", "https://www.javhdporn.net/v1/category/uncensored/"),
            ("Amateur", "https://www.javhdporn.net/category/amateur/"),
            ("Decensored", "https://www.javhdporn.net/category/decensored/"),
        ]

    def _headers(self, referer=None, accept=None):
        return {
            "User-Agent": self.ua,
            "Referer": referer or self.base_url,
            "Accept": accept or "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }

    def _fetch(self, url, referer=None):
        """
        Vendored-only fetch path.

        Current real-world result with the updated vendored stack:
        - requests: still often 403
        - vendored cloudscraper 3.x: root HTML fetch works
        """
        errors = []
        for label, session in (("requests", self.session), ("cloudscraper", self.cf_session)):
            try:
                response = session.get(url, headers=self._headers(referer=referer), timeout=30)
                if response.status_code == 200:
                    return response.text
                errors.append("{} HTTP {}".format(label, response.status_code))
            except Exception as exc:
                errors.append("{} {}".format(label, exc))

        self.logger.warning("[JavHDPorn] Fetch failed for %s :: %s", url, " | ".join(errors))
        return None

    def _absolute(self, url):
        if not url:
            return ""
        return urllib.parse.urljoin(self.base_url, html.unescape(url.strip()))

    def _clean_text(self, value):
        return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", html.unescape(value or ""))).strip()

    def _is_real_thumb(self, url):
        if not url:
            return False
        lowered = html.unescape(url).strip().lower()
        if lowered.startswith("data:"):
            return False
        if ".svg" in lowered or "viewbox" in lowered:
            return False
        if "404.jpeg" in lowered or "404.jpg" in lowered or "404.png" in lowered:
            return False
        return lowered.startswith(("http://", "https://", "//", "/"))

    def _extract_title(self, block, fallback_url):
        title_match = re.search(r'<a class="archive-entry"[^>]+title="([^"]+)"', block, re.IGNORECASE)
        if title_match:
            title = self._clean_text(title_match.group(1))
            if title:
                return title

        header_match = re.search(r'<header[^>]*class="[^"]*entry-header[^"]*"[^>]*>\s*<span[^>]*>(.*?)</span>', block, re.IGNORECASE | re.DOTALL)
        if header_match:
            title = self._clean_text(header_match.group(1))
            if title:
                return title

        heading_match = re.search(r'<h[1-6][^>]*>\s*<a[^>]*>(.*?)</a>', block, re.IGNORECASE | re.DOTALL)
        if heading_match:
            title = self._clean_text(heading_match.group(1))
            if title:
                return title

        return fallback_url.rstrip("/").split("/")[-1]

    def _extract_thumbnail(self, block):
        for attr in ("data-lazy-src", "data-wpsrc", "data-src", "data-original", "data-thumb", "poster"):
            match = re.search(r'%s="([^"]+)"' % attr, block, re.IGNORECASE)
            if match and self._is_real_thumb(match.group(1)):
                return self._absolute(match.group(1))

        srcset_match = re.search(r'(?:data-lazy-srcset|data-srcset|srcset)="([^"]+)"', block, re.IGNORECASE)
        if srcset_match:
            candidates = [part.strip().split(" ")[0] for part in html.unescape(srcset_match.group(1)).split(",")]
            for candidate in reversed(candidates):
                if self._is_real_thumb(candidate):
                    return self._absolute(candidate)

        for src in re.findall(r'\ssrc="([^"]+)"', block, re.IGNORECASE):
            if self._is_real_thumb(src):
                return self._absolute(src)

        return self.icon

    def _extract_listing_items(self, html_content):
        items = []
        seen = set()
        pattern = re.compile(
            r'(<article id="post-\d+"[^>]*class="[^"]*thumb-block[^"]*loop-video[^"]*"[\s\S]*?</article>)',
            re.IGNORECASE,
        )
        for block in pattern.findall(html_content):
            url_match = re.search(
                r'<a class="archive-entry" href="(https://www\.javhdporn\.net/video/[^"]+/?)"',
                block,
                re.IGNORECASE,
            )
            if not url_match:
                continue
            video_url = self._absolute(url_match.group(1))
            if video_url in seen:
                continue
            seen.add(video_url)

            duration_match = re.search(r'<span class="duration">\s*([^<]+)\s*</span>', block, re.IGNORECASE)

            title = self._extract_title(block, video_url)
            thumb = self._extract_thumbnail(block)
            duration_text = duration_match.group(1).strip() if duration_match else ""
            info = {"title": title or video_url, "plot": title or video_url}
            duration_seconds = self.convert_duration(duration_text)
            if duration_seconds:
                info["duration"] = duration_seconds

            items.append(
                {
                    "title": title or video_url.rstrip("/").split("/")[-1],
                    "url": video_url,
                    "thumb": thumb,
                    "info": info,
                }
            )
        return items

    def _extract_next_page(self, html_content):
        match = re.search(r'<a[^>]+class="[^"]*next[^"]*"[^>]+href="([^"]+)"', html_content, re.IGNORECASE)
        if match:
            return self._absolute(match.group(1))
        match = re.search(r'<link rel="next" href="([^"]+)"', html_content, re.IGNORECASE)
        if match:
            return self._absolute(match.group(1))
        return None

    def process_content(self, url):
        if not url or url == "BOOTSTRAP":
            url = self.base_url

        self.add_dir("Search", "", 5, self.icons.get("search", self.icon))
        self.add_dir("Categories", "JAVHDPORN_CATEGORIES", 8, self.icons.get("categories", self.icon))

        html_content = self._fetch(url)
        if not html_content:
            self.notify_error(
                "JavHDPorn fetch failed. Root HTML should work with the updated vendored stack, but this request did not complete."
            )
            self.end_directory("videos")
            return

        items = self._extract_listing_items(html_content)
        for item in items:
            self.add_link(item["title"], item["url"], 4, item["thumb"], self.fanart, info_labels=item["info"])

        next_page = self._extract_next_page(html_content)
        if next_page and next_page != url:
            self.add_dir("Next Page", next_page, 2, self.icons.get("default", self.icon))

        self.end_directory("videos")

    def process_categories(self, url):
        for label, target in self.category_links:
            self.add_dir(label, target, 2, self.icons.get("categories", self.icon))
        self.end_directory("videos")

    def search(self, query):
        if not query:
            return
        self.process_content(self.search_url.format(urllib.parse.quote_plus(query.strip())))

    def play_video(self, url):
        try:
            stream_url, headers = javhdporn_resolver.resolve(url, referer=self.base_url)
        except Exception as exc:
            self.logger.error("[JavHDPorn] Playback resolve failed for %s: %s", url, exc)
            self.notify_error("JavHDPorn: Could not resolve video stream")
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
            return

        header_string = urllib.parse.urlencode(headers)
        list_item = xbmcgui.ListItem(path=stream_url + "|" + header_string)
        list_item.setProperty("IsPlayable", "true")
        if ".m3u8" in stream_url:
            list_item.setMimeType("application/vnd.apple.mpegurl")
            list_item.setContentLookup(False)
        else:
            list_item.setMimeType("video/mp4")
        xbmcplugin.setResolvedUrl(self.addon_handle, True, list_item)
