# -*- coding: utf-8 -*-
from resources.lib.retro_stream_network import RetroStreamNetworkWebsite


class MyClassicP(RetroStreamNetworkWebsite):
    def __init__(self, addon_handle, addon=None):
        super().__init__("myclassicp", "MyClassicP", "https://myclassicp.com/", addon_handle, addon, "s")
