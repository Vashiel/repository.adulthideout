#!/usr/bin/env python
# -*- coding: utf-8 -*-

import re
import urllib.parse

from resources.lib.kvs_tube import KVSTubeWebsite


class PornMedium(KVSTubeWebsite):
    label = "PornMedium"
    sort_options = ["Latest", "Best Rated", "Most Viewed"]
    sort_paths = {
        "Latest": "/newest",
        "Best Rated": "/best",
        "Most Viewed": "/most-viewed",
    }
    search_path = "/search/"
    categories_path = "/categories"
    models_path = None
    video_path_markers = ("/video/",)
    category_path_markers = ("/category/",)
    skip_category_titles = {"3d"}

    def __init__(self, addon_handle, addon=None):
        super().__init__(
            name="pornmedium",
            base_url="https://pornmedium.com/",
            search_url="https://pornmedium.com/search/{}",
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
            (parsed.scheme, parsed.netloc, parsed.path, parsed.params, urllib.parse.urlencode(query, doseq=True), parsed.fragment)
        )

    def _is_top_listing(self, url):
        parsed = urllib.parse.urlparse(url or self.base_url)
        return parsed.path.rstrip("/") in ("", "/newest", "/best", "/most-viewed")

    def _get_sort_key(self):
        if self.addon.getSetting("pornmedium_sort_migrated_1012") != "true":
            try:
                legacy_index = int(self.addon.getSetting("pornmedium_sort_by") or "0")
            except (TypeError, ValueError):
                legacy_index = 0
            migrated_index = max(0, legacy_index - 1)
            self.addon.setSetting("pornmedium_sort_by", str(migrated_index))
            self.addon.setSetting("pornmedium_sort_migrated_1012", "true")
        return super(PornMedium, self)._get_sort_key()

    def _extract_videos(self, html_content):
        videos = []
        seen = set()
        blocks = re.split(r'(?=<a\b[^>]+class=["\'][^"\']*vcard__link[^"\']*["\'])', html_content or "", flags=re.IGNORECASE)
        for block in blocks:
            href_match = re.search(r'<a\b[^>]+href=["\']([^"\']*/video/[^"\']+)["\']', block, re.IGNORECASE)
            if not href_match:
                continue
            video_url = self._absolute(href_match.group(1))
            if not video_url or video_url in seen:
                continue
            seen.add(video_url)

            img_match = re.search(r"<img\b[^>]*>", block, re.IGNORECASE)
            img_tag = img_match.group(0) if img_match else ""
            title_match = re.search(r'\s(?:alt|title)=["\']([^"\']+)["\']', img_tag, re.IGNORECASE)
            title = self._clean(title_match.group(1) if title_match else "")
            if not title:
                continue

            thumb = ""
            for attr in ("data-src", "data-original", "src"):
                thumb_match = re.search(r'\s{}=["\']([^"\']+)["\']'.format(attr), img_tag, re.IGNORECASE)
                if thumb_match:
                    thumb = self._absolute(thumb_match.group(1))
                    break
            if thumb.startswith("data:image/"):
                thumb = self.icon

            duration_match = re.search(r'class=["\'][^"\']*vcard__duration[^"\']*["\'][^>]*>([\s\S]*?)</span>', block, re.IGNORECASE)
            duration = self._clean(duration_match.group(1)) if duration_match else ""
            seconds = self.convert_duration(duration)
            label = "{} [COLOR lime]({})[/COLOR]".format(title, duration) if duration else title
            info = {"title": title, "plot": title}
            if seconds:
                info["duration"] = seconds
            videos.append({"label": label, "url": video_url, "thumb": thumb or self.icon, "info": info})
        return videos

    def _extract_stream_url(self, html_content, referer=None):
        candidates = []
        for src, size in re.findall(r'src:\s*["\']([^"\']+\.mp4[^"\']*)["\'][^}]*size:\s*(\d+)', html_content or "", re.IGNORECASE):
            candidates.append((int(size), self._normalize_stream(src)))
        for src in re.findall(r'"contentUrl"\s*:\s*"([^"]+\.mp4[^"]*)"', html_content or "", re.IGNORECASE):
            candidates.append((0, self._normalize_stream(src)))
        candidates.sort(key=lambda item: item[0], reverse=True)
        for _, stream_url in candidates:
            if self._is_stream_candidate(stream_url) and self._probe_stream(stream_url, referer or self.base_url):
                return stream_url
        for _, stream_url in candidates:
            if self._is_stream_candidate(stream_url):
                return stream_url
        return None
