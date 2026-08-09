#!/usr/bin/env python
# -*- coding: utf-8 -*-

import html
import re
import urllib.parse

from resources.lib.resolvers import resolver
from resources.lib.thumb_proxy import build_thumb_url
from resources.lib.wordpress_api_tube import WordPressApiTube


class SwingerPornFun(WordPressApiTube):
    def __init__(self, addon_handle, addon=None):
        super().__init__(
            "swingerpornfun", "SwingerPornFun",
            "https://swingerpornfun.com/", addon_handle, addon,
        )

    def _get_json(self, url, referer=None):
        # The posts API reports featured_media=0 although the HTML catalogue
        # contains a real JPEG for every video card.
        if "/wp-json/wp/v2/posts?" in (url or ""):
            return None, {}
        return super()._get_json(url, referer=referer)

    def _html_video_items(self, url, page):
        items, has_next = super()._html_video_items(url, page)
        for item in items:
            item["thumb"] = build_thumb_url(item.get("thumb"), referer=self.base_url)
        return items, has_next

    def resolve_recording_stream(self, url):
        page = self._get(url, referer=self.base_url)
        embeds = []
        for value in re.findall(r'<iframe\b[^>]+src=["\']([^"\']+)', page or "", re.IGNORECASE):
            embed = html.unescape(value).strip()
            if embed.startswith("//"):
                embed = "https:" + embed
            else:
                embed = urllib.parse.urljoin(url, embed)
            if resolver.resolver_entry_for_url(embed) and embed not in embeds:
                embeds.append(embed)
        stream, headers, _ = resolver.resolve_first_working(
            embeds,
            referer=url,
            headers=self._headers(url, accept="*/*"),
            addon=self.addon,
        )
        if stream:
            return {"url": stream, "headers": headers or {}, "extension": "mp4"}

        return None
