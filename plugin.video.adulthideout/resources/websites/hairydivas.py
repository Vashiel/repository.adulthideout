#!/usr/bin/env python
# -*- coding: utf-8 -*-

import html
import re
import urllib.parse

import xbmc
import xbmcgui
import xbmcplugin

from resources.lib.kvs_tube import KVSTubeWebsite
from resources.lib.thumb_proxy import build_thumb_url


class HairyDivas(KVSTubeWebsite):
    label = "HairyDivas"
    sort_options = ["Latest", "Popular"]
    sort_paths = {"Latest": "/newest", "Popular": "/"}
    categories_path = "/categories"
    models_path = "/pornstars"
    use_playback_proxy = True

    def __init__(self, addon_handle, addon=None):
        super().__init__(
            name="hairydivas",
            base_url="https://hairydivas.com/",
            search_url="https://hairydivas.com/search/{}/",
            addon_handle=addon_handle,
            addon=addon,
        )

    def get_page_url(self, base_url, page_num):
        if page_num <= 1:
            return base_url
        parsed = urllib.parse.urlparse(base_url)
        query = urllib.parse.parse_qs(parsed.query)
        query["page"] = [str(page_num)]
        return urllib.parse.urlunparse(parsed._replace(query=urllib.parse.urlencode(query, doseq=True)))

    def _pick_thumb(self, img_tag):
        match = re.search(r'\sdata-src=["\']([^"\']+)', img_tag or "", re.IGNORECASE)
        thumb = self._absolute(match.group(1)) if match else super()._pick_thumb(img_tag)
        return build_thumb_url(thumb, referer=self.base_url) if thumb else thumb

    def _extract_videos(self, html_content):
        videos = []
        seen = set()
        blocks = re.split(
            r'(?=<div\b[^>]+class=["\'][^"\']*\bb-thumb-item\s+js-thumb\b[^"\']*["\'])',
            html_content or "",
            flags=re.IGNORECASE,
        )
        for block in blocks:
            link = re.search(
                r'<a\b[^>]+href=["\']([^"\']*/video/[^"\']+)["\'][^>]+title=["\']([^"\']+)',
                block,
                re.IGNORECASE,
            )
            if not link:
                continue
            video_url = self._absolute(link.group(1))
            if video_url in seen:
                continue
            seen.add(video_url)
            title = self._clean(link.group(2))
            image = re.search(r'<img\b[^>]+data-src=["\']([^"\']+)', block, re.IGNORECASE)
            thumb = self._absolute(image.group(1)) if image else self.icon
            if image:
                thumb = build_thumb_url(thumb, referer=self.base_url)
            duration_match = re.search(
                r'class=["\'][^"\']*b-thumb-item__duration[^"\']*["\'][^>]*>([^<]+)',
                block,
                re.IGNORECASE,
            )
            duration = self._clean(duration_match.group(1)) if duration_match else ""
            videos.append({
                "label": title,
                "url": video_url,
                "thumb": thumb,
                "info": {
                    "title": title,
                    "plot": title,
                    "duration": self.convert_duration(duration),
                },
            })
        return videos

    def resolve_recording_stream(self, url):
        page = self._get(url, referer=self.base_url)
        source = re.search(
            r'<source\s+src=["\']([^"\']+__TPL_\.mp4)["\'][^>]*type=["\']application/x-mpegURL',
            page or "", re.IGNORECASE,
        )
        signer = re.search(r'data-v-update-url=["\']([^"\']+)', page or "", re.IGNORECASE)
        if not source or not signer:
            return None
        unsigned = urllib.parse.unquote(html.unescape(source.group(1)))
        sign_url = urllib.parse.urljoin(signer.group(1), "/ah/sign")
        try:
            response = self.session.post(
                sign_url,
                json={"urls": {"hls": unsigned}},
                headers={
                    "User-Agent": self.ua,
                    "Referer": url,
                    "Origin": self.base_url.rstrip("/"),
                    "Accept": "application/json",
                },
                timeout=15,
            )
            stream = ((response.json().get("urls") or {}).get("hls") or "") if response.status_code == 200 else ""
        except Exception as exc:
            self.logger.warning("HairyDivas signing failed: %s", exc)
            stream = ""
        if not stream:
            return None
        try:
            master = self.session.get(stream, headers=self._headers(url, accept="*/*"), timeout=15)
            if master.status_code != 200 or not master.text.startswith("#EXTM3U"):
                return None
            variants = re.findall(
                r'#EXT-X-STREAM-INF:[^\r\n]*RESOLUTION=(\d+)x(\d+)[^\r\n]*[\r\n]+([^\r\n#]+)',
                master.text,
                re.IGNORECASE,
            )
            if variants:
                usable = [entry for entry in variants if int(entry[1]) <= 720] or variants
                _, _, child = max(usable, key=lambda entry: int(entry[0]) * int(entry[1]))
                stream = urllib.parse.urljoin(stream, child.strip())
        except Exception as exc:
            self.logger.warning("HairyDivas master playlist parsing failed: %s", exc)
        return {"url": stream, "headers": self._headers(url, accept="*/*"), "extension": "m3u8"}

    def play_video(self, url):
        resolved = self.resolve_recording_stream(url)
        if not resolved:
            self.notify_error("Could not resolve HairyDivas stream")
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
            return
        encoded_headers = urllib.parse.urlencode(resolved["headers"])
        play_url = resolved["url"] + "|" + encoded_headers
        item = xbmcgui.ListItem(path=play_url)
        item.setProperty("IsPlayable", "true")
        item.setMimeType("application/vnd.apple.mpegurl")
        item.setContentLookup(False)
        if xbmc.getCondVisibility("System.HasAddon(inputstream.adaptive)"):
            item.setProperty("inputstream", "inputstream.adaptive")
            item.setProperty("inputstream.adaptive.manifest_type", "hls")
            item.setProperty("inputstream.adaptive.manifest_headers", encoded_headers)
            item.setProperty("inputstream.adaptive.stream_headers", encoded_headers)
        xbmcplugin.setResolvedUrl(self.addon_handle, True, item)
