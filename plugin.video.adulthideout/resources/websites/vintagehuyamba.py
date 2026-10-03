#!/usr/bin/env python
# -*- coding: utf-8 -*-

import html
import os
import re
import urllib.parse

from resources.lib.cyrillic_utils import translate_cyrillic
from resources.lib.kvs_tube import KVSTubeWebsite
from resources.lib.thumb_proxy import build_thumb_url


class VintageHuyamba(KVSTubeWebsite):
    label = "Vintage Huyamba"
    sort_options = ["Newest", "Most Popular", "Top Rated", "Longest"]
    sort_paths = {
        "Newest": "/videos/",
        "Most Popular": "/most-popular/",
        "Top Rated": "/top-rated/",
        "Longest": "/videos/?sort_by=duration",
    }
    categories_path = "/categories/"
    models_path = "/models/"
    video_path_markers = ("/video/",)
    use_playback_proxy = True
    use_urllib_proxy = True

    def __init__(self, addon_handle, addon=None):
        super().__init__(
            name="vintagehuyamba",
            base_url="https://vintage.huyamba.mobi/",
            search_url="https://vintage.huyamba.mobi/search/{}/",
            addon_handle=addon_handle,
            addon=addon,
        )
        self.icon = os.path.join(self.addon.getAddonInfo("path"), "resources", "logos", "vintagehuyamba.png")
        self.icons["default"] = self.icon

    def _is_video_href(self, href):
        return bool(href and "/video/" in href and "/link/" not in href)

    def _pick_thumb(self, img_tag):
        match = re.search(r'\s(?:data-original|data-webp|data-src)=["\']([^"\']+)', img_tag or "", re.IGNORECASE)
        if not match:
            match = re.search(r'\ssrc=["\']([^"\']+)', img_tag or "", re.IGNORECASE)
        thumb = self._absolute(match.group(1)) if match else ""
        if thumb.startswith("data:"):
            return ""
        return build_thumb_url(thumb, referer=self.base_url) if thumb else thumb

    def get_page_url(self, url, page):
        if page <= 1:
            return url
        parsed = urllib.parse.urlparse(url)
        path = parsed.path.rstrip("/")
        if re.search(r"/\d+$", path):
            path = re.sub(r"/\d+$", f"/{page}", path)
        else:
            path = f"{path}/{page}/"
        return urllib.parse.urlunparse((parsed.scheme, parsed.netloc, path, parsed.params, parsed.query, parsed.fragment))

    def _extract_videos(self, html_content):
        videos = []
        for block in re.finditer(r'<div\b[^>]*class=["\'][^"\']*\bitem\b[^"\']*\bthumb\b[^"\']*["\'][^>]*>([\s\S]*?)(?:<div\b[^>]*class=["\'][^"\']*\bitem\b|\Z)', html_content or "", re.IGNORECASE):
            b = block.group(1)
            link = re.search(r'<a\b[^>]*class=["\'][^"\']*card[^"\']*["\'][^>]*href=["\']([^"\']+)["\'][^>]*title=["\']([^"\']+)["\']', b, re.I)
            if not link:
                continue
            video_url = self._absolute(link.group(1))
            raw_title = self._clean(html.unescape(link.group(2)))
            title = translate_cyrillic(raw_title)
            img_match = re.search(r'<img\b[^>]*>', b, re.I)
            thumb = self._pick_thumb(img_match.group(0)) if img_match else ""

            dur_match = re.search(r'<div\b[^>]*class=["\']box["\'][^>]*>\s*(\d{1,2}:\d{2}(?::\d{2})?)\s*</div>', b, re.I)
            duration = dur_match.group(1).strip() if dur_match else ""

            seconds = self.convert_duration(duration)
            label = "{} [COLOR lime]({})[/COLOR]".format(title, duration) if duration else title
            info = {"title": title, "plot": title}
            if seconds:
                info["duration"] = seconds
            videos.append({"label": label, "url": video_url, "thumb": thumb or self.icon, "info": info})
        return videos

    def _format_category_title(self, title):
        return translate_cyrillic(title)

    def _extract_next_page(self, html_content, current_url, page):
        next_page = page + 1
        if f"from:{next_page}" in (html_content or ""):
            return self.get_page_url(current_url, next_page)
        return None
