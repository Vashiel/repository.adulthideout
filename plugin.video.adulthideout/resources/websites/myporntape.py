#!/usr/bin/env python
# -*- coding: utf-8 -*-

import re
import urllib.parse

from resources.lib.kvs_tube import KVSTubeWebsite


class MyPornTape(KVSTubeWebsite):
    label = "MyPornTape"
    sort_options = ["Latest", "Most Viewed", "Top Rated", "Longest", "Most Commented", "Most Favourited"]
    sort_paths = {
        "Latest": "/latest-updates/",
        "Most Viewed": "/most-popular/",
        "Top Rated": "/top-rated/",
        "Longest": "/longest/",
        "Most Commented": "/most-commented/",
        "Most Favourited": "/most-favourited/",
    }
    search_path = "/search/{}/"
    categories_path = "/categories/"
    models_path = "/models/"
    video_path_markers = ("/videos/",)
    category_path_markers = ("/categories/", "/tags/")
    prefer_default_stream = True
    use_playback_proxy = True
    next_page_full_count = 16

    def __init__(self, addon_handle, addon=None):
        super().__init__(
            name="myporntape",
            base_url="https://myporntape.com/",
            search_url="https://myporntape.com/search/{}/",
            addon_handle=addon_handle,
            addon=addon,
        )

    def _is_top_listing(self, url):
        parsed = urllib.parse.urlparse(url or self.base_url)
        return parsed.path.rstrip("/") in (
            "",
            "/latest-updates",
            "/most-popular",
            "/top-rated",
            "/longest",
            "/most-commented",
            "/most-favourited",
        )

    def search(self, query):
        if not query:
            return
        slug = urllib.parse.quote_plus(query.strip().replace(" ", "-"))
        self.process_content(self._absolute("/tags/{}/".format(slug)))

    def _extract_videos(self, html_content):
        videos = super(MyPornTape, self)._extract_videos(html_content)
        if videos:
            return videos

        videos = []
        seen = set()
        blocks = re.split(
            r'(?=<a\b[^>]+href=["\'][^"\']*/videos/\d+/[^"\']+["\'])',
            html_content or "",
            flags=re.IGNORECASE,
        )
        for block in blocks:
            href_match = re.search(r'<a\b[^>]+href=["\']([^"\']*/videos/\d+/[^"\']+)["\']', block, re.IGNORECASE)
            if not href_match:
                continue
            video_url = self._absolute(href_match.group(1))
            if not video_url or video_url in seen:
                continue
            seen.add(video_url)

            img_match = re.search(r"<img\b[^>]*>", block, re.IGNORECASE)
            img_tag = img_match.group(0) if img_match else ""
            title_match = re.search(r'\s(?:alt|title)=["\']([^"\']+)["\']', img_tag, re.IGNORECASE)
            if not title_match:
                title_match = re.search(
                    r'<span\b[^>]+class=["\'][^"\']*title[^"\']*["\'][^>]*>([\s\S]{0,200}?)</span>',
                    block,
                    re.IGNORECASE,
                )
            title = self._clean(title_match.group(1) if title_match else "")
            if not title:
                continue

            thumb = ""
            for attr in ("data-original", "data-src", "src"):
                thumb_match = re.search(r'\s{}=["\']([^"\']+)["\']'.format(attr), img_tag, re.IGNORECASE)
                if thumb_match:
                    thumb = self._absolute(thumb_match.group(1))
                    break

            duration_match = re.search(
                r'<(?:div|span)\b[^>]*class=["\'][^"\']*duration[^"\']*["\'][^>]*>([\s\S]*?)</(?:div|span)>',
                block,
                re.IGNORECASE,
            )
            duration = self._clean(duration_match.group(1)) if duration_match else ""
            seconds = self.convert_duration(duration)
            label = "{} [COLOR lime]({})[/COLOR]".format(title, duration) if duration else title
            info = {"title": title, "plot": title}
            if seconds:
                info["duration"] = seconds
            videos.append({"label": label, "url": video_url, "thumb": thumb or self.icon, "info": info})
        return videos
