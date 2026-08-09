#!/usr/bin/env python
# -*- coding: utf-8 -*-

import re
import urllib.parse

from resources.lib.kvs_tube import KVSTubeWebsite


class YourAmateurPorn(KVSTubeWebsite):
    label = "YourAmateurPorn"
    video_path_markers = ("/video/",)
    category_path_markers = ("/channels/",)
    sort_options = ["Latest", "Top Rated", "Most Viewed", "Longest"]
    sort_paths = {
        "Latest": "/most-recent/",
        "Top Rated": "/top-rated/",
        "Most Viewed": "/most-viewed/",
        "Longest": "/longest/",
    }
    categories_path = "/channels/"
    models_path = None
    use_playback_proxy = True
    prefer_default_stream = True

    def __init__(self, addon_handle, addon=None):
        super().__init__(
            name="youramateurporn",
            base_url="https://www.youramateurporn.com/",
            search_url="https://www.youramateurporn.com/search/{}/",
            addon_handle=addon_handle,
            addon=addon,
        )

    def get_page_url(self, base_url, page_num):
        parsed = urllib.parse.urlparse(base_url)
        path = re.sub(r"/page\d+\.html$", "/", parsed.path, flags=re.IGNORECASE)
        if page_num > 1:
            path = path.rstrip("/") + "/page{}.html".format(page_num)
        return urllib.parse.urlunparse(
            (parsed.scheme, parsed.netloc, path, parsed.params, parsed.query, parsed.fragment)
        )

    def _include_video_block(self, block):
        lowered = (block or "").lower()
        return not any(marker in lowered for marker in (
            "thumbs/embedded/",
            'title="(ad)',
            'title="(blog)',
            "title='(ad)",
            "title='(blog)",
        ))

    def _extract_next_page(self, html_content, current_url, page):
        next_page = page + 1
        if re.search(r'href=["\'][^"\']*page{}\.html["\']'.format(next_page), html_content or "", re.IGNORECASE):
            return self.get_page_url(current_url, next_page)
        return None
