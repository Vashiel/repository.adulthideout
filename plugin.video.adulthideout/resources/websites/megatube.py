#!/usr/bin/env python
# -*- coding: utf-8 -*-

import re

from resources.lib.kvs_tube import KVSTubeWebsite


class MegaTube(KVSTubeWebsite):
    label = "MegaTube"
    sort_options = ["Latest", "Popular", "Top Rated", "Longest"]
    sort_paths = {
        "Latest": "/latest-updates/",
        "Popular": "/most-popular/",
        "Top Rated": "/top-rated/",
        "Longest": "/longest/",
    }
    categories_path = "/categories/"
    models_path = "/models/"
    category_path_markers = (".porn",)
    next_page_full_count = 24
    use_playback_proxy = True

    def __init__(self, addon_handle, addon=None):
        super().__init__("megatube", "https://www.megatube.xxx/", "https://www.megatube.xxx/search/{}/", addon_handle, addon)

    def _extract_videos(self, html_content):
        videos, seen = [], set()
        for attrs, body in re.findall(r'<a\b([^>]*)>([\s\S]*?)</a>', html_content or "", re.I):
            link = re.search(r'\bhref=["\']([^"\']*/videos/\d+/[^"\']*)["\']', attrs, re.I)
            image = re.search(r'<img\b[^>]*>', body, re.I)
            title = re.search(r'\btitle=["\']([^"\']+)["\']', attrs, re.I)
            if not link or not image or not title:
                continue
            url = self._absolute(link.group(1))
            if url in seen:
                continue
            seen.add(url)
            label = self._clean(title.group(1))
            videos.append({"label": label, "url": url, "thumb": self._pick_thumb(image.group(0)),
                           "info": {"title": label, "plot": label}})
        return videos
