# -*- coding: utf-8 -*-
import html
import re
import urllib.parse
from resources.lib.wpstube_movies import WPSTubeMoviesWebsite


class IcePornCasting(WPSTubeMoviesWebsite):
    def __init__(self, addon_handle, addon=None):
        super().__init__("iceporncasting", "IcePornCasting", "https://iceporncasting.net", addon_handle, addon)
        self.sort_options = [
            "Latest",
            "Most Viewed",
            "Longest",
            "Top Rated",
        ]
        self.sort_paths = {
            "Latest": "/latest-casting-videos/",
            "Most Viewed": "/latest-casting-videos/?filter=most-viewed",
            "Longest": "/latest-casting-videos/?filter=longest",
            "Top Rated": "/latest-casting-videos/?filter=popular",
        }

    def process_categories(self, url):
        page_html = self._get(self.base_url + "/channels/")
        seen = set()
        pattern = (
            r'<article[^>]*class="[^"]*thumb-block[^"]*"[^>]*>.*?<a[^>]+href="([^"]+)".*?<span[^>]*class="[^"]*cat-title[^"]*"[^>]*>([^<]+)</span>'
        )
        for target, label in re.findall(pattern, page_html or "", re.I | re.DOTALL):
            target = self._absolute(target)
            name = self._clean(label)
            if not name:
                slug = urllib.parse.urlsplit(target).path.rstrip("/").rsplit("/", 1)[-1]
                name = slug.replace("-", " ").title()
            if name and target not in seen:
                seen.add(target)
                self.add_dir(name, target, 2, self.icons.get("categories", self.icon))
        self.end_directory("videos")
