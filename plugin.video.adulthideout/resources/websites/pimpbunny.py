#!/usr/bin/env python
# -*- coding: utf-8 -*-

import re
import urllib.parse

from resources.lib.kvs_tube import KVSTubeWebsite


class PimpBunny(KVSTubeWebsite):
    label = "PimpBunny"
    sort_options = ["Latest", "Most Viewed", "Best Rated"]
    sort_paths = {
        "Latest": "/videos/",
        "Most Viewed": "/videos/?sort_by=video_viewed",
        "Best Rated": "/videos/?sort_by=rating",
    }
    search_path = "/search/{}/"
    categories_path = "/categories/"
    models_path = "/onlyfans-creators/"
    video_path_markers = ("/videos/",)
    category_path_markers = ("/categories/", "/channels/", "/tags/")
    next_page_full_count = 30
    use_playback_proxy = True

    def __init__(self, addon_handle, addon=None):
        super().__init__(
            name="pimpbunny",
            base_url="https://pimpbunny.com/",
            search_url="https://pimpbunny.com/search/{}/",
            addon_handle=addon_handle,
            addon=addon,
        )

    def get_page_url(self, base_url, page_num):
        if page_num <= 1:
            return base_url
        parsed = urllib.parse.urlparse(base_url)
        path = parsed.path
        if re.search(r"/\d+/$", path):
            path = re.sub(r"/\d+/$", "/{}/".format(page_num), path)
        else:
            path = path.rstrip("/") + "/{}/".format(page_num)
        return urllib.parse.urlunparse((parsed.scheme, parsed.netloc, path, parsed.params, parsed.query, parsed.fragment))

    def _is_top_listing(self, url):
        parsed = urllib.parse.urlparse(url or self.base_url)
        return parsed.path.rstrip("/") in ("", "/videos")

    def _extract_videos(self, html_content):
        videos = []
        seen = set()
        blocks = re.findall(r'<a\b[^>]*ui-card-link[^>]*href=["\'][^"\']*/videos/[^"\']+/["\'][^>]*>[\s\S]{0,24000}?</a>', html_content or "", flags=re.IGNORECASE)
        for block in blocks:
            href_match = re.search(r'<a\b[^>]+href=["\']([^"\']*/videos/[^"\']+/)["\']', block, re.IGNORECASE)
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
                title_match = re.search(r'class=["\'][^"\']*\bui-card-title\b[^"\']*["\'][^>]*>([\s\S]*?)</div>', block, re.IGNORECASE)
            title = self._clean(title_match.group(1) if title_match else "")
            if not title:
                continue

            thumb = ""
            for attr in ("data-original", "data-webp", "data-src", "src"):
                thumb_match = re.search(r'\s{}=["\']([^"\']+)["\']'.format(attr), img_tag, re.IGNORECASE)
                if thumb_match:
                    thumb = self._absolute(thumb_match.group(1))
                    break
            if thumb.startswith("data:image/"):
                thumb = self.icon

            duration_match = re.search(r'class=["\'][^"\']*ui-card-duration[^"\']*["\'][^>]*>([\s\S]*?)</div>', block, re.IGNORECASE)
            duration = self._clean(duration_match.group(1)) if duration_match else ""
            seconds = self.convert_duration(duration)
            label = "{} [COLOR lime]({})[/COLOR]".format(title, duration) if duration else title
            info = {"title": title, "plot": title}
            if seconds:
                info["duration"] = seconds
            videos.append({"label": label, "url": video_url, "thumb": thumb or self.icon, "info": info})
        return videos
