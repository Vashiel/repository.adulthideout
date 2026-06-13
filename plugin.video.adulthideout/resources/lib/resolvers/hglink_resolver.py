# -*- coding: utf-8 -*-
import re
import urllib.parse
import xbmc

from resources.lib.resolvers import resolver_utils


def _base_n(num, base):
    chars = "0123456789abcdefghijklmnopqrstuvwxyz"
    if num == 0:
        return "0"
    value = ""
    while num:
        num, rem = divmod(num, base)
        value = chars[rem] + value
    return value


def _unpack_packed_js(html):
    match = re.search(
        r"eval\(function\(p,a,c,k,e,d\)\{.*?\}\('([\s\S]*?)',(\d+),(\d+),'([\s\S]*?)'\.split\('\|'\)",
        html,
    )
    if not match:
        return ""

    payload = match.group(1).encode("utf-8").decode("unicode_escape")
    base = int(match.group(2))
    count = int(match.group(3))
    words = match.group(4).split("|")

    for index in range(count - 1, -1, -1):
        if index < len(words) and words[index]:
            payload = re.sub(r"\b" + re.escape(_base_n(index, base)) + r"\b", words[index], payload)
    return payload


def _hglink_to_hanerix(url):
    parsed = urllib.parse.urlparse(url)
    if "hglink.to" not in parsed.netloc:
        return url

    path = parsed.path
    if path.startswith("/e/"):
        return urllib.parse.urlunparse(("https", "hanerix.com", path, "", parsed.query, parsed.fragment))
    return url


def resolve(url, referer="", headers=None):
    xbmc.log("[AdultHideout][hglink] Resolving: {}".format(url), xbmc.LOGINFO)

    page_url = _hglink_to_hanerix(url)
    request_headers = {
        "User-Agent": resolver_utils.get_ua(),
        "Referer": referer or "https://hglink.to/",
    }
    if headers:
        request_headers.update(headers)

    html = resolver_utils.http_get(page_url, headers=request_headers)
    if not html:
        xbmc.log("[AdultHideout][hglink] Empty player page", xbmc.LOGWARNING)
        return "", {}

    unpacked = _unpack_packed_js(html)
    if not unpacked:
        xbmc.log("[AdultHideout][hglink] Packed player script not found", xbmc.LOGWARNING)
        return "", {}

    links_match = re.search(r"var\s+links\s*=\s*\{([\s\S]*?)\};\s*jwplayer", unpacked)
    if not links_match:
        xbmc.log("[AdultHideout][hglink] links object not found", xbmc.LOGWARNING)
        return "", {}

    links_body = links_match.group(1)
    links = {}
    for key, value in re.findall(r'"([^"]+)"\s*:\s*"([^"]*)"', links_body):
        if value:
            links[key] = value.replace("\\/", "/")

    stream_url = links.get("hls4") or links.get("hls3") or links.get("hls2")
    if not stream_url:
        xbmc.log("[AdultHideout][hglink] No HLS stream found", xbmc.LOGWARNING)
        return "", {}

    stream_url = urllib.parse.urljoin(page_url, stream_url)
    xbmc.log("[AdultHideout][hglink] Final stream URL: {}".format(stream_url), xbmc.LOGINFO)
    return stream_url, {
        "User-Agent": request_headers["User-Agent"],
        "Referer": page_url,
    }
