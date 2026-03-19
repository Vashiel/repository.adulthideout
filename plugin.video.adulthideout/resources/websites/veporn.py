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


class Veporn(BaseWebsite):
    def __init__(self, addon_handle, addon=None):
        super().__init__(
            name="veporn",
            base_url="https://veporn.com",
            search_url="https://veporn.com/?s={}",
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
            r'<article[^>]+class="[^"]*\bloop-post\b[^"]*\bvdeo\b[^"]*"[^>]*>(.*?)</article>',
            re.IGNORECASE | re.DOTALL,
        )

        seen = set()
        for block in item_pattern.findall(html_content):
            link_match = re.search(
                r'<a[^>]+class="[^"]*\blka\b[^"]*"[^>]+href="([^"]+)"',
                block,
                re.IGNORECASE,
            )
            title_match = re.search(
                r'<h2[^>]+class="[^"]*\bttl\b[^"]*"[^>]*>\s*([^<]+?)\s*</h2>',
                block,
                re.IGNORECASE | re.DOTALL,
            )
            thumb_match = re.search(
                r'<img[^>]+(?:data-src|data-lazy-src|src)="([^"]+)"',
                block,
                re.IGNORECASE,
            )
            duration_match = re.search(
                r'<i[^>]+fa-clock[^>]*></i>\s*([^<]+)',
                block,
                re.IGNORECASE | re.DOTALL,
            )

            if not (link_match and title_match):
                continue

            video_url = urllib.parse.urljoin(self.base_url, link_match.group(1).strip())
            if video_url in seen:
                continue
            seen.add(video_url)

            title = html.unescape(title_match.group(1).strip())
            thumb = thumb_match.group(1).strip() if thumb_match else ""
            if thumb.startswith("//"):
                thumb = "https:" + thumb

            info = {"title": title, "plot": title}
            duration_seconds = self.convert_duration(
                duration_match.group(1).strip() if duration_match else ""
            )
            if duration_seconds:
                info["duration"] = duration_seconds

            self.add_link(title, video_url, 4, thumb, self.fanart, info_labels=info)

        next_match = re.search(
            r'<a(?=[^>]*class="[^"]*\bnext\b[^"]*")(?=[^>]*href="([^"]+)")[^>]*>.*?(?:Next Page|Next)\b',
            html_content,
            re.IGNORECASE | re.DOTALL,
        )
        if next_match:
            next_url = urllib.parse.urljoin(self.base_url, next_match.group(1))
            self.add_dir("Next Page", next_url, 2, self.icons.get("default", self.icon))

        self.end_directory("videos")

    def process_categories(self, url):
        html_content = self.make_request(url)
        if not html_content:
            return self.end_directory("videos")

        seen = set()
        item_pattern = re.compile(
            r'<div[^>]+class="[^"]*\bctgr\b[^"]*"[^>]*>.*?'
            r'(?:<img[^>]+(?:data-src|data-lazy-src|src)="([^"]+)")?.*?'
            r'<div[^>]+class="[^"]*\bttl\b[^"]*"[^>]*>\s*([^<]+?)\s*</div>.*?'
            r'<a[^>]+class="[^"]*\blka\b[^"]*"[^>]+href="([^"]+)"',
            re.IGNORECASE | re.DOTALL,
        )

        for thumb, title, cat_href in item_pattern.findall(html_content):
            cat_url = urllib.parse.urljoin(self.base_url, cat_href.strip())
            if cat_url in seen:
                continue
            seen.add(cat_url)

            title = html.unescape(title.strip())
            thumb = thumb.strip() if thumb else self.icons.get("categories", self.icon)
            if thumb.startswith("//"):
                thumb = "https:" + thumb

            self.add_dir(title, cat_url, 2, thumb)

        next_match = re.search(
            r'<a(?=[^>]*class="[^"]*\bnext\b[^"]*")(?=[^>]*href="([^"]+)")[^>]*>.*?(?:Next Page|Next)\b',
            html_content,
            re.IGNORECASE | re.DOTALL,
        )
        if next_match:
            next_url = urllib.parse.urljoin(self.base_url, next_match.group(1))
            self.add_dir("Next Page", next_url, 8, self.icons.get("default", self.icon))

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
