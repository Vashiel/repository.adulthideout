#!/usr/bin/env python
# -*- coding: utf-8 -*-

import re
import urllib.parse

from resources.lib.kvs_tube import KVSTubeWebsite


class AsianViralHub(KVSTubeWebsite):
    label = "AsianViralHub"
    sort_options = ["Latest", "Most Viewed", "Top Rated"]
    sort_paths = {
        "Latest": "/latest-updates/",
        "Most Viewed": "/most-popular/",
        "Top Rated": "/top-rated/",
    }
    search_path = "/search/{}/"
    categories_path = "/categories/"
    models_path = "/models/"
    video_path_markers = ("/video/",)
    category_path_markers = ("/categories/",)
    next_page_full_count = 25
    use_playback_proxy = True

    def __init__(self, addon_handle, addon=None):
        super().__init__(
            name="asianviralhub",
            base_url="https://asianviralhub.com/",
            search_url="https://asianviralhub.com/search/{}/",
            addon_handle=addon_handle,
            addon=addon,
        )

    def _include_video_block(self, block):
        opening_tag = block.split(">", 1)[0]
        classes = re.search(r'class=["\']([^"\']+)', opening_tag, re.IGNORECASE)
        return not classes or "private" not in classes.group(1).lower().split()

    def process_categories(self, url):
        current_url = url or self._absolute(self.categories_path)
        current_path = urllib.parse.urlparse(current_url).path.rstrip("/")
        if not current_path.startswith("/models"):
            return super().process_categories(current_url)

        html_content = self._get(current_url)
        if not html_content:
            self.notify_error("Could not load AsianViralHub models")
            return self.end_directory("videos")

        seen = set()
        pattern = r'<a\b[^>]*class=["\'][^"\']*\bitem\b[^"\']*["\'][^>]*href=["\']([^"\']*/models/[^"\']+)["\'][^>]*title=["\']([^"\']+)["\']'
        for match in re.finditer(pattern, html_content, re.IGNORECASE):
            model_url = self._absolute(match.group(1))
            title = self._clean(match.group(2))
            if model_url in seen or not title:
                continue
            seen.add(model_url)
            self.add_dir(title, model_url, 2, self.icons.get("pornstars", self.icon), self.fanart)

        next_match = re.search(r'<a\b[^>]*href=["\']([^"\']*/models/\d+/)["\'][^>]*data-parameters=["\'][^"\']*from:(\d+)', html_content, re.IGNORECASE)
        if next_match:
            self.add_dir("Next Page", self._absolute(next_match.group(1)), 8,
                         self.icons.get("default", self.icon), self.fanart)
        self.end_directory("videos")
