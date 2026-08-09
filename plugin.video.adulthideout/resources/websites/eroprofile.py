#!/usr/bin/env python
# -*- coding: utf-8 -*-

import html
import os
import re
import sys
import urllib.parse

from resources.lib.kvs_tube import KVSTubeWebsite


vendor_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "lib", "vendor")
if os.path.isdir(vendor_path) and vendor_path not in sys.path:
    sys.path.insert(0, vendor_path)

try:
    import cloudscraper
except Exception:
    cloudscraper = None


class EroProfile(KVSTubeWebsite):
    label = "EroProfile"
    video_path_markers = ("/m/videos/view/",)
    sort_options = ["Latest", "Popular"]
    sort_paths = {
        "Latest": "/m/videos/home",
        "Popular": "/m/videos/popular",
    }
    categories_path = "/m/videos/home"
    models_path = None
    use_playback_proxy = False

    def __init__(self, addon_handle, addon=None):
        super().__init__(
            name="eroprofile",
            base_url="https://www.eroprofile.com/",
            search_url="https://www.eroprofile.com/m/videos/search?text={}",
            addon_handle=addon_handle,
            addon=addon,
        )
        if cloudscraper:
            try:
                self.session = cloudscraper.create_scraper(browser={"custom": self.ua})
            except Exception as exc:
                self.logger.warning("EroProfile cloudscraper init failed: %s", exc)

    def get_page_url(self, base_url, page_num):
        parsed = urllib.parse.urlparse(base_url)
        query = urllib.parse.parse_qs(parsed.query, keep_blank_values=True)
        if page_num > 1:
            query["pnum"] = [str(page_num)]
        else:
            query.pop("pnum", None)
        return urllib.parse.urlunparse(
            (parsed.scheme, parsed.netloc, parsed.path, parsed.params, urllib.parse.urlencode(query, doseq=True), parsed.fragment)
        )

    def _extract_videos(self, html_content):
        videos = []
        seen = set()
        blocks = re.split(r'(?=<div\b[^>]+class=["\'][^"\']*grid-tile-video)', html_content or "", flags=re.IGNORECASE)
        for block in blocks:
            match = re.search(r'<a\b[^>]+href=["\']([^"\']*/m/videos/view/[^"\']+)["\'][^>]*>([\s\S]{0,1200}?)</a>', block, re.IGNORECASE)
            if not match:
                continue
            video_url = self._absolute(match.group(1))
            if video_url in seen:
                continue
            seen.add(video_url)
            body = match.group(2)
            image_match = re.search(r'<img\b[^>]*\bdata-src=["\']([^"\']+)["\'][^>]*', body, re.IGNORECASE)
            title_match = re.search(r'<img\b[^>]*\balt=["\']([^"\']+)', body, re.IGNORECASE)
            if not title_match:
                title_match = re.search(r'<div\b[^>]*class=["\'][^"\']*title[^"\']*["\'][^>]*>([\s\S]*?)</div>', block, re.IGNORECASE)
            duration_match = re.search(r'<div\b[^>]*class=["\'][^"\']*duration[^"\']*["\'][^>]*>([^<]+)', body, re.IGNORECASE)
            title = self._clean(title_match.group(1) if title_match else "")
            duration = self._clean(duration_match.group(1) if duration_match else "")
            if not title:
                continue
            seconds = self.convert_duration(duration)
            info = {"title": title, "plot": title}
            if seconds:
                info["duration"] = seconds
            label = "{} [COLOR lime]({})[/COLOR]".format(title, duration) if duration else title
            videos.append({
                "label": label,
                "url": video_url,
                "thumb": self._absolute(html.unescape(image_match.group(1))) if image_match else self.icon,
                "info": info,
            })
        return videos

    def _extract_next_page(self, html_content, current_url, page):
        next_page = page + 1
        if re.search(r'href=["\'][^"\']*(?:[?&]|&amp;)pnum={}(?:[&"\'])'.format(next_page), html_content or "", re.IGNORECASE):
            return self.get_page_url(current_url, next_page)
        return None

    def process_categories(self, url):
        html_content = self._get(self._absolute("/m/videos/home"))
        if not html_content:
            self.notify_error("Could not load EroProfile categories")
            return self.end_directory("videos")
        seen = set()
        for match in re.finditer(r'<a\b[^>]*href=["\']([^"\']*/m/videos/search\?niche=\d+)["\'][^>]*>([^<]+)</a>', html_content, re.IGNORECASE):
            category_url = self._absolute(html.unescape(match.group(1)))
            title = self._clean(match.group(2))
            if category_url in seen or not title:
                continue
            seen.add(category_url)
            self.add_dir(title, category_url, 2, self.icons.get("categories", self.icon), self.fanart)
        self.end_directory("videos")

    def _extract_stream_url(self, html_content, referer=None):
        match = re.search(r'<source\b[^>]*\bsrc=["\']([^"\']+\.(?:m4v|mp4)(?:\?[^"\']*)?)["\']', html_content or "", re.IGNORECASE)
        return self._absolute(html.unescape(match.group(1))) if match else None
