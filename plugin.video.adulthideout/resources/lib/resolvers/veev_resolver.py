# -*- coding: utf-8 -*-
import binascii
import json
import re
import ssl
import urllib.parse
import urllib.request

import xbmc

from resources.lib.resolvers import resolver_utils


def _decode_lzw(value):
    if not value:
        return ""
    table = {}
    code = 256
    previous = value[0]
    output = [previous]
    for char in value[1:]:
        number = ord(char)
        current = char if number < 256 else table.get(number, previous + previous[0])
        output.append(current)
        table[code] = previous + current[0]
        code += 1
        previous = current
    return "".join(output)


def _decode_steps(token):
    digits = list(token or "")
    if not digits or not digits[0].isdigit():
        return []
    count = int(digits.pop(0))
    steps = []
    while count and digits:
        step = []
        for _ in range(count):
            if not digits:
                return []
            char = digits.pop(0)
            step.insert(0, int(char) if char.isdigit() else 0)
        steps.append(step)
        if not digits or not digits[0].isdigit():
            break
        count = int(digits.pop(0))
    return steps


def _decode_stream(value, steps):
    decoded = value
    for step in steps:
        if step == 1:
            decoded = decoded[::-1]
        try:
            decoded = binascii.unhexlify(decoded).decode("utf-8")
        except (binascii.Error, UnicodeDecodeError, ValueError):
            return ""
        decoded = decoded.replace("dXRmOA==", "")
    return decoded


def _player_tokens(html):
    matches = re.findall(
        r'(?:\.fc|\bfc|_vvto\[[^\]]+\])\s*[=:]\s*[\'"]([^\'"]+)[\'"]',
        html,
    )
    return list(reversed(matches))


def _fetch_player_page(url, headers):
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=8) as response:
        final_url = response.geturl()
        html = response.read().decode("utf-8", "replace")
    return final_url, html


def _is_playable_candidate(url, headers):
    host = (urllib.parse.urlparse(url).hostname or "").lower().rstrip(".")
    context = None
    if host == "veevcdn.co" or host.endswith(".veevcdn.co"):
        context = ssl._create_unverified_context()
    request_headers = dict(headers)
    request_headers.update({
        "Accept": "*/*",
        "Accept-Encoding": "identity",
        "Accept-Language": "en-US,en;q=0.9",
        "Connection": "keep-alive",
        "Sec-Fetch-Dest": "video",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "cross-site",
        "Range": "bytes=0-1",
    })
    try:
        request = urllib.request.Request(url, headers=request_headers)
        with urllib.request.urlopen(request, timeout=5, context=context) as response:
            status = getattr(response, "status", response.getcode())
            content_type = (response.headers.get("Content-Type") or "").lower()
            sample = response.read(64).lstrip().lower()
            valid = (
                status in (200, 206)
                and bool(sample)
                and not any(value in content_type for value in ("text/", "html", "json", "xml"))
                and not sample.startswith((b"<!doctype", b"<html", b"<?xml", b"{", b"["))
            )
            xbmc.log("[AdultHideout][veev] Candidate host={} status={} type={} accepted={}".format(
                host, status, content_type[:48], valid
            ), xbmc.LOGINFO)
            return valid
    except Exception as exc:
        status = getattr(exc, "code", "network-error")
        xbmc.log("[AdultHideout][veev] Candidate host={} status={} error={} accepted=False".format(
            host, status, type(exc).__name__
        ), xbmc.LOGWARNING)
        return False


def resolve(url, referer="", headers=None):
    request_headers = {
        "User-Agent": resolver_utils.get_ua(),
        "Referer": url,
    }
    if headers:
        request_headers.update(headers)

    try:
        final_url, html = _fetch_player_page(url, request_headers)
    except Exception as exc:
        xbmc.log("[AdultHideout][veev] Player page request failed: {}".format(exc), xbmc.LOGWARNING)
        return "", {}

    media_id = urllib.parse.urlparse(final_url).path.rstrip("/").split("/")[-1]
    for token in _player_tokens(html):
        decoded_token = _decode_lzw(token)
        if decoded_token == token:
            continue
        query = urllib.parse.urlencode({
            "op": "player_api",
            "cmd": "gi",
            "file_code": media_id,
            "ch": decoded_token,
            "ie": "1",
        })
        api_url = urllib.parse.urljoin(final_url, "/dl") + "?" + query
        api_headers = dict(request_headers)
        api_headers["Referer"] = final_url
        response = resolver_utils.http_get(api_url, headers=api_headers, retries=0, timeout=5)
        try:
            data = json.loads(response or "{}")
        except (TypeError, ValueError):
            continue
        file_info = data.get("file") or {}
        variants = file_info.get("dv") or []
        xbmc.log("[AdultHideout][veev] API returned {} stream variants".format(len(variants)), xbmc.LOGINFO)
        steps = (_decode_steps(decoded_token) or [[]])[0]
        for variant in variants:
            encoded_stream = _decode_lzw(variant.get("s", ""))
            stream_url = _decode_stream(encoded_stream, steps)
            if stream_url.startswith(("http://", "https://")):
                stream_headers = {
                    "User-Agent": request_headers["User-Agent"],
                    "Referer": url,
                }
                if not _is_playable_candidate(stream_url, stream_headers):
                    continue
                xbmc.log("[AdultHideout][veev] Resolved player stream", xbmc.LOGINFO)
                return stream_url, {
                    "User-Agent": request_headers["User-Agent"],
                    "Referer": url,
                }

    xbmc.log("[AdultHideout][veev] No stream URL returned by player API", xbmc.LOGWARNING)
    return "", {}
