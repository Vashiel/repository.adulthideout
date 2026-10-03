#!/usr/bin/env python
# -*- coding: utf-8 -*-

import html
import os
import re
import urllib.parse

from resources.lib.cyrillic_utils import translate_cyrillic
from resources.lib.kvs_tube import KVSTubeWebsite
from resources.lib.thumb_proxy import build_thumb_url


class Pezdwood(KVSTubeWebsite):
    label = "Pezdwood"
    sort_options = ["Latest"]
    sort_paths = {"Latest": "/"}
    categories_path = "CATEGORIES"
    video_path_markers = (".html",)
    use_playback_proxy = True
    use_urllib_proxy = True

    FEATURED_CATEGORIES = [
        ("Русское порно", "https://pezdwood.com/russkoe-porno/"),
        ("Зрелые тетки", "https://pezdwood.com/porno-zrelyh-zhenschin/"),
        ("Большие жопы", "https://pezdwood.com/bolshie-zhopy/"),
        ("Соседка", "https://pezdwood.com/sosedka/"),
        ("Милф", "https://pezdwood.com/milf/"),
        ("Молодые", "https://pezdwood.com/molodye/"),
        ("Русские мамки", "https://pezdwood.com/russkie-mamki/"),
        ("Муж с женой", "https://pezdwood.com/muzh-s-zhenoy/"),
        ("На природе", "https://pezdwood.com/porno-na-prirode/"),
        ("От первого лица", "https://pezdwood.com/pov-otlica/"),
        ("Классный сюжет", "https://pezdwood.com/sjuzhetnyj-porn/"),
        ("Красивая грудь", "https://pezdwood.com/krasivaya-grud/"),
        ("Сочные попки", "https://pezdwood.com/krasivye-popki/"),
        ("HD порно", "https://pezdwood.com/full-hd-porn/"),
        ("Пышки", "https://pezdwood.com/pywechki/"),
        ("Толстушки", "https://pezdwood.com/pyshki/"),
        ("Отчим", "https://pezdwood.com/motchim/"),
        ("Долги и развод", "https://pezdwood.com/dolgi-i-razvod/"),
        ("Страстный секс", "https://pezdwood.com/strastnyy-seks/"),
        ("Испанки", "https://pezdwood.com/ispanki/"),
    ]

    def __init__(self, addon_handle, addon=None):
        super().__init__(
            name="pezdwood",
            base_url="https://pezdwood.com/",
            search_url="https://pezdwood.com/index.php?do=search&subaction=search&story={}",
            addon_handle=addon_handle,
            addon=addon,
        )
        self.icon = os.path.join(self.addon.getAddonInfo("path"), "resources", "logos", "pezdwood.png")
        self.icons["default"] = self.icon

    def _is_video_href(self, href):
        return bool(href and re.search(r'/\d+-[^/]+\.html$', href))

    def _pick_thumb(self, img_tag):
        match = re.search(r'\s(?:data-src|data-original|data-webp)=["\']([^"\']+)', img_tag or "", re.IGNORECASE)
        if not match:
            match = re.search(r'\ssrc=["\']([^"\']+)', img_tag or "", re.IGNORECASE)
        thumb = self._absolute(match.group(1)) if match else ""
        if "no-img.png" in thumb or thumb.startswith("data:"):
            return ""
        return build_thumb_url(thumb, referer=self.base_url) if thumb else thumb

    def get_page_url(self, url, page):
        if page <= 1:
            return url
        parsed = urllib.parse.urlparse(url)
        path = parsed.path.rstrip("/")
        if re.search(r"/page/\d+$", path):
            path = re.sub(r"/page/\d+$", f"/page/{page}/", path)
        else:
            path = f"{path}/page/{page}/"
        return urllib.parse.urlunparse((parsed.scheme, parsed.netloc, path, parsed.params, parsed.query, parsed.fragment))

    def _extract_next_page(self, html_content, current_url, page):
        next_page = page + 1
        if f"/page/{next_page}/" in (html_content or ""):
            return self.get_page_url(current_url, next_page)
        return None

    def _extract_videos(self, html_content):
        videos = []
        for block in re.finditer(r'<a\b[^>]*class=["\'][^"\']*\bthumb\b[^"\']*["\'][^>]*href=["\'](https://pezdwood\.com/\d+-[^"\']+\.html)["\']([\s\S]*?)(?=<a\b[^>]*class=["\'][^"\']*\bthumb\b|\Z)', html_content or "", re.I):
            video_url = block.group(1)
            b = block.group(2)

            img_m = re.search(r'<img\b[^>]*>', b, re.I)
            img_tag = img_m.group(0) if img_m else ""
            thumb = self._pick_thumb(img_tag)

            title_m = re.search(r'<h3\b[^>]*class=["\']thumb__title[^"\']*["\'][^>]*>([^<]+)<', b, re.I)
            if not title_m:
                title_m = re.search(r'\salt=["\']([^"\']+)["\']', img_tag, re.I)
            raw_title = self._clean(title_m.group(1) if title_m else "")
            if not raw_title:
                continue

            dur_m = re.search(r'class=["\'][^"\']*thumb__time[^"\']*["\'][^>]*>([^<]+)<', b, re.I)
            duration = dur_m.group(1).strip() if dur_m else ""

            translated = translate_cyrillic(raw_title)
            label = f"{translated} [COLOR lime]({duration})[/COLOR]" if duration else translated
            info = {"title": translated, "plot": translated}
            seconds = self.convert_duration(duration)
            if seconds:
                info["duration"] = seconds
            videos.append({"label": label, "url": video_url, "thumb": thumb or self.icon, "info": info})
        return videos

    def process_categories(self, url):
        context_menu = self._context_menu(self.base_url)
        for name, cat_url in self.FEATURED_CATEGORIES:
            translated = translate_cyrillic(name)
            self.add_dir(translated, cat_url, 2, self.icons.get("categories", self.icon), context_menu=context_menu)
        self.end_directory("categories")

    def resolve_recording_stream(self, url):
        html_content = self._get(url, referer=self.base_url)
        if not html_content:
            return None
        file_match = re.search(r'file:\s*["\']([^"\']+)["\']', html_content)
        if file_match:
            stream_url = file_match.group(1).strip()
            if stream_url.startswith("//"):
                stream_url = "https:" + stream_url
            headers = self._headers(referer="https://pezdwood.com/", accept="*/*")
            return {"url": stream_url, "headers": headers, "extension": "mp4"}
        return None
