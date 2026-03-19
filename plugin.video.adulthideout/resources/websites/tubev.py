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


class Tubev(BaseWebsite):
    def __init__(self, addon_handle, addon=None):
        super().__init__(
            name="tubev",
            base_url="https://www.tubev.sex",
            search_url="https://www.tubev.sex/search?q={}",
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
        self.sort_options = ["Popular", "New"]
        self.sort_paths = {
            "Popular": "/videos",
            "New": "/videos?s=n",
        }

    def get_start_url_and_label(self):
        try:
            current_idx = int(self.addon.getSetting("tubev_sort_by") or "0")
        except Exception:
            current_idx = 0

        if not 0 <= current_idx < len(self.sort_options):
            current_idx = 0

        sort_name = self.sort_options[current_idx]
        sort_path = self.sort_paths.get(sort_name, "/videos")
        return urllib.parse.urljoin(self.base_url, sort_path), f"Tubev [COLOR yellow]{sort_name}[/COLOR]"

    def make_request(self, url):
        headers = {"Referer": self.base_url + "/", "User-Agent": "Mozilla/5.0"}

        try:
            self.logger.info(f"[Tubev] GET {url}")
            response = self._scraper.get(url, timeout=20, headers=headers)
            if self._looks_like_valid_page(response.text):
                return response.text
            self.logger.error(f"[Tubev] HTTP {response.status_code} for {url}")
        except Exception as exc:
            self.logger.error(f"[Tubev] Request error: {exc}")
        return None

    def _looks_like_valid_page(self, html_content):
        if not html_content:
            return False
        markers = (
            "https://www.tubev.sex/video/",
            "https://www.tubev.sex/video-archive/",
            "https://www.tubev.sex/categories/",
            'rel="next"',
            'class="drop"',
        )
        return any(marker in html_content for marker in markers)

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
            urllib.parse.urljoin(self.base_url, "/categories"),
            8,
            self.icons.get("categories", self.icon),
            context_menu=context_menu,
        )

        self._render_listing(url, context_menu=context_menu)

    def _render_listing(self, url, context_menu=None):
        html_content = self.make_request(url)
        if not html_content:
            return self.end_directory("videos")

        pattern = re.compile(
            r'<figure[^>]*>.*?'
            r'<a[^>]+href="(https://www\.tubev\.sex/(?:video|video-archive)/\d+/[^"]+)"[^>]+title="([^"]+)"[^>]*>.*?'
            r'<img[^>]+(?:src|data-src|data-original)="([^"]+)"[^>]*>.*?'
            r'<div class="drop">\s*(.*?)\s*</div>.*?'
            r'<div class="label">\s*<div>\s*([^<]+)\s*</div>',
            re.IGNORECASE | re.DOTALL,
        )

        seen = set()
        for video_url, title_attr, thumb, title_text, duration in pattern.findall(html_content):
            if video_url in seen:
                continue
            seen.add(video_url)

            title = html.unescape((title_text or title_attr).strip())
            thumb = thumb.strip()
            if thumb.startswith("//"):
                thumb = "https:" + thumb
            elif thumb.startswith("/"):
                thumb = urllib.parse.urljoin(self.base_url, thumb)

            info = {"title": title, "plot": title}
            duration_seconds = self.convert_duration(duration.strip())
            if duration_seconds:
                info["duration"] = duration_seconds

            self.add_link(
                title,
                video_url,
                4,
                thumb,
                self.fanart,
                context_menu=context_menu,
                info_labels=info,
            )

        next_url = None
        next_match = re.search(r'<link rel="next" href="([^"]+)"', html_content, re.IGNORECASE)
        if next_match:
            next_url = html.unescape(next_match.group(1))
        else:
            pager_match = re.search(
                r"<a[^>]+href=['\"]([^'\"]+)['\"][^>]*>\s*Next\s*</a>",
                html_content,
                re.IGNORECASE,
            )
            if pager_match:
                next_url = urllib.parse.urljoin(self.base_url, html.unescape(pager_match.group(1)))

        if next_url:
            self.add_dir(
                "Next Page",
                next_url,
                2,
                self.icons.get("default", self.icon),
                context_menu=context_menu,
            )

        self.end_directory("videos")

    def process_categories(self, url):
        html_content = self.make_request(url)
        if not html_content:
            return self.end_directory("videos")

        pattern = re.compile(
            r'<a href="(https://www\.tubev\.sex/categories/\d+/[^"]+)" title="([^"]+):\s*([\d,]+)\s+videos">',
            re.IGNORECASE,
        )

        seen = set()
        for cat_url, title, count in pattern.findall(html_content):
            if cat_url in seen:
                continue
            seen.add(cat_url)
            label = html.unescape(title.strip())
            if count:
                label = f"{label} ({count.strip()})"
            self.add_dir(label, cat_url, 2, self.icons.get("categories", self.icon))

        next_url = None
        next_match = re.search(r'<link rel="next" href="([^"]+)"', html_content, re.IGNORECASE)
        if next_match:
            next_url = html.unescape(next_match.group(1))
        else:
            pager_match = re.search(
                r"<a[^>]+href=['\"]([^'\"]+)['\"][^>]*>\s*Next\s*</a>",
                html_content,
                re.IGNORECASE,
            )
            if pager_match:
                next_url = urllib.parse.urljoin(self.base_url, html.unescape(pager_match.group(1)))

        if next_url:
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
            r'https://vcdn\d+\.tubev\.sex/[^"\']+\.mp4[^"\']*',
            html_content,
            re.IGNORECASE,
        )

        best_url = sources[0] if sources else None
        if not best_url:
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
            return

        proxy_headers = {
            "User-Agent": "Mozilla/5.0",
            "Referer": url,
            "Origin": self.base_url,
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
            self.logger.error(f"[Tubev] Proxy playback failed: {exc}")
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
