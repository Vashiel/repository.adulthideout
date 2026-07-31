# -*- coding: utf-8 -*-
import html
import os
import re
import urllib.parse

import requests
import xbmcgui
import xbmcplugin

from resources.lib.base_website import BaseWebsite


class WordPressApiTube(BaseWebsite):
    """Small reusable WordPress REST listing engine for first-party tube sites."""

    POSTS_PER_PAGE = 24

    def __init__(self, name, label, base_url, addon_handle, addon=None):
        super().__init__(name, base_url, base_url + "?s={}", addon_handle, addon)
        self.label = label
        self.session = requests.Session()
        self.ua = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/128.0.0.0 Safari/537.36"
        )
        self.icon = os.path.join(
            self.addon.getAddonInfo("path"), "resources", "logos", name + ".png"
        )
        self.icons["default"] = self.icon

    def _headers(self, referer=None, accept=None):
        return {
            "User-Agent": self.ua,
            "Referer": referer or self.base_url,
            "Accept": accept or "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "identity",
        }

    def _get(self, url, referer=None):
        try:
            response = self.session.get(url, headers=self._headers(referer), timeout=20)
            if response.status_code == 200:
                return response.text
            self.logger.warning("[%s] HTTP %s for %s", self.name, response.status_code, url)
        except Exception as exc:
            self.logger.warning("[%s] Request failed for %s: %s", self.name, url, exc)
        return ""

    def _get_json(self, url, referer=None):
        try:
            response = self.session.get(url, headers=self._headers(referer), timeout=25)
            if response.status_code == 200:
                return response.json(), response.headers
            self.logger.warning("[%s] API HTTP %s for %s", self.name, response.status_code, url)
        except Exception as exc:
            self.logger.warning("[%s] API request failed for %s: %s", self.name, url, exc)
        return None, {}

    def _clean(self, value):
        value = re.sub(r"<[^>]+>", " ", value or "")
        return re.sub(r"\s+", " ", html.unescape(value)).strip()

    def _absolute(self, value, base=None):
        return urllib.parse.urljoin(base or self.base_url, html.unescape(value or "").strip())

    def get_start_url_and_label(self):
        return self.base_url, self.label

    def _post_api_url(self, url, page):
        parsed = urllib.parse.urlparse(url or self.base_url)
        query = urllib.parse.parse_qs(parsed.query)
        params = {
            "per_page": str(self.POSTS_PER_PAGE),
            "page": str(max(1, int(page))),
            "_embed": "wp:featuredmedia",
            "orderby": "date",
            "order": "desc",
        }
        if query.get("s"):
            params["search"] = query["s"][0]
        if query.get("ah_category"):
            params["categories"] = query["ah_category"][0]
        if query.get("ah_tag"):
            params["tags"] = query["ah_tag"][0]
        return self._absolute("wp-json/wp/v2/posts?" + urllib.parse.urlencode(params))

    def _thumbnail(self, post):
        media = ((post.get("_embedded") or {}).get("wp:featuredmedia") or [])
        if not media:
            return self.icon
        item = media[0] or {}
        sizes = ((item.get("media_details") or {}).get("sizes") or {})
        for key in ("medium_large", "large", "medium", "post-thumbnail"):
            if (sizes.get(key) or {}).get("source_url"):
                return self._absolute(sizes[key]["source_url"])
        return self._absolute(item.get("source_url")) or self.icon

    def _video_items(self, posts):
        items = []
        for post in posts or []:
            title = self._clean((post.get("title") or {}).get("rendered"))
            url = self._absolute(post.get("link"))
            if not title or not url:
                continue
            items.append({
                "title": title,
                "url": url,
                "thumb": self._thumbnail(post),
                "info": {
                    "title": title,
                    "plot": self._clean((post.get("excerpt") or {}).get("rendered")) or title,
                },
            })
        return items

    def process_content(self, url, page=1):
        url = self.base_url if not url or url == "BOOTSTRAP" else url
        posts, headers = self._get_json(self._post_api_url(url, page), referer=self.base_url)
        if posts is None:
            self.notify_error("Could not load {} content".format(self.label))
            self.end_directory("videos")
            return

        if self.is_primary_listing_url(url):
            self.add_dir("Search", "", 5, self.icons.get("search", self.icon))
            self.add_dir("Categories", "WP_CATEGORIES", 8, self.icons.get("categories", self.icon))
            if getattr(self, "show_pornstars", False):
                self.add_dir("Pornstars", "WP_TAGS", 9, self.icons.get("pornstars", self.icon))

        items = self._video_items(posts)
        for item in items:
            self.add_link(
                item["title"], item["url"], 4, item["thumb"], self.fanart,
                info_labels=item["info"],
            )

        try:
            total_pages = int(headers.get("X-WP-TotalPages") or 0)
        except (TypeError, ValueError):
            total_pages = 0
        if items and page < total_pages:
            self.add_dir("Next Page", url, 2, self.icons.get("default", self.icon), page=page + 1)
        self.end_directory("videos")

    def _taxonomy_page(self, taxonomy, url, mode, icon):
        page = 1
        if url and url not in ("WP_CATEGORIES", "WP_TAGS"):
            try:
                page = max(1, int(urllib.parse.parse_qs(urllib.parse.urlparse(url).query).get("page", [1])[0]))
            except (TypeError, ValueError):
                page = 1
        params = {"per_page": "100", "page": str(page), "orderby": "count", "order": "desc", "hide_empty": "true"}
        data, headers = self._get_json(
            self._absolute("wp-json/wp/v2/{}?{}".format(taxonomy, urllib.parse.urlencode(params))),
            referer=self.base_url,
        )
        if data is None:
            self.notify_error("Could not load {} directory".format(self.label))
            self.end_directory("videos")
            return
        key = "ah_category" if taxonomy == "categories" else "ah_tag"
        for entry in data:
            name = self._clean(entry.get("name"))
            if name and name.lower() != "uncategorized":
                target = self.base_url + "?" + urllib.parse.urlencode({
                    key: entry.get("id"),
                    "ah_source": self._absolute(entry.get("link")),
                })
                self.add_dir(name, target, 2, icon)
        try:
            total_pages = int(headers.get("X-WP-TotalPages") or 0)
        except (TypeError, ValueError):
            total_pages = 0
        if page < total_pages:
            self.add_dir("Next Page", "WP_DIRECTORY?page={}".format(page + 1), mode, icon)
        self.end_directory("videos")

    def process_categories(self, url):
        self._taxonomy_page("categories", url, 8, self.icons.get("categories", self.icon))

    def process_pornstars(self, url):
        self._taxonomy_page("tags", url, 9, self.icons.get("pornstars", self.icon))

    def search(self, query):
        if query:
            self.process_content(self.base_url + "?" + urllib.parse.urlencode({"s": query.strip()}))

    def _play_resolved(self, resolved):
        if not resolved or not resolved.get("url"):
            self.notify_error("Could not resolve {} stream".format(self.label))
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
            return
        stream_url = resolved["url"]
        headers = resolved.get("headers") or {}
        play_url = stream_url
        if headers:
            play_url += "|" + urllib.parse.urlencode(headers)
        item = xbmcgui.ListItem(path=play_url)
        item.setProperty("IsPlayable", "true")
        if ".m3u8" in stream_url.lower() or resolved.get("extension") == "m3u8":
            item.setMimeType("application/vnd.apple.mpegurl")
        else:
            item.setMimeType("video/mp4")
        item.setContentLookup(False)
        xbmcplugin.setResolvedUrl(self.addon_handle, True, item)

    def play_video(self, url):
        self._play_resolved(self.resolve_recording_stream(url))
