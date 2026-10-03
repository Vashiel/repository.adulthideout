# -*- coding: utf-8 -*-
import re
import socket
import time
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
    if parsed.netloc.lower() not in ("hglink.to", "www.hglink.to", "hgcloud.to", "www.hgcloud.to"):
        return url

    path = parsed.path
    if path.startswith("/e/"):
        return urllib.parse.urlunparse(("https", "hanerix.com", path, "", parsed.query, parsed.fragment))
    return url


def _streams_from_html(html, page_url):
    unpacked = _unpack_packed_js(html)
    if not unpacked:
        return []
    links_match = re.search(r"var\s+links\s*=\s*\{([\s\S]*?)\};\s*jwplayer", unpacked)
    if not links_match:
        return []
    links = {}
    for key, value in re.findall(r'"([^"]+)"\s*:\s*"([^"]*)"', links_match.group(1)):
        if value:
            links[key] = value.replace("\\/", "/")
    return [
        urllib.parse.urljoin(page_url, links[key])
        for key in ("hls3", "hls2", "hls4") if links.get(key)
    ]


_MAX_RESOLVE_SECONDS = 18.0
_REQUEST_TIMEOUT_SECONDS = 3.0


def _bounded_get(url, headers, deadline):
    remaining = deadline - time.monotonic()
    if remaining <= 0.5:
        return ""
    timeout = min(_REQUEST_TIMEOUT_SECONDS, remaining / 4.0)
    return resolver_utils.http_get(
        url, headers=headers, retries=0, sleep=0, timeout=timeout
    )


def _playlist_hosts_resolve(stream_url, headers, deadline):
    if not _host_resolves(stream_url):
        return False
    master = _bounded_get(stream_url, headers, deadline)
    if not master or "#EXTM3U" not in master[:64]:
        return False
    media_url = ""
    for line in master.splitlines():
        if line.strip() and not line.startswith("#"):
            media_url = urllib.parse.urljoin(stream_url, line.strip())
            break
    if not media_url or not _host_resolves(media_url):
        return False
    if "#EXT-X-STREAM-INF" not in master:
        return True
    # The master playlist and its selected variant share the same CDN. Do not
    # fetch every nested playlist/segment here; Kodi will request them during playback.
    return time.monotonic() < deadline


def _host_resolves(url):
    host = urllib.parse.urlparse(url).hostname
    if not host:
        return False
    try:
        socket.getaddrinfo(host, 443, socket.AF_UNSPEC, socket.SOCK_STREAM)
        return True
    except OSError:
        return False


def resolve(url, referer="", headers=None):
    xbmc.log("[AdultHideout][hglink] Resolving: {}".format(url), xbmc.LOGINFO)

    page_url = _hglink_to_hanerix(url)
    request_headers = {
        "User-Agent": resolver_utils.get_ua(),
        "Referer": referer or "https://hglink.to/",
    }
    if headers:
        request_headers.update(headers)

    deadline = time.monotonic() + _MAX_RESOLVE_SECONDS
    page_html = _bounded_get(page_url, request_headers, deadline)
    if not page_html:
        xbmc.log(
            "[AdultHideout][hglink] Player page unavailable; stopped within {:.0f}s budget".format(
                _MAX_RESOLVE_SECONDS
            ),
            xbmc.LOGWARNING,
        )
        return "", {}

    for candidate in _streams_from_html(page_html, page_url):
        if time.monotonic() >= deadline:
            break
        if _playlist_hosts_resolve(candidate, request_headers, deadline):
            xbmc.log("[AdultHideout][hglink] Found reachable HLS playlist", xbmc.LOGINFO)
            return candidate, {
                "User-Agent": request_headers["User-Agent"],
                "Referer": page_url,
            }

    xbmc.log(
        "[AdultHideout][hglink] No reachable HLS stream found within {:.1f}s".format(
            min(_MAX_RESOLVE_SECONDS, time.monotonic() - (deadline - _MAX_RESOLVE_SECONDS))
        ),
        xbmc.LOGWARNING,
    )
    return "", {}
