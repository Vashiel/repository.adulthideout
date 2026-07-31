# -*- coding: utf-8 -*-
from resources.lib.resolver_wordpress_tube import ResolverWordPressTube


class WatchXXXFree(ResolverWordPressTube):
    show_pornstars = True

    def __init__(self, addon_handle, addon=None):
        super().__init__(
            "watchxxxfree", "WatchXXXFree", "https://xxxfree.watch/", addon_handle, addon
        )
