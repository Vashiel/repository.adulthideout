#!/usr/bin/env python
# -*- coding: utf-8 -*-

import re
import urllib.parse

from resources.lib.kvs_tube import KVSTubeWebsite
from resources.lib.thumb_proxy import build_thumb_url


class HentaiMoon(KVSTubeWebsite):
    label = "Hentai-Moon"
    sort_options = ["Latest", "Most Viewed", "Top Rated"]
    sort_paths = {
        "Latest": "/latest-updates/",
        "Most Viewed": "/most-populars/",
        "Top Rated": "/top-rated/",
    }
    search_path = "/search/{}/"
    categories_path = "/categories/"
    models_path = None
    video_path_markers = ("/videos/",)
    category_path_markers = ("/categories/",)
    skip_category_path_prefixes = ("/categories/shota-videos/",)
    next_page_full_count = 18

    def __init__(self, addon_handle, addon=None):
        super().__init__(
            name="hentaimoon",
            base_url="https://hentai-moon.com/",
            search_url="https://hentai-moon.com/search/{}/",
            addon_handle=addon_handle,
            addon=addon,
        )

    def _is_top_listing(self, url):
        return urllib.parse.urlparse(url or self.base_url).path.rstrip("/") in (
            "", "/watch-d1", "/latest-updates", "/most-populars", "/top-rated"
        )

    def _pick_thumb(self, img_tag):
        srcset = re.search(r'\ssrcset=["\']([^"\']+)["\']', img_tag or "", re.IGNORECASE)
        if srcset:
            thumb = self._absolute(srcset.group(1).split(",", 1)[0].strip().split(" ", 1)[0])
        else:
            thumb = super()._pick_thumb(img_tag)
        # The CDN labels WebP payloads as JPEG. The in-memory proxy corrects
        # the MIME type so Kodi selects the right decoder.
        return build_thumb_url(thumb, referer=self.base_url) if thumb else thumb
