# -*- coding: utf-8 -*-
from resources.lib.wpstube_movies import WPSTubeMoviesWebsite


class HDShemalez(WPSTubeMoviesWebsite):
    def __init__(self, addon_handle, addon=None):
        super().__init__("hdshemalez", "HDShemalez", "https://hdshemalez.com", addon_handle, addon)
        category = "/category/full-movies-international/"
        self.extra_categories = [("Full Movies International", category)]
        self.sort_paths = {
            "Latest": category + "?filter=latest",
            "Most Viewed": category + "?filter=most-viewed",
            "Longest": category + "?filter=longest",
            "Top Rated": category + "?filter=popular",
        }
