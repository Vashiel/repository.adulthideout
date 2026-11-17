#!/usr/bin/env python
# -*- coding: utf-8 -*-

import re

from resources.lib.kvs_tube import KVSTubeWebsite


class CamHub(KVSTubeWebsite):
    label = "CamHub"
    # Most Viewed first: on "Latest" whole pages are members-only videos, which are hidden.
    sort_options = ["Most Viewed", "Latest", "Top Rated"]
    sort_paths = {
        "Most Viewed": "/most-popular/",
        "Latest": "/latest-updates/",
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
            name="camhub",
            base_url="https://www.camhub.cc/",
            search_url="https://www.camhub.cc/search/{}/",
            addon_handle=addon_handle,
            addon=addon,
        )

    def _include_video_block(self, block):
        # Members-only videos carry the "private" class and do not play without an account.
        opening_tag = block.split(">", 1)[0]
        classes = re.search(r'class=["\']([^"\']+)', opening_tag, re.IGNORECASE)
        return not classes or "private" not in classes.group(1).lower().split()
