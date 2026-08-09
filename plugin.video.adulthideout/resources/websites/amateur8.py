#!/usr/bin/env python
# -*- coding: utf-8 -*-

import re

from resources.lib.kvs_tube import KVSTubeWebsite
from resources.lib.thumb_proxy import build_thumb_url


class Amateur8(KVSTubeWebsite):
    label = "Amateur8"
    sort_options = ["Latest", "Most Popular", "Top Rated", "Longest"]
    sort_paths = {
        "Latest": "/latest-updates/",
        "Most Popular": "/most-popular/",
        "Top Rated": "/top-rated/",
        "Longest": "/longest/",
    }
    categories_path = "/categories/"
    models_path = "/models/"
    video_path_markers = ("/videos/",)
    use_playback_proxy = False

    def __init__(self, addon_handle, addon=None):
        super().__init__(
            name="amateur8",
            base_url="https://www.amateur8.com/",
            search_url="https://www.amateur8.com/search/{}/",
            addon_handle=addon_handle,
            addon=addon,
        )

    def _is_video_href(self, href):
        return bool(href and "/videos/" in href and "/link/videos/" not in href)

    def _pick_thumb(self, img_tag):
        # data-webp is WebP despite its .jpg suffix; src is the real JPEG.
        match = re.search(r'\ssrc=["\']([^"\']+)', img_tag or "", re.IGNORECASE)
        thumb = self._absolute(match.group(1)) if match else super()._pick_thumb(img_tag)
        return build_thumb_url(thumb, referer=self.base_url) if thumb else thumb
