# -*- coding: utf-8 -*-
from resources.lib.resolver_wordpress_tube import ResolverWordPressTube


class TabooJizz(ResolverWordPressTube):
    def __init__(self, addon_handle, addon=None):
        super().__init__(
            "taboojizz", "TabooJizz", "https://taboojizz.com/", addon_handle, addon
        )
