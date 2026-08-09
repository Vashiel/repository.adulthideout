#!/usr/bin/env python
# -*- coding: utf-8 -*-

import re
import urllib.parse

from resources.lib.kvs_tube import KVSTubeWebsite


class XoxPorn(KVSTubeWebsite):
    label = "XoxPorn"
    video_path_markers = ("/videos/",)
    sort_options = ["Most Recent", "Most Viewed", "Best Rated"]
    sort_paths = {
        "Most Recent": "/videos/?videos_per_page=32&sort_by=post_date",
        "Most Viewed": "/videos/?videos_per_page=32&sort_by=video_viewed",
        "Best Rated": "/videos/?videos_per_page=32&sort_by=rating",
    }
    categories_path = "/categories/"
    models_path = None
    use_playback_proxy = True
    next_page_full_count = 32

    def __init__(self, addon_handle, addon=None):
        super().__init__(
            name="xoxporn",
            base_url="https://xoxporn.com/",
            search_url="https://xoxporn.com/search/{}/",
            addon_handle=addon_handle,
            addon=addon,
        )

    def _is_video_href(self, href):
        path = urllib.parse.urlparse(self._absolute(href)).path
        return bool(re.match(r"^/videos/[^/]+/?$", path, re.IGNORECASE))

    def process_categories(self, url):
        html_content = self._get(url or self._absolute(self.categories_path))
        if not html_content:
            self.notify_error("Could not load XoxPorn categories")
            return self.end_directory("videos")

        seen = set()
        for match in re.finditer(
            r'<a\b[^>]*href=["\']([^"\']*/categories/[^/"\']+/)["\'][^>]*>',
            html_content,
            re.IGNORECASE,
        ):
            category_url = self._absolute(match.group(1))
            if category_url in seen:
                continue
            seen.add(category_url)
            body = html_content[match.end():match.end() + 1200]
            image_match = re.search(r"<img\b[^>]*>", body, re.IGNORECASE)
            image_tag = image_match.group(0) if image_match else ""
            title_match = re.search(r'(?:alt|title)=["\']([^"\']+)', image_tag, re.IGNORECASE)
            title = self._clean(title_match.group(1) if title_match else "")
            if not title:
                title = urllib.parse.unquote(urllib.parse.urlparse(category_url).path.strip("/").split("/")[-1]).replace("-", " ").title()
            thumb = self._pick_thumb(image_tag) if image_tag else self.icons.get("categories", self.icon)
            self.add_dir(title, category_url, 2, thumb, self.fanart)
        self.end_directory("videos")
