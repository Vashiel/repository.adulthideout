#!/usr/bin/env python
# -*- coding: utf-8 -*-

import re

from resources.lib.kvs_tube import KVSTubeWebsite


class CamWhoresBay(KVSTubeWebsite):
    label = "CamWhoresBay"
    sort_options = ["Latest", "Most Viewed", "Top Rated"]
    sort_paths = {
        "Latest": "/latest-updates/",
        "Most Viewed": "/most-popular/",
        "Top Rated": "/top-rated/",
    }
    categories_path = "/categories/"
    models_path = "/models/"
    use_playback_proxy = True
    next_page_full_count = 24

    def __init__(self, addon_handle, addon=None):
        super().__init__(
            name="camwhoresbay",
            base_url="https://www.camwhoresbay.com/",
            search_url="https://www.camwhoresbay.com/search/{}/",
            addon_handle=addon_handle,
            addon=addon,
        )

    def _include_video_block(self, block):
        # Members-only videos carry the "private" class and do not play without an account.
        opening_tag = block.split(">", 1)[0]
        classes = re.search(r'class=["\']([^"\']+)', opening_tag, re.IGNORECASE)
        return not classes or "private" not in classes.group(1).lower().split()
