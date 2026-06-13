# -*- coding: utf-8 -*-
import re
import urllib.parse
import xbmc
import requests

from resources.lib.resolvers import resolver_utils

UA = resolver_utils.get_ua()


def resolve(url, referer=None, headers=None):
    xbmc.log("[AdultHideout][watchstreamhd] Resolving: {}".format(url), xbmc.LOGINFO)

    match = re.search(r'/video/([a-zA-Z0-9]+)', url)
    if not match:
        xbmc.log("[AdultHideout][watchstreamhd] Could not parse video ID from: {}".format(url), xbmc.LOGERROR)
        return "", {}
    video_id = match.group(1)

    parsed_url = urllib.parse.urlparse(url)
    host = "{}://{}".format(parsed_url.scheme, parsed_url.netloc)

    api_url = "{}/player/index.php?data={}&do=getVideo".format(host, video_id)

    request_headers = {
        "User-Agent": UA,
        "Referer": url,
        "X-Requested-With": "XMLHttpRequest",
    }
    if headers:
        request_headers.update(headers)

    post_data = {
        "hash": video_id,
        "r": referer or "https://familypornhd.com/"
    }

    try:
        res = requests.post(api_url, headers=request_headers, data=post_data, timeout=20)
    except Exception as exc:
        xbmc.log("[AdultHideout][watchstreamhd] API request failed: {}".format(exc), xbmc.LOGERROR)
        return "", {}

    if res.status_code != 200:
        xbmc.log("[AdultHideout][watchstreamhd] HTTP {} for API request".format(res.status_code), xbmc.LOGERROR)
        return "", {}

    try:
        jsondata = res.json()
        secured_link = jsondata.get("securedLink")
    except Exception as exc:
        xbmc.log("[AdultHideout][watchstreamhd] Failed parsing API JSON: {}".format(exc), xbmc.LOGERROR)
        return "", {}

    if not secured_link:
        xbmc.log("[AdultHideout][watchstreamhd] securedLink not found in API response", xbmc.LOGERROR)
        return "", {}

    play_headers = {
        "User-Agent": request_headers.get("User-Agent", UA),
        "Referer": url,
    }
    try:
        probe = requests.get(secured_link, headers=play_headers, timeout=20)
        if probe.status_code != 200 or "#EXTM3U" not in probe.text[:2048]:
            xbmc.log(
                "[AdultHideout][watchstreamhd] Invalid master playlist response: HTTP {}".format(
                    probe.status_code
                ),
                xbmc.LOGERROR,
            )
            return "", {}
    except Exception as exc:
        xbmc.log("[AdultHideout][watchstreamhd] Failed to probe master playlist: {}".format(exc), xbmc.LOGERROR)
        return "", {}

    xbmc.log("[AdultHideout][watchstreamhd] Resolved direct playlist: {}".format(secured_link), xbmc.LOGINFO)
    return secured_link, play_headers
