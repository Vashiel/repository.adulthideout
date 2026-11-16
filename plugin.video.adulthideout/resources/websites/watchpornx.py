# -*- coding: utf-8 -*-
import html
import json
import re

from resources.lib.resolvers import resolver
from resources.lib.resolver_wordpress_tube import ResolverWordPressTube


class WatchPornX(ResolverWordPressTube):
    """Formerly netflixporno.net. Videos list the host mirrors in a player on /video-embed/<id>."""

    def __init__(self, addon_handle, addon=None):
        super().__init__(
            "watchpornx", "WatchPornX", "https://watchpornx.com/", addon_handle, addon
        )

    def _mirrors(self, url):
        page_html = self._get(url, referer=self.base_url) or ""
        embed = re.search(r'"embedUrl"\s*:\s*"([^"]+/video-embed/\d+)"', page_html)
        embed_url = embed.group(1).replace("\\/", "/") if embed else url
        embed_html = self._get(embed_url, referer=url) if embed else page_html
        # <section class="hlm" data-servers='[{"u": host embed, "l": label, "h": hash}]'>
        servers = re.search(r'data-servers="([^"]*)"', embed_html or "")
        try:
            entries = json.loads(html.unescape(servers.group(1))) if servers else []
        except ValueError:
            entries = []
        return embed_url, [entry["u"] for entry in entries if entry.get("u") and resolver.resolver_entry_for_url(entry["u"])]

    def resolve_recording_stream(self, url):
        embed_url, mirrors = self._mirrors(url)
        if not mirrors:
            return None
        stream_url, headers, _ = resolver.resolve_first_working(
            mirrors, referer=embed_url, headers=self._headers(embed_url), addon=self.addon
        )
        if not stream_url:
            return None
        return {
            "url": stream_url,
            "headers": headers or {},
            "extension": "m3u8" if ".m3u8" in stream_url.lower() else "mp4",
        }
