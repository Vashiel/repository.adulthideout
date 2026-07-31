#!/usr/bin/env python
# -*- coding: utf-8 -*-

from resources.lib.kvs_tube import KVSTubeWebsite


class HcBDSM(KVSTubeWebsite):
    label = "hcBDSM"
    sort_options = ["Latest", "Most Viewed", "Top Rated"]
    sort_paths = {
        "Latest": "/latest-updates/",
        "Most Viewed": "/most-popular/",
        "Top Rated": "/top-rated/",
    }
    categories_path = "/categories/"
    models_path = "/models/"
    video_path_markers = ("/video/",)
    category_path_markers = ("/categories/",)
    use_playback_proxy = True
    next_page_full_count = 24

    def __init__(self, addon_handle, addon=None):
        super().__init__(
            name="hcbdsm",
            base_url="https://hcbdsm.com/",
            search_url="https://hcbdsm.com/search/{}/",
            addon_handle=addon_handle,
            addon=addon,
        )
