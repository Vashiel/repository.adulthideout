#!/usr/bin/env python
# -*- coding: utf-8 -*-

import html
import os
import re
import urllib.parse

from resources.lib.cyrillic_utils import translate_cyrillic
from resources.lib.kvs_tube import KVSTubeWebsite
from resources.lib.thumb_proxy import build_thumb_url


class XXXPerevod(KVSTubeWebsite):
    label = "XXX Perevod"
    sort_options = ["Newest", "Top Rated", "Most Popular"]
    sort_paths = {
        "Newest": "/latest-updates/",
        "Top Rated": "/top-rated/",
        "Most Popular": "/most-popular/",
    }
    categories_path = "/categories/"
    video_path_markers = ("/video/",)
    category_path_markers = ("/categories/",)
    use_playback_proxy = True
    use_urllib_proxy = True

    def __init__(self, addon_handle, addon=None):
        super().__init__(
            name="xxxperevod",
            base_url="https://xxxperevod.com/",
            search_url="https://xxxperevod.com/search/{}/",
            addon_handle=addon_handle,
            addon=addon,
        )
        self.icon = os.path.join(self.addon.getAddonInfo("path"), "resources", "logos", "xxxperevod.png")
        self.icons["default"] = self.icon

    def _is_video_href(self, href):
        return bool(href and "/video/" in href)

    def _pick_thumb(self, img_tag):
        for attr in ("data-original", "data-webp", "data-src", "src"):
            m = re.search(r'\s' + attr + r'=["\']([^"\']+)', img_tag or "", re.I)
            if m:
                val = m.group(1).strip()
                if not val.startswith("data:"):
                    return self._absolute(val)
        return ""

    def get_page_url(self, url, page):
        if page <= 1:
            return url
        parsed = urllib.parse.urlparse(url)
        path = parsed.path.rstrip("/")
        if re.search(r"/\d+$", path):
            path = re.sub(r"/\d+$", f"/{page}/", path)
        else:
            path = f"{path}/{page}/"
        return urllib.parse.urlunparse((parsed.scheme, parsed.netloc, path, parsed.params, parsed.query, parsed.fragment))

    def _extract_next_page(self, html_content, current_url, page):
        next_page = page + 1
        if f"/{next_page}/" in (html_content or "") or f"from:{next_page}" in (html_content or ""):
            return self.get_page_url(current_url, next_page)
        return None

    def _extract_videos(self, html_content):
        videos = []
        blocks = re.split(r'(?=<div\b[^>]+class=["\'][^"\']*\bitem\b[^"\']*["\'])', html_content or "", flags=re.I)

        for b in blocks:
            link_m = re.search(r'<a\b[^>]*href=["\']([^"\']*/video/[^"\']*)["\']', b, re.I)
            if not link_m:
                continue
            video_url = self._absolute(link_m.group(1))

            title_m = re.search(r'title=["\']([^"\']+)["\']', b, re.I)
            if not title_m:
                title_m = re.search(r'<strong\b[^>]*class=["\'][^"\']*title[^"\']*["\'][^>]*>([^<]+)<', b, re.I)
            raw_title = self._clean(title_m.group(1) if title_m else "")
            if not raw_title:
                continue

            img_m = re.search(r'<img\b[^>]*>', b, re.I)
            thumb = self._pick_thumb(img_m.group(0) if img_m else "")

            dur_m = re.search(r'class=["\'][^"\']*duration[^"\']*["\'][^>]*>[\s\S]*?(\d{1,2}:\d{2}(?::\d{2})?)', b, re.I)
            if not dur_m:
                dur_m = re.search(r'\b(\d{1,2}:\d{2}(?::\d{2})?)\b', b)
            duration = dur_m.group(1).strip() if dur_m else ""

            title = translate_cyrillic(raw_title)
            seconds = self.convert_duration(duration)
            label = f"{title} [COLOR lime]({duration})[/COLOR]" if duration else title
            info = {"title": title, "plot": title}
            if seconds:
                info["duration"] = seconds
            videos.append({"label": label, "url": video_url, "thumb": thumb or self.icon, "info": info})
        return videos

    def process_categories(self, url):
        target_url = self._absolute(self.categories_path)
        html_content = self._get(target_url)
        if not html_content:
            self.notify_error("Could not load categories")
            self.end_directory("categories")
            return

        context_menu = self._context_menu(self.base_url)
        matches = re.findall(
            r'<a\b[^>]*href=["\'](https?://[^"\']*/categories/[^"/]+/?)[^>]*>[\s\S]*?<img\b[^>]*src=["\']([^"\']+)["\'][^>]*alt=["\']([^"\']*)["\']',
            html_content,
            re.I,
        )
        if not matches:
            matches = re.findall(
                r'<a\b[^>]*href=["\']([^"\']*/categories/[^"/]+/?)[^>]*>([\s\S]*?)</a>',
                html_content,
                re.I,
            )

        seen = set()
        for item in matches:
            if len(item) == 3:
                cat_url, thumb, raw_title = item
            elif len(item) == 2:
                cat_url, raw_title = item
                thumb = self.icon
            else:
                continue

            cat_url = self._absolute(cat_url)
            if cat_url in seen:
                continue
            seen.add(cat_url)

            clean_name = self._clean(raw_title)
            if not clean_name:
                slug = cat_url.rstrip("/").split("/")[-1]
                clean_name = slug.replace("-", " ").replace("_", " ").title()

            title = translate_cyrillic(clean_name)
            self.add_dir(title, cat_url, 2, thumb or self.icon, context_menu=context_menu)

        self.end_directory("categories")
