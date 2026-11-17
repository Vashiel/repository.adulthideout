# -*- coding: utf-8 -*-
import base64
import html
import json
import urllib.parse

import requests
import xbmc

from resources.lib.resolvers import resolver_utils
from resources.lib.vendor.byse_crypto import gcm_decrypt

_CODE_PREFIXES = ("e", "v", "d", "embed", "watch")


def _b64url_decode(value):
    padded = str(value or "").strip().replace("-", "+").replace("_", "/")
    padded += "=" * ((-len(padded)) % 4)
    return base64.b64decode(padded)


def _extract_video_code(url):
    parsed = urllib.parse.urlparse((url or "").strip())
    parts = [part for part in parsed.path.split("/") if part]
    if not parts:
        return ""
    if len(parts) >= 2 and parts[0].lower() in _CODE_PREFIXES:
        return parts[1]
    return parts[0]


def _select_key_parts(key_parts, version):
    parts = [part for part in (key_parts or []) if isinstance(part, str) and part]
    if not parts:
        return []
    try:
        ver = int(str(version or "").strip())
    except (TypeError, ValueError):
        return parts
    # Byse Frontend (Qa/ws) pairs key_parts[version] with key_parts[31 - version] (1-indexed).
    other = 31 - ver
    if 1 <= ver <= len(parts) and 1 <= other <= len(parts):
        return [parts[ver - 1], parts[other - 1]]
    return parts


def _decrypt_playback(playback):
    if not isinstance(playback, dict) or not playback.get("payload"):
        return {}
    if str(playback.get("algorithm") or "").upper() != "AES-256-GCM":
        return {}
    selected = _select_key_parts(playback.get("key_parts"), playback.get("version"))
    if not selected or not playback.get("iv"):
        return {}
    key_bytes = b"".join(_b64url_decode(part) for part in selected)
    iv_bytes = _b64url_decode(playback["iv"])
    raw_payload = _b64url_decode(playback["payload"])
    if len(raw_payload) <= 16:
        return {}
    plaintext = gcm_decrypt(key_bytes, iv_bytes, raw_payload[:-16], raw_payload[-16:])
    return json.loads(plaintext.decode("utf-8", errors="replace"))


def _sorted_source_urls(decrypted):
    candidates = []
    for entry in (decrypted or {}).get("sources") or []:
        if isinstance(entry, str):
            raw = entry
            height = bitrate = 0
        elif isinstance(entry, dict):
            raw = entry.get("url") or entry.get("src") or entry.get("file") or ""
            height = int(entry.get("height") or 0)
            bitrate = int(entry.get("bitrate_kbps") or entry.get("bitrate") or 0)
        else:
            continue
        clean = html.unescape(str(raw or "").strip())
        if clean.startswith("//"):
            clean = "https:" + clean
        if clean.startswith(("http://", "https://")):
            candidates.append((height, bitrate, clean))
    candidates.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return [item[2] for item in candidates]


def _probe_stream(stream_url, headers):
    try:
        probe_headers = dict(headers)
        probe_headers["Range"] = "bytes=0-1023"
        resp = requests.get(stream_url, headers=probe_headers, timeout=12, stream=True)
        chunk = resp.raw.read(1024, decode_content=False)
        resp.close()
        ctype = (resp.headers.get("Content-Type") or "").lower()
        return resp.status_code in (200, 206) and bool(chunk) and "text/html" not in ctype
    except Exception:
        return False


def resolve(url, referer=None, headers=None):
    """Resolve Byse Frontend embeds whose /api/videos/<code> response includes AES-GCM playback."""
    parsed = urllib.parse.urlparse((url or "").strip())
    host = parsed.netloc
    code = _extract_video_code(url)
    if not host or not code:
        return "", {}

    scheme = parsed.scheme or "https"
    origin = "{}://{}".format(scheme, host)
    ua = (headers or {}).get("User-Agent") or resolver_utils.get_ua()
    api_url = "{}/api/videos/{}".format(origin, urllib.parse.quote(code))
    api_headers = {
        "User-Agent": ua,
        "Referer": url,
        "Accept": "application/json, text/plain, */*",
    }

    try:
        resp = requests.get(api_url, headers=api_headers, timeout=15)
        if resp.status_code != 200:
            xbmc.log("[AdultHideout][byse_frontend] API HTTP {} for {}".format(resp.status_code, api_url), xbmc.LOGWARNING)
            return "", {}
        data = resp.json() or {}
    except Exception as exc:
        xbmc.log("[AdultHideout][byse_frontend] API error for {}: {}".format(api_url, exc), xbmc.LOGWARNING)
        return "", {}

    playback = data.get("playback")
    if not playback:
        xbmc.log("[AdultHideout][byse_frontend] No playback payload for {}/{}".format(host, code), xbmc.LOGWARNING)
        return "", {}

    try:
        decrypted = _decrypt_playback(playback)
    except Exception as exc:
        xbmc.log("[AdultHideout][byse_frontend] Playback decrypt failed for {}/{}: {}".format(host, code, exc), xbmc.LOGWARNING)
        return "", {}

    play_headers = {
        "User-Agent": ua,
        "Referer": origin + "/",
        "Origin": origin,
        "Accept": "*/*",
    }
    urls = _sorted_source_urls(decrypted)
    for stream_url in urls:
        if _probe_stream(stream_url, play_headers):
            xbmc.log("[AdultHideout][byse_frontend] Resolved {} -> {}".format(host, stream_url[:140]), xbmc.LOGINFO)
            return stream_url, play_headers

    return (urls[0], play_headers) if urls else ("", {})
