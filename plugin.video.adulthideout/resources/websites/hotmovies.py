#!/usr/bin/env python
# -*- coding: utf-8 -*-

import html
import os
import re
import urllib.parse

from resources.lib.cyrillic_utils import translate_cyrillic
from resources.lib.kvs_tube import KVSTubeWebsite
from resources.lib.thumb_proxy import build_thumb_url


class HotMovies(KVSTubeWebsite):
    label = "HotMovies"
    sort_options = ["Latest"]
    sort_paths = {"Latest": "/"}
    categories_path = "/categories/"
    video_path_markers = ("/categories/", "/erotik/")
    next_page_full_count = 20
    use_playback_proxy = True
    use_urllib_proxy = True

    def __init__(self, addon_handle, addon=None):
        super().__init__(
            name="hotmovies",
            base_url="https://mx.hotmovies.cc/",
            search_url="https://mx.hotmovies.cc/search/?search_string={}",
            addon_handle=addon_handle,
            addon=addon,
        )
        self.icon = os.path.join(self.addon.getAddonInfo("path"), "resources", "logos", "hotmovies.png")
        self.icons["default"] = self.icon

    def _is_video_href(self, href):
        if not href:
            return False
        return "/categories/" in href or "/erotik/" in href

    def _pick_thumb(self, img_src):
        if not img_src:
            return ""
        thumb = self._absolute(img_src)
        if thumb.startswith("data:"):
            return ""
        return build_thumb_url(thumb, referer=self.base_url) if thumb else thumb

    def get_page_url(self, url, page):
        if page <= 1:
            return url
        parsed = urllib.parse.urlparse(url)
        query = urllib.parse.parse_qs(parsed.query)
        query["p"] = [str(page - 1)]
        new_query = urllib.parse.urlencode(query, doseq=True)
        return urllib.parse.urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, new_query, parsed.fragment))

    def _extract_next_page(self, html_content, current_url, page):
        next_p = page
        if f"?p={next_p}" in (html_content or "") or f"&p={next_p}" in (html_content or ""):
            return self.get_page_url(current_url, page + 1)
        num_vids = len(re.findall(r'<div\b[^>]*class=["\'][^"\']*\bitem\b[^"\']*\bvideo-block\b', html_content or "", re.I))
        if num_vids >= 20:
            return self.get_page_url(current_url, page + 1)
        return None

    def _extract_videos(self, html_content):
        videos = []
        # 1. Standard video-block
        for block in re.finditer(r'<div\b[^>]*class=["\'][^"\']*\bitem\b[^"\']*\bvideo-block\b[^"\']*["\'][^>]*>([\s\S]*?)(?=<div\b[^>]*class=["\'][^"\']*\bitem\b[^"\']*\bvideo-block\b|\Z)', html_content or "", re.I):
            b = block.group(1)
            link_m = re.search(r'<a\b[^>]*href=["\']([^"\']+)["\']', b, re.I)
            if not link_m:
                continue
            video_url = self._absolute(link_m.group(1))
            if video_url.rstrip("/") == self.base_url.rstrip("/") or ("/categories/" not in video_url and "/erotik/" not in video_url):
                continue

            img_m = re.search(r'<img\b[^>]*src=["\']([^"\']+)["\']', b, re.I)
            thumb = self._pick_thumb(img_m.group(1) if img_m else "")

            title_m = re.search(r'<div\b[^>]*class=["\']title["\'][^>]*>([^<]+)<', b, re.I)
            if not title_m and img_m:
                title_m = re.search(r'\salt=["\']([^"\']+)["\']', img_m.group(0), re.I)
            raw_title = self._clean(title_m.group(1) if title_m else "")
            if not raw_title:
                continue

            dur_m = re.search(r'class=["\']duration["\'][^>]*>([^<]+)<', b, re.I)
            duration = dur_m.group(1).strip() if dur_m else ""

            translated = translate_cyrillic(raw_title)
            label = f"{translated} [COLOR lime]({duration})[/COLOR]" if duration else translated
            info = {"title": translated, "plot": translated}
            seconds = self.convert_duration(duration)
            if seconds:
                info["duration"] = seconds
            videos.append({"label": label, "url": video_url, "thumb": thumb or self.icon, "info": info})

        # 2. Search items
        if not videos and 'class="search-item"' in (html_content or ""):
            for block in re.finditer(r'<div\b[^>]*class=["\'][^"\']*\bsearch-item\b[^"\']*["\'][^>]*>([\s\S]*?)(?=<div\b[^>]*class=["\'][^"\']*\bsearch-item\b|\Z)', html_content or "", re.I):
                b = block.group(1)
                link_m = re.search(r'<p\b[^>]*class=["\']search-title["\'][^>]*>[\s\S]*?<a\b[^>]*href=["\']([^"\']+)["\'][^>]*>([^<]+)</a>', b, re.I)
                if not link_m:
                    continue
                video_url = self._absolute(link_m.group(1))
                raw_title = self._clean(link_m.group(2))
                translated = translate_cyrillic(raw_title)
                videos.append({"label": translated, "url": video_url, "thumb": self.icon, "info": {"title": translated, "plot": translated}})

        return videos

    def _extract_categories(self, html_content):
        categories = []
        seen = set()
        for m in re.finditer(r'<a\b[^>]*href=["\'](/categories/[^"\'/]+/)["\'][^>]*>([\s\S]*?)</a>', html_content or "", re.I):
            href = m.group(1)
            if href in seen or href == "/categories/":
                continue
            seen.add(href)
            raw_name = re.sub(r'<[^>]+>', ' ', m.group(2)).strip()
            if not raw_name:
                continue
            translated = translate_cyrillic(raw_name)
            cat_url = self._absolute(href)
            categories.append({"label": translated, "url": cat_url, "thumb": self.icon})
        return categories

    def _format_category_title(self, title):
        return translate_cyrillic(title)

    def resolve_recording_stream(self, url):
        html_content = self._get(url, referer=self.base_url)
        if not html_content:
            return None
        ifr_match = re.search(r'<iframe\b[^>]*src=["\']([^"\']+)["\']', html_content, re.I)
        if ifr_match:
            ifr_url = ifr_match.group(1)
            u_param = re.search(r'url=([^&]+)', ifr_url)
            if u_param:
                direct_url = urllib.parse.unquote(u_param.group(1))
                headers = self._headers(referer=url, accept="*/*")
                return {"url": direct_url, "headers": headers, "extension": "mp4"}
        return None
