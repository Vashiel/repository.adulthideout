# -*- coding: utf-8 -*-
import re
import html
import urllib.parse

from resources.lib.resolvers import resolver
from resources.lib.wordpress_api_tube import WordPressApiTube


class PornBusy(WordPressApiTube):
    def __init__(self, addon_handle, addon=None):
        super().__init__("pornbusy", "PornBusy", "https://pornbusy.com/", addon_handle, addon)

    def _thumbnail(self, post):
        thumbnail = super()._thumbnail(post)
        if thumbnail and thumbnail != self.icon and "|" not in thumbnail:
            thumbnail += "|" + urllib.parse.urlencode({
                "User-Agent": self.ua,
                "Referer": self.base_url,
            })
        return thumbnail

    def resolve_recording_stream(self, url):
        page = self._get(url, referer=self.base_url)
        if not page:
            return None

        # 1. Check for direct jwplayer or video tag stream
        file_match = re.search(r'jwplayer\([^)]*\)\.setup\(\s*\{[\s\S]*?file:\s*["\']([^"\']+)["\']', page, re.I)
        if not file_match:
            file_match = re.search(r'file:\s*["\'](https?://[^"\']+\.(?:mp4|m3u8)[^"\']*)["\']', page, re.I)
        if file_match:
            stream = html.unescape(file_match.group(1)).strip()
            ext = "m3u8" if ".m3u8" in stream.lower() else "mp4"
            return {"url": stream, "headers": self._headers(url), "extension": ext}

        # 2. Check for iframes with resolver hosts
        embeds = []
        for value in re.findall(r'<iframe\b[^>]+src=["\']([^"\']+)', page or "", re.I):
            embed = html.unescape(value).strip()
            if embed.startswith("//"):
                embed = "https:" + embed
            else:
                embed = urllib.parse.urljoin(url, embed)
            if resolver.resolver_entry_for_url(embed) and embed not in embeds:
                embeds.append(embed)

        stream_url, headers, _ = resolver.resolve_first_working(
            embeds,
            referer=url,
            headers=self._headers(url),
            addon=self.addon,
        )
        if stream_url:
            ext = "m3u8" if ".m3u8" in stream_url.lower() else "mp4"
            return {"url": stream_url, "headers": headers or {}, "extension": ext}

        # 3. Direct mp4 in page
        for m in re.findall(r'https?://(?:y\d+\.zpi\.cx|cdn\.videy\.co)/[^"\'<>\s]+\.mp4', page, re.I):
            return {"url": m, "headers": self._headers(url), "extension": "mp4"}

        return None
