#!/usr/bin/env python
# -*- coding: utf-8 -*-

from resources.lib.kvs_tube import KVSTubeWebsite
import urllib.parse


class YesPornVIP(KVSTubeWebsite):
    label = "YesPornVIP"
    request_retries = 4
    next_page_full_count = 19
    sort_options = ["Latest", "Most Viewed", "Top Rated", "Longest"]
    sort_paths = {
        "Latest": "/",
        "Most Viewed": "/most-popular/",
        "Top Rated": "/top-rated/",
        "Longest": "/longest/",
    }
    search_path = "/search/{}/"
    categories_path = None
    models_path = "/models/"
    video_path_markers = ("/video/",)
    category_path_markers = ("/categories/", "/tags/")

    def __init__(self, addon_handle, addon=None):
        super().__init__(
            name="yespornvip",
            base_url="https://yesporn.vip/",
            search_url="https://yesporn.vip/search/{}/",
            addon_handle=addon_handle,
            addon=addon,
        )

    def _absolute(self, value):
        url = super(YesPornVIP, self)._absolute(value)
        parsed = urllib.parse.urlparse(url)
        if parsed.netloc.lower() == "yesnn.b-cdn.net":
            return urllib.parse.urlunparse(("https", "yesporn.vip", parsed.path, parsed.params, parsed.query, parsed.fragment))
        return url

    def get_page_url(self, base_url, page_num):
        if page_num <= 1:
            return base_url
        parsed = urllib.parse.urlparse(base_url)
        path = parsed.path.rstrip("/")
        if path in ("", "/"):
            path = "/latest-updates"
        if path.endswith("/latest-updates") or path.endswith("/most-popular") or path.endswith("/top-rated") or path.endswith("/longest") or path.endswith("/models"):
            path = "{}/{}/".format(path, page_num)
            return urllib.parse.urlunparse((parsed.scheme, parsed.netloc, path, parsed.params, parsed.query, parsed.fragment))
        return super(YesPornVIP, self).get_page_url(base_url, page_num)
