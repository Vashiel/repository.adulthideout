# -*- coding: utf-8 -*-
import re

from resources.lib.resolvers import resolver
from resources.lib.wordpress_api_tube import WordPressApiTube


class PornEZ(WordPressApiTube):
    show_pornstars = True

    def __init__(self, addon_handle, addon=None):
        super().__init__("pornez", "PornEZ", "https://pornez.cam/", addon_handle, addon)

    def resolve_recording_stream(self, url):
        page_html = self._get(url, referer=self.base_url)
        iframe = re.search(
            r'<iframe\b[^>]+src=["\'](https?://player\.mediadelivery\.net/embed/[^"\']+)',
            page_html or "",
            re.IGNORECASE,
        )
        if iframe:
            iframe_url = iframe.group(1).replace("&amp;", "&")
            player_html = self._get(iframe_url, referer=url)
            stream = re.search(r'(?:content-src|cast-src)=["\'](https?://[^"\']+/playlist\.m3u8[^"\']*)', player_html or "", re.IGNORECASE)
            if stream:
                return {
                    "url": stream.group(1).replace("&amp;", "&"),
                    "headers": self._headers(iframe_url),
                    "extension": "m3u8",
                }

        mirrors = []
        for value in re.findall(r'<iframe\b[^>]+src=["\']([^"\']+)', page_html or "", re.IGNORECASE):
            candidate = self._absolute(value, url)
            if resolver.resolver_entry_for_url(candidate):
                mirrors.append(candidate)
        stream_url, headers, _ = resolver.resolve_first_working(
            mirrors, referer=url, headers=self._headers(url), addon=self.addon
        )
        if not stream_url:
            return None
        return {
            "url": stream_url,
            "headers": headers or {},
            "extension": "m3u8" if ".m3u8" in stream_url.lower() else "mp4",
        }
