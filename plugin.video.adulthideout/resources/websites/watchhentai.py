#!/usr/bin/env python
# -*- coding: utf-8 -*-

import html
import re
import urllib.parse

from resources.lib.kvs_tube import KVSTubeWebsite
from resources.lib.thumb_proxy import build_thumb_url


class WatchHentai(KVSTubeWebsite):
    label = "WatchHentai"
    use_playback_proxy = True
    sort_options = ["Latest", "Most Viewed", "Top Rated"]
    sort_paths = {
        "Latest": "/videos/",
        "Most Viewed": "/videos/?order=views",
        "Top Rated": "/videos/?order=rating",
    }
    categories_path = "/genre/"
    models_path = None
    video_path_markers = ("/videos/",)
    category_path_markers = ("/genre/",)

    def __init__(self, addon_handle, addon=None):
        super().__init__(
            name="watchhentai",
            base_url="https://watchhentai.net/",
            search_url="https://watchhentai.net/?s={}&post_type=episodes",
            addon_handle=addon_handle,
            addon=addon,
        )

    def get_page_url(self, base_url, page_num):
        if page_num <= 1:
            return base_url
        parsed = urllib.parse.urlparse(base_url)
        path = re.sub(r"/page/\d+/?$", "/", parsed.path)
        path = path.rstrip("/") + "/page/{}/".format(page_num)
        return urllib.parse.urlunparse(
            (parsed.scheme, parsed.netloc, path, parsed.params, parsed.query, parsed.fragment)
        )

    def _is_top_listing(self, url):
        return urllib.parse.urlparse(url or self.base_url).path.rstrip("/") in ("", "/videos")

    def _extract_videos(self, html_content):
        videos = []
        seen = set()
        for block in re.findall(
            r'<article\b[^>]*class=["\'][^"\']*\bitem\b[^"\']*["\'][^>]*>[\s\S]{0,5000}?</article>',
            html_content or "",
            re.IGNORECASE,
        ):
            href = re.search(r'href=["\']([^"\']*/videos/[^"\']+/)["\']', block, re.IGNORECASE)
            if not href:
                continue
            video_url = self._absolute(href.group(1))
            if video_url in seen:
                continue
            img = re.search(r"<img\b[^>]*>", block, re.IGNORECASE)
            img_tag = img.group(0) if img else ""
            title = re.search(r'\s(?:alt|title)=["\']([^"\']+)["\']', img_tag, re.IGNORECASE)
            if not title:
                title = re.search(r"<h3\b[^>]*>([\s\S]*?)</h3>", block, re.IGNORECASE)
            clean_title = self._clean(title.group(1) if title else "")
            if not clean_title or any(term in clean_title.lower() for term in ("loli", "shota")):
                continue
            thumb = self._pick_thumb(img_tag)
            if thumb:
                thumb = build_thumb_url(thumb, referer=self.base_url)
            duration = re.search(r"\b(\d{1,2}:\d{2}(?::\d{2})?)\b", block)
            duration_text = duration.group(1) if duration else ""
            info = {"title": clean_title, "plot": clean_title}
            seconds = self.convert_duration(duration_text)
            if seconds:
                info["duration"] = seconds
            label = "{} [COLOR lime]({})[/COLOR]".format(clean_title, duration_text) if duration_text else clean_title
            seen.add(video_url)
            videos.append({"label": label, "url": video_url, "thumb": thumb or self.icon, "info": info})
        return videos

    def _extract_next_page(self, html_content, current_url, page):
        expected = self.get_page_url(current_url, page + 1)
        marker = "/page/{}/".format(page + 1)
        return expected if marker in (html_content or "") else None

    def _series_videos(self, content, referer):
        videos = []
        seen = set()
        series_urls = []
        for value in re.findall(r'href=["\']([^"\']*/series/[^"\']+/)["\']', content or "", re.IGNORECASE):
            target = self._absolute(value)
            if target not in series_urls:
                series_urls.append(target)
        for series_url in series_urls[:10]:
            series = self._get(series_url, referer=referer)
            poster = re.search(r'<meta\b[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)', series or "", re.IGNORECASE)
            thumb = self._absolute(poster.group(1)) if poster else self.icon
            if thumb != self.icon:
                thumb = build_thumb_url(thumb, referer=self.base_url)
            for href in re.findall(r'href=["\']([^"\']*/videos/[^"\']+/)["\']', series or "", re.IGNORECASE):
                video_url = self._absolute(href)
                if video_url in seen:
                    continue
                seen.add(video_url)
                slug = urllib.parse.urlparse(video_url).path.rstrip("/").rsplit("/", 1)[-1]
                title = self._clean(urllib.parse.unquote(slug).replace("-", " ").replace(" id 01", ""))
                if any(term in title.lower() for term in ("loli", "shota")):
                    continue
                videos.append({
                    "label": title,
                    "url": video_url,
                    "thumb": thumb,
                    "info": {"title": title, "plot": title},
                })
        return videos

    def process_content(self, url, page=1):
        if not url or url == "BOOTSTRAP":
            url, _ = self.get_start_url_and_label()
        context_menu = self._context_menu(url)
        if page == 1 and self._is_top_listing(url):
            self.add_dir("Search", "", 5, self.icons.get("search", self.icon), context_menu=context_menu)
            self.add_dir("Categories", self._absolute(self.categories_path), 8, self.icons.get("categories", self.icon), context_menu=context_menu)
        target_url = self.get_page_url(url, page)
        content = self._get(target_url)
        videos = self._extract_videos(content)
        if not videos:
            videos = self._series_videos(content, target_url)
        for item in videos:
            self.add_link(
                item["label"], item["url"], 4, item["thumb"], self.fanart,
                context_menu=context_menu, info_labels=item["info"],
            )
        if self._extract_next_page(content, target_url, page):
            self.add_dir("Next Page", url, 2, self.icons.get("default", self.icon), context_menu=context_menu, page=page + 1)
        if not videos:
            self.notify_error("No WatchHentai videos found")
        self.end_directory("videos")

    def process_categories(self, url):
        content = self._get(self.base_url)
        seen = set()
        for href, title in re.findall(
            r'<a\b[^>]+href=["\']([^"\']*/genre/[^"\']+/)["\'][^>]*>([^<]+)</a>',
            content or "",
            re.IGNORECASE,
        ):
            target = self._absolute(href)
            clean_title = self._clean(title)
            if target in seen or not clean_title or any(term in clean_title.lower() for term in ("loli", "shota")):
                continue
            seen.add(target)
            self.add_dir(clean_title, target, 2, self.icons.get("categories", self.icon), self.fanart)
        self.end_directory("videos")

    def _extract_stream_url(self, html_content, referer=None):
        match = re.search(
            r'<iframe\b[^>]+src=["\']([^"\']*/jwplayer/\?[^"\']*\bsource=[^"\']+)',
            html_content or "",
            re.IGNORECASE,
        )
        if not match:
            return None
        player_url = self._absolute(html.unescape(match.group(1)))
        player = self._get(player_url, referer=referer or self.base_url)
        candidates = []
        for stream in re.findall(r'https?[^"\'\\\s]+\.mp4(?:\?[^"\'\\\s<]+)?', player or "", re.IGNORECASE):
            stream = html.unescape(stream).replace("\\/", "/")
            if stream not in candidates:
                candidates.append(stream)

        query = urllib.parse.parse_qs(urllib.parse.urlparse(player_url).query)
        base_stream = urllib.parse.unquote((query.get("source") or [""])[0])
        if base_stream.startswith("http"):
            stem, suffix = (base_stream.rsplit(".mp4", 1) + [""])[:2]
            for quality in ("_1080p", "_720p", "_480p"):
                candidate = "{}{}.mp4{}".format(stem, quality, suffix)
                if candidate not in candidates:
                    candidates.append(candidate)
            if base_stream not in candidates:
                candidates.append(base_stream)

        def rank(value):
            match_quality = re.search(r"_(1080|720|480)p\.mp4", value, re.IGNORECASE)
            return int(match_quality.group(1)) if match_quality else 0

        for candidate in sorted(candidates, key=rank, reverse=True):
            if self._probe_stream(candidate, player_url):
                return candidate
        return None
