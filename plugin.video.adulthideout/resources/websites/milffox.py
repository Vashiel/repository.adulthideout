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


class MilfFox(BaseWebsite):
    def __init__(self, addon_handle, addon=None):
        super().__init__("milffox", "https://www.milffox.com/", "https://www.milffox.com/search/?q={}", addon_handle, addon)
        self.label = "MilfFox"
        self.icon = os.path.join(self.addon.getAddonInfo("path"), "resources", "logos", "milffox.png")
        self.icons["default"] = self.icon
        self.session = requests.Session()
        self.ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
        self.sort_options = ["Popular", "Recent", "Longest"]
        self.sort_codes = {"Popular": "", "Recent": "1", "Longest": "2"}

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
            self.logger.warning("MilfFox HTTP %s for %s", response.status_code, url)
        except Exception as exc:
            self.logger.warning("MilfFox request failed for %s: %s", url, exc)
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
            index = int(self.addon.getSetting("milffox_sort_by") or "0")
        except Exception:
            index = 0
        return self.sort_options[index] if 0 <= index < len(self.sort_options) else self.sort_options[0]

    def get_start_url_and_label(self):
        key = self._get_sort_key()
        code = self.sort_codes[key]
        url = "{}?o={}".format(self.base_url, code) if code else self.base_url
        return url, "{} [COLOR yellow]{}[/COLOR]".format(self.label, key)

    def _context_menu(self):
        return [("Sort by...", "RunPlugin({}?mode=7&action=select_sort&website={})".format(sys.argv[0], self.name))]

    def get_page_url(self, base_url, page_num):
        if page_num <= 1:
            return base_url
        parsed = urllib.parse.urlparse(base_url)
        query = urllib.parse.parse_qs(parsed.query)
        query["page"] = [str(page_num)]
        return urllib.parse.urlunparse(
            (parsed.scheme, parsed.netloc, parsed.path, parsed.params, urllib.parse.urlencode(query, doseq=True), parsed.fragment)
        )

    def _items(self, content):
        items, seen = [], set()
        for match in re.finditer(r'<a\b[^>]*href="((?://www\.milffox\.com)?/porn-movies/[^"]+)"[^>]*>', content or "", re.IGNORECASE):
            video_url = self._absolute(match.group(1))
            if video_url in seen:
                continue
            seen.add(video_url)
            block = content[match.start():match.start() + 500]

            title = ""
            t_match = re.search(r'<a\b[^>]+title="([^"]+)"', block, re.IGNORECASE)
            if not t_match:
                t_match = re.search(r'<img\b[^>]+alt="([^"]+)"', block, re.IGNORECASE)
            if t_match:
                title = self._clean(t_match.group(1))
            if not title:
                continue

            thumb = ""
            img_match = re.search(r'<img\b[^>]+src="([^"]+\.(?:jpg|jpeg|png|webp)[^"]*)"', block, re.IGNORECASE)
            if img_match:
                thumb = self._absolute(img_match.group(1))

            dur_match = re.search(r"<i>\s*(\d{1,3}:\d{2}(?::\d{2})?)\s*</i>", block, re.IGNORECASE)
            duration = dur_match.group(1) if dur_match else ""

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

        parsed = urllib.parse.urlparse(url)
        menu = self._context_menu()
        if page == 1 and parsed.path.rstrip("/") in ("", "/"):
            self.add_dir("Search", "", 5, self.icons.get("search", self.icon), context_menu=menu)
            self.add_dir("Categories", self.base_url + "categories/", 8, self.icons.get("categories", self.icon), context_menu=menu)
            self.add_dir("Models", self.base_url + "milf-pornstars/", 9, self.icons.get("pornstars", self.icon), context_menu=menu)

        content = self._get(self.get_page_url(url, page))
        if not content:
            self.notify_error("Could not load MilfFox")
            return self.end_directory("videos")

        items = self._items(content)
        if not items:
            self.notify_error("No MilfFox videos found")
            return self.end_directory("videos")

        for label, item_url, thumb, info in items:
            self.add_link(label, item_url, 4, thumb, self.fanart, context_menu=menu, info_labels=info)

        if re.search(r'href="[^"]*[?&]page={}\b'.format(page + 1), content):
            self.add_dir("Next Page", url, 2, self.icons.get("default", self.icon), context_menu=menu, page=page + 1)

        self.end_directory("videos")

    def process_categories(self, url):
        content = self._get(url or (self.base_url + "categories/"))
        if not content:
            self.notify_error("Could not load MilfFox categories")
            return self.end_directory("videos")

        self.add_dir("Search", "", 5, self.icons.get("search", self.icon))
        seen = set()
        for match in re.finditer(r'<a\b[^>]*href="((?://www\.milffox\.com)?/tags/[^"/]+/)"[^>]*>([\s\S]*?)</a>', content, re.IGNORECASE):
            category_url = self._absolute(match.group(1))
            if category_url in seen:
                continue
            seen.add(category_url)
            title = self._clean(match.group(2))
            if not title:
                title = urllib.parse.unquote(category_url.rstrip("/").rsplit("/", 1)[-1]).replace("-", " ").title()
            self.add_dir(title, category_url, 2, self.icons.get("categories", self.icon), self.fanart)
        self.end_directory("videos")

    def process_pornstars(self, url):
        content = self._get(url or (self.base_url + "milf-pornstars/"))
        if not content:
            self.notify_error("Could not load MilfFox models")
            return self.end_directory("videos")

        seen = set()
        for match in re.finditer(r'<a\b[^>]*href="((?://www\.milffox\.com)?/milf-pornstars/[A-Za-z0-9-]+/)"[^>]*>', content, re.IGNORECASE):
            model_url = self._absolute(match.group(1))
            if model_url in seen or model_url.rstrip("/").endswith("/milf-pornstars"):
                continue
            seen.add(model_url)
            slug = model_url.rstrip("/").rsplit("/", 1)[-1]
            block = content[match.start():match.start() + 400]
            t_match = re.search(r'(?:title|alt)="([^"]+)"', block, re.IGNORECASE)
            title = self._clean(t_match.group(1)) if t_match else slug.replace("-", " ")
            img_match = re.search(r'<img\b[^>]+src="([^"]+\.(?:jpg|jpeg|png|webp)[^"]*)"', block, re.IGNORECASE)
            thumb = self._absolute(img_match.group(1)) if img_match else self.icons.get("pornstars", self.icon)
            self.add_dir(title, model_url, 2, thumb, self.fanart)

        if re.search(r'href="[^"]*milf-pornstars/[^"]*[?&]page=2', content) or re.search(r'[?&]page=2', content):
            next_url = self.get_page_url(url or (self.base_url + "milf-pornstars/"), 2)
            self.add_dir("Next Page", next_url, 9, self.icons.get("default", self.icon))
        self.end_directory("videos")

    def search(self, query):
        if query:
            self.process_content(self.search_url.format(urllib.parse.quote_plus(query.strip())))

    def resolve_recording_stream(self, url):
        content = self._get(url, referer=self.base_url)
        if not content:
            return None
        alt = re.search(r"video_alt_url:\s*'([^']+)'", content)
        primary = re.search(r"video_url:\s*'([^']+)'", content)
        match = alt or primary
        if not match:
            return None
        stream_url = html.unescape(match.group(1)).replace("\\/", "/").strip()
        if not stream_url.startswith("http"):
            return None
        return {"url": stream_url, "headers": self._headers(url, accept="*/*"), "extension": "mp4"}

    def play_video(self, url):
        resolved = self.resolve_recording_stream(url)
        if not resolved:
            self.notify_error("Could not resolve MilfFox stream")
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
            self.logger.error("MilfFox playback failed: %s", exc)
            self.notify_error("MilfFox playback failed")
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
