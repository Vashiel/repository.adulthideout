# -*- coding: utf-8 -*-
"""
Small AdultHideout-native Vidello resolver.

Based on the public ResolveURL Vidello resolver pattern:
Copyright (C) 2023 shellc0de, GPL-3.0-or-later.
Ported to AdultHideout without the ResolveURL runtime dependency.
"""

import html
import re
import urllib.parse

import xbmc

from resources.lib.resolvers import resolver_utils


def _normalise_embed_url(url):
    parsed = urllib.parse.urlparse(url)
    path = parsed.path.strip("/")
    if path.startswith("embed-") or path.startswith("e/"):
        return url

    media_id = path.split("/")[-1]
    if media_id:
        return urllib.parse.urlunparse((parsed.scheme or "https", parsed.netloc, "/embed-" + media_id + ".html", "", "", ""))
    return url


def resolve(url, referer=None, headers=None):
    xbmc.log("[AdultHideout][vidello] Resolving: {}".format(url), xbmc.LOGINFO)
    headers = dict(headers or {})
    headers.setdefault("User-Agent", resolver_utils.get_ua())
    headers["Referer"] = referer or url

    embed_url = _normalise_embed_url(url)
    page = resolver_utils.http_get(embed_url, headers=headers, timeout=20)
    if not page:
        xbmc.log("[AdultHideout][vidello] Empty embed page", xbmc.LOGWARNING)
        return None, {}

    for pattern in (
        r'''sources:\s*\[\s*\{\s*src:\s*["'](?P<url>[^"']+)''',
        r'''src\s*[:=]\s*["'](?P<url>https?://[^"']+\.(?:m3u8|mp4)[^"']*)''',
        r'''(?P<url>https?://[^\s"']+\.(?:m3u8|mp4)[^\s"']*)''',
    ):
        match = re.search(pattern, page, re.IGNORECASE)
        if match:
            stream_url = html.unescape(match.group("url")).strip()
            xbmc.log("[AdultHideout][vidello] Resolved stream", xbmc.LOGINFO)
            return stream_url, headers

    xbmc.log("[AdultHideout][vidello] No playable stream found", xbmc.LOGWARNING)
    return None, {}
