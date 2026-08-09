#!/usr/bin/env python
# -*- coding: utf-8 -*-

import html
import re
import urllib.parse

from resources.lib.kvs_tube import KVSTubeWebsite


class BDSMVilla(KVSTubeWebsite):
    label = "BDSM Villa"
    sort_options = ["Latest", "Best"]
    sort_paths = {"Latest": "/new", "Best": "/best"}
    categories_path = "/categories"
    models_path = None
    video_path_markers = ("/video/",)
    category_path_markers = ("/category/",)
    use_playback_proxy = True
    next_page_full_count = 24

    def __init__(self, addon_handle, addon=None):
        super().__init__(
            name="bdsmvilla",
            base_url="https://bdsmvilla.com/",
            search_url="https://bdsmvilla.com/search/{}",
            addon_handle=addon_handle,
            addon=addon,
        )

    def get_page_url(self, base_url, page_num):
        if page_num <= 1:
            return base_url
        parsed = urllib.parse.urlparse(base_url)
        query = urllib.parse.parse_qs(parsed.query)
        query["page"] = [str(page_num)]
        return urllib.parse.urlunparse(
            (parsed.scheme, parsed.netloc, parsed.path, parsed.params, urllib.parse.urlencode(query, doseq=True), "")
        )

    def _extract_videos(self, html_content):
        videos = []
        pattern = re.compile(
            r'<a\b[^>]+href=["\'](/video/\d+/[^"\']+)["\'][^>]*>'
            r'([\s\S]{0,1800}?)</a>',
            re.IGNORECASE,
        )
        for href, body in pattern.findall(html_content or ""):
            image = re.search(r'<img\b[^>]+src=["\']([^"\']+)["\'][^>]+alt=["\']([^"\']+)["\']', body, re.IGNORECASE)
            if not image:
                continue
            duration = re.search(r'>(\d{1,2}:\d{2}(?::\d{2})?)</span>', body)
            duration_text = duration.group(1) if duration else ""
            title = html.unescape(image.group(2)).strip()
            info = {"title": title, "plot": title}
            seconds = self.convert_duration(duration_text)
            if seconds:
                info["duration"] = seconds
            label = "{} [COLOR lime]({})[/COLOR]".format(title, duration_text) if duration_text else title
            videos.append({
                "label": label,
                "url": self._absolute(href),
                "thumb": self._absolute(image.group(1)),
                "info": info,
            })
        return videos

    def _extract_next_page(self, html_content, current_url, page):
        return self.get_page_url(current_url, page + 1) if re.search(
            r'href=["\'][^"\']*[?&]page={}(?:["\'&])'.format(page + 1),
            html_content or "",
            re.IGNORECASE,
        ) else None
