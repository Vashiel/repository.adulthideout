# -*- coding: utf-8 -*-
import html
import os
import re
import sys
import urllib.parse

import requests
import xbmc
import xbmcgui
import xbmcplugin

from resources.lib.base_website import BaseWebsite
from resources.lib.decoders.kvs_decoder import kvs_decode_url
from resources.lib.resilient_http import fetch_text


class BigTitsLust(BaseWebsite):
    def __init__(self, addon_handle, addon=None):
        super().__init__(
            name="bigtitslust",
            base_url="https://www.bigtitslust.com",
            search_url="https://www.bigtitslust.com/search/{}/",
            addon_handle=addon_handle,
            addon=addon,
        )
        self.session = requests.Session()
        self.ua = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/128.0.0.0 Safari/537.36"
        )
        try:
            import xbmcaddon

            addon_path = xbmcaddon.Addon().getAddonInfo("path")
            vendor_path = os.path.join(addon_path, "resources", "lib", "vendor")
            if vendor_path not in sys.path:
                sys.path.insert(0, vendor_path)
        except Exception:
            pass

        self._scraper = None
        try:
            import cloudscraper

            self._scraper = cloudscraper.create_scraper(
                browser={"browser": "chrome", "platform": "windows", "mobile": False}
            )
        except Exception:
            self._scraper = None

        self.sort_options = ["Latest", "Most Popular"]
        self.sort_paths = {
            "Latest": "/",
            "Most Popular": "/most-popular/",
        }

    def make_request(self, url, referer=None):
        headers = {
            "User-Agent": self.ua,
            "Referer": referer or (self.base_url + "/"),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }
        return fetch_text(
            url=url,
            headers=headers,
            scraper=self._scraper,
            logger=self.logger,
            timeout=20,
            use_windows_curl_fallback=True,
        )

    def _get_sort_key(self):
        try:
            idx = int(self.addon.getSetting("bigtitslust_sort_by") or "0")
        except Exception:
            idx = 0
        if not 0 <= idx < len(self.sort_options):
            idx = 0
        return self.sort_options[idx]

    def get_start_url_and_label(self):
        sort_key = self._get_sort_key()
        return urllib.parse.urljoin(self.base_url, self.sort_paths.get(sort_key, "/")), (
            "BigTitsLust [COLOR yellow]{}[/COLOR]".format(sort_key)
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

        self.addon.setSetting("bigtitslust_sort_by", str(idx))
        new_url, _ = self.get_start_url_and_label()
        xbmc.executebuiltin(
            "Container.Update({}?mode=2&website={}&url={})".format(
                sys.argv[0], self.name, urllib.parse.quote_plus(new_url)
            )
        )

    def _normalize_thumb(self, thumb):
        thumb = (thumb or "").strip()
        if not thumb or thumb.startswith("data:image/"):
            return self.icon
        if thumb.startswith("//"):
            return "https:" + thumb
        if thumb.startswith("/"):
            return urllib.parse.urljoin(self.base_url, thumb)
        return thumb

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
        self._render_listing(url, context_menu=context_menu)

    def _render_listing(self, url, context_menu=None):
        html_content = self.make_request(url)
        if not html_content:
            return self.end_directory("videos")

        seen = set()
        for block in re.split(r'<a href="https://www\.bigtitslust\.com/videos/', html_content, flags=re.IGNORECASE)[1:]:
            start_url = "https://www.bigtitslust.com/videos/" + block.split('"', 1)[0]
            title_match = re.search(r'title="([^"]+)"', block, re.IGNORECASE)
            alt_match = re.search(r'alt="([^"]+)"', block, re.IGNORECASE)
            thumb_data_original = re.search(r'data-original="([^"]+)"', block, re.IGNORECASE)
            thumb_src = re.search(r'<img[^>]+class="thumb[^"]*"[^>]+src="([^"]+)"', block, re.IGNORECASE)
            duration_match = re.search(r'<div class="duration">([^<]+)</div>', block, re.IGNORECASE)
            if not title_match:
                continue
            if start_url in seen:
                continue
            seen.add(start_url)
            alt_text = alt_match.group(1) if alt_match else ""
            title = html.unescape((title_match.group(1) or alt_text).strip())
            if not title:
                continue
            thumb_url = ""
            if thumb_data_original:
                thumb_url = thumb_data_original.group(1)
            elif thumb_src:
                thumb_url = thumb_src.group(1)
            info = {"title": title, "plot": title}
            duration_seconds = self.convert_duration((duration_match.group(1) if duration_match else "").strip())
            if duration_seconds:
                info["duration"] = duration_seconds
            self.add_link(
                title,
                start_url,
                4,
                self._normalize_thumb(thumb_url),
                self.fanart,
                context_menu=context_menu,
                info_labels=info,
            )

        next_url = None
        next_match = re.search(r'<a[^>]+href="([^"]+)"[^>]*>Next<', html_content, re.IGNORECASE)
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
            r'<a class="item" href="(https://www\.bigtitslust\.com/categories/[^"]+/)" title="([^"]+)">',
            re.IGNORECASE,
        )
        seen = set()
        for cat_url, title in pattern.findall(html_content):
            if cat_url in seen:
                continue
            seen.add(cat_url)
            self.add_dir(html.unescape(title.strip()), cat_url, 2, self.icons.get("categories", self.icon), self.fanart, context_menu=self._get_context_menu())

        self.end_directory("videos")

    def search(self, query):
        if not query:
            return
        self.process_content(self.search_url.format(urllib.parse.quote(query)))

    def _build_header_url(self, stream_url, headers):
        return stream_url + "|" + urllib.parse.urlencode(headers)

    def play_video(self, url):
        html_content = self.make_request(url)
        if not html_content:
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
            return

        video_url = None
        video_match = re.search(r"video_url\s*:\s*'([^']+)'", html_content, re.IGNORECASE)
        license_match = re.search(r"license_code\s*:\s*'([^']+)'", html_content, re.IGNORECASE)
        if video_match:
            video_url = html.unescape(video_match.group(1).replace("\\/", "/").strip())
            if license_match:
                video_url = kvs_decode_url(video_url, license_match.group(1).strip())

        if not video_url or not video_url.startswith("http"):
            fallback_match = re.search(r'(https://www\.bigtitslust\.com/get_file/[^"\']+\.mp4[^"\']*)', html_content, re.IGNORECASE)
            if fallback_match:
                video_url = html.unescape(fallback_match.group(1).replace("&amp;", "&"))

        if not video_url or not video_url.startswith("http"):
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
            return

        headers = {
            "User-Agent": self.ua,
            "Referer": url,
            "Origin": self.base_url,
            "Accept": "*/*",
            "Accept-Language": "en-US,en;q=0.9",
            "Connection": "keep-alive",
        }

        list_item = xbmcgui.ListItem(path=self._build_header_url(video_url, headers))
        list_item.setProperty("IsPlayable", "true")
        list_item.setMimeType("video/mp4")
        list_item.setContentLookup(False)
        xbmcplugin.setResolvedUrl(self.addon_handle, True, list_item)
