#!/usr/bin/env python
# -*- coding: utf-8 -*-

import html
import re
import urllib.parse

import xbmcgui
import xbmcplugin

from resources.lib.kvs_tube import KVSTubeWebsite
from resources.lib.thumb_proxy import build_thumb_url


class TheClassicPorn(KVSTubeWebsite):
    label = "The Classic Porn"
    sort_options = [
        "German Vintage",
        "Latest",
        "Most Popular",
        "Top Rated",
        "Longest",
        "Italian Classic",
        "French Classic",
    ]
    sort_paths = {
        "German Vintage": "/videos/languages/german/?sort_by=post_date",
        "Latest": "/videos/?sort_by=post_date",
        "Most Popular": "/videos/?sort_by=video_viewed",
        "Top Rated": "/videos/?sort_by=rating",
        "Longest": "/videos/?sort_by=duration",
        "Italian Classic": "/videos/languages/italian/?sort_by=post_date",
        "French Classic": "/videos/languages/french/?sort_by=post_date",
    }
    search_path = "/search/?q={}&sort_by=post_date"
    categories_path = "/"
    models_path = "/actors/categories/?sort_by=title"
    video_path_markers = ("/videos/",)
    category_path_markers = ("/videos/categories/", "/videos/languages/")
    use_playback_proxy = True

    LANGUAGE_SECTIONS = [
        ("German Vintage Movies", "https://theclassicporn.com/videos/languages/german/?sort_by=post_date"),
        ("Italian Classic Movies", "https://theclassicporn.com/videos/languages/italian/?sort_by=post_date"),
        ("French Classic Movies", "https://theclassicporn.com/videos/languages/french/?sort_by=post_date"),
        ("Spanish Classic Movies", "https://theclassicporn.com/videos/languages/spanish/?sort_by=post_date"),
        ("English Classic Movies", "https://theclassicporn.com/videos/languages/english/?sort_by=post_date"),
    ]

    def __init__(self, addon_handle, addon=None):
        super().__init__(
            name="theclassicporn",
            base_url="https://theclassicporn.com",
            search_url="https://theclassicporn.com/search/?q={}&sort_by=post_date",
            addon_handle=addon_handle,
            addon=addon,
        )

    def _is_video_href(self, href):
        if not href or "/categories/" in href or "sort_by=" in href or "/languages/" in href:
            return False
        return bool(re.search(r"/videos/\d+/[^/]+/?", href))

    def _extract_videos(self, html_content):
        videos = []
        seen = set()

        # Match video links with covers/thumbnails
        pattern = r'<a\b[^>]+href="(/videos/\d+/[^"]+/)"[^>]*title="([^"]+)"[^>]*>[\s\S]*?<img\b[^>]+src="([^"]+)"'
        for match in re.finditer(pattern, html_content or "", re.IGNORECASE):
            v_path = match.group(1)
            v_url = self._absolute(v_path)
            if v_url in seen:
                continue
            seen.add(v_url)

            title = html.unescape(match.group(2).strip())
            thumb = self._absolute(match.group(3).strip()) if match.group(3) else self.icon
            thumb = build_thumb_url(thumb, referer=self.base_url)

            info = {"title": title, "plot": title}
            videos.append({
                "label": title,
                "url": v_url,
                "thumb": thumb,
                "info": info,
            })

        # Fallback for featured film items
        if not videos:
            featured_pattern = r'<a\b[^>]+href="(/videos/\d+/[^"]+/)"[^>]*class="thumb-film-link"[^>]*>([\s\S]*?)</a>'
            for match in re.finditer(featured_pattern, html_content or "", re.IGNORECASE):
                v_path = match.group(1)
                v_url = self._absolute(v_path)
                if v_url in seen:
                    continue
                seen.add(v_url)

                img_src = match.group(2).strip()
                thumb = self._absolute(img_src) if img_src else self.icon
                thumb = build_thumb_url(thumb, referer=self.base_url)

                pos = match.start()
                surrounding = html_content[max(0, pos - 400):min(len(html_content), pos + 400)]
                t_match = re.search(r'class="link-blue">([^<]+)</a>', surrounding)
                title = html.unescape(t_match.group(1).strip()) if t_match else v_path.rstrip("/").split("/")[-1].replace("-", " ").title()

                info = {"title": title, "plot": title}
                videos.append({
                    "label": title,
                    "url": v_url,
                    "thumb": thumb,
                    "info": info,
                })

        return videos

    def _extract_next_page(self, html_content, current_url, page):
        next_match = re.search(r'href="([^"]+)"[^>]*>\s*(?:Next|»|&gt;&gt;)', html_content or "", re.IGNORECASE)
        if next_match:
            return self._absolute(next_match.group(1))

        # Direct pagination structure: /videos/{page}/?sort_by=... or /videos/languages/{lang}/{page}/?...
        next_page = page + 1
        candidate = re.sub(r'(/videos/(?:languages/[^/]+/)?)(?:\d+/)?(\?.*)?$', rf'\g<1>{next_page}/\g<2>', current_url)
        if candidate != current_url:
            return candidate

        return None

    def _extract_stream_url(self, html_content, referer=None):
        stream = super()._extract_stream_url(html_content, referer)
        if stream:
            return stream

        # Check video_url="..." or video_url='...' with equals sign
        match = re.search(r'video_url\s*[:=]\s*["\']([^"\']+)["\']', html_content or "", re.IGNORECASE)
        if match:
            return match.group(1)

        return None

    def process_categories(self, url):
        target_url = self.base_url + "/" if (not url or url == "CATEGORIES" or not url.startswith("http")) else url

        # 1. Add Language sections first
        for lang_label, lang_url in self.LANGUAGE_SECTIONS:
            self.add_dir(f"[COLOR gold]{lang_label}[/COLOR]", lang_url, 2, self.icons.get("categories", self.icon))

        # 2. Add regular categories from homepage (linear O(N) parsing)
        page_html = self._get(target_url)
        seen = set()
        for block in re.findall(r'<li\b[^>]*>[\s\S]{1,600}?</li>', page_html or "", re.IGNORECASE):
            cat_m = re.search(r'href="(/videos/categories/[^"]+)"', block)
            if not cat_m:
                continue
            cat_path = cat_m.group(1)
            name_m = re.search(r'class="category-name"[^>]*>.*?<span>(.*?)</span>', block, re.DOTALL)
            name = html.unescape(name_m.group(1).strip()) if name_m else cat_path.rstrip('/').split('/')[-1].replace('-', ' ').title()
            count_m = re.search(r'>([0-9,]+)</a>', block)
            count = count_m.group(1).strip() if count_m else ""
            display = f"{name} [COLOR gray]({count})[/COLOR]" if count else name
            cat_url = self._absolute(cat_path)
            if cat_url not in seen:
                seen.add(cat_url)
                self.add_dir(display, cat_url, 2, self.icons.get("categories", self.icon))

        self.end_directory("categories")
