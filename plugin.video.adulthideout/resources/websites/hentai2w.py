#!/usr/bin/env python
# -*- coding: utf-8 -*-

import re
import urllib.parse

from resources.lib.kvs_tube import KVSTubeWebsite


class Hentai2W(KVSTubeWebsite):
    label = "Hentai2W"
    use_playback_proxy = True
    sort_options = ["Most Recent", "Most Viewed", "Top Rated", "Longest"]
    sort_paths = {
        "Most Recent": "/videos/",
        "Most Viewed": "/most-viewed/",
        "Top Rated": "/top-rated/",
        "Longest": "/longest/",
    }
    categories_path = "/channels/"
    models_path = None
    video_path_markers = ("/video/",)
    category_path_markers = ("/channels/",)

    def __init__(self, addon_handle, addon=None):
        super().__init__(
            name="hentai2w",
            base_url="https://hentai2w.com/",
            search_url="https://hentai2w.com/search/{}/",
            addon_handle=addon_handle,
            addon=addon,
        )

    def _is_top_listing(self, url):
        return urllib.parse.urlparse(url or self.base_url).path.rstrip("/") in (
            "", "/videos", "/most-viewed", "/top-rated", "/longest"
        )

    def get_page_url(self, base_url, page_num):
        if page_num <= 1:
            return base_url
        parsed = urllib.parse.urlparse(base_url)
        path = re.sub(r"/page\d+\.html$", "/", parsed.path)
        path = path.rstrip("/") + "/page{}.html".format(page_num)
        return urllib.parse.urlunparse(
            (parsed.scheme, parsed.netloc, path, parsed.params, parsed.query, parsed.fragment)
        )

    def _extract_videos(self, html_content):
        videos = []
        seen = set()
        for block in re.findall(
            r'<div\b[^>]+class=["\'][^"\']*\bitem-col\b[^"\']*-video[^"\']*["\'][^>]*>'
            r'[\s\S]{0,5000}?<!--\s*item END\s*-->',
            html_content or "",
            re.IGNORECASE,
        ):
            href_match = re.search(
                r'<a\b[^>]+href=["\']([^"\']*/video/[^"\']+\.html)["\'][^>]*'
                r'title=["\']([^"\']+)["\']',
                block,
                re.IGNORECASE,
            )
            if not href_match:
                continue
            video_url = self._absolute(href_match.group(1))
            title = self._clean(href_match.group(2))
            if not video_url or video_url in seen or not title:
                continue
            img_match = re.search(r"<img\b[^>]*>", block, re.IGNORECASE)
            thumb = self._pick_thumb(img_match.group(0) if img_match else "")
            duration_match = re.search(
                r'class=["\'][^"\']*\bitem-time\b[^"\']*["\'][^>]*>([^<]+)',
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
        filename = urllib.parse.urlparse(expected).path.rsplit("/", 1)[-1]
        if re.search(r'(?:rel=["\']next["\'][^>]+href|href)=["\'][^"\']*{}["\']'.format(
                re.escape(filename)), html_content or "", re.IGNORECASE):
            return expected
        return None

    def process_categories(self, url):
        current_url = url or self._absolute(self.categories_path)
        html_content = self._get(current_url)
        seen = set()
        for block in re.findall(
            r'<div\b[^>]+class=["\'][^"\']*\bitem-col\b[^"\']*-channel[^"\']*["\'][^>]*>'
            r'[\s\S]{0,2600}?<!--\s*item END\s*-->',
            html_content or "",
            re.IGNORECASE,
        ):
            match = re.search(
                r'<a\b[^>]+href=["\']([^"\']*/channels/\d+/[^"\']+/)["\'][^>]*'
                r'title=["\']([^"\']+)["\']',
                block,
                re.IGNORECASE,
            )
            if not match:
                continue
            target = self._absolute(match.group(1))
            title = self._clean(match.group(2))
            if target in seen or not title or any(term in title.lower() for term in ("shota", "loli")):
                continue
            img_match = re.search(r"<img\b[^>]*>", block, re.IGNORECASE)
            thumb = self._pick_thumb(img_match.group(0) if img_match else "")
            seen.add(target)
            self.add_dir(title, target, 2, thumb or self.icons.get("categories", self.icon), self.fanart)
        self.end_directory("videos")

    def search(self, query):
        if query:
            slug = urllib.parse.quote_plus(query.strip().replace(" ", "-"))
            self.process_content(self._absolute("/search/{}/".format(slug)))
