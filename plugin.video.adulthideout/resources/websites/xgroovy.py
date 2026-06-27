#!/usr/bin/env python
# -*- coding: utf-8 -*-

import html
import os
import re
import urllib.parse

from resources.lib.kvs_tube import KVSTubeWebsite


class XGroovy(KVSTubeWebsite):
    label = "XGroovy"
    sort_options = ["New", "Best"]
    sort_paths = {
        "New": "/new/",
        "Best": "/best/",
    }
    search_path = "/search/{}/"
    categories_path = "/tags/"
    models_path = "/pornstars/"
    video_path_markers = ("/videos/",)
    category_path_markers = ("/categories/",)
    next_page_full_count = 40
    directory_host_only = True
    directory_path_prefixes = ("/categories/",)
    use_playback_proxy = True

    def __init__(self, addon_handle, addon=None):
        super().__init__(
            name="xgroovy",
            base_url="https://xgroovy.com/",
            search_url="https://xgroovy.com/search/{}/",
            addon_handle=addon_handle,
            addon=addon,
        )
        self.icon = os.path.join(self.addon.getAddonInfo("path"), "resources", "logos", "xgroovy.png")
        self.icons["default"] = self.icon

    def _is_top_listing(self, url):
        parsed = urllib.parse.urlparse(url or self.base_url)
        return parsed.path.rstrip("/") in ("", "/new", "/best")

    def _pick_thumb(self, img_tag):
        # XGroovy serves a webp disguised as .jpg in src (Kodi cannot decode it)
        # and exposes the real JPEG in the data-jpg attribute.
        jpg_match = re.search(r'\sdata-jpg=["\']([^"\']+)["\']', img_tag, re.IGNORECASE)
        if jpg_match:
            return self._absolute(jpg_match.group(1))
        return super()._pick_thumb(img_tag)

    def _extract_stream_url(self, html_content, referer=None):
        # XGroovy serves HTML5 <source> tags with several qualities on its own
        # get_file CDN (no KVS flashvars). Pick the highest real quality and skip
        # the short clips on preview.xgroovy.com.
        best_url = None
        best_quality = -1
        for src in re.findall(r'<source\b[^>]*\bsrc=["\']([^"\']+)["\']', html_content or "", re.IGNORECASE):
            stream_url = html.unescape(src).replace("\\/", "/").strip()
            lowered = stream_url.lower()
            if "/get_file/" not in lowered or ".mp4" not in lowered:
                continue
            quality_match = re.search(r"_(\d{3,4})p", stream_url)
            if quality_match:
                quality = int(quality_match.group(1))
            else:
                # Plain ID.mp4 without a quality suffix is the site default; rank it
                # just under 720p so an explicit 1080p source still wins.
                quality = 700
            if quality > best_quality:
                best_quality = quality
                best_url = self._absolute(stream_url)
        if best_url:
            return best_url
        return super()._extract_stream_url(html_content, referer=referer)
