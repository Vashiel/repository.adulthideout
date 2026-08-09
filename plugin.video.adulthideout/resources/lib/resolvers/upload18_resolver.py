# -*- coding: utf-8 -*-
import html
import json
import re

import requests
import xbmc

from resources.lib.resolvers import resolver_utils


def resolve(url, referer=None, headers=None):
    request_headers = dict(headers or {})
    request_headers.update({
        "User-Agent": request_headers.get("User-Agent") or resolver_utils.get_ua(),
        "Referer": referer or url,
        "Accept-Encoding": "identity",
    })
    try:
        session = requests.Session()
        response = session.get(url, headers=request_headers, timeout=20)
        response.raise_for_status()
        config_match = re.search(
            r'window\.PLAYER_CONFIG\s*=\s*(\{[\s\S]*?\})\s*;',
            response.text,
            re.I,
        )
        config = {}
        if config_match:
            try:
                config = json.loads(config_match.group(1))
            except (TypeError, ValueError):
                config = {}
        stream = config.get("m3u8") or config.get("alternate720")
        if not stream:
            match = re.search(r'["\']?m3u8["\']?\s*:\s*["\']([^"\']+)', response.text, re.I)
            stream = match.group(1) if match else ""
        stream = html.unescape(stream).replace("\\/", "/").replace("\\u0026", "&")
        if not stream:
            return None, {}
        playback_headers = {
            "User-Agent": request_headers["User-Agent"],
            "Referer": url,
            "Origin": "https://upload18.org",
        }
        if session.cookies:
            playback_headers["Cookie"] = "; ".join(
                "{}={}".format(cookie.name, cookie.value) for cookie in session.cookies
            )
        xbmc.log("[AdultHideout][upload18] HLS stream resolved", xbmc.LOGINFO)
        return stream, playback_headers
    except Exception as exc:
        xbmc.log("[AdultHideout][upload18] Resolve failed: {}".format(exc), xbmc.LOGERROR)
        return None, {}
