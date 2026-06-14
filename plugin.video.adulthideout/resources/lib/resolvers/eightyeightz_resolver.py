# -*- coding: utf-8 -*-
import json
import re
import urllib.parse
import urllib.request

import requests
import xbmc

from resources.lib.resolvers import resolver_utils
from resources.lib.vendor.byse_crypto import cbc_decrypt, pkcs7_unpad


_API_BASE = "https://88z.io"
_KEY = b"kiemtienmua911ca"
_IV = b"1234567890oiuytr"


def _headers(video_id=None, accept="application/json, text/plain, */*"):
    referer = "https://88z.io/"
    if video_id:
        referer += "#{}".format(video_id)
    return {
        "User-Agent": resolver_utils.get_ua(),
        "Accept": accept,
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "identity",
        "Origin": "https://88z.io",
        "Referer": referer,
    }


def _play_headers():
    return {
        "User-Agent": resolver_utils.get_ua(),
        "Accept": "*/*",
        "Accept-Language": "en-US,en;q=0.9",
        "Origin": "https://88z.io",
        "Referer": "https://88z.io/",
    }


def _extract_video_id(url):
    url = urllib.parse.unquote(url or "").strip()
    parsed = urllib.parse.urlparse(url)
    if parsed.fragment:
        return parsed.fragment.split("&", 1)[0].strip()
    query = urllib.parse.parse_qs(parsed.query)
    for key in ("id", "v", "video"):
        value = query.get(key)
        if value and value[0]:
            return value[0].strip()
    match = re.search(r"88z\.io/(?:embed/|video/)?#?([A-Za-z0-9_-]{4,})", url, re.IGNORECASE)
    return match.group(1) if match else ""


def _decrypt_json(hex_payload):
    if not hex_payload:
        return {}
    decrypted = cbc_decrypt(_KEY, _IV, bytes.fromhex(hex_payload.strip()))
    decrypted = pkcs7_unpad(decrypted).decode("utf-8", errors="replace")
    return json.loads(decrypted)


def _api_get(video_id, endpoint="video"):
    api_url = "{}/api/v1/{}?id={}".format(_API_BASE, endpoint, urllib.parse.quote(video_id))
    try:
        response = requests.get(api_url, headers=_headers(video_id), timeout=18)
        if response.status_code != 200:
            xbmc.log("[AdultHideout][88z] API HTTP {} for {}".format(response.status_code, video_id), xbmc.LOGWARNING)
            return {}
        return _decrypt_json(response.text)
    except Exception as exc:
        xbmc.log("[AdultHideout][88z] API/decrypt failed for {}: {}".format(video_id, exc), xbmc.LOGWARNING)
        return {}


def _absolute(url):
    if not url:
        return ""
    url = str(url).strip()
    if url.startswith("//"):
        return "https:" + url
    if url.startswith("/"):
        return urllib.parse.urljoin(_API_BASE, url)
    return url


def _stream_candidates(data):
    candidates = []
    source = _absolute(data.get("source"))
    if source:
        candidates.append(source)
    tiktok = _absolute(data.get("hlsVideoTiktok"))
    if tiktok:
        candidates.append(tiktok)
    cf = _absolute(data.get("cf"))
    if cf:
        candidates.append(cf)
    for item in data.get("sources") or []:
        if isinstance(item, dict):
            src = _absolute(item.get("src") or item.get("url") or item.get("file"))
        else:
            src = _absolute(item)
        if src:
            candidates.append(src)

    seen = set()
    unique = []
    for candidate in candidates:
        if candidate not in seen:
            seen.add(candidate)
            unique.append(candidate)
    return unique


def _probe_hls(url, headers):
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=12) as response:
            status = response.getcode() or 200
            data = response.read(4096)
        return status < 400 and b"#EXTM3U" in data
    except Exception as exc:
        xbmc.log("[AdultHideout][88z] HLS probe failed: {}".format(exc), xbmc.LOGDEBUG)
        return False


def _parse_stream_info(line):
    info = {}
    for key, value in re.findall(r"([A-Z0-9-]+)=([^,]+)", line or ""):
        value = value.strip().strip('"')
        info[key.upper()] = value
    resolution = info.get("RESOLUTION") or ""
    match = re.match(r"(\d+)x(\d+)", resolution)
    if match:
        info["WIDTH"] = int(match.group(1))
        info["HEIGHT"] = int(match.group(2))
    try:
        info["BANDWIDTH_INT"] = int(info.get("BANDWIDTH") or "0")
    except Exception:
        info["BANDWIDTH_INT"] = 0
    return info


def _select_variant(master_url, headers):
    try:
        req = urllib.request.Request(master_url, headers=headers)
        with urllib.request.urlopen(req, timeout=12) as response:
            status = response.getcode() or 200
            text = response.read(128 * 1024).decode("utf-8", errors="replace")
        if status >= 400 or "#EXTM3U" not in text:
            return ""
    except Exception as exc:
        xbmc.log("[AdultHideout][88z] Variant read failed: {}".format(exc), xbmc.LOGDEBUG)
        return ""

    variants = []
    pending_info = None
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("#EXT-X-STREAM-INF"):
            pending_info = _parse_stream_info(line)
            continue
        if pending_info is not None and not line.startswith("#"):
            variant_url = urllib.parse.urljoin(master_url, line)
            variants.append((variant_url, pending_info))
            pending_info = None

    if not variants:
        return master_url

    hd_or_lower = [item for item in variants if item[1].get("HEIGHT", 9999) <= 720]
    if hd_or_lower:
        selected = max(hd_or_lower, key=lambda item: (item[1].get("HEIGHT", 0), item[1].get("BANDWIDTH_INT", 0)))
    else:
        selected = min(variants, key=lambda item: item[1].get("BANDWIDTH_INT", 0) or 999999999)

    variant_url, info = selected
    xbmc.log(
        "[AdultHideout][88z] Selected HLS variant: {} ({}p, {} bps)".format(
            variant_url,
            info.get("HEIGHT", "?"),
            info.get("BANDWIDTH_INT", "?"),
        ),
        xbmc.LOGINFO,
    )
    return variant_url


def resolve(url, referer=None, headers=None):
    video_id = _extract_video_id(url)
    if not video_id:
        xbmc.log("[AdultHideout][88z] No video id found in {}".format(url), xbmc.LOGWARNING)
        return "", {}

    xbmc.log("[AdultHideout][88z] Resolving id {}".format(video_id), xbmc.LOGINFO)
    data = _api_get(video_id, "video")
    if not data:
        return "", {}

    play_headers = _play_headers()
    if headers:
        for key, value in headers.items():
            if value and key.lower() not in ("range", "referer", "origin"):
                play_headers[key] = value

    for stream_url in _stream_candidates(data):
        if ".m3u8" not in stream_url.lower():
            continue
        selected_url = _select_variant(stream_url, play_headers) or stream_url
        if _probe_hls(selected_url, play_headers):
            xbmc.log("[AdultHideout][88z] Resolved HLS stream: {}".format(selected_url), xbmc.LOGINFO)
            return selected_url, play_headers

    xbmc.log("[AdultHideout][88z] No playable HLS stream found for {}".format(video_id), xbmc.LOGWARNING)
    return "", {}
