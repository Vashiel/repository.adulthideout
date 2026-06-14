# -*- coding: utf-8 -*-
import html
import re
import urllib.parse
import urllib.request

import xbmc

from resources.lib.resolvers import resolver_utils


def _normalise_url(url):
    url = html.unescape(url or "").strip()
    if url.startswith("//"):
        return "https:" + url
    if not url.startswith(("http://", "https://")):
        return urllib.parse.urljoin("https://mydaddy.cc/", url)
    return url


def _extract_mydaddy_url(url):
    url = html.unescape(url or "").strip()
    parsed = urllib.parse.urlparse(url)
    query = urllib.parse.parse_qs(parsed.query)
    for value in query.get("url", []):
        value = urllib.parse.unquote(value)
        if "mydaddy" in value.lower():
            return value

    decoded = urllib.parse.unquote(url)
    match = re.search(r"https?://mydaddy\.cc/video/[^\"'&<>\s]+", decoded, re.IGNORECASE)
    if match:
        return match.group(0)
    return url


def _alt_url(url):
    url = _extract_mydaddy_url(url)
    if "&alt" in url:
        return url
    parsed = urllib.parse.urlparse(url)
    path = parsed.path.rstrip("/") + "/&alt"
    return urllib.parse.urlunparse(parsed._replace(path=path, query="", fragment=""))


def _headers(referer="https://diepornos.com/"):
    return {
        "User-Agent": resolver_utils.get_ua(),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7",
        "Accept-Encoding": "identity",
        "Referer": referer,
        "Sec-Fetch-Dest": "iframe",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "cross-site",
        "Upgrade-Insecure-Requests": "1",
    }


def _stream_headers():
    return {
        "User-Agent": resolver_utils.get_ua(),
        "Accept": "*/*",
        "Referer": "https://mydaddy.cc/",
        "Sec-Fetch-Dest": "video",
        "Sec-Fetch-Mode": "no-cors",
        "Sec-Fetch-Site": "cross-site",
    }


def _extract_streams(page_html):
    streams = {}
    if not page_html:
        return []

    for match in re.finditer(
        r'((?:https?:)?//[^"\'>\s]+/pubs/[^"\'>\s/]+/)(360|480|720|1080)\.mp4',
        page_html,
        re.IGNORECASE,
    ):
        base, quality = match.groups()
        streams[int(quality)] = _normalise_url(base + quality + ".mp4")

    for base in re.findall(
        r'((?:https?:)?//[^"\'>\s]+/pubs/[^"\'>\s/]+/)\s*["\']?\s*\+\s*q\s*\+\s*["\']?\.mp4',
        page_html,
        re.IGNORECASE,
    ):
        base = _normalise_url(base)
        for quality in (1080, 720, 480, 360):
            streams.setdefault(quality, base + "{}.mp4".format(quality))

    for base in re.findall(r'pu:\s*((?:https?:)?//[^"\'>\s]+/pubs/[^"\'>\s/]+/)', page_html, re.IGNORECASE):
        base = _normalise_url(base)
        for quality in (1080, 720, 480, 360):
            streams.setdefault(quality, base + "{}.mp4".format(quality))

    return [streams[quality] for quality in sorted(streams.keys(), reverse=True)]


def _probe(url, headers):
    probe_headers = dict(headers or {})
    probe_headers["Range"] = "bytes=0-0"
    try:
        req = urllib.request.Request(url, headers=probe_headers)
        with urllib.request.urlopen(req, timeout=8) as response:
            status = response.getcode() or 200
            content_type = response.headers.get("Content-Type", "").lower()
            response.read(1)
        return status in (200, 206) and "video" in content_type
    except Exception as exc:
        xbmc.log("[AdultHideout][mydaddy] Probe failed: {}".format(exc), xbmc.LOGDEBUG)
        return False


def resolve(url, referer=None, headers=None):
    xbmc.log("[AdultHideout][mydaddy] Resolving stream", xbmc.LOGINFO)

    candidates = []
    url = _extract_mydaddy_url(url)
    alt = _alt_url(url)
    candidates.append(alt)
    if alt != url:
        candidates.append(url)

    request_headers = _headers("https://diepornos.com/")
    if headers:
        for key, value in headers.items():
            if value and key.lower() not in ("range", "referer"):
                request_headers[key] = value

    for candidate in candidates:
        page_html = resolver_utils.http_get(candidate, headers=request_headers, retries=1, timeout=15)
        if not page_html:
            continue
        streams = _extract_streams(page_html)
        if not streams:
            if "this domain has been blocked" in page_html.lower():
                xbmc.log("[AdultHideout][mydaddy] Block page returned for {}".format(candidate), xbmc.LOGWARNING)
            continue

        play_headers = _stream_headers()
        for stream_url in streams:
            if _probe(stream_url, play_headers):
                xbmc.log("[AdultHideout][mydaddy] Resolved stream: {}".format(stream_url), xbmc.LOGINFO)
                return stream_url, play_headers

    xbmc.log("[AdultHideout][mydaddy] No playable stream found", xbmc.LOGWARNING)
    return "", {}
