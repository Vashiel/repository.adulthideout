#!/usr/bin/env python
# -*- coding: utf-8 -*-

import html
import os
import re
import urllib.parse

from resources.lib.cyrillic_utils import translate_cyrillic
from resources.lib.kvs_tube import KVSTubeWebsite
from resources.lib.thumb_proxy import build_thumb_url


class MixPorn(KVSTubeWebsite):
    label = "MixPorn"
    sort_options = ["Latest", "Most Viewed", "Top Rated", "Longest"]
    sort_paths = {
        "Latest": "/",
        "Most Viewed": "/most-viewed/",
        "Top Rated": "/top-rated/",
        "Longest": "/longest/",
    }
    categories_path = "/categories/"
    models_path = "/models/"
    video_path_markers = ("/videos/",)
    use_playback_proxy = True
    use_urllib_proxy = True

    def __init__(self, addon_handle, addon=None):
        super().__init__(
            name="mixporn",
            base_url="https://r11.mixporn.space/",
            search_url="https://r11.mixporn.space/search/{}/",
            addon_handle=addon_handle,
            addon=addon,
        )
        self.icon = os.path.join(self.addon.getAddonInfo("path"), "resources", "logos", "mixporn.png")
        self.icons["default"] = self.icon

    def _is_video_href(self, href):
        return bool(href and "/videos/" in href and "/link/" not in href)

    def _pick_thumb(self, img_tag):
        match = re.search(r'\s(?:data-src|data-original|data-webp)=["\']([^"\']+)', img_tag or "", re.IGNORECASE)
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
        if f"/{next_page}/" in (html_content or ""):
            return self.get_page_url(current_url, next_page)
        return None

    def _extract_videos(self, html_content):
        videos = []
        for block in re.finditer(r'<div\b[^>]*class=["\'][^"\']*\bthumb\s+item\b[^"\']*["\'][^>]*>([\s\S]*?)(?=<div\b[^>]*class=["\'][^"\']*\bthumb\s+item\b|\Z)', html_content or "", re.I):
            b = block.group(1)
            link_m = re.search(r'<a\b[^>]*href=["\']([^"\']+/videos/\d+/[^"\']*)["\']', b, re.I)
            if not link_m:
                continue
            video_url = self._absolute(link_m.group(1))

            img_m = re.search(r'<img\b[^>]*>', b, re.I)
            img_tag = img_m.group(0) if img_m else ""
            thumb = self._pick_thumb(img_tag)

            title_m = re.search(r'<div\b[^>]*class=["\']thumb-text["\'][^>]*>([^<]+)<', b, re.I)
            if not title_m:
                title_m = re.search(r'\salt=["\']([^"\']+)["\']', img_tag, re.I)
            raw_title = self._clean(title_m.group(1) if title_m else "")
            if not raw_title:
                continue

            dur_m = re.search(r'class=["\'](?:duration|time)["\'][^>]*>([^<]+)<', b, re.I)
            duration = dur_m.group(1).strip() if dur_m else ""

            translated = translate_cyrillic(raw_title)
            label = f"{translated} [COLOR lime]({duration})[/COLOR]" if duration else translated
            info = {"title": translated, "plot": translated}
            seconds = self.convert_duration(duration)
            if seconds:
                info["duration"] = seconds
            videos.append({"label": label, "url": video_url, "thumb": thumb or self.icon, "info": info})
        return videos

    def _extract_categories(self, html_content):
        categories = super()._extract_categories(html_content)
        for cat in categories:
            label = cat.get("label", "")
            if label:
                translated = translate_cyrillic(label)
                cat["label"] = translated
        return categories
