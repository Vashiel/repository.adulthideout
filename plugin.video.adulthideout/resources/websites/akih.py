#!/usr/bin/env python
# -*- coding: utf-8 -*-

import html
import re
import urllib.parse

import xbmc
import xbmcgui
import xbmcplugin

from resources.lib.kvs_tube import KVSTubeWebsite
from resources.lib.proxy_utils import HlsProxyController, PlaybackGuard
from resources.lib.thumb_proxy import build_thumb_url


class AkiH(KVSTubeWebsite):
    label = "Aki-H"
    sort_options = ["Latest", "Popular"]
    sort_paths = {"Latest": "/", "Popular": "/popular/"}
    categories_path = "/genre/"
    models_path = None
    video_path_markers = ("/videos/",)
    category_path_markers = ("/genre/",)

    def __init__(self, addon_handle, addon=None):
        super().__init__(
            name="akih",
            base_url="https://aki-h.com/",
            search_url="https://aki-h.com/?s={}",
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
        return urllib.parse.urlparse(url or self.base_url).path.rstrip("/") in ("", "/popular")

    def _episode_urls(self, content):
        output = []
        for value in re.findall(r'href=["\']([^"\']*/episode/[^"\']+/)["\']', content or "", re.IGNORECASE):
            target = self._absolute(value)
            if target not in output:
                output.append(target)
        return output

    def _extract_videos(self, html_content):
        videos = []
        seen = set()
        for episode_url in self._episode_urls(html_content)[:12]:
            episode = self._get(episode_url, referer=self.base_url)
            series_title = re.search(r"<h1\b[^>]*>([\s\S]*?)</h1>", episode or "", re.IGNORECASE)
            series_name = self._clean(series_title.group(1) if series_title else "")
            for href in re.findall(r'href=["\']([^"\']*/videos/([^/"\']+)/)["\']', episode or "", re.IGNORECASE):
                video_url = self._absolute(href[0])
                public_id = href[1]
                if video_url in seen:
                    continue
                seen.add(video_url)
                context_pos = episode.find(href[0])
                context = episode[max(0, context_pos - 500):context_pos + 900]
                title_match = re.search(r'(?:title|alt)=["\']([^"\']+)["\']', context, re.IGNORECASE)
                title = self._clean(title_match.group(1) if title_match else "")
                if not title:
                    title = "{} {}".format(series_name, len(videos) + 1).strip()
                if any(term in title.lower() for term in ("loli", "shota")):
                    continue
                thumb = build_thumb_url(
                    "https://t.aki-h.com/thumbnail/{}.webp".format(public_id),
                    referer=self.base_url,
                )
                videos.append({
                    "label": title,
                    "url": video_url,
                    "thumb": thumb,
                    "info": {"title": title, "plot": title},
                })
        return videos

    def _extract_next_page(self, html_content, current_url, page):
        expected = self.get_page_url(current_url, page + 1)
        return expected if "/page/{}/".format(page + 1) in (html_content or "") else None

    def process_categories(self, url):
        content = self._get(self.base_url)
        seen = set()
        for href, title in re.findall(
            r'<a\b[^>]+href=["\']([^"\']*/genre/[^"\']+/)["\'][^>]*>([^<]+)</a>',
            content or "",
            re.IGNORECASE,
        ):
            target = self._absolute(href)
            clean_title = self._clean(title)
            if target in seen or not clean_title or any(term in clean_title.lower() for term in ("loli", "shota")):
                continue
            seen.add(target)
            search_target = self.search_url.format(urllib.parse.quote_plus(clean_title))
            self.add_dir(clean_title, search_target, 2, self.icons.get("categories", self.icon), self.fanart)
        self.end_directory("videos")

    def _extract_player_url(self, content, referer, pattern):
        match = re.search(pattern, content or "", re.IGNORECASE)
        return urllib.parse.urljoin(referer, html.unescape(match.group(1))) if match else ""

    def resolve_recording_stream(self, url):
        page = self._get(url, referer=self.base_url)
        player_id = re.search(r'displayvideo\(\s*\d+\s*,\s*(\d+)\s*\)', page or "", re.IGNORECASE)
        if not player_id:
            return None
        player_url = self._absolute("/video/{}/".format(player_id.group(1)))
        player = self._get(player_url, referer=url)
        first = self._extract_player_url(
            player, player_url, r"['\"]url['\"]\s*:\s*['\"]([^'\"]*v\.aki-h\.com/v/\d+)",
        )
        first_page = self._get(first, referer=player_url) if first else ""
        public_id = re.search(r"\bvid\s*=\s*['\"]([^'\"]+)", first_page or "", re.IGNORECASE)
        if not public_id:
            return None
        relay_url = "https://v.aki-h.com/f/{}".format(public_id.group(1))
        relay = self._get(relay_url, referer=first)
        second = self._extract_player_url(
            relay, relay_url, r'<iframe\b[^>]+src=["\']([^"\']*streaming\.aki\.today/[^"\']+)',
        )
        second_page = self._get(second, referer=relay_url) if second else ""
        final_page = self._extract_player_url(
            second_page, second, r'<iframe\b[^>]+src=["\'](https://aki-h\.stream/v/([^"\']+))',
        )
        token_match = re.search(r"/v/([^/?#]+)", final_page or "")
        if not token_match:
            return None
        stream_url = "https://aki-h.stream/file/{}/".format(token_match.group(1))
        return {
            "url": stream_url,
            "headers": self._headers(final_page, accept="*/*"),
            "extension": "m3u8",
        }

    def play_video(self, url):
        resolved = self.resolve_recording_stream(url)
        if not resolved:
            self.notify_error("Could not resolve Aki-H stream")
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
            return
        controller = HlsProxyController(
            resolved["url"],
            headers=resolved["headers"],
            session=self.session,
            preserve_query=True,
        )
        local_url = controller.start()
        item = xbmcgui.ListItem(path=local_url)
        item.setProperty("IsPlayable", "true")
        item.setMimeType("application/vnd.apple.mpegurl")
        item.setContentLookup(False)
        xbmcplugin.setResolvedUrl(self.addon_handle, True, item)
        PlaybackGuard(xbmc.Player(), xbmc.Monitor(), local_url, controller).start()
