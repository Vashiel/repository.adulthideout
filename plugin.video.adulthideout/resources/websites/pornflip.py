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


class Pornflip(BaseWebsite):
    def __init__(self, addon_handle, addon=None):
        super().__init__(
            name="pornflip",
            base_url="https://www.pornflip.com",
            search_url="https://www.pornflip.com/search?q={}",
            addon_handle=addon_handle,
            addon=addon,
        )
        self.session = requests.Session()
        self.ua = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/126.0.0.0 Safari/537.36"
        )
        self.sort_options = ["Latest", "Trending"]
        self.sort_paths = {
            "Latest": "/",
            "Trending": "/Trending-Porn",
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
            self.logger.error("[PornFlip] HTTP %s for %s", response.status_code, url)
        except Exception as exc:
            self.logger.error("[PornFlip] Request error: %s", exc)
        return None

    def _get_sort_key(self):
        try:
            idx = int(self.addon.getSetting("pornflip_sort_by") or "0")
        except Exception:
            idx = 0
        if not 0 <= idx < len(self.sort_options):
            idx = 0
        return self.sort_options[idx]

    def get_start_url_and_label(self):
        sort_key = self._get_sort_key()
        return urllib.parse.urljoin(self.base_url, self.sort_paths.get(sort_key, "/")), (
            "PornFlip [COLOR yellow]{}[/COLOR]".format(sort_key)
        )

    def _get_context_menu(self):
        return [
            (
                "Sort by...",
                "RunPlugin({}?mode=7&action=select_sort_order&website={})".format(sys.argv[0], self.name),
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

        self.addon.setSetting("pornflip_sort_by", str(idx))
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
            urllib.parse.urljoin(self.base_url, "/categories"),
            8,
            self.icons.get("categories", self.icon),
            context_menu=context_menu,
        )
        self.add_dir(
            "Pornstars",
            urllib.parse.urljoin(self.base_url, "/pornstars"),
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
            r'<div class="card thumbs_rotate itemVideo[^"]*"[^>]*>.*?'
            r'<a href="(/[^"]+)"[^>]*>\s*'
            r'<img class="card-img-top" src="([^"]+)" alt="([^"]+)".*?'
            r'<span class="duration">([^<]+)</span>.*?'
            r'<h5 class="card-title">\s*<a href="/[^"]+">([^<]+)</a>',
            re.IGNORECASE | re.DOTALL,
        )

        seen = set()
        for href, thumb, alt_text, duration, title_text in pattern.findall(html_content):
            video_url = urllib.parse.urljoin(self.base_url, href.strip())
            if video_url in seen:
                continue
            seen.add(video_url)

            title = html.unescape((title_text or alt_text).strip())
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

        next_url = None
        next_match = re.search(r'<link rel="next" href="([^"]+)"', html_content, re.IGNORECASE)
        if not next_match:
            next_match = re.search(r'<a[^>]+href="([^"]+)"[^>]*rel="next"', html_content, re.IGNORECASE)
        if not next_match:
            next_match = re.search(r'<a[^>]+href="([^"]*page=\d+[^"]*)"[^>]*>\s*Next\s*</a>', html_content, re.IGNORECASE)
        if next_match:
            next_url = urllib.parse.urljoin(self.base_url, html.unescape(next_match.group(1).strip()))

        if next_url and next_url != url:
            self.add_dir("Next Page", next_url, 2, self.icons.get("default", self.icon), context_menu=context_menu)

        self.end_directory("videos")

    def process_categories(self, url):
        html_content = self.make_request(url)
        if not html_content:
            return self.end_directory("videos")

        pattern = re.compile(r'<a href="(/(?:lesbian/)?category/[^"]+)">([^<]+)</a>', re.IGNORECASE)
        seen = set()
        for href, title in pattern.findall(html_content):
            cat_url = urllib.parse.urljoin(self.base_url, href.strip())
            if cat_url in seen:
                continue
            seen.add(cat_url)
            label = html.unescape(title.strip())
            self.add_dir(label, cat_url, 2, self.icons.get("categories", self.icon))

        self.end_directory("videos")

    def process_pornstars(self, url):
        html_content = self.make_request(url)
        if not html_content:
            return self.end_directory("videos")

        pattern = re.compile(
            r'<img class="card-img-top" src="([^"]+)" alt="([^"]+)".*?'
            r'<h5 class="card-title">\s*<a href="(/pornstar/[^"]+)">\s*([^<]+)\s*</a>',
            re.IGNORECASE | re.DOTALL,
        )
        seen = set()
        for thumb, alt_text, href, title_text in pattern.findall(html_content):
            star_url = urllib.parse.urljoin(self.base_url, href.strip())
            if star_url in seen:
                continue
            seen.add(star_url)
            label = html.unescape((title_text or alt_text).strip())
            if thumb.startswith("//"):
                thumb = "https:" + thumb
            elif thumb.startswith("/"):
                thumb = urllib.parse.urljoin(self.base_url, thumb)
            self.add_dir(label, star_url, 2, thumb or self.icons.get("pornstars", self.icon))

        next_url = None
        next_match = re.search(r'<link rel="next" href="([^"]+)"', html_content, re.IGNORECASE)
        if not next_match:
            next_match = re.search(r'<a[^>]+href="([^"]+)"[^>]*rel="next"', html_content, re.IGNORECASE)
        if next_match:
            next_url = urllib.parse.urljoin(self.base_url, html.unescape(next_match.group(1).strip()))

        if next_url and next_url != url:
            self.add_dir("Next Page", next_url, 9, self.icons.get("default", self.icon))

        self.end_directory("videos")

    def search(self, query):
        if not query:
            return
        search_url = self.search_url.format(urllib.parse.quote(query))
        self.process_content(search_url)

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

    def _select_variant_playlist(self, master_url, headers):
        try:
            response = self.session.get(master_url, headers=headers, timeout=20)
            if response.status_code != 200:
                return master_url

            variants = []
            current_resolution = 0
            pending_resolution = None
            for raw_line in response.text.splitlines():
                line = raw_line.strip()
                if not line:
                    continue
                if line.startswith("#EXT-X-STREAM-INF:"):
                    match = re.search(r"RESOLUTION=\d+x(\d+)", line, re.IGNORECASE)
                    pending_resolution = int(match.group(1)) if match else 0
                    continue
                if line.startswith("#"):
                    continue
                variant_url = urllib.parse.urljoin(master_url, line)
                variants.append((pending_resolution or 0, variant_url))
                pending_resolution = None

            if not variants:
                return master_url

            # Prefer 480p/360p for faster startup in Kodi while staying watchable.
            preferred = [item for item in variants if item[0] in (480, 360)]
            if preferred:
                preferred.sort(key=lambda item: abs(item[0] - 480))
                return preferred[0][1]

            variants.sort(key=lambda item: item[0] or 99999)
            return variants[-1][1]
        except Exception as exc:
            self.logger.error("[PornFlip] Variant selection error: %s", exc)
            return master_url

    def play_video(self, url):
        html_content = self.make_request(url)
        if not html_content:
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
            return

        source_match = re.search(r'<source[^>]+src="([^"]+master\.m3u8[^"]*)"', html_content, re.IGNORECASE)
        if not source_match:
            source_match = re.search(r'(https://[^"\']+master\.m3u8[^"\']*)', html_content, re.IGNORECASE)
        if not source_match:
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
            return

        stream_url = html.unescape(source_match.group(1).strip()).replace("&amp;", "&")
        headers = {
            "User-Agent": self.ua,
            "Referer": url,
            "Origin": self.base_url,
            "Accept": "*/*",
            "Accept-Language": "en-US,en;q=0.9",
            "Connection": "keep-alive",
        }
        stream_url = self._select_variant_playlist(stream_url, headers)
        playback_url = self._build_header_url(stream_url, headers)

        list_item = xbmcgui.ListItem(path=playback_url)
        list_item.setProperty("IsPlayable", "true")
        list_item.setMimeType("application/vnd.apple.mpegurl")
        list_item.setContentLookup(False)
        xbmcplugin.setResolvedUrl(self.addon_handle, True, list_item)
