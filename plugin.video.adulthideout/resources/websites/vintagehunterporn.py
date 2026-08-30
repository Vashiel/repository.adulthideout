# -*- coding: utf-8 -*-
from resources.lib.retro_stream_network import RetroStreamNetworkWebsite


class VintageHunterPorn(RetroStreamNetworkWebsite):
    def __init__(self, addon_handle, addon=None):
        super().__init__("vintagehunterporn", "VintageHunterPorn", "https://vintagehunterporn.com/", addon_handle, addon, "s")
