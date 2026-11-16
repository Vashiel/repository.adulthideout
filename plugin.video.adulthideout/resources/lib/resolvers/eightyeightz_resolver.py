# -*- coding: utf-8 -*-
import json
import re
import time
import urllib.parse
import urllib.request

import requests
import xbmc

from resources.lib.resolvers import resolver_utils
from resources.lib.vendor.byse_crypto import cbc_decrypt, cbc_encrypt, pkcs7_pad, pkcs7_unpad


_API_BASE = "https://88z.io"
_LEGACY_KEY = b"kiemtienmua911ca"
_LEGACY_IV = b"1234567890oiuytr"

_SIMPLE_KEY_CHARS = ["𝕊", "𝔼", "𝕮", "𝚁", "𝔼", "𝚃", "𝓚", "𝓔", "𝓨", "𝟙", "𝟚", "𝟛"]
_SIMPLE_SALT_CHARS = ["🔐", "🗝️", "🔑", "🚪", "🛡️", "⚡"]


def _headers(origin=_API_BASE, referer=None, accept="application/json, text/plain, */*"):
    return {
        "User-Agent": resolver_utils.get_ua(),
        "Accept": accept,
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "identity",
        "Origin": origin,
        "Referer": referer or (origin + "/"),
    }


def _play_headers(origin=_API_BASE):
    return {
        "User-Agent": resolver_utils.get_ua(),
        "Accept": "*/*",
        "Accept-Language": "en-US,en;q=0.9",
        "Origin": origin,
        "Referer": origin + "/",
    }


def _simple_key(day_offset=0):
    hex_prefix = "".join(format(ord(ch), "x") for ch in _SIMPLE_KEY_CHARS)
    day_hex = format(int(time.time() // 86400) + day_offset, "x")
    key_hex = (hex_prefix + day_hex)[:32].ljust(32, "0")
    return bytes.fromhex(key_hex)


def _simple_iv(hostname=""):
    salt_hex = "".join(format(ord(ch[0]), "x") for ch in _SIMPLE_SALT_CHARS)
    host_hex = (hostname or "").encode("utf-8").hex()
    iv_hex = (salt_hex + host_hex)[:32].ljust(32, "0")
    return bytes.fromhex(iv_hex)


def _simple_encrypt(text, hostname):
    padded = pkcs7_pad(text.encode("utf-8"), 16)
    return cbc_encrypt(_simple_key(0), _simple_iv(hostname), padded).hex()


def _simple_decrypt_json(hex_payload, hostname):
    if not hex_payload:
        return {}
    raw = bytes.fromhex(hex_payload.strip())
    iv = _simple_iv(hostname)
    for day_offset in (0, -1, 1):
        try:
            decrypted = pkcs7_unpad(cbc_decrypt(_simple_key(day_offset), iv, raw), 16)
            return json.loads(decrypted.decode("utf-8", errors="replace"))
        except Exception:
            continue
    return {}


def _extract_slug_and_host(url):
    url = urllib.parse.unquote(url or "").strip()
    parsed = urllib.parse.urlparse(url)
    host = (parsed.hostname or "").lower()
    if parsed.fragment:
        slug = parsed.fragment.split("&", 1)[0].strip()
        if slug:
            return slug, host
    query = urllib.parse.parse_qs(parsed.query)
    for key in ("id", "s", "v", "video", "file1"):
        value = query.get(key)
        if value and value[0]:
            return value[0].strip(), host
    path_parts = [part for part in parsed.path.split("/") if part]
    if path_parts:
        return path_parts[-1].strip(), host
    match = re.search(r"(?:88z|65s|38x)\.io/(?:embed/|video/|e/)?#?([A-Za-z0-9_-]{3,})", url, re.IGNORECASE)
    return (match.group(1) if match else ""), host


def _decrypt_legacy_json(hex_payload):
    if not hex_payload:
        return {}
    decrypted = cbc_decrypt(_LEGACY_KEY, _LEGACY_IV, bytes.fromhex(hex_payload.strip()))
    decrypted = pkcs7_unpad(decrypted).decode("utf-8", errors="replace")
    return json.loads(decrypted)


def _legacy_api_get(video_id):
    api_url = "{}/api/v1/video?id={}".format(_API_BASE, urllib.parse.quote(video_id))
    referer = "{}/#{}".format(_API_BASE, video_id)
    try:
        response = requests.get(api_url, headers=_headers(_API_BASE, referer), timeout=15)
        if response.status_code != 200:
            xbmc.log("[AdultHideout][88z] Legacy API HTTP {} for {}".format(response.status_code, video_id), xbmc.LOGWARNING)
            return {}
        return _decrypt_legacy_json(response.text)
    except Exception as exc:
        xbmc.log("[AdultHideout][88z] Legacy API/decrypt failed for {}: {}".format(video_id, exc), xbmc.LOGWARNING)
        return {}


def _resolve_88z_redirect(video_id):
    """88z.io resolves legacy hash IDs to newer player URLs (e.g. 38x.io)."""
    api_url = "{}/api/public/resolve?file1={}".format(_API_BASE, urllib.parse.quote(video_id))
    referer = "{}/#{}".format(_API_BASE, video_id)
    try:
        response = requests.get(api_url, headers=_headers(_API_BASE, referer), timeout=15)
        if response.status_code == 200:
            payload = response.json()
            target = (payload or {}).get("url") or (payload or {}).get("link2") or ""
            if target.startswith("http"):
                return target
    except Exception as exc:
        xbmc.log("[AdultHideout][88z] Public redirect lookup failed for {}: {}".format(video_id, exc), xbmc.LOGWARNING)
    return ""


def _tracking_get(url, slug, hostname):
    origin = "https://{}".format(hostname)
    parsed = urllib.parse.urlparse(url or "")
    pv_vals = urllib.parse.parse_qs(parsed.query).get("pv")
    pv_param = "&pv=" + urllib.parse.quote(pv_vals[0]) if pv_vals and pv_vals[0] else ""
    try:
        encrypted_slug = _simple_encrypt(slug, hostname)
        api_url = "{}/api/stream/tracking?c={}&ld=1{}".format(origin, encrypted_slug, pv_param)
        response = requests.get(api_url, headers=_headers(origin, url), timeout=15)
        if response.status_code not in (200, 204):
            xbmc.log("[AdultHideout][88z] Tracking API HTTP {} on {}".format(response.status_code, hostname), xbmc.LOGWARNING)
            return {}
        token_payload = response.headers.get("X-Tracking") or response.headers.get("x-tracking") or ""
        if not token_payload:
            xbmc.log("[AdultHideout][88z] Missing X-Tracking header on {}".format(hostname), xbmc.LOGWARNING)
            return {}
        return _simple_decrypt_json(token_payload, hostname)
    except Exception as exc:
        xbmc.log("[AdultHideout][88z] Tracking resolve failed on {}: {}".format(hostname, exc), xbmc.LOGWARNING)
        return {}


def _absolute(url, base_origin):
    if not url:
        return ""
    url = str(url).strip()
    if url.startswith("//"):
        return "https:" + url
    if url.startswith("/"):
        return urllib.parse.urljoin(base_origin, url)
    return url


def _stream_candidates(data, base_origin):
    candidates = []
    stream_block = data.get("stream") if isinstance(data.get("stream"), dict) else {}

    # Prefer clean HLS (fMP4) and direct MP4 over PNG-masked fallback streams.
    for key in ("hls", "direct", "tiktok", "source", "hlsVideoTiktok", "cf"):
        value = stream_block.get(key) or data.get(key)
        resolved = _absolute(value, base_origin)
        if resolved:
            candidates.append(resolved)

    for item in data.get("sources") or stream_block.get("sources") or []:
        src = _absolute(item.get("src") or item.get("url") or item.get("file") if isinstance(item, dict) else item, base_origin)
        if src:
            candidates.append(src)

    seen = set()
    unique = []
    for candidate in candidates:
        if candidate not in seen:
            seen.add(candidate)
            unique.append(candidate)
    return unique


def _probe_stream(url, headers):
    try:
        probe_headers = dict(headers)
        probe_headers["Range"] = "bytes=0-4095"
        req = urllib.request.Request(url, headers=probe_headers)
        with urllib.request.urlopen(req, timeout=12) as response:
            status = response.getcode() or 200
            content_type = (response.headers.get("Content-Type") or "").lower()
            data = response.read(4096)
        if status >= 400 or not data:
            return False
        if b"#EXTM3U" in data:
            return True
        if ".m3u8" in url.lower() or "mpegurl" in content_type:
            return False
        return "text/html" not in content_type and "application/json" not in content_type
    except Exception as exc:
        xbmc.log("[AdultHideout][88z] Stream probe failed: {}".format(exc), xbmc.LOGDEBUG)
        return False


def _resolve_target(url, headers=None, depth=0):
    if depth > 2:
        return "", {}
    slug, hostname = _extract_slug_and_host(url)
    if not slug or not hostname:
        xbmc.log("[AdultHideout][88z] No video id/slug found in {}".format(url), xbmc.LOGWARNING)
        return "", {}

    if hostname == "88z.io" or hostname.endswith(".88z.io"):
        redirected = _resolve_88z_redirect(slug)
        if redirected:
            xbmc.log("[AdultHideout][88z] Redirected {} -> {}".format(slug, redirected), xbmc.LOGINFO)
            return _resolve_target(redirected, headers=headers, depth=depth + 1)
        data = _legacy_api_get(slug)
    else:
        xbmc.log("[AdultHideout][88z] Resolving encrypted player {}/{}".format(hostname, slug), xbmc.LOGINFO)
        data = _tracking_get(url, slug, hostname)

    if not data:
        return "", {}

    origin = "https://{}".format(hostname)
    play_headers = _play_headers(origin)
    if headers:
        for key, value in headers.items():
            if value and key.lower() not in ("range", "referer", "origin"):
                play_headers[key] = value

    for stream_url in _stream_candidates(data, origin):
        if _probe_stream(stream_url, play_headers):
            xbmc.log("[AdultHideout][88z] Resolved stream via {}: {}".format(hostname, stream_url[:140]), xbmc.LOGINFO)
            return stream_url, play_headers

    xbmc.log("[AdultHideout][88z] No playable stream found for {}/{}".format(hostname, slug), xbmc.LOGWARNING)
    return "", {}


def resolve(url, referer=None, headers=None):
    return _resolve_target(url, headers=headers, depth=0)
