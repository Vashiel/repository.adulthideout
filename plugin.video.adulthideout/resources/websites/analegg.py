#!/usr/bin/env python
# -*- coding: utf-8 -*-

import re

from resources.lib.kvs_tube import KVSTubeWebsite
from resources.lib.thumb_proxy import build_thumb_url


class Analegg(KVSTubeWebsite):
    label = "Analegg"
    sort_options = ["Latest", "Most Popular", "Top Rated", "Longest"]
    sort_paths = {
        "Latest": "/latest-updates/",
        "Most Popular": "/most-popular/",
        "Top Rated": "/top-rated/",
        "Longest": "/longest/",
    }
    categories_path = "/categories/"
    models_path = "/models/"
    use_playback_proxy = True

    def __init__(self, addon_handle, addon=None):
        super().__init__(
            name="analegg",
            base_url="https://www.analegg.com/",
            search_url="https://www.analegg.com/search/{}/",
            addon_handle=addon_handle,
            addon=addon,
        )

    def _pick_thumb(self, img_tag):
        match = re.search(r'\ssrc=["\']([^"\']+)', img_tag or "", re.IGNORECASE)
        thumb = self._absolute(match.group(1)) if match else super()._pick_thumb(img_tag)
        if thumb:
            thumb = re.sub(r"/\d+x\d+/\d+\.jpg(?:\?.*)?$", "/preview.jpg", thumb)
        return build_thumb_url(thumb, referer=self.base_url) if thumb else thumb
