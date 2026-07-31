# -*- coding: utf-8 -*-
from resources.lib.resolver_wordpress_tube import ResolverWordPressTube


class IcePornCasting(ResolverWordPressTube):
    show_pornstars = True

    def __init__(self, addon_handle, addon=None):
        super().__init__(
            "iceporncasting", "IcePornCasting", "https://iceporncasting.net/", addon_handle, addon
        )
