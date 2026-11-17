#!/usr/bin/env python
# -*- coding: utf-8 -*-

import html
import re
import urllib.parse
from concurrent.futures import ThreadPoolExecutor

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

        # Skip entries whose embed hosts are unsupported by any configured resolver.
        def playable(item):
            try:
                item_url = item.get("url")
                content = self._get(item_url, referer=url)
                return bool(self._extract_supported_embeds(content, item_url or url))
            except Exception:
                return False

        if items:
            with ThreadPoolExecutor(max_workers=min(8, len(items))) as pool:
                keep = list(pool.map(playable, items))
            items = [item for item, supported in zip(items, keep) if supported]
        return items, has_next

    def _extract_supported_embeds(self, page_html, page_url):
        embeds = []
        base = page_url or self.base_url
        for tag in re.findall(r"<iframe\b[^>]+>", page_html or "", re.IGNORECASE):
            for value in re.findall(r'(?:data-lazy-src|src)=["\']([^"\']+)', tag, re.IGNORECASE):
                embed = html.unescape(value).strip()
                if not embed:
                    continue
                embed = "https:" + embed if embed.startswith("//") else urllib.parse.urljoin(base, embed)
                if resolver.resolver_entry_for_url(embed) and embed not in embeds:
                    embeds.append(embed)
        return embeds

    def resolve_recording_stream(self, url):
        page = self._get(url, referer=self.base_url)
        embeds = self._extract_supported_embeds(page, url)
        stream, headers, _ = resolver.resolve_first_working(
            embeds,
            referer=url,
            headers=self._headers(url, accept="*/*"),
            addon=self.addon,
        )
        if stream:
            ext = "m3u8" if ".m3u8" in stream.lower() else "mp4"
            return {"url": stream, "headers": headers or {}, "extension": ext}

        return None
