# -*- coding: utf-8 -*-
import html
import os
import re
import sys
import urllib.parse

import xbmc
import xbmcgui
import xbmcplugin

from resources.lib.base_website import BaseWebsite
from resources.lib.proxy_utils import PlaybackGuard, ProxyController


class Porn00(BaseWebsite):
    def __init__(self, addon_handle, addon=None):
        super().__init__(
            name="porn00",
            base_url="https://www.porn00.org",
            search_url="https://www.porn00.org/q/{}/",
            addon_handle=addon_handle,
            addon=addon,
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
        self.sort_options = ["Latest", "All", "Popular", "Top Rated"]
        self.sort_paths = {
            "Latest": "/latest-vids/",
            "All": "/videos-all/",
            "Popular": "/popular-vids/",
            "Top Rated": "/top-vids/",
        }

    def make_request(self, url):
        try:
            self.logger.info(f"[Porn00] GET {url}")
            response = self._scraper.get(
                url,
                timeout=20,
                headers={"Referer": self.base_url + "/", "User-Agent": "Mozilla/5.0"},
            )
            if response.status_code == 200:
                return response.text
            self.logger.error(f"[Porn00] HTTP {response.status_code} for {url}")
        except Exception as exc:
            self.logger.error(f"[Porn00] Request error: {exc}")
        return None

    def get_start_url_and_label(self):
        try:
            current_idx = int(self.addon.getSetting("porn00_sort_by") or "0")
        except Exception:
            current_idx = 0

        if not 0 <= current_idx < len(self.sort_options):
            current_idx = 0

        sort_name = self.sort_options[current_idx]
        sort_path = self.sort_paths.get(sort_name, "/latest-vids/")
        return urllib.parse.urljoin(self.base_url, sort_path), f"Porn00 [COLOR yellow]{sort_name}[/COLOR]"

    def process_content(self, url):
        start_url, _ = self.get_start_url_and_label()
        parsed = urllib.parse.urlparse(url or "")
        path = parsed.path.rstrip("/")
        if url == "BOOTSTRAP" or path == "" or path == "/":
            url = start_url

        context_menu = [
            ("Sort by...", f"RunPlugin({sys.argv[0]}?mode=7&action=select_sort&website={self.name})")
        ]

        self.add_dir("Search", "", 5, self.icons.get("search", self.icon), context_menu=context_menu)
        self.add_dir(
            "Categories",
            urllib.parse.urljoin(self.base_url, "/categories-list/"),
            8,
            self.icons.get("categories", self.icon),
            context_menu=context_menu,
        )

        self._render_listing(url, context_menu=context_menu)

    def _render_listing(self, url, context_menu=None):
        html_content = self.make_request(url)
        if not html_content:
            return self.end_directory("videos")

        item_pattern = re.compile(
            r'<div class="item\s*[^"]*">\s*<a href="(https://www\.porn00\.org/video/[^"]+/)"[^>]*title="([^"]+)"[^>]*>.*?'
            r'<img[^>]+(?:data-original|src)="([^"]+)"[^>]*alt="([^"]+)"[^>]*>.*?'
            r'<div class="duration">([^<]+)</div>',
            re.IGNORECASE | re.DOTALL,
        )

        seen = set()
        for video_url, title_attr, thumb, img_alt, duration in item_pattern.findall(html_content):
            if video_url in seen:
                continue
            seen.add(video_url)

            title = html.unescape((title_attr or img_alt).strip())
            thumb = thumb.strip()
            if thumb.startswith("//"):
                thumb = "https:" + thumb
            elif thumb.startswith("/"):
                thumb = urllib.parse.urljoin(self.base_url, thumb)

            info = {"title": title, "plot": title}
            duration_seconds = self.convert_duration(duration.strip())
            if duration_seconds:
                info["duration"] = duration_seconds

            self.add_link(title, video_url, 4, thumb, self.fanart, context_menu=context_menu, info_labels=info)

        next_url = None
        next_match = re.search(
            r'<li class="next">\s*<a[^>]+href="([^"]+)"',
            html_content,
            re.IGNORECASE,
        )
        if next_match:
            next_url = urllib.parse.urljoin(self.base_url, html.unescape(next_match.group(1)))
        else:
            current_path = urllib.parse.urlparse(url).path.rstrip("/")
            current_page = 1
            page_match = re.search(r"/(\d+)$", current_path)
            if page_match:
                current_page = int(page_match.group(1))
            candidate = current_page + 1
            page_marker = f">{candidate}</a>"
            href_marker = f"/{candidate}/"
            if page_marker in html_content or href_marker in html_content:
                if page_match:
                    next_path = re.sub(r"/\d+$", f"/{candidate}", current_path)
                else:
                    next_path = current_path + f"/{candidate}"
                next_url = urllib.parse.urljoin(self.base_url, next_path + "/")

        if next_url:
            self.add_dir("Next Page", next_url, 2, self.icons.get("default", self.icon), context_menu=context_menu)

        self.end_directory("videos")

    def process_categories(self, url):
        html_content = self.make_request(url)
        if not html_content:
            return self.end_directory("videos")

        item_pattern = re.compile(
            r'<a class="item" href="(https://www\.porn00\.org/category-name/[^"]+/)"[^>]*title="([^"]+)"[^>]*>.*?'
            r'<img[^>]+class="thumb"[^>]+src="([^"]+)"[^>]*>.*?'
            r'<strong class="title">([^<]+)</strong>.*?'
            r'<div class="videos">([^<]+)</div>',
            re.IGNORECASE | re.DOTALL,
        )

        seen = set()
        for cat_url, title_attr, thumb, title_text, count in item_pattern.findall(html_content):
            if cat_url in seen:
                continue
            seen.add(cat_url)
            label = html.unescape((title_text or title_attr).strip())
            if count:
                label = f"{label} ({count.strip()})"
            self.add_dir(label, cat_url, 2, thumb.strip() or self.icons.get("categories", self.icon))

        next_match = re.search(
            r'<li class="next">\s*<a[^>]+href="([^"]+)"',
            html_content,
            re.IGNORECASE,
        )
        if next_match:
            next_url = urllib.parse.urljoin(self.base_url, html.unescape(next_match.group(1)))
            self.add_dir("Next Page", next_url, 8, self.icons.get("default", self.icon))

        self.end_directory("videos")

    def search(self, query):
        if not query:
            return
        search_url = self.search_url.format(urllib.parse.quote_plus(query))
        self.process_content(search_url)

    def play_video(self, url):
        html_content = self.make_request(url)
        if not html_content:
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
            return

        sources = re.findall(
            r'(https://www\.porn00\.org/get_file/[^"\']+\.mp4/[^"\']*)',
            html_content,
            re.IGNORECASE,
        )

        best_url = None
        best_quality = -1
        for src in sources:
            quality = 0
            quality_match = re.search(r'_(\d{3,4})p\.mp4', src, re.IGNORECASE)
            if quality_match:
                quality = int(quality_match.group(1))
            elif ".mp4/" in src:
                quality = 360
            if quality >= best_quality:
                best_quality = quality
                best_url = src

        if not best_url:
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
            return

        proxy_headers = {
            "User-Agent": "Mozilla/5.0",
            "Referer": url,
            "Accept": "*/*",
            "Accept-Encoding": "identity",
            "Accept-Language": "en-US,en;q=0.9",
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
            self.logger.error(f"[Porn00] Proxy playback failed: {exc}")
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
