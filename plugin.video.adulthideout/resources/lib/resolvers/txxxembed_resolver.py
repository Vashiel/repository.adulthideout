# -*- coding: utf-8 -*-
"""Embeds of the txxx network (videohotmovs, videopornl, ...).

The embed page loads its stream from /api/videofile.php. The video_url there is
base64 in which some Latin letters are written as look-alike Cyrillic ones.
"""
import base64
import json
import re
import urllib.parse

import xbmc

from resources.lib.resolvers import resolver_utils

_LOOKALIKES = {
    0x0410: "A", 0x0412: "B", 0x0415: "E", 0x041C: "M", 0x0421: "C", 0x041D: "H",
    0x041A: "K", 0x0420: "P", 0x0422: "T", 0x041E: "O", 0x0425: "X",
}
_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0 Safari/537.36"


def _decode(encoded, origin):
    normalized = "".join(_LOOKALIKES.get(ord(ch), ch) for ch in encoded or "")
    normalized = normalized.replace(",", "+").replace("~", "=")
    normalized += "=" * ((4 - len(normalized) % 4) % 4)
    decoded = base64.b64decode(normalized).decode("utf-8", "replace")
    decoded = decoded.replace("/>", "/?")
    if ">" in decoded:
        decoded = decoded.replace(">", "?", 1)
    return urllib.parse.urljoin(origin, decoded)


def _score(entry):
    fmt = (entry.get("format") or "").lower()
    if "_fhd" in fmt or "1080" in fmt:
        return 3
    if "_hq" in fmt or "720" in fmt:
        return 2
    return 1


def resolve(url, referer=None, headers=None):
    parsed = urllib.parse.urlparse(url or "")
    match = re.search(r"/embed/(\d+)", parsed.path)
    if not match:
        return "", {}
    origin = "{}://{}/".format(parsed.scheme or "https", parsed.netloc)
    embed_url = urllib.parse.urljoin(origin, "embed/{}/".format(match.group(1)))
    request_headers = {"User-Agent": _UA, "Referer": embed_url, "Accept": "application/json, */*"}
    api_url = urllib.parse.urljoin(origin, "api/videofile.php?video_id={}&lifetime=8640000".format(match.group(1)))
    try:
        entries = json.loads(resolver_utils.http_get(api_url, headers=request_headers, retries=1, timeout=15) or "[]")
    except ValueError:
        entries = []
    entries = [entry for entry in entries if isinstance(entry, dict) and entry.get("video_url")]
    if not entries:
        xbmc.log("[AdultHideout][txxxembed] No video file for %s" % url, xbmc.LOGWARNING)
        return "", {}
    best = max(entries, key=_score)
    stream_url = _decode(best["video_url"], origin)
    # The file host rejects a foreign Referer (403) but serves the file without one.
    return stream_url, {"User-Agent": _UA}
