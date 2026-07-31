#!/usr/bin/env python
# -*- coding: utf-8 -*-

import re
import urllib.parse

import xbmc
import xbmcgui
import xbmcplugin

from resources.lib.kvs_tube import KVSTubeWebsite
from resources.lib.proxy_utils import PlaybackGuard, ProxyController
from resources.lib.resolvers import resolver
from resources.lib.thumb_proxy import build_thumb_url


class YourDailyPornVideos(KVSTubeWebsite):
    label = "YourDailyPornVideos"
    use_playback_proxy = False
    sort_options = ["Latest"]
    sort_paths = {"Latest": "/"}
    categories_path = None
    models_path = None
    video_path_markers = ("/",)

    def __init__(self, addon_handle, addon=None):
        super().__init__(
            name="yourdailypornvideos",
            base_url="https://yourdailypornvideos.ws/",
            search_url="https://yourdailypornvideos.ws/?s={}",
            addon_handle=addon_handle,
            addon=addon,
        )

    def get_page_url(self, base_url, page_num):
        if page_num <= 1:
            return base_url
        parsed = urllib.parse.urlparse(base_url)
        path = re.sub(r"/page/\d+/?$", "/", parsed.path)
        path = path.rstrip("/") + "/page/{}/".format(page_num)
        return urllib.parse.urlunparse(
            (parsed.scheme, parsed.netloc, path, parsed.params, parsed.query, parsed.fragment)
        )

    def _is_top_listing(self, url):
        parsed = urllib.parse.urlparse(url or self.base_url)
        return parsed.path in ("", "/") and not parsed.query

    def _extract_videos(self, html_content):
        videos = []
        seen = set()
        pattern = re.compile(
            r'class=["\'][^"\']*\bentry-title\b[^"\']*["\'][^>]*>[\s\S]{0,500}?'
            r'<a\b[^>]+href=["\']([^"\']+)["\'][^>]+title=["\']([^"\']+)["\']',
            re.IGNORECASE,
        )
        for title_match in pattern.finditer(html_content or ""):
            video_url = self._absolute(title_match.group(1))
            if urllib.parse.urlparse(video_url).netloc != urllib.parse.urlparse(self.base_url).netloc or video_url in seen:
                continue
            title = self._clean(title_match.group(2))
            context = (html_content or "")[max(0, title_match.start() - 2200):title_match.start()]
            images = list(re.finditer(r"<img\b[^>]*>", context, re.IGNORECASE))
            img = images[-1] if images else None
            thumb = self._pick_thumb(img.group(0) if img else "")
            if thumb:
                thumb = build_thumb_url(thumb.strip(), referer=self.base_url)
            seen.add(video_url)
            videos.append({
                "label": title,
                "url": video_url,
                "thumb": thumb or self.icon,
                "info": {"title": title, "plot": title},
            })
        return videos

    def _extract_next_page(self, html_content, current_url, page):
        expected = self.get_page_url(current_url, page + 1)
        return expected if "/page/{}/".format(page + 1) in (html_content or "") else None

    def _mirror_urls(self, content):
        mirrors = []
        for value in re.findall(
            r'https?://(?:[^/"\']+\.)?(?:playmogo\.com|streamtape\.com|streamtape\.to)/[^"\'<\s]+',
            content or "",
            re.IGNORECASE,
        ):
            clean = value.replace("&amp;", "&")
            if clean not in mirrors:
                mirrors.append(clean)
        return mirrors

    def resolve_recording_stream(self, url):
        content = self._get(url, referer=self.base_url)
        stream, headers, _ = resolver.resolve_first_working(
            self._mirror_urls(content),
            referer=url,
            headers=self._headers(url, accept="*/*"),
            addon=self.addon,
        )
        return {"url": stream, "headers": headers, "extension": "mp4"} if stream else None

    def play_video(self, url):
        resolved = self.resolve_recording_stream(url)
        if not resolved:
            self.notify_error("Could not resolve YourDailyPornVideos stream")
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
            return
        headers = resolved.get("headers") or {}
        controller = ProxyController(
            resolved["url"],
            upstream_headers=headers,
            use_urllib=True,
            probe_size=True,
        )
        play_url = controller.start()
        PlaybackGuard(xbmc.Player(), xbmc.Monitor(), play_url, controller).start()
        item = xbmcgui.ListItem(path=play_url)
        item.setProperty("IsPlayable", "true")
        item.setMimeType("video/mp4")
        item.setContentLookup(False)
        xbmcplugin.setResolvedUrl(self.addon_handle, True, item)
