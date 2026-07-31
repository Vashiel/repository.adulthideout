# -*- coding: utf-8 -*-
import os
import urllib.parse

from resources.lib.base_website import BaseWebsite
from resources.websites.abxxx import Abxxx


class Vxxx(Abxxx):
    def __init__(self, addon_handle, addon=None):
        BaseWebsite.__init__(
            self, "vxxx", "https://vxxx.com/", "vxxx://search?q={}", addon_handle, addon
        )
        self.ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131 Safari/537.36"
        self.icon = os.path.join(self.addon.getAddonInfo("path"), "resources", "logos", "vxxx.png")
        self.icons["default"] = self.icon

    def _listing_url(self, sort="latest-updates", page=1, query=""):
        return "vxxx://listing?" + urllib.parse.urlencode({"sort": sort, "page": page, "q": query})

    def get_start_url_and_label(self):
        try:
            index = int(self.addon.getSetting("vxxx_sort_by") or "0")
        except Exception:
            index = 0
        index = index if 0 <= index < len(self.sort_options) else 0
        return self._listing_url(self.sort_values[index]), "VXXX [COLOR yellow]{}[/COLOR]".format(self.sort_options[index])
