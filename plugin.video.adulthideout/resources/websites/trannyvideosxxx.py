# -*- coding: utf-8 -*-
import html
import os
import re
import sys
import urllib.parse

import requests
import xbmc
import xbmcgui
import xbmcplugin

from resources.lib.base_website import BaseWebsite
from resources.lib.proxy_utils import PlaybackGuard, ProxyController
from resources.lib.resilient_http import fetch_text


class TrannyVideosXXX(BaseWebsite):
    SORT_SLUGS = ("recent", "popular", "viewed", "discussed", "rated", "favorited", "downloaded", "watched", "featured")

    def __init__(self, addon_handle, addon=None):
        super().__init__("trannyvideosxxx", "https://trannyvideosxxx.com/", "https://trannyvideosxxx.com/search/video/?s={}", addon_handle, addon)
        self.label = "TrannyVideosXXX"
        self.icon = os.path.join(self.addon.getAddonInfo("path"), "resources", "logos", "trannyvideosxxx.png")
        self.icons["default"] = self.icon
        self.session = requests.Session()
        self.ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
        self.sort_options = ["Recent", "Popular", "Most Viewed", "Top Rated", "Featured"]
        self.sort_paths = {
            "Recent": "/videos/recent/",
            "Popular": "/videos/popular/",
            "Most Viewed": "/videos/viewed/",
            "Top Rated": "/videos/rated/",
            "Featured": "/videos/featured/",
        }

    def _headers(self, referer=None, accept="text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"):
        return {
            "User-Agent": self.ua,
            "Accept": accept,
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": referer or self.base_url,
        }

    def _get(self, url, referer=None):
        try:
            response = self.session.get(url, headers=self._headers(referer), timeout=25, allow_redirects=True)
            if response.status_code == 200:
                return response.text
            self.logger.warning("TrannyVideosXXX HTTP %s for %s", response.status_code, url)
        except Exception as exc:
            self.logger.warning("TrannyVideosXXX request failed for %s: %s", url, exc)
            self.session = requests.Session()
        return fetch_text(url, headers=self._headers(referer), logger=self.logger, timeout=25, use_windows_curl_fallback=True) or ""

    def _absolute(self, value):
        value = html.unescape(value or "").strip()
        if value.startswith("//"):
            value = "https:" + value
        return urllib.parse.urljoin(self.base_url, value)

    def _clean(self, value):
        return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", value or ""))).strip()

    def _get_sort_key(self):
        try:
            index = int(self.addon.getSetting("trannyvideosxxx_sort_by") or "0")
        except Exception:
            index = 0
        return self.sort_options[index] if 0 <= index < len(self.sort_options) else self.sort_options[0]

    def get_start_url_and_label(self):
        key = self._get_sort_key()
        return self._absolute(self.sort_paths[key]), "{} [COLOR yellow]{}[/COLOR]".format(self.label, key)

    def _context_menu(self):
        return [("Sort by...", "RunPlugin({}?mode=7&action=select_sort&website={})".format(sys.argv[0], self.name))]

    def _is_top_listing(self, url):
        path = urllib.parse.urlparse(url or "").path.rstrip("/")
        return path in (sort.rstrip("/") for sort in self.sort_paths.values()) or path in ("", "/videos")

    def get_page_url(self, base_url, page_num):
        if page_num <= 1:
            return base_url
        parsed = urllib.parse.urlparse(base_url)
        path = parsed.path.rstrip("/")
        if re.search(r"/\d+$", path):
            path = re.sub(r"/\d+$", "/{}".format(page_num), path)
        else:
            path = "{}/{}".format(path, page_num)
        path += "/"
        return urllib.parse.urlunparse((parsed.scheme, parsed.netloc, path, parsed.params, parsed.query, parsed.fragment))

    def _items(self, content):
        items, seen = [], set()
        for match in re.finditer(r'<a\b[^>]*href="(/\d+/[a-z0-9-]+/)"[^>]*\btitle="([^"]*)"', content or "", re.IGNORECASE):
            video_url = self._absolute(match.group(1))
            if video_url in seen:
                continue
            seen.add(video_url)
            title = self._clean(match.group(2))
            if not title:
                continue
            block = content[match.start():match.start() + 600]

            thumb = ""
            img_match = re.search(r'<img\b[^>]+src="([^"]+\.(?:jpg|jpeg|png|webp)[^"]*)"', block, re.IGNORECASE)
            if img_match:
                thumb = self._absolute(img_match.group(1))

            dur_match = re.search(r'class="duration"[^>]*>([\s\S]*?)</span>', block, re.IGNORECASE)
            duration = self._clean(dur_match.group(1)) if dur_match else ""
            time_match = re.search(r"\d{1,3}:\d{2}(?::\d{2})?", duration)
            duration = time_match.group(0) if time_match else ""

            info = {"title": title, "plot": title, "mediatype": "video"}
            seconds = self.convert_duration(duration)
            if seconds:
                info["duration"] = seconds
            label = "{} [COLOR lime]({})[/COLOR]".format(title, duration) if duration else title
            items.append((label, video_url, thumb or self.icon, info))
        return items

    def process_content(self, url, page=1):
        if not url or url == "BOOTSTRAP":
            url, _ = self.get_start_url_and_label()

        menu = self._context_menu()
        if page == 1 and self._is_top_listing(url):
            self.add_dir("Search", "", 5, self.icons.get("search", self.icon), context_menu=menu)
            self.add_dir("Categories", self.base_url + "categories/", 8, self.icons.get("categories", self.icon), context_menu=menu)
            self.add_dir("Models", self.base_url + "models/", 9, self.icons.get("pornstars", self.icon), context_menu=menu)

        content = self._get(self.get_page_url(url, page))
        if not content:
            self.notify_error("Could not load TrannyVideosXXX")
            return self.end_directory("videos")

        items = self._items(content)
        if not items:
            self.notify_error("No TrannyVideosXXX videos found")
            return self.end_directory("videos")

        for label, item_url, thumb, info in items:
            self.add_link(label, item_url, 4, thumb, self.fanart, context_menu=menu, info_labels=info)

        next_path = urllib.parse.urlparse(self.get_page_url(url, page + 1)).path
        if re.search(r'href="[^"]*{}"'.format(re.escape(next_path)), content) or re.search(r'rel="next"', content, re.IGNORECASE):
            self.add_dir("Next Page", url, 2, self.icons.get("default", self.icon), context_menu=menu, page=page + 1)

        self.end_directory("videos")

    def process_categories(self, url):
        content = self._get(url or (self.base_url + "categories/"))
        if not content:
            self.notify_error("Could not load TrannyVideosXXX categories")
            return self.end_directory("videos")

        self.add_dir("Search", "", 5, self.icons.get("search", self.icon))
        seen = set()
        for match in re.finditer(r'href="(/videos/([a-z0-9-]+)/)"', content, re.IGNORECASE):
            slug = match.group(2).lower()
            if slug in self.SORT_SLUGS:
                continue
            cat_url = self._absolute(match.group(1))
            if cat_url in seen:
                continue
            seen.add(cat_url)
            block = content[match.start():match.start() + 300]
            t_match = re.search(r'>([^<]{2,40})</a>', block)
            title = self._clean(t_match.group(1)) if t_match else ""
            if not title:
                title = slug.replace("-", " ").title()
            self.add_dir(title, cat_url, 2, self.icons.get("categories", self.icon), self.fanart)
        self.end_directory("videos")

    def process_pornstars(self, url):
        content = self._get(url or (self.base_url + "models/"))
        if not content:
            self.notify_error("Could not load TrannyVideosXXX models")
            return self.end_directory("videos")

        seen = set()
        for match in re.finditer(r'href="((?:https?://[^/"]+)?/model/[a-z0-9-]+/)"[^>]*\btitle="([^"]*)"', content, re.IGNORECASE):
            model_url = self._absolute(match.group(1))
            if model_url in seen:
                continue
            seen.add(model_url)
            title = self._clean(match.group(2))
            if not title:
                continue
            block = content[match.start():match.start() + 400]
            img_match = re.search(r'<img\b[^>]+src="([^"]+\.(?:jpg|jpeg|png|webp)[^"]*)"', block, re.IGNORECASE)
            thumb = self._absolute(img_match.group(1)) if img_match else self.icons.get("pornstars", self.icon)
            self.add_dir(title, model_url, 2, thumb, self.fanart)

        next_match = re.search(r'href="((?:https?://[^/"]+)?/models/\d+/)"', content, re.IGNORECASE)
        if next_match:
            self.add_dir("Next Page", self._absolute(next_match.group(1)), 9, self.icons.get("default", self.icon))
        self.end_directory("videos")

    def search(self, query):
        if query:
            search_url = self.search_url.format(urllib.parse.quote_plus(query.strip()))
            content = self._get(search_url)
            if not content:
                self.notify_error("No TrannyVideosXXX results")
                return self.end_directory("videos")
            menu = self._context_menu()
            items = self._items(content)
            if not items:
                self.notify_error("No TrannyVideosXXX results")
                return self.end_directory("videos")
            for label, item_url, thumb, info in items:
                self.add_link(label, item_url, 4, thumb, self.fanart, context_menu=menu, info_labels=info)
            self.end_directory("videos")

    def _extract_stream(self, content):
        candidates = re.findall(r'(https?://[^"\']+?/vfile/[^"\']+\.mp4[^"\']*)', content or "", re.IGNORECASE)
        if not candidates:
            candidates = [
                self._absolute(src)
                for src in re.findall(r'<source\b[^>]*src="([^"]+\.mp4[^"]*)"', content or "", re.IGNORECASE)
            ]
        if not candidates:
            return ""
        for marker in ("_2160p", "_1080p", "_720p", "_480p"):
            for url in candidates:
                if marker in url:
                    return self._absolute(html.unescape(url))
        return self._absolute(html.unescape(candidates[0]))

    def resolve_recording_stream(self, url):
        content = self._get(url, referer=self.base_url)
        stream_url = self._extract_stream(content)
        if not stream_url:
            embed_match = re.search(r'/embed/(\d+)/', content or "")
            if embed_match:
                embed = self._get("{}embed/{}/".format(self.base_url, embed_match.group(1)), referer=url)
                stream_url = self._extract_stream(embed)
        if not stream_url:
            return None
        return {"url": stream_url, "headers": self._headers(url), "extension": "mp4"}

    def play_video(self, url):
        resolved = self.resolve_recording_stream(url)
        if not resolved:
            self.notify_error("Could not resolve TrannyVideosXXX stream")
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
            return
        try:
            controller = ProxyController(resolved["url"], upstream_headers=resolved["headers"], use_urllib=True, probe_size=True)
            play_url = controller.start()
            PlaybackGuard(xbmc.Player(), xbmc.Monitor(), play_url, controller).start()
            item = xbmcgui.ListItem(path=play_url)
            item.setProperty("IsPlayable", "true")
            item.setMimeType("video/mp4")
            item.setContentLookup(False)
            xbmcplugin.setResolvedUrl(self.addon_handle, True, item)
        except Exception as exc:
            self.logger.error("TrannyVideosXXX playback failed: %s", exc)
            self.notify_error("TrannyVideosXXX playback failed")
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
