# -*- coding: utf-8 -*-
import os
import re
import sys
import urllib.parse

import xbmc

from resources.lib.resolvers import resolver_utils

try:
    addon_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
    vendor_path = os.path.join(addon_root, "resources", "lib", "vendor")
    if os.path.isdir(vendor_path) and vendor_path not in sys.path:
        sys.path.insert(0, vendor_path)
    import cloudscraper
except Exception:
    cloudscraper = None


UA = resolver_utils.get_ua()


def _make_session():
    if cloudscraper:
        try:
            return cloudscraper.create_scraper(
                browser={"browser": "chrome", "platform": "windows", "desktop": True}
            )
        except Exception:
            pass
    import requests
    return requests.Session()


def resolve(url, referer=None, headers=None):
    xbmc.log("[AdultHideout][turboplayers] Resolving: {}".format(url), xbmc.LOGINFO)
    session = _make_session()
    request_headers = {
        "User-Agent": UA,
        "Referer": referer or url,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
    if headers:
        request_headers.update(headers)

    try:
        response = session.get(url, headers=request_headers, timeout=25, allow_redirects=True)
    except Exception as exc:
        xbmc.log("[AdultHideout][turboplayers] Request failed: {}".format(exc), xbmc.LOGERROR)
        return "", {}

    if response.status_code != 200:
        xbmc.log("[AdultHideout][turboplayers] HTTP {} for {}".format(response.status_code, url), xbmc.LOGERROR)
        return "", {}

    html = (response.text or "").replace("\x00", "")
    match = re.search(r"""var\s+urlPlay\s*=\s*['"]([^'"]+\.mp4[^'"]*)['"]""", html, re.IGNORECASE)
    if not match:
        match = re.search(r"""['"]((?:https?:)?//[^'"]+\.mp4[^'"]*)['"]""", html, re.IGNORECASE)
    if not match:
        xbmc.log("[AdultHideout][turboplayers] No MP4 urlPlay found", xbmc.LOGERROR)
        return "", {}

    stream_url = match.group(1).replace("\\/", "/")
    if stream_url.startswith("//"):
        stream_url = "https:" + stream_url
    elif stream_url.startswith("/"):
        parsed = urllib.parse.urlparse(response.url or url)
        stream_url = "{}://{}{}".format(parsed.scheme, parsed.netloc, stream_url)

    parsed_embed = urllib.parse.urlparse(response.url or url)
    origin = "{}://{}".format(parsed_embed.scheme, parsed_embed.netloc)
    play_headers = {
        "User-Agent": request_headers.get("User-Agent", UA),
        "Referer": response.url or url,
        "Origin": origin,
    }
    xbmc.log("[AdultHideout][turboplayers] Resolved: {}".format(stream_url[:120]), xbmc.LOGINFO)
    return stream_url, play_headers
