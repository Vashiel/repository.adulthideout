#!/usr/bin/env python
# -*- coding: utf-8 -*-

from resources.lib.kvs_tube import KVSTubeWebsite


class ExtremeAdult(KVSTubeWebsite):
    label = "Extreme.Adult"
    sort_options = ["Latest", "Most Viewed", "Top Rated"]
    sort_paths = {
        "Latest": "/latest-updates/",
        "Most Viewed": "/most-popular/",
        "Top Rated": "/top-rated/",
    }
    categories_path = "/categories/"
    models_path = "/models/"
    use_playback_proxy = True
    # The stream redirects to a CDN that wants the cookie set on that redirect; urllib drops it.
    use_urllib_proxy = False
    next_page_full_count = 20

    def __init__(self, addon_handle, addon=None):
        super().__init__(
            name="extremeadult",
            base_url="https://www.extreme.adult/",
            search_url="https://www.extreme.adult/search/{}/",
            addon_handle=addon_handle,
            addon=addon,
        )
