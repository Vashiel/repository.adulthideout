# -*- coding: utf-8 -*-
# Listing only: the Byse player demands a captcha before every video, so playback does not work (not bypassed on purpose).
from resources.lib.resolver_wordpress_tube import ResolverWordPressTube


class FullTaboo(ResolverWordPressTube):
    def __init__(self, addon_handle, addon=None):
        super().__init__(
            "fulltaboo", "FullTaboo", "https://fulltaboo.tv/", addon_handle, addon
        )
