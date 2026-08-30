# -*- coding: utf-8 -*-
from resources.lib.retro_stream_network import RetroStreamNetworkWebsite


class RetroPornGallery(RetroStreamNetworkWebsite):
    def __init__(self, addon_handle, addon=None):
        super().__init__("retroporngallery", "RetroPornGallery", "https://retroporngallery.com/", addon_handle, addon, "s")
