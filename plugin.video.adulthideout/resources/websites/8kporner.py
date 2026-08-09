# -*- coding: utf-8 -*-

import urllib.parse

import xbmc
import xbmcgui
import xbmcplugin

from resources.lib.playtube_website import PlayTubeWebsite
from resources.lib.proxy_utils import PlaybackGuard, ProxyController


class EightKPorner(PlayTubeWebsite):
    def __init__(self, addon_handle, addon=None):
        super().__init__("8kporner", "8KPorner", "https://8kporner.com/", addon_handle, addon)

    def _internal_url(self, url):
        parsed = urllib.parse.urlsplit(url or "")
        if parsed.netloc.lower() not in ("8kporner.com", "www.8kporner.com"):
            return url

        query = urllib.parse.parse_qs(parsed.query)
        if query.get("link1"):
            return url

        path = urllib.parse.unquote(parsed.path).rstrip("/")
        page_id = query.get("page_id", [""])[0]
        params = []

        if path in ("/videos/latest", "/videos/trending", "/videos/top"):
            params = [("link1", "videos"), ("page", path.rsplit("/", 1)[-1])]
        elif path == "/search":
            params = [("link1", "search"), ("keyword", query.get("keyword", [""])[0])]
        elif path == "/categories":
            params = [("link1", "categories")]
        elif path == "/pornstars":
            params = [("link1", "pornstars")]
        elif path.startswith("/videos/category/"):
            params = [
                ("link1", "videos"),
                ("page", "category"),
                ("id", path[len("/videos/category/"):]),
            ]
        elif path.startswith("/videos/pornstar/"):
            params = [
                ("link1", "videos"),
                ("page", "pornstar"),
                ("id", path[len("/videos/pornstar/"):]),
            ]
        elif path.startswith("/watch/"):
            params = [("link1", "watch"), ("id", path[len("/watch/"):])]

        if not params:
            return url
        if page_id:
            params.append(("page_id", page_id))
        return urllib.parse.urljoin(self.base_url, "?" + urllib.parse.urlencode(params))

    def _get(self, url, referer=None):
        return super()._get(self._internal_url(url), referer=referer)

    def resolve_recording_stream(self, url):
        variants = self._stream_variants(self._get(url, referer=self.base_url))
        if not variants:
            return None
        stream_url = variants[0][1]
        headers = self._headers(url, "*/*")
        parsed = urllib.parse.urlsplit(stream_url)
        cdn_ips = urllib.parse.parse_qs(parsed.query).get("urls", [""])[0].split(";")
        if cdn_ips and self._is_ipv4(cdn_ips[0]):
            headers["Host"] = parsed.netloc
            stream_url = urllib.parse.urlunsplit(
                (parsed.scheme, cdn_ips[0], parsed.path, parsed.query, parsed.fragment)
            )
        return {
            "url": stream_url,
            "headers": headers,
            "extension": "mp4",
        }

    @staticmethod
    def _is_ipv4(value):
        parts = (value or "").split(".")
        return len(parts) == 4 and all(part.isdigit() and 0 <= int(part) <= 255 for part in parts)

    def play_video(self, url):
        resolved = self.resolve_recording_stream(url)
        if not resolved:
            self.notify_error("Could not resolve 8KPorner stream")
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
            return
        try:
            controller = ProxyController(
                resolved["url"],
                upstream_headers=resolved.get("headers") or {},
                session=self.session,
                probe_size=True,
                use_urllib=True,
                include_origin=False,
            )
            play_url = controller.start()
            PlaybackGuard(xbmc.Player(), xbmc.Monitor(), play_url, controller).start()
            item = xbmcgui.ListItem(path=play_url)
            item.setProperty("IsPlayable", "true")
            item.setMimeType("video/mp4")
            item.setContentLookup(False)
            xbmcplugin.setResolvedUrl(self.addon_handle, True, item)
        except Exception as exc:
            self.logger.error("[8kporner] Proxy playback failed: %s", exc)
            self.notify_error("8KPorner playback failed")
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
