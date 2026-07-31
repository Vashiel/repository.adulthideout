#!/usr/bin/env python
# -*- coding: utf-8 -*-

import html
import re

from resources.lib.kvs_tube import KVSTubeWebsite


class FemdomVC(KVSTubeWebsite):
    label = "FemdomVC"
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
    use_playback_proxy = True
    next_page_full_count = 24

    def __init__(self, addon_handle, addon=None):
        super().__init__(
            name="femdomvc",
            base_url="https://www.femdomvc.com/",
            search_url="https://www.femdomvc.com/search/{}/",
            addon_handle=addon_handle,
            addon=addon,
        )

    def _extract_stream_url(self, html_content, referer=None):
        # The normal KVS player URLs intermittently return placeholders here.
        # The public source-download link points to the same complete file and
        # consistently supports byte ranges.
        matches = re.findall(
            r'href=["\']([^"\']+\.mp4/?[^"\']*\bdownload_filename=[^"\']+)["\']',
            html_content or "",
            re.IGNORECASE,
        )
        for value in matches:
            stream_url = self._normalize_stream(html.unescape(value))
            if self._probe_stream(stream_url, referer or self.base_url):
                return stream_url
        return super()._extract_stream_url(html_content, referer=referer)
