# -*- coding: utf-8 -*-
from resources.lib.retro_stream_network import RetroStreamNetworkWebsite


class RetroPornArchives(RetroStreamNetworkWebsite):
    def __init__(self, addon_handle, addon=None):
        super().__init__("retropornarchives", "RetroPornArchives", "https://retropornarchives.com/", addon_handle, addon, "s")
