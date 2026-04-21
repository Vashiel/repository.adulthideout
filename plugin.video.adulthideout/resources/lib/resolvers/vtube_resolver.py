# -*- coding: utf-8 -*-
"""
Small AdultHideout-native VTube resolver.

Based on the public ResolveURL VTube resolver pattern:
Copyright (C) 2021 shellc0de, GPL-3.0-or-later.
Ported to AdultHideout without the ResolveURL runtime dependency.
"""

import html
import re
import urllib.parse

import xbmc

from resources.lib.resolvers import resolver_utils


DOMAINS = ("vtube.to", "vtplay.net", "vtbe.net", "vtbe.to", "vtube.network")


def _normalise_embed_url(url):
    parsed = urllib.parse.urlparse(url)
    host = parsed.netloc.lower()
    path = parsed.path.strip("/")

    media_id = ""
    match = re.search(r"(?:embed-)?([0-9a-zA-Z]+)", path)
    if match:
        media_id = match.group(1)
    if not media_id:
        return url

    # ResolveURL uses vtbe.to as the canonical embed endpoint.
    return "https://vtbe.to/embed-{}.html".format(media_id)


def resolve(url, referer=None, headers=None):
    xbmc.log("[AdultHideout][vtube] Resolving: {}".format(url), xbmc.LOGINFO)
    headers = dict(headers or {})
    headers.setdefault("User-Agent", resolver_utils.get_ua())
    headers["Referer"] = referer or url

    embed_url = _normalise_embed_url(url)
    page = resolver_utils.http_get(embed_url, headers=headers, timeout=20)
    if not page:
        xbmc.log("[AdultHideout][vtube] Empty embed page", xbmc.LOGWARNING)
        return None, {}

    for pattern in (
        r'''sources:\s*\[\s*\{\s*file:\s*["'](?P<url>[^"']+)''',
        r'''file\s*[:=]\s*["'](?P<url>https?://[^"']+\.(?:m3u8|mp4)[^"']*)''',
        r'''(?P<url>https?://[^\s"']+\.(?:m3u8|mp4)[^\s"']*)''',
    ):
        match = re.search(pattern, page, re.IGNORECASE)
        if match:
            stream_url = html.unescape(match.group("url")).strip()
            xbmc.log("[AdultHideout][vtube] Resolved stream", xbmc.LOGINFO)
            return stream_url, headers

    xbmc.log("[AdultHideout][vtube] No playable stream found", xbmc.LOGWARNING)
    return None, {}
