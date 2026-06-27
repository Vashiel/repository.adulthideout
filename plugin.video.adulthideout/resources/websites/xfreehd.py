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


class XFreeHD(BaseWebsite):
    def __init__(self, addon_handle, addon=None):
        super().__init__("xfreehd", "https://www.xfreehd.com/", "https://www.xfreehd.com/search", addon_handle, addon)
        self.label = "XFreeHD"
        self.icon = os.path.join(self.addon.getAddonInfo("path"), "resources", "logos", "xfreehd.png")
        self.icons["default"] = self.icon
        self.session = requests.Session()
        self.ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
        self.sort_options = ["Most Recent", "Top Rated", "Most Viewed"]
        self.sort_codes = {"Most Recent": "mr", "Top Rated": "tr", "Most Viewed": "mv"}

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
            self.logger.warning("XFreeHD HTTP %s for %s", response.status_code, url)
        except Exception as exc:
            self.logger.warning("XFreeHD request failed for %s: %s", url, exc)
            self.session = requests.Session()
        return fetch_text(url, headers=self._headers(referer), logger=self.logger, timeout=25, use_windows_curl_fallback=True) or ""

    def _absolute(self, value):
        value = html.unescape(value or "").strip()
        if value.startswith("//"):
            value = "https:" + value
        return urllib.parse.urljoin(self.base_url, value)

    def _clean(self, value):
        return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", value or ""))).strip()

    def _duration_seconds(self, text):
        text = (text or "").strip().lower()
        if not text:
            return 0
        if ":" in text:
            return self.convert_duration(text)
        total = 0
        hours = re.search(r"(\d+)\s*h", text)
        minutes = re.search(r"(\d+)\s*m", text)
        if hours:
            total += int(hours.group(1)) * 3600
        if minutes:
            total += int(minutes.group(1)) * 60
        return total

    def _get_sort_key(self):
        try:
            index = int(self.addon.getSetting("xfreehd_sort_by") or "0")
        except Exception:
            index = 0
        return self.sort_options[index] if 0 <= index < len(self.sort_options) else self.sort_options[0]

    def get_start_url_and_label(self):
        key = self._get_sort_key()
        url = "{}videos?o={}".format(self.base_url, self.sort_codes.get(key, "mr"))
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
        for match in re.finditer(r'<a\b[^>]*class="video-link"[^>]*href="([^"]+)"', content or "", re.IGNORECASE):
            video_url = self._absolute(match.group(1))
            if "/video/" not in video_url or video_url in seen:
                continue
            seen.add(video_url)
            block = content[match.start():match.start() + 700]

            # Private cards always redirect anonymous users to the login form.
            if 'class="label-private"' in block or "/images/private1.png" in block:
                continue

            title = ""
            t_match = re.search(r'<img\b[^>]+alt="([^"]+)"', block, re.IGNORECASE)
            if t_match:
                title = self._clean(t_match.group(1))
            if not title:
                continue

            thumb = ""
            img_match = re.search(r'<img\b[^>]+data-src="([^"]+)"', block, re.IGNORECASE)
            if not img_match:
                img_match = re.search(r'<img\b[^>]+src="([^"]+\.(?:jpg|jpeg|png|webp)[^"]*)"', block, re.IGNORECASE)
            if img_match and "ximgx" not in img_match.group(1):
                thumb = self._absolute(img_match.group(1))

            dur_match = re.search(r'class="duration-new"[^>]*>([\s\S]*?)</div>', block, re.IGNORECASE)
            duration = self._clean(dur_match.group(1)) if dur_match else ""

            info = {"title": title, "plot": title, "mediatype": "video"}
            seconds = self._duration_seconds(duration)
            if seconds:
                info["duration"] = seconds
            label = "{} [COLOR lime]({})[/COLOR]".format(title, duration) if duration else title
            items.append((label, video_url, thumb or self.icon, info))
        return items

    def process_content(self, url, page=1):
        if not url or url == "BOOTSTRAP":
            url, _ = self.get_start_url_and_label()

        menu = self._context_menu()
        parsed = urllib.parse.urlparse(url)
        if parsed.path.rstrip("/") in ("", "/videos") and "o=" in (parsed.query or ""):
            self.add_dir("Search", "", 5, self.icons.get("search", self.icon), context_menu=menu)
            self.add_dir("Categories", self.base_url + "categories", 8, self.icons.get("categories", self.icon), context_menu=menu)

        content = self._get(self.get_page_url(url, page))
        if not content:
            self.notify_error("Could not load XFreeHD")
            return self.end_directory("videos")

        items = self._items(content)
        if not items:
            self.notify_error("No XFreeHD videos found")
            return self.end_directory("videos")

        for label, item_url, thumb, info in items:
            self.add_link(label, item_url, 4, thumb, self.fanart, context_menu=menu, info_labels=info)

        if re.search(r'rel="next"', content, re.IGNORECASE) or re.search(r'[?&]page={}\b'.format(page + 1), content):
            self.add_dir("Next Page", url, 2, self.icons.get("default", self.icon), context_menu=menu, page=page + 1)

        self.end_directory("videos")

    def process_categories(self, url):
        content = self._get(url or (self.base_url + "categories"))
        if not content:
            self.notify_error("Could not load XFreeHD categories")
            return self.end_directory("videos")

        self.add_dir("Search", "", 5, self.icons.get("search", self.icon))
        seen = set()
        for match in re.finditer(r'href="([^"]*/videos/[a-z0-9-]+)"', content, re.IGNORECASE):
            cat_url = self._absolute(match.group(1))
            slug = urllib.parse.urlparse(cat_url).path.rstrip("/").rsplit("/", 1)[-1]
            if cat_url in seen or not slug:
                continue
            seen.add(cat_url)
            block = content[match.start():match.start() + 400]
            t_match = re.search(r'>([^<]{2,40})</a>', block)
            title = self._clean(t_match.group(1)) if t_match else ""
            if not title:
                title = slug.replace("-", " ").title()
            self.add_dir(title, cat_url, 2, self.icons.get("categories", self.icon), self.fanart)
        self.end_directory("videos")

    def search(self, query):
        if query:
            search_url = "{}search?search_query={}".format(self.base_url, urllib.parse.quote_plus(query.strip()))
            self.process_content(search_url)

    def resolve_recording_stream(self, url):
        content = self._get(url, referer=self.base_url)
        if not content:
            return None
        ranked = []
        for tag in re.findall(r"<source\b[^>]*>", content, re.IGNORECASE):
            src_match = re.search(r'src="([^"]+\.mp4[^"]*)"', tag, re.IGNORECASE)
            if not src_match:
                continue
            title_match = re.search(r'title="([^"]*)"', tag, re.IGNORECASE)
            title = (title_match.group(1) if title_match else "").strip().upper()
            rank = 2 if title == "HD" else (1 if title == "SD" else 0)
            ranked.append((rank, self._absolute(src_match.group(1))))
        if not ranked:
            return None
        ranked.sort(key=lambda item: item[0], reverse=True)
        return {"url": ranked[0][1], "headers": self._headers(url), "extension": "mp4"}

    def play_video(self, url):
        resolved = self.resolve_recording_stream(url)
        if not resolved:
            self.notify_error("Could not resolve XFreeHD stream")
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
            self.logger.error("XFreeHD playback failed: %s", exc)
            self.notify_error("XFreeHD playback failed")
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
