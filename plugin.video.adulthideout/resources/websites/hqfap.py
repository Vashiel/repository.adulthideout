# -*- coding: utf-8 -*-

import urllib.parse

import xbmc
import xbmcgui
import xbmcplugin

from resources.lib.playtube_website import PlayTubeWebsite
from resources.lib.proxy_utils import PlaybackGuard, ProxyController


class HQFap(PlayTubeWebsite):
    skip_directory_titles = {"3d"}
    sort_paths = {
        "Latest": "/?link1=videos&page=latest",
        "Trending": "/?link1=videos&page=trending",
        "Top Rated": "/?link1=videos&page=top",
    }

    def __init__(self, addon_handle, addon=None):
        super().__init__("hqfap", "HQFap", "https://hqfap.com/", addon_handle, addon)
        self.search_url = self.base_url + "?link1=search&keyword={}"

    def _is_top_listing(self, url):
        query = urllib.parse.parse_qs(urllib.parse.urlparse(url or "").query)
        return (
            query.get("link1", [""])[0] == "videos"
            and query.get("page", [""])[0] in ("latest", "trending", "top")
        )

    def _internal_url(self, url):
        parsed = urllib.parse.urlparse(url)
        path = urllib.parse.unquote(parsed.path).rstrip("/")
        query = urllib.parse.parse_qs(parsed.query)

        if path.startswith("/watch/"):
            query = {"link1": ["watch"], "id": [path.rsplit("/", 1)[-1]]}
            path = "/"
        elif path == "/search":
            query["link1"] = ["search"]
            path = "/"
        elif path == "/categories":
            query = {"link1": ["categories"], **query}
            path = "/"
        elif path == "/pornstars":
            query = {"link1": ["pornstars"], **query}
            path = "/"
        elif path.startswith("/videos/category/"):
            query = {
                "link1": ["videos"],
                "page": ["category"],
                "id": [path.split("/videos/category/", 1)[1]],
                **query,
            }
            path = "/"
        elif path.startswith("/videos/pornstar/"):
            query = {
                "link1": ["videos"],
                "page": ["pornstar"],
                "id": [path.split("/videos/pornstar/", 1)[1]],
                **query,
            }
            path = "/"
        elif path in ("/videos/latest", "/videos/trending", "/videos/top"):
            query = {
                "link1": ["videos"],
                "page": [path.rsplit("/", 1)[-1]],
                **query,
            }
            path = "/"

        return urllib.parse.urlunparse(
            (
                parsed.scheme,
                parsed.netloc,
                path or "/",
                "",
                urllib.parse.urlencode(query, doseq=True),
                "",
            )
        )

    def _get(self, url, referer=None):
        return super()._get(self._internal_url(url), referer)

    def process_categories(self, url):
        super().process_categories(url or self.base_url + "?link1=categories")

    def process_pornstars(self, url):
        super().process_pornstars(url or self.base_url + "?link1=pornstars")

    def play_video(self, url):
        resolved = self.resolve_recording_stream(url)
        if not resolved:
            self.notify_error("Could not resolve HQFap stream")
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
            return
        try:
            controller = ProxyController(
                resolved["url"],
                upstream_headers=resolved.get("headers") or {},
                session=self.session,
                probe_size=True,
            )
            play_url = controller.start()
            PlaybackGuard(xbmc.Player(), xbmc.Monitor(), play_url, controller).start()
            item = xbmcgui.ListItem(path=play_url)
            item.setProperty("IsPlayable", "true")
            item.setMimeType("video/mp4")
            item.setContentLookup(False)
            xbmcplugin.setResolvedUrl(self.addon_handle, True, item)
        except Exception as exc:
            self.logger.error("[hqfap] Proxy playback failed: %s", exc)
            self.notify_error("HQFap playback failed")
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
