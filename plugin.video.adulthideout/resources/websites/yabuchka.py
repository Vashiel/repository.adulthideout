#!/usr/bin/env python
# -*- coding: utf-8 -*-

import html
import os
import re
import urllib.parse

from resources.lib.cyrillic_utils import translate_cyrillic
from resources.lib.kvs_tube import KVSTubeWebsite
from resources.lib.thumb_proxy import build_thumb_url


class Yabuchka(KVSTubeWebsite):
    label = "Yabuchka"
    sort_options = ["Latest", "Most Popular", "Top Rated", "Longest"]
    sort_paths = {
        "Latest": "/latest-updates/",
        "Most Popular": "/most-popular/",
        "Top Rated": "/top-rated/",
        "Longest": "/videos/?sort_by=duration",
    }
    categories_path = "/categories/"
    models_path = "/models/"
    video_path_markers = ("/videos/",)
    use_playback_proxy = True
    use_urllib_proxy = True

    def __init__(self, addon_handle, addon=None):
        super().__init__(
            name="yabuchka",
            base_url="https://www1.yabuchka.xyz/",
            search_url="https://www1.yabuchka.xyz/search/{}/",
            addon_handle=addon_handle,
            addon=addon,
        )
        self.icon = os.path.join(self.addon.getAddonInfo("path"), "resources", "logos", "yabuchka.png")
        self.icons["default"] = self.icon

    def _is_video_href(self, href):
        return bool(href and "/videos/" in href and "/link/" not in href)

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

    def _extract_next_page(self, html_content, current_url, page):
        next_page = page + 1
        if f"from:{next_page:02d}" in (html_content or "") or f"from:{next_page}" in (html_content or ""):
            return self.get_page_url(current_url, next_page)
        return None

    def _extract_videos(self, html_content):
        videos = super()._extract_videos(html_content)
        for v in videos:
            title = v.get("info", {}).get("title", "")
            if title:
                translated = translate_cyrillic(title)
                v["info"]["title"] = translated
                v["info"]["plot"] = translated
                dur_idx = v.get("label", "").find(" [COLOR lime]")
                duration_part = v["label"][dur_idx:] if dur_idx != -1 else ""
                v["label"] = translated + duration_part
        return videos

    def _format_category_title(self, title):
        return translate_cyrillic(title)
