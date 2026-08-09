#!/usr/bin/env python
# -*- coding: utf-8 -*-

from resources.lib.kvs_tube import KVSTubeWebsite


class RulePorn(KVSTubeWebsite):
    label = "RulePorn"
    video_path_markers = ("/video/",)
    sort_options = ["Latest", "Most Popular", "Top Rated"]
    sort_paths = {
        "Latest": "/latest-updates/",
        "Most Popular": "/most-popular/",
        "Top Rated": "/top-rated/",
    }
    categories_path = "/categories/"
    models_path = "/models/"
    use_playback_proxy = True
    next_page_full_count = 24

    def __init__(self, addon_handle, addon=None):
        super().__init__(
            name="ruleporn",
            base_url="https://ruleporn.com/",
            search_url="https://ruleporn.com/search/{}/",
            addon_handle=addon_handle,
            addon=addon,
        )

