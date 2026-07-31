# -*- coding: utf-8 -*-
import re

from resources.lib.resolvers import resolver
from resources.lib.wordpress_api_tube import WordPressApiTube


class ResolverWordPressTube(WordPressApiTube):
    """WordPress listings backed by AdultHideout's neutral-host resolvers."""

    def resolve_recording_stream(self, url):
        page_html = self._get(url, referer=self.base_url)
        mirrors = []
        for value in re.findall(r'<iframe\b[^>]+src=["\']([^"\']+)', page_html or "", re.IGNORECASE):
            iframe_url = self._absolute(value, url)
            if resolver.resolver_entry_for_url(iframe_url):
                mirrors.append(iframe_url)
        stream_url, headers, _ = resolver.resolve_first_working(
            mirrors,
            referer=url,
            headers=self._headers(url),
            addon=self.addon,
        )
        if not stream_url:
            return None
        return {
            "url": stream_url,
            "headers": headers or {},
            "extension": "m3u8" if ".m3u8" in stream_url.lower() else "mp4",
        }
