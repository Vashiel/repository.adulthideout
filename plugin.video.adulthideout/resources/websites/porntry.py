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


class Porntry(BaseWebsite):
    def __init__(self, addon_handle, addon=None):
        super().__init__(
            name="porntry",
            base_url="https://www.porntry.com",
            search_url="https://www.porntry.com/search/{}/",
            addon_handle=addon_handle,
            addon=addon,
        )
        self.session = requests.Session()
        self.ua = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/126.0.0.0 Safari/537.36"
        )
        self.sort_options = ["Latest", "Top Rated", "Most Viewed"]
        self.sort_paths = {
            "Latest": "/",
            "Top Rated": "/top-rated/",
            "Most Viewed": "/most-popular/",
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
            self.logger.error("[PornTry] HTTP %s for %s", response.status_code, url)
        except Exception as exc:
            self.logger.error("[PornTry] Request error: %s", exc)
        return None

    def _get_sort_key(self):
        try:
            idx = int(self.addon.getSetting("porntry_sort_by") or "0")
        except Exception:
            idx = 0
        if not 0 <= idx < len(self.sort_options):
            idx = 0
        return self.sort_options[idx]

    def get_start_url_and_label(self):
        sort_key = self._get_sort_key()
        return urllib.parse.urljoin(self.base_url, self.sort_paths.get(sort_key, "/")), (
            "PornTry [COLOR yellow]{}[/COLOR]".format(sort_key)
        )

    def _get_context_menu(self, original_url=None):
        suffix = ""
        if original_url:
            suffix = "&original_url={}".format(urllib.parse.quote_plus(original_url))
        return [
            (
                "Sort by...",
                "RunPlugin({}?mode=7&action=select_sort_order&website={}{} )".format(
                    sys.argv[0], self.name, suffix
                ).replace(" )", ")"),
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

        self.addon.setSetting("porntry_sort_by", str(idx))
        new_url, _ = self.get_start_url_and_label()
        xbmc.executebuiltin(
            "Container.Update({}?mode=2&website={}&url={})".format(
                sys.argv[0], self.name, urllib.parse.quote_plus(new_url)
            )
        )

    def process_content(self, url):
        if not url or url == "BOOTSTRAP":
            url, _ = self.get_start_url_and_label()

        context_menu = self._get_context_menu(url)
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
            r'<div class="thumb item [^"]*">.*?'
            r'<a href="(https://www\.porntry\.com/videos/\d+/[^"]+/)" class="thumb__top[^"]*">.*?'
            r'<img src="([^"]+)" alt="([^"]+)">.*?'
            r'<span class="thumb__duration">([^<]+)</span>.*?'
            r'<div class="thumb__title">\s*<span>([^<]+)</span>',
            re.IGNORECASE | re.DOTALL,
        )

        seen = set()
        for video_url, thumb, alt_text, duration, title_text in pattern.findall(html_content):
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
        next_match = re.search(
            r'<a class="pagination__link" href="([^"]+)">\s*Next\s*</a>', html_content, re.IGNORECASE
        )
        if not next_match:
            next_match = re.search(r'<a href="([^"]+)"[^>]*>\s*Next\s*</a>', html_content, re.IGNORECASE)
        if next_match:
            next_url = urllib.parse.urljoin(self.base_url, html.unescape(next_match.group(1).strip()))

        if next_url and next_url != url:
            self.add_dir("Next Page", next_url, 2, self.icons.get("default", self.icon), context_menu=context_menu)

        self.end_directory("videos")

    def process_categories(self, url):
        html_content = self.make_request(url)
        if not html_content:
            return self.end_directory("videos")

        pattern = re.compile(r'<a[^>]+href="(/categories/[^"]+/)"[^>]*>([^<]+)</a>', re.IGNORECASE)
        seen = set()
        for href, title in pattern.findall(html_content):
            label = html.unescape(" ".join(title.split()))
            if not label or label.isdigit() or len(label) > 40:
                continue
            cat_url = urllib.parse.urljoin(self.base_url, href.strip())
            if cat_url in seen:
                continue
            seen.add(cat_url)
            self.add_dir(label, cat_url, 2, self.icons.get("categories", self.icon))

        self.end_directory("videos")

    def process_pornstars(self, url):
        html_content = self.make_request(url)
        if not html_content:
            return self.end_directory("videos")

        pattern = re.compile(
            r'<a href="(https://www\.porntry\.com/models/[^"]+/)"[^>]*title="([^"]+)"[^>]*>.*?'
            r'<img[^>]+src="([^"]+)"[^>]+alt="([^"]+)"',
            re.IGNORECASE | re.DOTALL,
        )
        seen = set()
        for star_url, title_attr, thumb, alt_text in pattern.findall(html_content):
            if star_url in seen:
                continue
            seen.add(star_url)
            label = html.unescape(" ".join((title_attr or alt_text or "").split()))
            if not label:
                continue
            if thumb.startswith("//"):
                thumb = "https:" + thumb
            elif thumb.startswith("/"):
                thumb = urllib.parse.urljoin(self.base_url, thumb)
            self.add_dir(label, star_url, 2, thumb or self.icons.get("pornstars", self.icon))

        next_url = None
        next_match = re.search(
            r'<a class="pagination__link" href="([^"]+)">\s*Next\s*</a>', html_content, re.IGNORECASE
        )
        if not next_match:
            next_match = re.search(r'<a href="([^"]+)"[^>]*>\s*Next\s*</a>', html_content, re.IGNORECASE)
        if next_match:
            next_url = urllib.parse.urljoin(self.base_url, html.unescape(next_match.group(1).strip()))

        if next_url and next_url != url:
            self.add_dir("Next Page", next_url, 9, self.icons.get("default", self.icon))

        self.end_directory("videos")

    def search(self, query):
        if not query:
            return
        self.process_content(self.search_url.format(urllib.parse.quote(query)))

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

        source_match = re.search(r'<source[^>]+src="([^"]+\.mp4/?)"', html_content, re.IGNORECASE)
        if not source_match:
            source_match = re.search(r'(https://www\.porntry\.com/get_file/[^"\']+\.mp4/?)', html_content, re.IGNORECASE)
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
        playback_url = self._build_header_url(stream_url, headers)

        list_item = xbmcgui.ListItem(path=playback_url)
        list_item.setProperty("IsPlayable", "true")
        list_item.setMimeType("video/mp4")
        list_item.setContentLookup(False)
        xbmcplugin.setResolvedUrl(self.addon_handle, True, list_item)
