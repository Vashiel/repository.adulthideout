#!/usr/bin/env python

import json
import logging
import sys
import urllib.parse
from urllib import request

import xbmc
import xbmcgui
import xbmcplugin

from resources.lib.base_website import BaseWebsite
from resources.lib.decoders.txxx_decoder import TxxxDecoder


class Hdzog(BaseWebsite):
    def __init__(self, addon_handle):
        super().__init__("hdzog", "https://hdzog.com/", "https://hdzog.com/search/{}", addon_handle)

        self.label = "HDZog"
        self.logger.setLevel(logging.WARNING)

        self.sort_options = [
            "Most Popular",
            "Latest Updates",
            "Top Rated",
            "Most Viewed",
            "Longest",
        ]
        self.sort_paths = {
            "Most Popular": "most-popular",
            "Latest Updates": "latest-updates",
            "Top Rated": "top-rated",
            "Most Viewed": "most-viewed",
            "Longest": "longest",
        }
        self.headers = {
            "Accept": "application/json, text/plain, */*",
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/126.0.0.0 Safari/537.36"
            ),
            "X-Requested-With": "XMLHttpRequest",
        }
        self.api_filter = "str"
        self.txxx_decoder = TxxxDecoder()

    def get_start_url_and_label(self):
        setting_id = f"{self.name}_sort_by"
        try:
            sort_idx = int(self.addon.getSetting(setting_id))
        except Exception:
            sort_idx = 0
        if not 0 <= sort_idx < len(self.sort_options):
            sort_idx = 0

        sort_key = self.sort_options[sort_idx]
        sort_path = self.sort_paths.get(sort_key, "most-popular")
        return urllib.parse.urljoin(self.base_url, sort_path), f"{self.label} [COLOR yellow]{sort_key}[/COLOR]"

    def _get_context_menu(self, current_url):
        return [
            (
                "Sort by...",
                "RunPlugin({}?mode=7&website={}&action=select_sort&original_url={})".format(
                    sys.argv[0], self.name, urllib.parse.quote_plus(current_url)
                ),
            )
        ]

    def _get_json(self, url, headers=None):
        try:
            req = request.Request(url, headers=headers or self.headers)
            with request.urlopen(req, timeout=20) as response:
                if response.getcode() == 200:
                    return json.loads(response.read().decode("utf-8"))
        except Exception as exc:
            self.logger.error("HDZog JSON request failed for %s: %s", url, exc)
        return None

    def select_sort(self, original_url=None):
        setting_id = f"{self.name}_sort_by"
        try:
            current_idx = int(self.addon.getSetting(setting_id))
        except Exception:
            current_idx = 0
        if not 0 <= current_idx < len(self.sort_options):
            current_idx = 0

        selected_idx = xbmcgui.Dialog().select("Sort by...", self.sort_options, preselect=current_idx)
        if selected_idx == -1 or selected_idx == current_idx:
            return

        self.addon.setSetting(setting_id, str(selected_idx))
        new_start_url, _ = self.get_start_url_and_label()
        xbmc.executebuiltin(
            "Container.Update({}?mode=2&website={}&url={},replace)".format(
                sys.argv[0], self.name, urllib.parse.quote_plus(new_start_url)
            )
        )

    def _add_static_dirs(self, current_url):
        context_menu = self._get_context_menu(current_url)
        self.add_dir(
            "[COLOR blue]Search HDZog[/COLOR]",
            "",
            5,
            icon=self.icons["search"],
            context_menu=context_menu,
            name_param=self.name,
        )
        self.add_dir(
            "[COLOR blue]Categories[/COLOR]",
            urllib.parse.urljoin(self.base_url, "categories/"),
            8,
            icon=self.icons["categories"],
            context_menu=context_menu,
        )

    def process_content(self, url):
        parsed_url = urllib.parse.urlparse(url)
        path = parsed_url.path.strip("/")

        is_category = path.startswith("categories/")
        is_search = path.startswith("search/")
        is_main_page = not is_category and not is_search

        if is_main_page:
            self._add_static_dirs(url)

        path_parts = [part for part in path.split("/") if part]
        page = "1"
        if path_parts and path_parts[-1].isdigit():
            page = path_parts.pop()

        sort_order = "most-popular"
        if is_main_page and path_parts:
            sort_order = path_parts[0]
        elif not is_main_page:
            try:
                sort_idx = int(self.addon.getSetting(f"{self.name}_sort_by"))
            except Exception:
                sort_idx = 0
            if 0 <= sort_idx < len(self.sort_options):
                sort_order = self.sort_paths.get(self.sort_options[sort_idx], "most-popular")

        path_for_paging = "/".join(path_parts) if not is_main_page else sort_order
        filter_string = f"..{page}.all..day"
        timeframe = "14400"

        if is_category and len(path_parts) > 1:
            filter_string = "categories.{}.{}.all..day".format(path_parts[1], page)
        elif is_search:
            timeframe = "259200"
            query_part = path_parts[1] if len(path_parts) > 1 else ""
            api_url = (
                f"{self.base_url}api/videos2.php?params="
                f"{timeframe}/{self.api_filter}/relevance/60/search..{page}.all..&s="
                f"{urllib.parse.quote_plus(query_part)}"
            )

        if "api_url" not in locals():
            api_url = (
                f"{self.base_url}api/json/videos2/{timeframe}/{self.api_filter}/"
                f"{sort_order}/60/{filter_string}.json"
            )

        data = self._get_json(api_url)
        if not data or "videos" not in data:
            return self.end_directory()

        context_menu = self._get_context_menu(url)

        for video in data.get("videos", []):
            title = video.get("title", "Unknown Title")
            thumbnail = video.get("scr", self.icon)
            video_dir = video.get("dir")
            video_id = video.get("video_id")
            if not (video_id and video_dir):
                continue

            duration_str = "00:00"
            seconds = 0
            try:
                parts = video.get("duration", "0:0").split(":")
                if len(parts) == 2:
                    seconds = int(parts[0]) * 60 + int(parts[1])
                    duration_str = f"{int(parts[0]):02}:{int(parts[1]):02}"
                elif len(parts) == 3:
                    seconds = int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
                    duration_str = f"{int(parts[0]):02}:{int(parts[1]):02}:{int(parts[2]):02}"
            except Exception:
                pass

            label = f"{title} [COLOR lime]({duration_str})[/COLOR]"
            play_data = json.dumps(
                {
                    "video_id": video_id,
                    "dir": video_dir,
                    "title": title,
                    "thumbnail": thumbnail,
                    "base_url": self.base_url,
                }
            )
            self.add_link(
                name=label,
                url=play_data,
                mode=4,
                icon=thumbnail,
                fanart=self.fanart,
                context_menu=context_menu,
            )

        current_page = int(data.get("params", {}).get("page", 1))
        total_pages = int(data.get("pages", 1))
        if current_page < total_pages:
            next_page_url = urllib.parse.urljoin(self.base_url, f"{path_for_paging}/{current_page + 1}")
            self.add_dir(
                name="[COLOR cyan]>> Next Page[/COLOR]",
                url=next_page_url,
                mode=2,
                icon=self.icons["default"],
                context_menu=context_menu,
            )

        self.end_directory()

    def process_categories(self, url):
        data = self._get_json(f"{self.base_url}api/json/categories/14400/{self.api_filter}.all.en.json")
        if not data or "categories" not in data:
            return self.end_directory()

        context_menu = self._get_context_menu(url)
        for category in sorted(data.get("categories", []), key=lambda item: item.get("title", "")):
            title = category.get("title")
            cat_dir = category.get("dir")
            if not (title and cat_dir):
                continue
            self.add_dir(
                name=title,
                url=f"{self.base_url}categories/{cat_dir}/",
                mode=2,
                icon=self.icons["categories"],
                context_menu=context_menu,
            )

        self.end_directory()

    def play_video(self, url):
        try:
            video_data = json.loads(url)
        except Exception:
            self.notify_error("Invalid video data.")
            return

        video_id = video_data.get("video_id")
        video_dir = video_data.get("dir")
        title = video_data.get("title", "HDZog")
        thumbnail = video_data.get("thumbnail", self.icon)
        base_url = video_data.get("base_url", self.base_url)
        if not (video_id and video_dir):
            self.notify_error("Missing video information.")
            return

        video_page_url = f"{base_url}videos/{video_id}/{video_dir}/"
        req_headers = dict(self.headers)
        req_headers["Referer"] = video_page_url
        stream_info = self._get_json(
            f"{base_url}api/videofile.php?video_id={video_id}&lifetime=8640000",
            headers=req_headers,
        )
        if not stream_info or not isinstance(stream_info, list) or "video_url" not in stream_info[0]:
            self.notify_error("No playable streams found.")
            return

        stream_url = self.txxx_decoder.decode_stream_url(
            stream_info[0]["video_url"], base_url, video_page_url, self.logger
        )
        if not stream_url:
            self.notify_error("Error decoding video link.")
            return

        list_item = xbmcgui.ListItem(title, path=stream_url)
        list_item.setArt({"thumb": thumbnail, "icon": "DefaultVideo.png"})
        list_item.setProperty("IsPlayable", "true")
        if ".m3u8" in stream_url:
            list_item.setMimeType("application/vnd.apple.mpegurl")
            list_item.setProperty("inputstream", "inputstream.adaptive")
            list_item.setProperty("inputstream.adaptive.manifest_type", "hls")
        elif ".mp4" in stream_url:
            list_item.setMimeType("video/mp4")
        xbmcplugin.setResolvedUrl(self.addon_handle, True, listitem=list_item)

    def search(self, query):
        if query:
            super().search(query)
