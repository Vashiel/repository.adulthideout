# -*- coding: utf-8 -*-
import re

from resources.lib.resolvers import resolver
from resources.lib.wordpress_api_tube import WordPressApiTube


class ResolverWordPressTube(WordPressApiTube):
    """WordPress listings backed by AdultHideout's neutral-host resolvers."""

    def resolve_recording_stream(self, url):
        page_html = self._get(url, referer=self.base_url)
        mirrors = []
        # Lazy-loaded players keep the real address in data-lazy-src and "about:blank" in src.
        for value in re.findall(r'<iframe\b[^>]+(?:data-lazy-src|src)=["\']([^"\']+)', page_html or "", re.IGNORECASE):
            iframe_url = self._absolute(value, url)
            if resolver.resolver_entry_for_url(iframe_url) and iframe_url not in mirrors:
                mirrors.append(iframe_url)
        stream_url, headers, _ = resolver.resolve_first_working(
            mirrors,
            referer=url,
            headers=self._headers(url),
            addon=self.addon,
        ) if mirrors else (None, {}, None)
        if not stream_url:
            # Some themes play their own file: <source src="...mp4|m3u8"> / itemprop contentUrl.
            direct = re.search(
                r'(?:<source\b[^>]+src=|itemprop=["\']contentUrl["\'][^>]*content=)["\'](https?://[^"\']+\.(?:mp4|m3u8)[^"\']*)["\']',
                page_html or "",
                re.IGNORECASE,
            )
            if not direct:
                return None
            stream_url = direct.group(1).replace(" ", "%20")
            headers = self._headers(url)
        return {
            "url": stream_url,
            "headers": headers or {},
            "extension": "m3u8" if ".m3u8" in stream_url.lower() else "mp4",
        }
