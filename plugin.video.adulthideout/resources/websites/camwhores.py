#!/usr/bin/env python
# -*- coding: utf-8 -*-

import re
import urllib.parse
from concurrent.futures import ThreadPoolExecutor

import requests

from resources.lib.kvs_tube import KVSTubeWebsite
from resources.lib.thumb_proxy import build_thumb_url


class CamWhores(KVSTubeWebsite):
    label = "CamWhores"
    sort_options = ["Latest", "Most Viewed", "Top Rated"]
    sort_paths = {
        "Latest": "/latest-updates/",
        "Most Viewed": "/most-popular/",
        "Top Rated": "/top-rated/",
    }
    search_path = "/search/{}/"
    categories_path = "/categories/"
    models_path = "/models/"
    video_path_markers = ("/videos/",)
    category_path_markers = ("/categories/",)
    use_playback_proxy = True
    next_page_full_count = 24

    def _include_video_block(self, block):
        opening_tag = block.split(">", 1)[0]
        classes = re.search(r'class=["\']([^"\']+)', opening_tag, re.IGNORECASE)
        return not classes or "private" not in classes.group(1).lower().split()

    def _pick_thumb(self, img_tag):
        thumb = super()._pick_thumb(img_tag)
        if not thumb or thumb == self.icon:
            return thumb
        return build_thumb_url(thumb, referer=self.base_url)

    @staticmethod
    def _upstream_thumb(proxy_url):
        parsed = urllib.parse.urlparse(proxy_url or "")
        if parsed.hostname in ("127.0.0.1", "localhost"):
            return urllib.parse.parse_qs(parsed.query).get("u", [proxy_url])[0]
        return proxy_url

    def _thumbnail_status(self, item):
        url = self._upstream_thumb(item.get("thumb"))
        if "cdn.camwhores.tv/" not in url:
            return True
        try:
            response = requests.get(
                url,
                headers=self._headers(self.base_url, "image/avif,image/webp,image/jpeg,image/*,*/*;q=0.8"),
                timeout=(3, 6),
                stream=True,
            )
            status = response.status_code
            response.close()
            return status < 400
        except requests.RequestException:
            # Keep the entry on a local network failure; only confirmed broken
            # upstream artwork is removed.
            return True

    def _extract_videos(self, html_content):
        videos = super()._extract_videos(html_content)
        probe_count = min(36, len(videos))
        if not probe_count:
            return videos
        with ThreadPoolExecutor(max_workers=8) as executor:
            available = list(executor.map(self._thumbnail_status, videos[:probe_count]))
        return [item for index, item in enumerate(videos)
                if index >= probe_count or available[index]]

    def __init__(self, addon_handle, addon=None):
        super().__init__(
            name="camwhores",
            base_url="https://www.camwhores.tv/",
            search_url="https://www.camwhores.tv/search/{}/",
            addon_handle=addon_handle,
            addon=addon,
        )
