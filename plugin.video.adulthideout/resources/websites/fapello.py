#!/usr/bin/env python
# -*- coding: utf-8 -*-

import html
import json
import re
import urllib.parse

from resources.lib.kvs_tube import KVSTubeWebsite
from resources.lib.resilient_http import fetch_text


class Fapello(KVSTubeWebsite):
    label = "Fapello"
    sort_options = ["Latest", "Popular Today", "Popular Week", "Popular All Time"]
    sort_paths = {
        "Latest": "/videos/",
        "Popular Today": "/popular_videos/day/",
        "Popular Week": "/popular_videos/week/",
        "Popular All Time": "/popular_videos/all_time/",
    }
    categories_path = None
    models_path = None
    video_path_markers = ("/video/new/",)

    def __init__(self, addon_handle, addon=None):
        super().__init__(
            name="fapello",
            base_url="https://fapello.com/",
            search_url="https://fapello.com/search_v2/?ajax=1&q={}&type=models&limit=4&offset=0",
            addon_handle=addon_handle,
            addon=addon,
        )

    def _get(self, url, referer=None, max_retries=None):
        content = fetch_text(
            url,
            headers=self._headers(referer),
            logger=self.logger,
            timeout=15,
            use_windows_curl_fallback=True,
        )
        if content:
            return content
        self.logger.error("Fapello failed to fetch %s", url)
        return ""

    def _is_top_listing(self, url):
        path = urllib.parse.urlparse(url or self.base_url).path.rstrip("/")
        return path == "/videos" or path.startswith("/popular_videos/")

    def get_page_url(self, base_url, page_num):
        if page_num <= 1:
            return base_url
        parsed = urllib.parse.urlparse(base_url)
        path = re.sub(r"/page-\d+/?$", "/", parsed.path)
        path = path.rstrip("/") + "/page-{}/".format(page_num)
        return urllib.parse.urlunparse(
            (parsed.scheme, parsed.netloc, path, parsed.params, parsed.query, parsed.fragment)
        )

    def _thumb_url(self, value):
        value = self._absolute(value)
        if not value or "|" in value:
            return value
        return "{}|{}".format(value, urllib.parse.urlencode({
            "User-Agent": self.ua,
            "Referer": self.base_url,
        }))

    def _extract_videos(self, html_content):
        videos = []
        seen = set()
        pattern = re.compile(
            r'<a\b[^>]+href=["\']([^"\']*/video/new/\d+/?)["\'][^>]*>\s*'
            r'<img\b[^>]+src=["\']([^"\']+)["\']',
            re.IGNORECASE,
        )
        matches = list(pattern.finditer(html_content or ""))
        for index, match in enumerate(matches):
            video_url = self._absolute(match.group(1))
            if not video_url or video_url in seen:
                continue
            seen.add(video_url)
            end = matches[index + 1].start() if index + 1 < len(matches) else match.start() + 5000
            block = (html_content or "")[match.start():min(end, match.start() + 5000)]
            thumb = self._thumb_url(match.group(2))

            model_match = re.search(
                r'<a\b[^>]+href=["\']https?://[^"\']+/([^/"\']+)/["\'][^>]*'
                r'class=["\'][^"\']*flex-1 items-center[^"\']*["\'][^>]*>'
                r'[\s\S]*?<div>\s*([^<]+?)\s*</div>',
                block,
                re.IGNORECASE,
            )
            if model_match:
                title = self._clean(model_match.group(2))
            else:
                slug_match = re.search(r"/content/[^/]+/[^/]+/([^/]+)/", thumb)
                title = (slug_match.group(1).replace("-", " ").title()
                         if slug_match else "Fapello Video")

            item_id = re.search(r"/video/new/(\d+)", video_url)
            label = "{} #{}".format(title, item_id.group(1)) if item_id else title
            videos.append({
                "label": label,
                "url": video_url,
                "thumb": thumb or self.icon,
                "info": {"title": label, "plot": title},
            })
        return videos

    def _extract_model_videos(self, html_content, model_name):
        videos = []
        seen = set()
        matches = list(re.finditer(
            r'<a\b[^>]+href=["\'](https?://[^"\']+/[^/"\']+/\d+/)["\'][^>]*>',
            html_content or "",
            re.IGNORECASE,
        ))
        for index, match in enumerate(matches):
            video_url = self._absolute(match.group(1))
            if video_url in seen:
                continue
            end = matches[index + 1].start() if index + 1 < len(matches) else match.start() + 1800
            block = (html_content or "")[match.start():min(end, match.start() + 1800)]
            if "icon-play.svg" not in block:
                continue
            thumb_match = re.search(
                r'<img\b[^>]+src=["\']([^"\']+_300px\.(?:jpg|jpeg|png))["\']',
                block,
                re.IGNORECASE,
            )
            if not thumb_match:
                continue
            seen.add(video_url)
            item_id = re.search(r"/(\d+)/?$", urllib.parse.urlparse(video_url).path)
            label = "{} #{}".format(model_name, item_id.group(1)) if item_id else model_name
            videos.append({
                "label": label,
                "url": video_url,
                "thumb": self._thumb_url(thumb_match.group(1)),
                "info": {"title": label, "plot": model_name},
            })
        return videos

    def search(self, query):
        if not query:
            return
        api_url = self.search_url.format(urllib.parse.quote_plus(query.strip()))
        payload = self._get(api_url, referer=self.base_url)
        try:
            response = json.loads(payload)
            results = response.get("results", {}) if isinstance(response, dict) else {}
            if isinstance(results, dict):
                models = results.get("models", [])
            elif isinstance(results, list):
                models = results
            else:
                models = []
        except (TypeError, ValueError):
            models = []

        context_menu = self._context_menu()
        found = 0
        seen = set()
        for model in models[:4]:
            model_url = self._absolute(model.get("url"))
            model_name = self._clean(model.get("name") or "")
            if not model_url or not model_name:
                continue
            model_html = self._get(model_url, referer=api_url)
            for item in self._extract_model_videos(model_html, model_name):
                if item["url"] in seen:
                    continue
                seen.add(item["url"])
                self.add_link(
                    item["label"], item["url"], 4, item["thumb"], self.fanart,
                    context_menu=context_menu, info_labels=item["info"],
                )
                found += 1
        if not found:
            self.notify_error("No Fapello videos found")
        self.end_directory("videos")

    def _extract_stream_url(self, html_content, referer=None):
        match = re.search(
            r'<meta\b[^>]+property=["\']og:video["\'][^>]+content=["\']([^"\']+)["\']',
            html_content or "",
            re.IGNORECASE,
        )
        if not match:
            match = re.search(r'"contentUrl"\s*:\s*"([^"]+)"', html_content or "", re.IGNORECASE)
        if match:
            return self._absolute(html.unescape(match.group(1)).replace("\\/", "/"))
        return super()._extract_stream_url(html_content, referer=referer)
