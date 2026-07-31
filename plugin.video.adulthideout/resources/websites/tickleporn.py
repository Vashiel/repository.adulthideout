#!/usr/bin/env python
# -*- coding: utf-8 -*-

from resources.lib.kvs_tube import KVSTubeWebsite
from resources.lib.thumb_proxy import build_thumb_url


class TicklePorn(KVSTubeWebsite):
    label = "Tickle Porn"
    sort_options = ["Latest", "Most Viewed", "Top Rated"]
    sort_paths = {
        "Latest": "/latest-updates/",
        "Most Viewed": "/most-popular/",
        "Top Rated": "/top-rated/",
    }
    categories_path = "/categories/"
    models_path = "/models/"
    video_path_markers = ("/videos/",)
    category_path_markers = ("/categories/",)
    use_playback_proxy = True
    next_page_full_count = 24

    def __init__(self, addon_handle, addon=None):
        super().__init__(
            name="tickleporn",
            base_url="https://tickle.porn/",
            search_url="https://tickle.porn/search/{}/",
            addon_handle=addon_handle,
            addon=addon,
        )

    def _pick_thumb(self, img_tag):
        thumb = super()._pick_thumb(img_tag)
        return build_thumb_url(thumb, referer=self.base_url) if thumb else thumb
