#!/usr/bin/env python
# -*- coding: utf-8 -*-

import html
import json
import re
import urllib.parse

from resources.lib.kvs_tube import KVSTubeWebsite


class Javtiful(KVSTubeWebsite):
    label = "JAVtiful"
    use_playback_proxy = True
    sort_options = ["Latest", "Popular This Week", "Popular Today", "Most Viewed"]
    sort_paths = {
        "Latest": "/videos",
        "Popular This Week": "/videos?sort=popular_week",
        "Popular Today": "/videos?sort=popular_today",
        "Most Viewed": "/videos?sort=most_viewed",
    }
    categories_path = "/categories"
    models_path = "/actresses"
    channels_path = "/channels"
    video_path_markers = ("/video/",)

    def __init__(self, addon_handle, addon=None):
        super().__init__(
            name="javtiful",
            base_url="https://javtiful.com/",
            search_url="https://javtiful.com/search?q={}",
            addon_handle=addon_handle,
            addon=addon,
        )

    def _is_top_listing(self, url):
        return urllib.parse.urlparse(url or self.base_url).path.rstrip("/") in ("", "/main", "/videos")

    def get_page_url(self, base_url, page_num):
        if page_num <= 1:
            return base_url
        parsed = urllib.parse.urlparse(base_url)
        query = urllib.parse.parse_qs(parsed.query)
        query["page"] = [str(page_num)]
        return urllib.parse.urlunparse((
            parsed.scheme, parsed.netloc, parsed.path, parsed.params,
            urllib.parse.urlencode(query, doseq=True), parsed.fragment,
        ))

    def _extract_videos(self, html_content):
        videos = []
        seen = set()
        for block in re.findall(
            r'<article\b[^>]+class=["\'][^"\']*\bfront-video-card\b(?![^"\']*\bfront-partner-card\b)'
            r'[^"\']*["\'][^>]*>[\s\S]{0,8000}?</article>',
            html_content or "",
            re.IGNORECASE,
        ):
            href_match = re.search(
                r'<a\b[^>]+href=["\']([^"\']*/video/\d+/[^"\']+)["\'][^>]*'
                r'class=["\'][^"\']*\bfront-video-title\b',
                block,
                re.IGNORECASE,
            )
            if not href_match:
                href_match = re.search(r'href=["\']([^"\']*/video/\d+/[^"\']+)["\']', block, re.IGNORECASE)
            if not href_match:
                continue
            video_url = self._absolute(href_match.group(1))
            if video_url in seen:
                continue

            title_match = re.search(
                r'<a\b[^>]+class=["\'][^"\']*\bfront-video-title\b[^"\']*["\'][^>]*>'
                r'([\s\S]*?)</a>',
                block,
                re.IGNORECASE,
            )
            title = self._clean(title_match.group(1) if title_match else "")
            if not title:
                continue

            img_match = re.search(r"<img\b[^>]*>", block, re.IGNORECASE)
            img_tag = img_match.group(0) if img_match else ""
            thumb = ""
            for attr in ("data-front-lazy-src", "data-src", "src"):
                value = re.search(r'\s{}=["\']([^"\']+)["\']'.format(attr), img_tag, re.IGNORECASE)
                if value:
                    thumb = self._absolute(value.group(1))
                    if "placeholder" not in thumb:
                        break

            duration_match = re.search(
                r'class=["\'][^"\']*\bfront-duration-tag\b[^"\']*["\'][^>]*>([^<]+)',
                block,
                re.IGNORECASE,
            )
            duration = self._clean(duration_match.group(1) if duration_match else "")
            seconds = self.convert_duration(duration)
            label = "{} [COLOR lime]({})[/COLOR]".format(title, duration) if duration else title
            info = {"title": title, "plot": title}
            if seconds:
                info["duration"] = seconds
            seen.add(video_url)
            videos.append({"label": label, "url": video_url, "thumb": thumb or self.icon, "info": info})
        return videos

    def _extract_next_page(self, html_content, current_url, page):
        expected = self.get_page_url(current_url, page + 1)
        expected_query = urllib.parse.urlparse(expected).query
        if re.search(
            r'href=["\'][^"\']*{}[^"\']*["\'][^>]*>\s*(?:{}|Next)\s*</a>'.format(
                re.escape(expected_query), page + 1
            ),
            html_content or "",
            re.IGNORECASE,
        ):
            return expected
        return None

    def process_content(self, url, page=1):
        if not url or url == "BOOTSTRAP":
            url, _ = self.get_start_url_and_label()
        context_menu = self._context_menu(url)
        if page == 1 and self._is_top_listing(url):
            self.add_dir("Search", "", 5, self.icons.get("search", self.icon), context_menu=context_menu)
            self.add_dir("Categories", self._absolute(self.categories_path), 8, self.icons.get("categories", self.icon), context_menu=context_menu)
            self.add_dir("Actresses", self._absolute(self.models_path), 9, self.icons.get("pornstars", self.icon), context_menu=context_menu)
            self.add_dir("Channels", self._absolute(self.channels_path), 10, self.icons.get("categories", self.icon), context_menu=context_menu)

        target_url = self.get_page_url(url, page)
        html_content = self._get(target_url)
        videos = self._extract_videos(html_content)
        if not videos:
            self.notify_error("No JAVtiful videos found")
            return self.end_directory("videos")
        for item in videos:
            self.add_link(item["label"], item["url"], 4, item["thumb"], self.fanart, context_menu=context_menu, info_labels=item["info"])
        if self._extract_next_page(html_content, target_url, page):
            self.add_dir("Next Page", url, 2, self.icons.get("default", self.icon), context_menu=context_menu, page=page + 1)
        self.end_directory("videos")

    def _process_directory(self, url, path_marker, mode, icon_key):
        current_url = url or self.base_url
        html_content = self._get(current_url)
        seen = set()
        for anchor in re.findall(
            r'<a\b[^>]+href=["\']([^"\']*{}[^"\']*)["\'][^>]*>([\s\S]{{0,2600}}?)</a>'.format(
                re.escape(path_marker)
            ),
            html_content or "",
            re.IGNORECASE,
        ):
            href, body = anchor
            if not re.search(r"<img\b", body, re.IGNORECASE):
                continue
            target = self._absolute(href)
            if target in seen:
                continue
            img_match = re.search(r"<img\b[^>]*>", body, re.IGNORECASE)
            img_tag = img_match.group(0) if img_match else ""
            title_match = re.search(r'\s(?:alt|title)=["\']([^"\']+)["\']', img_tag, re.IGNORECASE)
            title = self._clean(title_match.group(1) if title_match else body)
            title = re.sub(r"^(?:Thumbnail|Avatar|Logo)\s+(?:for\s+)?", "", title, flags=re.IGNORECASE)
            if not title:
                continue
            thumb = ""
            for attr in ("data-front-lazy-src", "data-src", "src"):
                value = re.search(r'\s{}=["\']([^"\']+)["\']'.format(attr), img_tag, re.IGNORECASE)
                if value:
                    thumb = self._absolute(value.group(1))
                    if "placeholder" not in thumb:
                        break
            seen.add(target)
            self.add_dir(title, target, 2, thumb or self.icons.get(icon_key, self.icon), self.fanart)

        next_match = re.search(
            r'<a\b[^>]+href=["\']([^"\']+)["\'][^>]*class=["\'][^"\']*front-pagination-link'
            r'[^"\']*["\'][^>]*>\s*Next\s*</a>',
            html_content or "",
            re.IGNORECASE,
        )
        if next_match:
            self.add_dir("Next Page", self._absolute(next_match.group(1)), mode, self.icons.get("default", self.icon), self.fanart)
        self.end_directory("videos")

    def process_categories(self, url):
        self._process_directory(url or self._absolute(self.categories_path), "/category/", 8, "categories")

    def process_pornstars(self, url):
        self._process_directory(url or self._absolute(self.models_path), "/actress/", 9, "pornstars")

    def process_channels(self, url):
        self._process_directory(url or self._absolute(self.channels_path), "/channel/", 10, "categories")

    def _extract_stream_url(self, html_content, referer=None):
        sources = []
        match = re.search(r'"playerSources"\s*:\s*(\[[\s\S]*?\])\s*,\s*"videoTitle"', html_content or "")
        if match:
            try:
                for source in json.loads(match.group(1)):
                    stream = html.unescape(source.get("src") or "").replace("\\/", "/")
                    if stream.startswith("http"):
                        sources.append((int(source.get("size") or 0), stream))
            except (TypeError, ValueError):
                pass
        if not sources:
            for stream in re.findall(r'<source\b[^>]+src=["\']([^"\']+)["\']', html_content or "", re.IGNORECASE):
                stream = html.unescape(stream).replace("\\/", "/")
                if stream.startswith("http"):
                    sources.append((0, stream))
        for _, stream in sorted(sources, reverse=True):
            if self._probe_stream(stream, referer or self.base_url):
                return stream
        return sources[0][1] if sources else None
