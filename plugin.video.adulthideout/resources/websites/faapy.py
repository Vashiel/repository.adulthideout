#!/usr/bin/env python
# -*- coding: utf-8 -*-

import re
import urllib.parse

from resources.lib.kvs_tube import KVSTubeWebsite


class Faapy(KVSTubeWebsite):
    label = "Faapy"
    sort_options = ["Latest", "Most Viewed", "Top Rated"]
    sort_paths = {
        "Latest": "/latest-updates/",
        "Most Viewed": "/most-popular/",
        "Top Rated": "/top-rated/",
    }
    categories_path = "/categories/"
    models_path = "/models/"
    channels_path = "/channels/"
    video_path_markers = ("/videos/",)
    category_path_markers = ("/categories/", "/models/", "/channels/", "/tags/")
    next_page_full_count = 40
    use_playback_proxy = True
    skip_category_titles = {"channels", "alphabetically", "top rated", "most viewed", "most videos"}

    def __init__(self, addon_handle, addon=None):
        super().__init__(
            name="faapy",
            base_url="https://faapy.com/",
            search_url="https://faapy.com/search/{}/",
            addon_handle=addon_handle,
            addon=addon,
        )

    def _is_top_listing(self, url):
        parsed = urllib.parse.urlparse(url or self.base_url)
        return parsed.path.rstrip("/") in (
            "",
            "/latest-updates",
            "/most-popular",
            "/top-rated",
        )

    def process_content(self, url, page=1):
        effective_url = url
        if not effective_url or effective_url == "BOOTSTRAP":
            effective_url, _ = self.get_start_url_and_label()
        context_menu = self._context_menu(effective_url)
        self.add_dir("Search", "", 5, self.icons.get("search", self.icon), context_menu=context_menu)
        if page == 1 and self._is_top_listing(effective_url):
            self.add_dir(
                "Channels",
                self._absolute(self.channels_path),
                8,
                self.icons.get("groups", self.icon),
                context_menu=context_menu,
            )
            self.add_dir("Categories", self._absolute(self.categories_path), 8, self.icons.get("categories", self.icon), context_menu=context_menu)
            self.add_dir("Models", self._absolute(self.models_path), 8, self.icons.get("pornstars", self.icon), context_menu=context_menu)

        target_url = self.get_page_url(effective_url, page)
        html_content = self._get(target_url)
        if not html_content:
            self.notify_error("Could not load Faapy listing")
            self.end_directory("videos")
            return
        videos = self._extract_videos(html_content)
        if not videos:
            self.notify_error("No Faapy videos found")
            self.end_directory("videos")
            return
        for item in videos:
            self.add_link(
                item["label"], item["url"], 4, item["thumb"], self.fanart,
                context_menu=context_menu, info_labels=item["info"]
            )
        if self._extract_next_page(html_content, target_url, page):
            self.add_dir(
                "Next Page", effective_url, 2, self.icons.get("default", self.icon),
                context_menu=context_menu, page=page + 1
            )
        self.end_directory("videos")

    def process_categories(self, url):
        current_url = url or self._absolute(self.categories_path)
        self.add_dir("Search", "", 5, self.icons.get("search", self.icon))
        path = urllib.parse.urlparse(current_url).path.rstrip("/")
        if path.startswith("/channels"):
            item_prefix = "/channels/"
            fallback_icon = self.icons.get("groups", self.icon)
        elif path.startswith("/models"):
            item_prefix = "/model/"
            fallback_icon = self.icons.get("pornstars", self.icon)
        else:
            item_prefix = "/category/"
            fallback_icon = self.icons.get("categories", self.icon)

        html_content = self._get(current_url)
        if not html_content:
            self.notify_error("Could not load Faapy directory")
            self.end_directory("videos")
            return

        seen = set()
        for match in re.finditer(
            r'<a\b([^>]*)href=["\']([^"\']+)["\']([^>]*)>([\s\S]*?)</a>',
            html_content,
            re.IGNORECASE,
        ):
            attrs = "{} {}".format(match.group(1), match.group(3))
            href = match.group(2)
            body = match.group(4)
            item_url = self._absolute(href)
            item_path = urllib.parse.urlparse(item_url).path.rstrip("/")
            if item_prefix not in item_path + "/":
                continue
            if item_prefix == "/channels/" and item_path in (
                "/channels",
                "/channels/popularity",
                "/channels/rating",
                "/channels/total-videos",
            ):
                continue
            if item_url in seen:
                continue
            seen.add(item_url)

            title_match = re.search(r'\btitle=["\']([^"\']+)["\']', attrs, re.IGNORECASE)
            if not title_match:
                title_match = re.search(r'<img\b[^>]+\balt=["\']([^"\']+)["\']', body, re.IGNORECASE)
            if not title_match:
                title_match = re.search(r'class=["\'][^"\']*\bdesc\b[^"\']*["\'][^>]*>([\s\S]*?)</', body, re.IGNORECASE)
            title = self._clean(title_match.group(1) if title_match else "")
            if not title:
                continue

            thumb = ""
            img_match = re.search(r'<img\b[^>]+\bsrc=["\']([^"\']+)["\']', body, re.IGNORECASE)
            if img_match and "no_avatar" not in img_match.group(1):
                thumb = self._absolute(img_match.group(1))
            self.add_dir(title, item_url, 2, thumb or fallback_icon, self.fanart)

        next_match = re.search(r'<a\b[^>]*rel=["\']next["\'][^>]*href=["\']([^"\']+)["\']', html_content, re.IGNORECASE)
        if not next_match:
            next_match = re.search(r'<a\b[^>]*href=["\']([^"\']+)["\'][^>]*rel=["\']next["\']', html_content, re.IGNORECASE)
        if next_match:
            self.add_dir("Next Page", self._absolute(next_match.group(1)), 8, self.icons.get("default", self.icon), self.fanart)
        self.end_directory("videos")
