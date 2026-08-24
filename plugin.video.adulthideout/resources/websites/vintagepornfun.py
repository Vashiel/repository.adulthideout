# -*- coding: utf-8 -*-
from resources.lib.wpstube_movies import WPSTubeMoviesWebsite


class VintagePornFun(WPSTubeMoviesWebsite):
    def __init__(self, addon_handle, addon=None):
        super().__init__("vintagepornfun", "VintagePornFun", "https://vintagepornfun.com", addon_handle, addon)
        category = "/category/vintage-porn-movies/"
        self.sort_paths = {
            "Latest": category,
            "Most Viewed": category + "?filter=most-viewed",
            "Longest": category + "?filter=longest",
            "Top Rated": category + "?filter=popular",
        }
