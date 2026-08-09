#!/usr/bin/env python
# -*- coding: utf-8 -*-

import re
import urllib.parse

from resources.lib.kvs_tube import KVSTubeWebsite


class WatchMyGF(KVSTubeWebsite):
    label = "WatchMyGF"
    video_path_markers = ("/video/",)
    category_path_markers = (".porn",)
    sort_options = ["Latest", "Popular", "Popular This Month", "Longest"]
    sort_paths = {
        "Latest": "/new/",
        "Popular": "/popular/",
        "Popular This Month": "/popular/month/",
        "Longest": "/longest/",
    }
    categories_path = "/categories/"
    models_path = "/girls/"
    use_playback_proxy = True
    next_page_full_count = 20

    def __init__(self, addon_handle, addon=None):
        super().__init__(
            name="watchmygf",
            base_url="https://www.watchmygf.me/",
            search_url="https://www.watchmygf.me/search/{}/",
            addon_handle=addon_handle,
            addon=addon,
        )

    def _extract_videos(self, html_content):
        videos = []
        seen = set()
        blocks = re.split(
            r'(?=<div\b[^>]+class=["\'][^"\']*video-box-card\s+item[^"\']*["\'])',
            html_content or "",
            flags=re.IGNORECASE,
        )
        for block in blocks:
            href_match = re.search(r'<a\b[^>]+href=["\']([^"\']+/video/[^"\']+)["\']', block, re.IGNORECASE)
            if not href_match:
                continue
            video_url = self._absolute(href_match.group(1))
            if video_url in seen:
                continue
            seen.add(video_url)
            image_match = re.search(r'<img\b[^>]*\bdata-src=["\']([^"\']+)["\'][^>]*', block, re.IGNORECASE)
            title_match = re.search(r'<img\b[^>]*\balt=["\']([^"\']+)', block, re.IGNORECASE)
            duration_match = re.search(r'<div\b[^>]*class=["\'][^"\']*\btime\b[^"\']*["\'][^>]*>([^<]+)', block, re.IGNORECASE)
            title = self._clean(title_match.group(1) if title_match else "")
            duration = self._clean(duration_match.group(1) if duration_match else "")
            if not title:
                continue
            seconds = self.convert_duration(duration)
            info = {"title": title, "plot": title}
            if seconds:
                info["duration"] = seconds
            thumb = self._absolute(image_match.group(1)) if image_match else self.icon
            thumb = thumb.replace("https://cdn1.watchmygf.me/", "https://www.watchmygf.me/")
            videos.append({
                "label": "{} [COLOR lime]({})[/COLOR]".format(title, duration) if duration else title,
                "url": video_url,
                "thumb": thumb,
                "info": info,
            })
        return videos

    def process_categories(self, url):
        current_url = url or self._absolute(self.categories_path)
        html_content = self._get(current_url)
        if not html_content:
            self.notify_error("Could not load WatchMyGF categories")
            return self.end_directory("videos")

        seen = set()
        for match in re.finditer(
            r'<a\b[^>]*href=["\']([^"\']+\.porn/?)["\'][^>]*>([\s\S]{0,1200}?)</a>',
            html_content,
            re.IGNORECASE,
        ):
            category_url = self._absolute(match.group(1))
            body = match.group(2)
            if category_url in seen or not re.search(r"<img\b", body, re.IGNORECASE):
                continue
            seen.add(category_url)
            title_match = re.search(r'<img\b[^>]*(?:alt|title)=["\']([^"\']+)', body, re.IGNORECASE)
            title = self._clean(title_match.group(1) if title_match else body)
            title = re.sub(r"\s+\d[\d,.]*$", "", title).strip()
            if title:
                self.add_dir(title, category_url, 2, self.icons.get("categories", self.icon), self.fanart)
        self.end_directory("videos")
