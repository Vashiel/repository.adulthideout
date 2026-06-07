#!/usr/bin/env python
# -*- coding: utf-8 -*-

from resources.lib.kvs_tube import KVSTubeWebsite
import urllib.parse


class Tgtsporn(KVSTubeWebsite):
    label = "Tgtsporn"
    use_playback_proxy = True
    prefer_default_stream = True
    sort_options = ["Latest", "Trending", "Most Viewed", "Top Rated"]
    sort_paths = {
        "Latest": "/",
        "Trending": "/trending/",
        "Most Viewed": "/most-popular/",
        "Top Rated": "/top-rated/",
    }
    search_path = "/search/{}/"
    categories_path = None
    models_path = "/models/"
    video_path_markers = ("/videos/",)
    category_path_markers = ("/categories/", "/tags/")

    def __init__(self, addon_handle, addon=None):
        super().__init__(
            name="tgtsporn",
            base_url="https://tgtsporn.com/",
            search_url="https://tgtsporn.com/search/{}/",
            addon_handle=addon_handle,
            addon=addon,
        )

    def get_page_url(self, base_url, page_num):
        if page_num <= 1:
            return base_url
        parsed = urllib.parse.urlparse(base_url)
        path = parsed.path.rstrip("/")
        if path in ("", "/"):
            path = "/latest-updates"
        if path.endswith("/latest-updates") or path.endswith("/trending") or path.endswith("/most-popular") or path.endswith("/top-rated"):
            path = "{}/{}/".format(path, page_num)
            return urllib.parse.urlunparse((parsed.scheme, parsed.netloc, path, parsed.params, parsed.query, parsed.fragment))
        return super(Tgtsporn, self).get_page_url(base_url, page_num)
