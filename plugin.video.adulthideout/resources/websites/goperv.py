#!/usr/bin/env python
# -*- coding: utf-8 -*-

import html
import re

from resources.lib.kvs_tube import KVSTubeWebsite
from resources.lib.thumb_proxy import build_thumb_url


class GoPerv(KVSTubeWebsite):
    label = "GoPerv"
    sort_options = ["Latest", "Popular"]
    sort_paths = {"Latest": "/", "Popular": "/popular/"}
    categories_path = "/categories/"
    models_path = None
    video_path_markers = ("/video/",)
    use_playback_proxy = True

    def __init__(self, addon_handle, addon=None):
        super().__init__(
            name="goperv",
            base_url="https://goperv.com/",
            search_url="https://goperv.com/?s={}",
            addon_handle=addon_handle,
            addon=addon,
        )

    def _extract_stream_url(self, html_content, referer=None):
        candidates = []
        for value in re.findall(
            r'https?://[^"\'\\<>\s]+\.mp4(?:\?[^"\'\\<>\s]*)?',
            html_content or "", re.IGNORECASE,
        ):
            stream = html.unescape(value).replace("\\/", "/")
            if "/sample/" in stream and stream not in candidates:
                candidates.append(stream)
        for stream in candidates:
            if self._probe_stream(stream, referer or self.base_url):
                return stream
        return candidates[0] if candidates else ""

    def _extract_videos(self, html_content):
        videos = []
        seen = set()
        blocks = re.split(
            r'(?=<div\b[^>]+class=["\'][^"\']*episode-item[^"\']*["\'])',
            html_content or "",
            flags=re.IGNORECASE,
        )
        for block in blocks:
            href = re.search(r'href=["\']([^"\']*/video/[^"\']+)', block, re.IGNORECASE)
            if not href:
                continue
            url = self._absolute(href.group(1))
            if not url or url in seen:
                continue
            title = re.search(r'<h3\b[^>]*>([\s\S]*?)</h3>', block, re.IGNORECASE)
            wrapper = re.search(
                r'<div\b[^>]+class=["\'][^"\']*thumbnail_wrapper[^"\']*["\'][^>]*>([\s\S]*?)</div>',
                block,
                re.IGNORECASE,
            )
            image_scope = wrapper.group(1) if wrapper else block
            image = re.search(r'<img\b[^>]*>', image_scope, re.IGNORECASE)
            image_tag = image.group(0) if image else ""
            source = re.search(r'\sdata-optim-src=["\']([^"\']+)', image_tag, re.IGNORECASE)
            if not source:
                source = re.search(r'\ssrc=["\']([^"\']+)', image_tag, re.IGNORECASE)
            clean_title = self._clean(title.group(1) if title else "")
            if not clean_title:
                continue
            thumb = self._absolute(source.group(1).strip()) if source else self.icon
            thumb = build_thumb_url(thumb, referer=self.base_url)
            seen.add(url)
            videos.append({
                "label": clean_title,
                "url": url,
                "thumb": thumb,
                "info": {"title": clean_title, "plot": clean_title},
            })
        return videos
