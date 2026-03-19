# -*- coding: utf-8 -*-
import html
import json
import re
import sys
import urllib.parse

import requests
import xbmc
import xbmcgui
import xbmcplugin

from resources.lib.base_website import BaseWebsite
from resources.lib.proxy_utils import PlaybackGuard, ProxyController
from resources.lib.resilient_http import fetch_text


class Thumbzilla(BaseWebsite):
    def __init__(self, addon_handle, addon=None):
        super().__init__(
            name="thumbzilla",
            base_url="https://www.thumbzilla.com",
            search_url="https://www.thumbzilla.com/search/?query={}",
            addon_handle=addon_handle,
            addon=addon,
        )
        self.session = requests.Session()
        self.ua = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/126.0.0.0 Safari/537.36"
        )
        self.content_options = ["Straight", "Gay"]
        self.sort_options = ["Most Recent", "Most Viewed", "Top Rated"]

    def make_request(self, url, referer=None):
        headers = {
            "User-Agent": self.ua,
            "Referer": referer or (self.base_url + "/"),
        }
        return fetch_text(
            url,
            headers=headers,
            scraper=self.session,
            logger=self.logger,
            timeout=20,
        )

    def _get_content_key(self):
        try:
            idx = int(self.addon.getSetting("thumbzilla_content_type") or "0")
        except Exception:
            idx = 0
        if not 0 <= idx < len(self.content_options):
            idx = 0
        return self.content_options[idx]

    def _get_sort_key(self):
        try:
            idx = int(self.addon.getSetting("thumbzilla_sort_by") or "0")
        except Exception:
            idx = 0
        if not 0 <= idx < len(self.sort_options):
            idx = 0
        return self.sort_options[idx]

    def _get_listing_base(self):
        content_prefix = "/gay" if self._get_content_key() == "Gay" else ""
        sort_suffix = {
            "Most Recent": "/",
            "Most Viewed": "/most_viewed/",
            "Top Rated": "/top_rated/",
        }.get(self._get_sort_key(), "/")
        return urllib.parse.urljoin(self.base_url, content_prefix + sort_suffix)

    def _get_categories_url(self):
        return urllib.parse.urljoin(
            self.base_url,
            "/gay/categories/" if self._get_content_key() == "Gay" else "/categories/",
        )

    def _get_search_url(self, query):
        encoded = urllib.parse.quote_plus(query)
        if self._get_content_key() == "Gay":
            return f"{self.base_url}/gay/search/?query={encoded}"
        return self.search_url.format(encoded)

    def get_start_url_and_label(self):
        content_key = self._get_content_key()
        sort_key = self._get_sort_key()
        return self._get_listing_base(), f"Thumbzilla [COLOR yellow]({content_key} - {sort_key})[/COLOR]"

    def _get_context_menu(self):
        return [
            (
                "Select Content",
                f"RunPlugin({sys.argv[0]}?mode=7&action=select_content_type&website={self.name})",
            ),
            (
                "Sort by...",
                f"RunPlugin({sys.argv[0]}?mode=7&action=select_sort_order&website={self.name})",
            ),
        ]

    def _add_main_dirs(self, context_menu):
        self.add_dir("Search", "", 5, self.icons.get("search", self.icon), context_menu=context_menu)
        self.add_dir(
            "Categories",
            self._get_categories_url(),
            8,
            self.icons.get("categories", self.icon),
            context_menu=context_menu,
        )

    def select_content_type(self, original_url=None):
        try:
            preselect_idx = self.content_options.index(self._get_content_key())
        except ValueError:
            preselect_idx = 0

        idx = xbmcgui.Dialog().select("Content Type...", self.content_options, preselect=preselect_idx)
        if idx == -1:
            return

        self.addon.setSetting("thumbzilla_content_type", str(idx))
        new_url, _ = self.get_start_url_and_label()
        xbmc.executebuiltin(
            f"Container.Update({sys.argv[0]}?mode=2&website={self.name}&url={urllib.parse.quote_plus(new_url)})"
        )

    def select_sort_order(self, original_url=None):
        try:
            preselect_idx = self.sort_options.index(self._get_sort_key())
        except ValueError:
            preselect_idx = 0

        idx = xbmcgui.Dialog().select("Sort by...", self.sort_options, preselect=preselect_idx)
        if idx == -1:
            return

        self.addon.setSetting("thumbzilla_sort_by", str(idx))
        new_url, _ = self.get_start_url_and_label()
        xbmc.executebuiltin(
            f"Container.Update({sys.argv[0]}?mode=2&website={self.name}&url={urllib.parse.quote_plus(new_url)})"
        )

    def search(self, query):
        if not query:
            return
        self.process_content(self._get_search_url(query))

    def process_content(self, url):
        if not url or url == "BOOTSTRAP":
            url, _ = self.get_start_url_and_label()

        context_menu = self._get_context_menu()
        self._add_main_dirs(context_menu)
        self._list_videos(url, context_menu=context_menu)

    def _list_videos(self, url, context_menu=None):
        content = self.make_request(url)
        if not content:
            return self.end_directory("videos")

        blocks = re.split(r'<div class="video-box[^"]*"', content)[1:]
        seen = set()

        for block in blocks:
            url_match = re.search(r'<a href="(/watch/\d+/)"', block, re.IGNORECASE)
            title_match = re.search(
                r'class="video-title-text[^"]*"[^>]*>\s*<span>([^<]+)</span>',
                block,
                re.IGNORECASE | re.DOTALL,
            )
            if not title_match:
                title_match = re.search(r'alt="([^"]+)"', block, re.IGNORECASE)
            if not (url_match and title_match):
                continue

            video_url = urllib.parse.urljoin(self.base_url, url_match.group(1))
            if video_url in seen:
                continue
            seen.add(video_url)

            thumb_match = re.search(r'data-src="([^"]+)"', block, re.IGNORECASE)
            if not thumb_match:
                thumb_match = re.search(r'data-poster="([^"]+)"', block, re.IGNORECASE)
            duration_match = re.search(
                r'<div class="video-duration[^"]*">\s*<span>\s*([^<]+)\s*</span>',
                block,
                re.IGNORECASE | re.DOTALL,
            )

            title = html.unescape(title_match.group(1).strip())
            thumb = thumb_match.group(1).strip() if thumb_match else ""
            if thumb.startswith("//"):
                thumb = "https:" + thumb
            elif thumb.startswith("/"):
                thumb = urllib.parse.urljoin(self.base_url, thumb)

            info = {"title": title, "plot": title}
            duration = duration_match.group(1).strip() if duration_match else ""
            duration_seconds = self.convert_duration(duration)
            if duration_seconds:
                info["duration"] = duration_seconds

            self.add_link(
                title,
                video_url,
                4,
                thumb or self.icon,
                self.fanart,
                info_labels=info,
                context_menu=context_menu,
            )

        next_match = re.search(r'rel="next"\s+href="([^"]+)"', content, re.IGNORECASE)
        if next_match:
            next_url = html.unescape(next_match.group(1).strip())
            self.add_dir("Next Page", next_url, 2, self.icons.get("default", self.icon), context_menu=context_menu)

        self.end_directory("videos")

    def process_categories(self, url):
        categories_url = self._get_categories_url()
        if url != categories_url:
            return self._list_videos(url, context_menu=self._get_context_menu())

        content = self.make_request(categories_url)
        if not content:
            return self.end_directory("videos")

        seen = set()
        for path, title in re.findall(
            r'<a class="menu_elem_text" href="(/(?:gay/)?category/[^"]+/)">\s*<span>([^<]+)</span>',
            content,
            re.IGNORECASE | re.DOTALL,
        ):
            full_url = urllib.parse.urljoin(self.base_url, path)
            if full_url in seen:
                continue
            seen.add(full_url)
            self.add_dir(html.unescape(title.strip()), full_url, 2, self.icons.get("categories", self.icon))

        self.end_directory("videos")

    def _resolve_media_list(self, watch_url):
        page_html = self.make_request(watch_url, referer=self.base_url + "/")
        if not page_html:
            return []

        match = re.search(r'mediaDefinitions":(\[.*?\])', page_html, re.IGNORECASE | re.DOTALL)
        if not match:
            return []

        try:
            definitions = json.loads(match.group(1).replace("\\/", "/"))
        except Exception:
            return []

        api_headers = {
            "User-Agent": self.ua,
            "Referer": watch_url,
            "X-Requested-With": "XMLHttpRequest",
        }

        resolved = []
        for item in definitions:
            api_url = item.get("videoUrl")
            fmt = (item.get("format") or "").lower()
            if not api_url:
                continue
            try:
                response_text = self.make_request(api_url, referer=watch_url)
                entries = json.loads(response_text.replace("\\/", "/")) if response_text else []
            except Exception:
                entries = []

            for entry in entries:
                stream_url = entry.get("videoUrl")
                if not stream_url:
                    continue
                quality = entry.get("quality") or "0"
                try:
                    quality_num = int(re.sub(r"\D", "", str(quality)) or "0")
                except Exception:
                    quality_num = 0
                resolved.append(
                    {
                        "format": fmt,
                        "quality": quality_num,
                        "default": bool(entry.get("defaultQuality")),
                        "url": html.unescape(stream_url),
                        "headers": api_headers,
                    }
                )

        return resolved

    def play_video(self, url):
        media_entries = self._resolve_media_list(url)
        if not media_entries:
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
            return

        mp4_entries = [item for item in media_entries if item["format"] == "mp4"]
        hls_entries = [item for item in media_entries if item["format"] == "hls"]

        chosen = None
        if mp4_entries:
            chosen = next((item for item in mp4_entries if item["default"]), None)
            if not chosen:
                mp4_entries.sort(key=lambda item: item["quality"], reverse=True)
                chosen = mp4_entries[0]
        elif hls_entries:
            hls_entries.sort(key=lambda item: item["quality"], reverse=True)
            chosen = hls_entries[0]

        if not chosen:
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
            return

        if chosen["format"] == "mp4":
            controller = ProxyController(
                upstream_url=chosen["url"],
                upstream_headers=chosen["headers"],
                cookies=None,
                use_urllib=True,
            )
            local_url = controller.start()
            list_item = xbmcgui.ListItem(path=local_url)
            list_item.setProperty("IsPlayable", "true")
            list_item.setMimeType("video/mp4")
            list_item.setContentLookup(False)
            xbmcplugin.setResolvedUrl(self.addon_handle, True, list_item)

            player = xbmc.Player()
            monitor = xbmc.Monitor()
            PlaybackGuard(player, monitor, local_url, controller).start()
            return

        header_str = urllib.parse.urlencode(chosen["headers"])
        list_item = xbmcgui.ListItem(path=f"{chosen['url']}|{header_str}")
        list_item.setProperty("IsPlayable", "true")
        list_item.setMimeType("application/vnd.apple.mpegurl")
        list_item.setContentLookup(False)
        xbmcplugin.setResolvedUrl(self.addon_handle, True, list_item)
