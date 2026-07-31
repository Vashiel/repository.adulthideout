#!/usr/bin/env python
# -*- coding: utf-8 -*-

import urllib.parse

from resources.lib.kvs_tube import KVSTubeWebsite


class PornBimbo(KVSTubeWebsite):
    label = "PornBimbo"
    sort_options = ["Latest", "Most Viewed"]
    sort_paths = {
        "Latest": "/latest-updates/",
        "Most Viewed": "/most-popular/",
    }
    categories_path = "/categories/"
    models_path = "/models/"
    video_path_markers = ("/video/",)
    category_path_markers = ("/categories/",)
    use_playback_proxy = True
    next_page_full_count = 24

    def __init__(self, addon_handle, addon=None):
        super().__init__(
            name="pornbimbo",
            base_url="https://pornbimbo.com/",
            search_url="https://pornbimbo.com/search/{}/",
            addon_handle=addon_handle,
            addon=addon,
        )

    def _absolute(self, value):
        result = super()._absolute(value)
        parsed = urllib.parse.urlparse(result)
        if parsed.netloc.lower().lstrip("www.") == "pornbimbo.com":
            result = urllib.parse.urlunparse(
                ("https", "pornbimbo.com", parsed.path, parsed.params, parsed.query, parsed.fragment)
            )
        return result
