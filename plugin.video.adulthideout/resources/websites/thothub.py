#!/usr/bin/env python
# -*- coding: utf-8 -*-

import re
import urllib.parse

from resources.lib.kvs_tube import KVSTubeWebsite
from resources.lib.thumb_proxy import build_thumb_url


class ThotHub(KVSTubeWebsite):
    label = "ThotHub"
    sort_options = ["Most Viewed", "Top Rated", "Latest", "Longest"]
    sort_paths = {
        "Most Viewed": "/most-popular/",
        "Top Rated": "/top-rated/",
        "Latest": "/latest-updates/",
        "Longest": "/longest/",
    }
    categories_path = "/categories/"
    models_path = "/models/"
    video_path_markers = ("/videos/",)
    category_path_markers = ("/categories/", "/models/", "/tags/")
    next_page_full_count = 24
    use_playback_proxy = True

    def __init__(self, addon_handle, addon=None):
        super().__init__(
            name="thothub",
            base_url="https://thothub.to/",
            search_url="https://thothub.to/search/{}/",
            addon_handle=addon_handle,
            addon=addon,
        )

    def get_page_url(self, base_url, page_num):
        if page_num <= 1:
            return base_url
        parsed = urllib.parse.urlparse(base_url)
        path = parsed.path.rstrip("/")
        if "/search/" in path:
            path = path + "/" + str(page_num)
        elif path.rsplit("/", 1)[-1].isdigit():
            path = path.rsplit("/", 1)[0] + "/" + str(page_num)
        else:
            path += "/" + str(page_num)
        return urllib.parse.urlunparse((parsed.scheme, parsed.netloc, path + "/", "", parsed.query, ""))

    def _is_top_listing(self, url):
        path = urllib.parse.urlparse(url or self.base_url).path.rstrip("/")
        return path in ("", "/latest-updates", "/most-popular", "/top-rated", "/longest")

    def _include_video_block(self, block):
        lowered = (block or "").lower()
        if any(marker in lowered for marker in (
            "item private", "ico-private", "line-private", "private video", "premium video"
        )):
            return False
        return True

    def _pick_thumb(self, img_tag):
        thumb = super()._pick_thumb(img_tag)
        return build_thumb_url(thumb, referer=self.base_url) if thumb else thumb

    def process_content(self, url, page=1):
        if not url or url == "BOOTSTRAP":
            url, _ = self.get_start_url_and_label()
        context_menu = self._context_menu(url)
        if self._is_top_listing(url):
            self.add_dir("Search", "", 5, self.icons.get("search", self.icon), context_menu=context_menu)
            if self.categories_path:
                self.add_dir("Categories", self._absolute(self.categories_path), 8, self.icons.get("categories", self.icon), context_menu=context_menu)
            if self.models_path:
                self.add_dir("Models", self._absolute(self.models_path), 8, self.icons.get("pornstars", self.icon), context_menu=context_menu)

        videos = []
        seen_urls = set()
        current_page = page
        scanned = 0
        last_html = ""

        # Scan forward if page has few public videos (e.g. on Latest where many are private)
        while len(videos) < 16 and scanned < 8:
            target_url = self.get_page_url(url, current_page)
            html_content = self._get(target_url)
            if not html_content:
                break
            last_html = html_content
            page_videos = self._extract_videos(html_content)
            for v in page_videos:
                if v["url"] not in seen_urls:
                    seen_urls.add(v["url"])
                    videos.append(v)
            current_page += 1
            scanned += 1
            if not page_videos and not self._extract_next_page(html_content, target_url, current_page - 1):
                break

        if not videos:
            self.notify_error("No {} videos found".format(self.label or self.name))
            return self.end_directory("videos")

        for item in videos:
            self.add_link(item["label"], item["url"], 4, item["thumb"], self.fanart, context_menu=context_menu, info_labels=item["info"])

        if last_html and (self._extract_next_page(last_html, url, current_page - 1) or len(videos) >= 16):
            self.add_dir("Next Page", url, 2, self.icons.get("default", self.icon), context_menu=context_menu, page=current_page)
        self.end_directory("videos")
