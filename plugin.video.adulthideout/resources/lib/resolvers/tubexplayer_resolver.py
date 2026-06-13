# -*- coding: utf-8 -*-
import ast
import re
import urllib.parse
import xbmc
import requests

from resources.lib.resolvers import resolver_utils

UA = resolver_utils.get_ua()


def get_base_n(num, base):
    digits = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
    if num == 0:
        return "0"
    result = []
    while num > 0:
        result.append(digits[num % base])
        num //= base
    return "".join(reversed(result))


def unpack(p, a, c, k):
    # Sort or replace from high index down to 0
    for i in range(c - 1, -1, -1):
        if i < len(k) and k[i]:
            base_n = get_base_n(i, a)
            pattern = r'\b' + re.escape(base_n) + r'\b'
            p = re.sub(pattern, k[i], p)
    return p


def resolve(url, referer=None, headers=None):
    xbmc.log("[AdultHideout][tubexplayer] Resolving: {}".format(url), xbmc.LOGINFO)

    request_headers = {
        "User-Agent": UA,
        "Referer": referer or "https://pornobae.com/",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
    if headers:
        request_headers.update(headers)

    try:
        res = requests.get(url, headers=request_headers, timeout=20)
    except Exception as exc:
        xbmc.log("[AdultHideout][tubexplayer] Request failed: {}".format(exc), xbmc.LOGERROR)
        return "", {}

    if res.status_code != 200:
        xbmc.log("[AdultHideout][tubexplayer] HTTP {} for {}".format(res.status_code, url), xbmc.LOGERROR)
        return "", {}

    match = re.search(
        r"eval\(function\(p,a,c,k,e,d\).+?return p\}\((['\"].+?['\"]),(\d+),(\d+),(['\"].+?['\"])\.split\(['\"]\|['\"]\)\)\)",
        res.text,
    )
    if not match:
        xbmc.log("[AdultHideout][tubexplayer] Failed to match eval pattern in HTML", xbmc.LOGERROR)
        return "", {}

    try:
        payload_str = ast.literal_eval(match.group(1))
        base = int(match.group(2))
        count = int(match.group(3))
        words = ast.literal_eval(match.group(4)).split("|")
    except Exception as exc:
        xbmc.log("[AdultHideout][tubexplayer] Failed parsing eval parameters: {}".format(exc), xbmc.LOGERROR)
        return "", {}

    try:
        unpacked_js = unpack(payload_str, base, count, words)
    except Exception as exc:
        xbmc.log("[AdultHideout][tubexplayer] Failed unpacking: {}".format(exc), xbmc.LOGERROR)
        return "", {}

    file_match = re.search(r'file\s*:\s*["\'](https?://[^"\']+\.m3u8[^"\']*)["\']', unpacked_js)
    if not file_match:
        xbmc.log("[AdultHideout][tubexplayer] Master manifest URL not found in unpacked JS", xbmc.LOGERROR)
        return "", {}

    stream_url = file_match.group(1)

    play_headers = {
        "User-Agent": request_headers.get("User-Agent", UA),
    }

    xbmc.log("[AdultHideout][tubexplayer] Resolved: {}".format(stream_url[:120]), xbmc.LOGINFO)
    return stream_url, play_headers
