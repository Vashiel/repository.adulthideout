#!/usr/bin/env python
# -*- coding: utf-8 -*-

import html
import re
import urllib.parse

from resources.lib.kvs_tube import KVSTubeWebsite


class HentaiCity(KVSTubeWebsite):
    label = "HentaiCity"
    use_playback_proxy = True
    sort_options = ["Most Recent", "Most Popular", "Most Viewed", "Top Rated", "Longest"]
    sort_paths = {
        "Most Recent": "/videos/straight/all-recent.html",
        "Most Popular": "/videos/straight/all-popular.html",
        "Most Viewed": "/videos/straight/all-view.html",
        "Top Rated": "/videos/straight/all-rate.html",
        "Longest": "/videos/straight/all-length.html",
    }
    categories_path = "/categories/"
    models_path = None
    video_path_markers = ("/video/",)
    category_path_markers = ("/videos/straight/",)

    def __init__(self, addon_handle, addon=None):
        super().__init__(
            name="hentaicity",
            base_url="https://www.hentaicity.com/",
            search_url="https://www.hentaicity.com/search/video/{}/",
            addon_handle=addon_handle,
            addon=addon,
        )

    def _is_top_listing(self, url):
        path = urllib.parse.urlparse(url or self.base_url).path
        return bool(re.match(r"^/videos/straight/all-(?:recent|popular|view|rate|length)\.html$", path))

    def get_page_url(self, base_url, page_num):
        if page_num <= 1:
            return base_url
        parsed = urllib.parse.urlparse(base_url)
        path = parsed.path
        if path.startswith("/search/"):
            path = re.sub(r"/\d+/?$", "/", path)
            path = path.rstrip("/") + "/{}/".format(page_num)
        else:
            path = re.sub(r"-\d+\.html$", ".html", path)
            path = re.sub(r"\.html$", "-{}.html".format(page_num), path)
        return urllib.parse.urlunparse(
            (parsed.scheme, parsed.netloc, path, parsed.params, parsed.query, parsed.fragment)
        )

    def _extract_videos(self, html_content):
        videos = []
        seen = set()
        pattern = re.compile(
            r'<a\b[^>]+href=["\']([^"\']*/(?:click/[^"\']+/)?video/[^"\']+\.html)["\']'
            r'[^>]*class=["\'][^"\']*\bthumb-img\b[^"\']*["\'][^>]*>([\s\S]{0,1800}?)</a>',
            re.IGNORECASE,
        )
        for href, body in pattern.findall(html_content or ""):
            path = urllib.parse.urlparse(self._absolute(href)).path
            path = re.sub(r"^/click/[^/]+", "", path)
            video_url = self._absolute(path)
            if video_url in seen:
                continue
            img_match = re.search(r"<img\b[^>]*>", body, re.IGNORECASE)
            img_tag = img_match.group(0) if img_match else ""
            title_match = re.search(r'\s(?:alt|title)=["\']([^"\']+)["\']', img_tag, re.IGNORECASE)
            title = self._clean(title_match.group(1) if title_match else "")
            if not title:
                continue
            thumb = self._pick_thumb(img_tag)
            duration_match = re.search(
                r'class=["\'][^"\']*\btime\b[^"\']*["\'][^>]*>([^<]+)',
                body,
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
        match = re.search(
            r'<a\b[^>]+href=["\']([^"\']+)["\'][^>]*class=["\'][^"\']*\bnext\b[^"\']*["\'][^>]*>'
            r'\s*Next[\s\S]{0,300}?</a>',
            html_content or "",
            re.IGNORECASE,
        )
        return self._absolute(match.group(1)) if match else None

    def process_categories(self, url):
        html_content = self._get(url or self._absolute(self.categories_path))
        seen = set()
        for href, body in re.findall(
            r'<a\b[^>]+href=["\']([^"\']*/videos/straight/[^"\']+-popular\.html)["\']'
            r'[^>]*class=["\'][^"\']*\bthumb-img\b[^"\']*["\'][^>]*>([\s\S]{0,1000}?)</a>',
            html_content or "",
            re.IGNORECASE,
        ):
            target = self._absolute(href)
            if target in seen:
                continue
            img_match = re.search(r"<img\b[^>]*>", body, re.IGNORECASE)
            img_tag = img_match.group(0) if img_match else ""
            title_match = re.search(r'\s(?:alt|title)=["\']([^"\']+)["\']', img_tag, re.IGNORECASE)
            title = self._clean(title_match.group(1) if title_match else "")
            if not title or any(term in title.lower() for term in ("shota", "loli")):
                continue
            seen.add(target)
            self.add_dir(title, target, 2, self._pick_thumb(img_tag) or self.icons.get("categories", self.icon), self.fanart)
        self.end_directory("videos")

    def search(self, query):
        if query:
            slug = urllib.parse.quote_plus(query.strip().replace(" ", "-"))
            self.process_content(self.search_url.format(slug))

    def _extract_stream_url(self, html_content, referer=None):
        mp4_match = re.search(
            r'https://[^"\'\s]+/mobile\.mp4[^"\'\s<]*',
            html_content or "",
            re.IGNORECASE,
        )
        if mp4_match:
            return html.unescape(mp4_match.group(0)).replace("\\/", "/")
        hls_match = re.search(
            r'https://[^"\'\s]+/master\.m3u8[^"\'\s<]*',
            html_content or "",
            re.IGNORECASE,
        )
        return html.unescape(hls_match.group(0)).replace("\\/", "/") if hls_match else None

    def resolve_recording_stream(self, url):
        html_content = self._get(url, referer=self.base_url)
        stream_url = self._extract_stream_url(html_content, referer=url)
        if not stream_url:
            return None
        extension = "m3u8" if ".m3u8" in stream_url else "mp4"
        return {"url": stream_url, "headers": self._headers(url, accept="*/*"), "extension": extension}

    def play_video(self, url):
        super().play_video(url)
