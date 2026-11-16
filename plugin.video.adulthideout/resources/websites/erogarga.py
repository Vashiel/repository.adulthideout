# -*- coding: utf-8 -*-
from resources.lib.resolver_wordpress_tube import ResolverWordPressTube


class EroGarga(ResolverWordPressTube):
    def __init__(self, addon_handle, addon=None):
        super().__init__(
            "erogarga", "EroGarga", "https://www.erogarga.com/", addon_handle, addon
        )
