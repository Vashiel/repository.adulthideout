# -*- coding: utf-8 -*-
import re
import urllib.parse
from resources.lib.wpstube_movies import WPSTubeMoviesWebsite


class VintagePornFun(WPSTubeMoviesWebsite):
    def __init__(self, addon_handle, addon=None):
        super().__init__("vintagepornfun", "VintagePornFun", "https://vintagepornfun.com", addon_handle, addon)
        category = "/category/vintage-porn-movies/"
        self.sort_options = [
            "German Vintage",
            "Latest",
            "Most Viewed",
            "Longest",
            "Top Rated",
            "70s Vintage",
            "80s Vintage",
            "90s Vintage",
            "Classic Movies",
        ]
        self.sort_paths = {
            "German Vintage": "/category/german-vintage-porn/",
            "Latest": category,
            "Most Viewed": category + "?filter=most-viewed",
            "Longest": category + "?filter=longest",
            "Top Rated": category + "?filter=popular",
            "70s Vintage": "/category/70s-porn/",
            "80s Vintage": "/category/80s-porn/",
            "90s Vintage": "/category/90s-porn/",
            "Classic Movies": "/category/classic-porn-movies/",
        }
        self.extra_categories = [
            ("German Vintage Movies", "https://vintagepornfun.com/category/german-vintage-porn/"),
            ("70s Vintage Porn", "https://vintagepornfun.com/category/70s-porn/"),
            ("80s Vintage Porn", "https://vintagepornfun.com/category/80s-porn/"),
            ("90s Vintage Porn", "https://vintagepornfun.com/category/90s-porn/"),
            ("Classic Porn Movies", "https://vintagepornfun.com/category/classic-porn-movies/"),
        ]

    def process_categories(self, url):
        page_html = self._get("https://vintagepornfun.com/categories/")
        seen = set()
        for label, target in self.extra_categories:
            target = self._absolute(target)
            seen.add(target)
            self.add_dir(label, target, 2, self.icons.get("categories", self.icon))
        pattern = (
            r"<a[^>]+href\s*=\s*(?:\"([^\"]*/category/[^\"]+)\"|'([^']*/category/[^']+)'|"
            r"([^\s>]+/category/[^\s>]+))[^>]*>([\s\S]*?)</a>"
        )
        for double_url, single_url, plain_url, label in re.findall(pattern, page_html, re.I):
            target = double_url or single_url or plain_url
            target = self._absolute(target)
            name = self._clean(label)
            if not name:
                slug = urllib.parse.urlsplit(target).path.rstrip("/").rsplit("/", 1)[-1]
                name = slug.replace("-", " ").title()
            if name and target not in seen:
                seen.add(target)
                self.add_dir(name, target, 2, self.icons.get("categories", self.icon))
        self.end_directory("videos")
