# -*- coding: utf-8 -*-
import urllib.parse

from resources.lib.resolver_wordpress_tube import ResolverWordPressTube


class FullTaboo(ResolverWordPressTube):
    def __init__(self, addon_handle, addon=None):
        super().__init__(
            "fulltaboo", "FullTaboo", "https://fulltaboo.tv/", addon_handle, addon
        )

    def _html_listing_url(self, url, page):
        target = urllib.parse.urlsplit(super()._html_listing_url(url, page))
        query = urllib.parse.parse_qsl(target.query)
        if not any(key == "filter" for key, _ in query):
            query.append(("filter", "latest"))
        return target._replace(query=urllib.parse.urlencode(query)).geturl()

    def _listing_items(self, url, page):
        items, has_next = self._html_video_items(url, page)
        return [item for item in items if self._is_fulltaboo_url(item["url"])], has_next

    def _is_fulltaboo_url(self, url):
        target = urllib.parse.urlsplit(url)
        return target.scheme == "https" and target.netloc == urllib.parse.urlsplit(self.base_url).netloc

    def play_video(self, url):
        if not self._is_fulltaboo_url(url):
            self._play_resolved(None)
            return
        super().play_video(url)
