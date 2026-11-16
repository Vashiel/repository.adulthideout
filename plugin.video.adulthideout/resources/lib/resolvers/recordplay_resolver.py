# -*- coding: utf-8 -*-
import json
import re
import urllib.parse

from resources.lib.resolvers import resolver_utils


def _unpack(page):
    match = re.search(
        r"eval\(function\(p,a,c,k,e,d\).*?\}\('((?:\\.|[^'])*)',"
        r"(\d+),(\d+),'((?:\\.|[^'])*)'\.split\('\|'\)",
        page or "",
        re.DOTALL,
    )
    if not match:
        return page or ""
    return resolver_utils.unpack_js(
        match.group(1), int(match.group(2)), int(match.group(3)), match.group(4).split("|")
    )


# The newer player (e.g. video.playerrecord.cfd) is a script app that asks this API for the stream.
_PLAY_API = "https://embedorigin.cc/app/v1/play/{}?embed=1"


def _resolve_play_api(url, user_agent):
    code = re.search(r"/(?:e|embed)/([a-z0-9]{12})", url or "", re.I)
    if not code:
        return None, {}
    parts = urllib.parse.urlsplit(url)
    origin = "{}://{}".format(parts.scheme, parts.netloc)
    api_headers = {"User-Agent": user_agent, "Referer": origin + "/", "Origin": origin}
    try:
        data = json.loads(resolver_utils.http_get(_PLAY_API.format(code.group(1)), headers=api_headers, retries=1, timeout=20))
    except Exception:
        return None, {}
    stream = (data or {}).get("hls") or (data or {}).get("mp4")
    if not stream:
        return None, {}
    return stream, {"User-Agent": user_agent, "Referer": origin + "/"}


def resolve(url, referer=None, headers=None):
    request_headers = dict(headers or {})
    request_headers.setdefault("User-Agent", resolver_utils.get_ua())
    if "playerrecord" in (url or ""):
        return _resolve_play_api(url, request_headers["User-Agent"])
    request_headers["Referer"] = referer or url
    page = resolver_utils.http_get(url, headers=request_headers, retries=1, timeout=20)
    unpacked = _unpack(page)
    links = {}
    links_match = re.search(r"var\s+links\s*=\s*\{([^}]+)\}", unpacked, re.I)
    if links_match:
        for key, value in re.findall(r'["\']?(hls\d+)["\']?\s*:\s*["\']([^"\']+)', links_match.group(1), re.I):
            links[key.lower()] = value.replace("\\/", "/")
    for key in ("hls2", "hls3", "hls4"):
        stream = links.get(key)
        if not stream:
            continue
        stream = urllib.parse.urljoin(url, stream)
        return stream, {"User-Agent": request_headers["User-Agent"], "Referer": "https://recordplay.biz/"}
    direct = re.search(r'https?://[^\s"\']+\.m3u8[^\s"\']*', unpacked)
    if direct:
        return direct.group(0), {"User-Agent": request_headers["User-Agent"], "Referer": "https://recordplay.biz/"}
    return None, {}

