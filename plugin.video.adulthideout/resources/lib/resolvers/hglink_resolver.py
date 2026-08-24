# -*- coding: utf-8 -*-
import re
import socket
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


def _playlist_hosts_resolve(stream_url, headers):
    if not _host_resolves(stream_url):
        return False
    master = resolver_utils.http_get(stream_url, headers=headers)
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
    media = resolver_utils.http_get(media_url, headers=headers)
    if not media or "#EXTM3U" not in media[:64]:
        return False
    for line in media.splitlines():
        if line.strip() and not line.startswith("#"):
            return _host_resolves(urllib.parse.urljoin(media_url, line.strip()))
    return False


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

    for attempt in range(4):
        separator = "&" if "?" in page_url else "?"
        attempt_url = page_url if not attempt else "{}{}_ah_retry={}".format(page_url, separator, attempt)
        html = resolver_utils.http_get(attempt_url, headers=request_headers)
        stream_urls = _streams_from_html(html, page_url) if html else []
        stream_url = next(
            (candidate for candidate in stream_urls
             if _playlist_hosts_resolve(candidate, request_headers)), ""
        )
        if stream_url:
            xbmc.log(
                "[AdultHideout][hglink] Final stream URL after {} attempt(s): {}".format(
                    attempt + 1, stream_url
                ),
                xbmc.LOGINFO,
            )
            return stream_url, {
                "User-Agent": request_headers["User-Agent"],
                "Referer": page_url,
            }
        if stream_urls:
            xbmc.log(
                "[AdultHideout][hglink] Skipping unresolved CDN host (attempt {})".format(
                    attempt + 1
                ),
                xbmc.LOGWARNING,
            )
    xbmc.log("[AdultHideout][hglink] No reachable HLS stream found", xbmc.LOGWARNING)
    return "", {}
