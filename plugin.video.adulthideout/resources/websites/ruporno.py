#!/usr/bin/env python
# -*- coding: utf-8 -*-

import html
import os
import re
import urllib.parse

from resources.lib.cyrillic_utils import translate_cyrillic
from resources.lib.kvs_tube import KVSTubeWebsite
from resources.lib.thumb_proxy import build_thumb_url


class RuPorno(KVSTubeWebsite):
    label = "RuPorno"
    sort_options = ["Newest", "Top Rated", "Most Popular"]
    sort_paths = {
        "Newest": "/latest-updates/",
        "Top Rated": "/top-rated/",
        "Most Popular": "/most-popular/",
    }
    categories_path = "/category/"
    video_path_markers = ("/videos/",)
    category_path_markers = ("/categories/", "/category/")
    use_playback_proxy = True
    use_urllib_proxy = True

    def __init__(self, addon_handle, addon=None):
        super().__init__(
            name="ruporno",
            base_url="https://wvw.ruporno.net/",
            search_url="https://wvw.ruporno.net/search/{}/",
            addon_handle=addon_handle,
            addon=addon,
        )
        self.icon = os.path.join(self.addon.getAddonInfo("path"), "resources", "logos", "ruporno.png")
        self.icons["default"] = self.icon

    def _is_video_href(self, href):
        return bool(href and re.search(r'/videos/\d+/', href))

    def _pick_thumb(self, img_tag):
        match = re.search(r'\s(?:data-original|data-webp|data-src|src)=["\']([^"\']+)', img_tag or "", re.IGNORECASE)
        thumb = self._absolute(match.group(1)) if match else ""
        if thumb.startswith("data:"):
            return ""
        return thumb

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
        blocks = re.findall(r'<div\b[^>]*class=["\'][^"\']*\bitem\b[^"\']*["\'][^>]*>([\s\S]*?)</div>\s*</div>', html_content or "", re.I)
        if not blocks:
            blocks = re.findall(r'<div\b[^>]*class=["\'][^"\']*\bitem\b[^"\']*["\'][^>]*>([\s\S]*?)</div>', html_content or "", re.I)

        for b in blocks:
            link_m = re.search(r'<a\b[^>]*href=["\']([^"\']*/videos/\d+/[^"\']*)["\']', b, re.I)
            if not link_m:
                continue
            video_url = self._absolute(link_m.group(1))

            title_m = re.search(r'title=["\']([^"\']+)["\']', b, re.I)
            if not title_m:
                title_m = re.search(r'<span\b[^>]*class=["\'][^"\']*title[^"\']*["\'][^>]*>([^<]+)<', b, re.I)
            raw_title = self._clean(title_m.group(1) if title_m else "")
            if not raw_title:
                continue

            img_m = re.search(r'<img\b[^>]*>', b, re.I)
            thumb = self._pick_thumb(img_m.group(0)) if img_m else ""

            dur_m = re.search(r'class=["\'][^"\']*duration[^"\']*["\'][^>]*>([^<]+)<', b, re.I)
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
            r'<a\b[^>]*href=["\'](https?://[^"\']*/categories/[^"/]+/?)[^>]*>[\s\S]*?<img\b[^>]*src=["\']([^"\']+)["\'][\s\S]*?<strong\b[^>]*>([^<]+)</strong>',
            html_content,
            re.I,
        )
        if not matches:
            matches = re.findall(
                r'<a\b[^>]*href=["\'](https?://[^"\']*/categories/[^"/]+/?)[^>]*>[\s\S]*?<span\b[^>]*class=["\']title["\'][^>]*>([^<]+)</span>',
                html_content,
                re.I,
            )
        if not matches:
            matches = re.findall(
                r'<a\b[^>]*href=["\']([^"\']*/categories/[^"/]+/?)[^>]*>([^<]+)</a>',
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

            title = translate_cyrillic(self._clean(raw_title))
            self.add_dir(title, cat_url, 2, thumb or self.icon, context_menu=context_menu)

        self.end_directory("categories")
