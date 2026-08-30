# -*- coding: utf-8 -*-
from resources.lib.retro_stream_network import RetroStreamNetworkWebsite


class VintageWorldP(RetroStreamNetworkWebsite):
    def __init__(self, addon_handle, addon=None):
        super().__init__("vintageworldp", "VintageWorldP", "https://vintageworldp.com/", addon_handle, addon, "s")
