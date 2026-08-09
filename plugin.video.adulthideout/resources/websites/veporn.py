# -*- coding: utf-8 -*-
import html
import json
import os
import re
import sys
import urllib.parse

import xbmc
import xbmcgui
import xbmcplugin

from resources.lib.base_website import BaseWebsite
from resources.lib.proxy_utils import PlaybackGuard, ProxyController


class Veporn(BaseWebsite):
    def __init__(self, addon_handle, addon=None):
        super().__init__(
            name="veporn",
            base_url="https://veporn.com",
            search_url="https://veporn.com/search?q={}",
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
            self.logger.info(f"[Veporn] GET {url}")
            response = self._scraper.get(
                url,
                timeout=20,
                headers={"Referer": self.base_url, "User-Agent": "Mozilla/5.0"},
            )
            if response.status_code == 200:
                return response.text
            self.logger.error(f"[Veporn] HTTP {response.status_code} for {url}")
        except Exception as exc:
            self.logger.error(f"[Veporn] Request error: {exc}")
        return None

    def process_content(self, url):
        if url in ("BOOTSTRAP", self.base_url, self.base_url + "/"):
            url = self.base_url + "/videos"

        self.add_dir("Search", "", 5, self.icons.get("search", self.icon))
        self.add_dir(
            "Categories",
            urllib.parse.urljoin(self.base_url, "/search"),
            8,
            self.icons.get("categories", self.icon),
        )

        self._render_listing(url)

    def _render_listing(self, url):
        html_content = self.make_request(url)
        if not html_content:
            return self.end_directory("videos")

        seen = set()
        next_url = ""
        if "/api/videos?" in url:
            try:
                payload = json.loads(html_content)
            except (TypeError, ValueError):
                payload = {}
            for item in payload.get("data") or []:
                self._add_api_item(item, seen)
            cursor = payload.get("nextCursor")
            if payload.get("hasMore") and cursor:
                separator = "&" if "?" in url else "?"
                next_url = url.split("&cursor=", 1)[0] + separator + urllib.parse.urlencode({"cursor": cursor})
        else:
            card_pattern = re.compile(
                r'<a\b[^>]*class="[^"]*\bgroup\s+block\b[^"]*"[^>]*href="([^"]+)"[^>]*>'
                r'(?:(?!</a>).)*?<img\b[^>]*alt="([^"]+)"[^>]*src="([^"]+)"[^>]*>'
                r'(?:(?!</a>).)*?<span\b[^>]*>(\d{1,2}:\d{2}(?::\d{2})?)</span>',
                re.IGNORECASE | re.DOTALL,
            )
            for href, title, thumb, duration in card_pattern.findall(html_content):
                video_url = urllib.parse.urljoin(self.base_url, html.unescape(href))
                if video_url in seen:
                    continue
                seen.add(video_url)
                clean_title = html.unescape(title).strip()
                image_url = self._thumbnail_url(thumb)
                info = {"title": clean_title, "plot": clean_title}
                seconds = self.convert_duration(duration)
                if seconds:
                    info["duration"] = seconds
                self.add_link(clean_title, video_url, 4, image_url, self.fanart, info_labels=info)

            cursor_match = re.search(r'initialCursor\\?":\\?"([^"\\]+)', html_content, re.I)
            fetch_match = re.search(r'fetchUrl\\?":\\?"([^"\\]+)', html_content, re.I)
            if cursor_match and fetch_match:
                fetch_url = html.unescape(fetch_match.group(1)).replace("\\u0026", "&")
                separator = "&" if "?" in fetch_url else "?"
                next_url = urllib.parse.urljoin(
                    self.base_url,
                    fetch_url + separator + urllib.parse.urlencode({"cursor": cursor_match.group(1)}),
                )

        if next_url:
            self.add_dir("Next Page", next_url, 2, self.icons.get("default", self.icon))

        self.end_directory("videos")

    def _add_api_item(self, item, seen):
        slug = str(item.get("slug") or "").strip()
        title = html.unescape(str(item.get("title") or "")).strip()
        if not slug or not title:
            return
        video_url = urllib.parse.urljoin(self.base_url + "/", slug)
        if video_url in seen:
            return
        seen.add(video_url)
        thumb = self._thumbnail_url(item.get("thumbnailUrl"))
        info = {"title": title, "plot": html.unescape(str(item.get("description") or title)).strip()}
        try:
            duration = int(item.get("duration") or 0)
        except (TypeError, ValueError):
            duration = 0
        if duration:
            info["duration"] = duration
        self.add_link(title, video_url, 4, thumb, self.fanart, info_labels=info)

    def _thumbnail_url(self, value):
        url = urllib.parse.urljoin(self.base_url, html.unescape(str(value or "")))
        if url and "|" not in url:
            url += "|" + urllib.parse.urlencode({
                "User-Agent": "Mozilla/5.0",
                "Referer": self.base_url + "/",
            })
        return url

    def process_categories(self, url):
        html_content = self.make_request(url)
        if not html_content:
            return self.end_directory("videos")

        seen = set()
        for cat_href, slug in re.findall(
            r'<a\b[^>]*href="(/category/([^"/]+))"[^>]*>', html_content, re.I
        ):
            cat_url = urllib.parse.urljoin(self.base_url, cat_href)
            if cat_url in seen:
                continue
            seen.add(cat_url)
            title = urllib.parse.unquote(slug).replace("-", " ").title()
            self.add_dir(title, cat_url, 2, self.icons.get("categories", self.icon))

        self.end_directory("videos")

    def play_video(self, url):
        html_content = self.make_request(url)
        if not html_content:
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
            return

        sources = re.findall(
            r'<source[^>]+src="([^"]+)"(?:[^>]+label="([^"]*)")?',
            html_content,
            re.IGNORECASE,
        )

        best_url = None
        best_quality = -1
        for src, label in sources:
            quality = 0
            match = re.search(r"(\d{3,4})", label or "")
            if match:
                quality = int(match.group(1))
            if quality >= best_quality:
                best_quality = quality
                best_url = src

        if not best_url:
            content_match = re.search(r'contentUrl\\?"\s*:\s*\\?"(https?://[^"\\]+\.mp4)', html_content, re.I)
            if content_match:
                best_url = content_match.group(1).replace("\\/", "/")

        if not best_url:
            iframe_match = re.search(
                r'https://cdn\.veporn\.com/[^"\']+\.mp4[^"\']*',
                html_content,
                re.IGNORECASE,
            )
            if iframe_match:
                best_url = iframe_match.group(0)

        if not best_url:
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
            return

        if best_url.startswith("//"):
            best_url = "https:" + best_url

        proxy_headers = {
            "User-Agent": "Mozilla/5.0",
            "Accept": "*/*",
            "Accept-Encoding": "identity",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": self.base_url + "/",
            "Origin": self.base_url,
            "Sec-Fetch-Site": "cross-site",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Dest": "video",
            "Connection": "keep-alive",
        }

        try:
            controller = ProxyController(
                upstream_url=best_url,
                upstream_headers=proxy_headers,
                cookies=None,
                use_urllib=True,
            )
            local_url = controller.start()

            list_item = xbmcgui.ListItem(path=local_url)
            list_item.setProperty("IsPlayable", "true")
            list_item.setMimeType("video/mp4")
            list_item.setContentLookup(False)
            xbmcplugin.setResolvedUrl(self.addon_handle, True, list_item)

            PlaybackGuard(xbmc.Player(), xbmc.Monitor(), local_url, controller).start()
        except Exception as exc:
            self.logger.error(f"[Veporn] Proxy playback failed: {exc}")
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
