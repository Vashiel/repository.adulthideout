#!/usr/bin/env python
# -*- coding: utf-8 -*-

import re

from resources.lib.kvs_tube import KVSTubeWebsite
from resources.lib.thumb_proxy import build_thumb_url


class FetishShrine(KVSTubeWebsite):
    label = "Fetish Shrine"
    sort_options = ["Latest", "Most Popular", "Top Rated", "Longest"]
    sort_paths = {
        "Latest": "/latest-updates/",
        "Most Popular": "/most-popular/",
        "Top Rated": "/top-rated/",
        "Longest": "/longest/",
    }
    categories_path = "/categories/"
    models_path = "/pornstars/"
    video_path_markers = ("/videos/",)
    category_path_markers = ("/categories/",)
    use_playback_proxy = True

    def __init__(self, addon_handle, addon=None):
        super().__init__(
            name="fetishshrine",
            base_url="https://www.fetishshrine.com/",
            search_url="https://www.fetishshrine.com/search/{}/",
            addon_handle=addon_handle,
            addon=addon,
        )

    def _pick_thumb(self, img_tag):
        thumb = super()._pick_thumb(img_tag)
        if thumb:
            path = re.sub(r"/\d+x\d+/\d+\.jpg$", "/preview.jpg", thumb.split("?", 1)[0])
            path = re.sub(r"^https?://[^/]+", self.base_url.rstrip("/"), path)
            thumb = path
        return build_thumb_url(thumb, referer=self.base_url) if thumb else thumb
