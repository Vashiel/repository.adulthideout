#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import re
import urllib.parse
from resources.lib.kvs_tube import KVSTubeWebsite


class SpankingTube(KVSTubeWebsite):
    label = "SpankingTube"
    sort_options = ["Latest", "Most Viewed", "Top Rated"]
    sort_paths = {
        "Latest": "/videos?o=mr",
        "Most Viewed": "/videos?o=mv",
        "Top Rated": "/videos?o=tr",
    }
    search_path = "/search/videos/{}/"
    categories_path = "/categories/"
    models_path = "/models?o=mv&g=female"
    video_path_markers = ("/video/",)
    category_path_markers = ("/categories/", "/videos/", "/tags/")
    next_page_full_count = 20
    use_playback_proxy = False

    def __init__(self, addon_handle, addon=None):
        super().__init__(
            name="spankingtube",
            base_url="https://www.spankingtube.com",
            search_url="https://www.spankingtube.com/search/videos/{}/",
            addon_handle=addon_handle,
            addon=addon,
        )

    def get_page_url(self, base_url, page_num):
        if not base_url:
            base_url = self.get_start_url_and_label()[0]
        parsed = urllib.parse.urlparse(base_url)
        query = urllib.parse.parse_qs(parsed.query)
        if page_num > 1:
            query["page"] = [str(page_num)]
        elif "page" in query:
            del query["page"]
        new_query = urllib.parse.urlencode(query, doseq=True)
        return urllib.parse.urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, new_query, parsed.fragment))

    def process_content(self, url, page=1):
        if not url or url == "BOOTSTRAP":
            url, _ = self.get_start_url_and_label()

        if len(sys.argv) > 2 and sys.argv[2]:
            qs = urllib.parse.parse_qs(sys.argv[2].lstrip("?"))
            if "page" in qs and qs["page"][0].isdigit():
                page = int(qs["page"][0])

        parsed = urllib.parse.urlparse(url)
        query = urllib.parse.parse_qs(parsed.query)
        if "page" in query and query["page"][0].isdigit():
            page = int(query["page"][0])

        super().process_content(url, page=page)

    def _extract_videos(self, html_content):
        blocks = re.split(r'(?=<div\b[^>]+class=["\'][^"\']*\bcol-(?:12|6|4|3)\b[^"\']*["\'])', html_content or "", flags=re.IGNORECASE)
        videos = []
        seen = set()
        for block in blocks:
            if "/video/" not in block:
                continue
            href_match = re.search(r'<a\b[^>]+href=["\']([^"\']*/video/\d+/[^"\']*)["\']', block, re.IGNORECASE)
            if not href_match:
                continue
            video_url = self._absolute(href_match.group(1))
            if not video_url or video_url in seen:
                continue
            seen.add(video_url)

            img_match = re.search(r"<img\b[^>]*>", block, re.IGNORECASE)
            img_tag = img_match.group(0) if img_match else ""
            title_match = re.search(r'\stitle=["\']([^"\']+)["\']', img_tag, re.IGNORECASE)
            if not title_match:
                title_match = re.search(r'\s(?:alt|title)=["\']([^"\']+)["\']', block, re.IGNORECASE)
            title = self._clean(title_match.group(1) if title_match else "")
            if not title or title.lower() in ("videos", "rss"):
                continue

            thumb = self._pick_thumb(img_tag)
            duration_match = re.search(r'class=["\'][^"\']*duration[^"\']*["\'][^>]*>([\s\S]*?)</', block, re.IGNORECASE)
            duration = self._clean(duration_match.group(1)) if duration_match else ""
            seconds = self.convert_duration(duration)

            label = "{} [COLOR lime]({})[/COLOR]".format(title, duration) if duration else title
            info = {"title": title, "plot": title}
            if seconds:
                info["duration"] = seconds
            videos.append({"label": label, "url": video_url, "thumb": thumb or self.icon, "info": info})
        return videos

    def _extract_next_page(self, html_content, current_url, page):
        next_page = page + 1
        if "page={}".format(next_page) in (html_content or "") or 'class="page-link"' in (html_content or ""):
            return self.get_page_url(current_url, next_page)
        return super()._extract_next_page(html_content, current_url, page)

    def _is_stream_candidate(self, value):
        if not value:
            return False
        val_lower = value.lower()
        return ("video_stream" in val_lower or ".mp4" in val_lower or "get_file/" in val_lower) and val_lower.startswith("http")

    def _extract_stream_url(self, html_content, referer=None):
        for src in re.findall(r'<source\b[^>]*\bsrc=["\']([^"\']+)["\']', html_content or "", re.IGNORECASE):
            stream_url = self._normalize_stream(src)
            if self._is_stream_candidate(stream_url):
                return stream_url
        return super()._extract_stream_url(html_content, referer=referer)
