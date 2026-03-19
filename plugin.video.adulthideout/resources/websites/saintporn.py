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
from resources.lib.decoders.kvs_decoder import kvs_decode_url
from resources.lib.proxy_utils import PlaybackGuard, ProxyController


class SaintPorn(BaseWebsite):
    def __init__(self, addon_handle, addon=None):
        super().__init__(
            name="saintporn",
            base_url="https://saintporn.com",
            search_url="https://saintporn.com/search/{}/",
            addon_handle=addon_handle,
            addon=addon,
        )
        self.session = requests.Session()
        self.ua = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/128.0.0.0 Safari/537.36"
        )
        self.sort_options = ["Latest", "Top Rated", "Most Viewed"]
        self.sort_paths = {
            "Latest": "/latest-updates/",
            "Top Rated": "/top-rated/",
            "Most Viewed": "/most-popular/",
        }

    def make_request(self, url, referer=None):
        headers = {
            "User-Agent": self.ua,
            "Referer": referer or (self.base_url + "/"),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }
        try:
            response = self.session.get(url, headers=headers, timeout=20)
            if response.status_code in (200, 404):
                return response.text
            self.logger.error("[SaintPorn] HTTP %s for %s", response.status_code, url)
        except Exception as exc:
            self.logger.error("[SaintPorn] Request error for %s: %s", url, exc)
        return None

    def _get_sort_key(self):
        try:
            idx = int(self.addon.getSetting("saintporn_sort_by") or "0")
        except Exception:
            idx = 0
        if not 0 <= idx < len(self.sort_options):
            idx = 0
        return self.sort_options[idx]

    def get_start_url_and_label(self):
        sort_key = self._get_sort_key()
        return urllib.parse.urljoin(self.base_url, self.sort_paths.get(sort_key, "/latest-updates/")), (
            "SaintPorn [COLOR yellow]{}[/COLOR]".format(sort_key)
        )

    def _get_context_menu(self):
        return [
            (
                "Sort by...",
                "RunPlugin({}?mode=7&action=select_sort_order&website={})".format(
                    sys.argv[0],
                    self.name,
                ),
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

        self.addon.setSetting("saintporn_sort_by", str(idx))
        new_url, _ = self.get_start_url_and_label()
        xbmc.executebuiltin(
            "Container.Update({}?mode=2&website={}&url={})".format(
                sys.argv[0], self.name, urllib.parse.quote_plus(new_url)
            )
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
        self.add_dir(
            "Pornstars",
            urllib.parse.urljoin(self.base_url, "/models/"),
            9,
            self.icons.get("pornstars", self.icon),
            context_menu=context_menu,
        )
        self._render_listing(url, context_menu=context_menu)

    def _render_listing(self, url, context_menu=None):
        html_content = self.make_request(url)
        if not html_content:
            return self.end_directory("videos")

        pattern = re.compile(
            r'<div class="thumb[^"]*item[^"]*">\s*'
            r'<a href="(https://saintporn\.com/video/[^"]+/)" title="([^"]+)".*?'
            r'<img[^>]+(?:data-original|src)="([^"]+)"[^>]+alt="([^"]+)".*?'
            r'<div class="time">([^<]+)</div>.*?'
            r'<div class="title">\s*([^<]+?)\s*</div>',
            re.IGNORECASE | re.DOTALL,
        )

        seen = set()
        for video_url, title_attr, thumb, alt_text, duration, title_text in pattern.findall(html_content):
            if video_url in seen:
                continue
            seen.add(video_url)

            title = html.unescape((title_text or title_attr or alt_text).strip())
            thumb = html.unescape(thumb.strip()) if thumb else self.icon
            if thumb.startswith("//"):
                thumb = "https:" + thumb
            elif thumb.startswith("/"):
                thumb = urllib.parse.urljoin(self.base_url, thumb)

            info = {"title": title, "plot": title}
            duration_seconds = self.convert_duration(duration.strip() if duration else "")
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
        next_match = re.search(r'<a class=[\'"]next[\'"] href="([^"]+)"', html_content, re.IGNORECASE)
        if next_match:
            next_url = urllib.parse.urljoin(self.base_url, html.unescape(next_match.group(1).strip()))

        if next_url and next_url != url:
            self.add_dir("Next Page", next_url, 2, self.icons.get("default", self.icon), context_menu=context_menu)

        self.end_directory("videos")

    def process_categories(self, url):
        html_content = self.make_request(url)
        if not html_content:
            return self.end_directory("videos")

        pattern = re.compile(
            r'<div class="thumb item">\s*<a href="(https://saintporn\.com/categories/[^"]+/)" title="([^"]+)".*?'
            r'<img[^>]+src="([^"]+)"',
            re.IGNORECASE | re.DOTALL,
        )

        seen = set()
        for cat_url, title, thumb in pattern.findall(html_content):
            if cat_url in seen:
                continue
            seen.add(cat_url)
            self.add_dir(
                html.unescape(title.strip()),
                cat_url,
                2,
                thumb.strip() if thumb else self.icons.get("categories", self.icon),
                self.fanart,
                context_menu=self._get_context_menu(),
            )

        next_url = None
        next_match = re.search(r'<a class=[\'"]next[\'"] href="([^"]+)"', html_content, re.IGNORECASE)
        if next_match:
            next_url = urllib.parse.urljoin(self.base_url, html.unescape(next_match.group(1).strip()))
        if next_url and next_url != url:
            self.add_dir("Next Page", next_url, 8, self.icons.get("default", self.icon))

        self.end_directory("videos")

    def process_pornstars(self, url):
        html_content = self.make_request(url)
        if not html_content:
            return self.end_directory("videos")

        pattern = re.compile(
            r'<div class="thumb item">\s*<a href="(https://saintporn\.com/models/[^"]+/)" title="([^"]+)".*?'
            r'<img[^>]+src="([^"]+)"',
            re.IGNORECASE | re.DOTALL,
        )

        seen = set()
        for star_url, title, thumb in pattern.findall(html_content):
            if star_url in seen:
                continue
            seen.add(star_url)
            self.add_dir(
                html.unescape(title.strip()),
                star_url,
                2,
                thumb.strip() if thumb else self.icons.get("pornstars", self.icon),
                self.fanart,
                context_menu=self._get_context_menu(),
            )

        next_url = None
        next_match = re.search(r'<a class=[\'"]next[\'"] href="([^"]+)"', html_content, re.IGNORECASE)
        if next_match:
            next_url = urllib.parse.urljoin(self.base_url, html.unescape(next_match.group(1).strip()))
        if next_url and next_url != url:
            self.add_dir("Next Page", next_url, 9, self.icons.get("default", self.icon))

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

    def _resolve_final_stream_url(self, stream_url, referer):
        if "/get_file/" not in stream_url:
            return stream_url

        headers = {
            "User-Agent": self.ua,
            "Referer": referer,
            "Origin": self.base_url,
            "Accept": "*/*",
        }
        try:
            response = self.session.head(stream_url, headers=headers, timeout=15, allow_redirects=True)
            if response.url and response.url.startswith("http"):
                return response.url
        except Exception as exc:
            self.logger.error("[SaintPorn] Final URL resolve failed for %s: %s", stream_url, exc)
        return stream_url

    def play_video(self, url):
        html_content = self.make_request(url)
        if not html_content:
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
            return

        video_url = None
        video_match = re.search(r"video_url\s*:\s*'([^']+)'", html_content)
        license_match = re.search(r"license_code\s*:\s*'([^']+)'", html_content)
        if video_match:
            video_url = html.unescape(video_match.group(1).replace("\\/", "/").strip())
            if license_match:
                video_url = kvs_decode_url(video_url, license_match.group(1).strip())

        if not video_url:
            source_match = re.search(r'<source[^>]+src="([^"]+)"', html_content, re.IGNORECASE)
            if source_match:
                video_url = html.unescape(source_match.group(1).replace("\\/", "/").strip())

        if not video_url or not video_url.startswith("http"):
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
            return

        video_url = self._resolve_final_stream_url(video_url, url)

        proxy_headers = {
            "User-Agent": self.ua,
            "Referer": url,
            "Origin": self.base_url,
            "Accept": "*/*",
            "Accept-Encoding": "identity",
            "Accept-Language": "en-US,en;q=0.9",
            "Connection": "keep-alive",
        }

        try:
            controller = ProxyController(
                upstream_url=video_url,
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
            self.logger.error("[SaintPorn] Proxy playback failed for %s: %s", video_url, exc)
            fallback_item = xbmcgui.ListItem(path=self._build_header_url(video_url, proxy_headers))
            fallback_item.setProperty("IsPlayable", "true")
            fallback_item.setMimeType("video/mp4")
            fallback_item.setContentLookup(False)
            xbmcplugin.setResolvedUrl(self.addon_handle, True, fallback_item)
