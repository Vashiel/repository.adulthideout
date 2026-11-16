# -*- coding: utf-8 -*-
from resources.lib.resolver_wordpress_tube import ResolverWordPressTube


class PervTube(ResolverWordPressTube):
    def __init__(self, addon_handle, addon=None):
        super().__init__(
            "pervtube", "PervTube", "https://pervtube.net/", addon_handle, addon
        )

    def resolve_recording_stream(self, url):
        # Videos play from xtremestream.xyz; Perverzija's module already speaks that player.
        from resources.websites.perverzija import PerverzijaWebsite
        return PerverzijaWebsite(self.addon_handle).resolve_recording_stream(url)
