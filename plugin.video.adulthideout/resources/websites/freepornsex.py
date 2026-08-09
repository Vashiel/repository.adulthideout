# -*- coding: utf-8 -*-
import html
import os
import re
import urllib.parse

import requests
import xbmc
import xbmcgui
import xbmcplugin

from resources.lib.base_website import BaseWebsite
from resources.lib.proxy_utils import PlaybackGuard, ProxyController


class FreePornSex(BaseWebsite):
    def __init__(self, addon_handle, addon=None):
        super().__init__("freepornsex", "https://www.freepornsex.net/", "https://www.freepornsex.net/?s={}", addon_handle, addon)
        self.session = requests.Session()
        self.ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131 Safari/537.36"
        self.icon = os.path.join(self.addon.getAddonInfo("path"), "resources", "logos", "freepornsex.png")
        self.icons["default"] = self.icon

    def _headers(self, referer=None):
        return {"User-Agent": self.ua, "Referer": referer or self.base_url, "Accept-Encoding": "identity"}

    def _get(self, url, referer=None):
        try:
            response = self.session.get(url, headers=self._headers(referer), timeout=20)
            return response.text if response.status_code == 200 else ""
        except Exception as exc:
            self.logger.warning("FreePornSex request failed: %s", exc)
            return ""

    def _items(self, content):
        items, seen = [], set()
        blocks = re.findall(r'<article\b[^>]*>([\s\S]*?)</article>', content or "", re.I)
        if not blocks:
            blocks = re.split(r'(?=<div\b[^>]+class=["\'][^"\']*(?:post|latestPost)[^"\']*["\'])', content or "", flags=re.I)
        for block in blocks:
            title_link = re.search(
                r'<h2\b[^>]*class=["\'][^"\']*\btitle\b[^"\']*["\'][^>]*>\s*'
                r'<a\b[^>]*href=["\'](https?://www\.freepornsex\.net/[^"\']+/)["\']'
                r'[^>]*(?:title=["\']([^"\']+)["\'])?[^>]*>([\s\S]*?)</a>',
                block,
                re.I,
            )
            if not title_link:
                continue
            image = re.search(r'<img\b[^>]*\bsrc=["\']([^"\']+)["\']', block, re.I)
            if not image:
                continue
            url = html.unescape(title_link.group(1))
            if url in seen or any(part in url for part in ("/page/", "/wp-", "/images/")):
                continue
            seen.add(url)
            clean_title = self._clean_title(title_link.group(2) or title_link.group(3))
            thumb = html.unescape(image.group(1))
            if thumb.startswith("http") and "|" not in thumb:
                thumb += "|" + urllib.parse.urlencode({"User-Agent": self.ua, "Referer": self.base_url})
            items.append((clean_title, url, thumb))
        return items

    @staticmethod
    def _clean_title(value):
        value = re.sub(r"<[^>]+>", " ", value or "")
        return re.sub(r"\s+", " ", html.unescape(value)).strip()

    def process_content(self, url, page=1):
        if not url or url == "BOOTSTRAP":
            url = self.base_url
        self.add_dir("Search", "", 5, self.icons.get("search", self.icon))
        self.add_dir("Categories", self.base_url, 8, self.icons.get("categories", self.icon))
        content = self._get(url)
        for title, item_url, thumb in self._items(content):
            self.add_link(title, item_url, 4, thumb, self.fanart, info_labels={"title": title, "plot": title})
        next_match = re.search(r'<a\b[^>]*href=["\']([^"\']+/page/\d+/)["\'][^>]*>(?:\s*Next|[\s\S]*?fa-angle-right)', content or "", re.I)
        if not next_match:
            next_match = re.search(r'<link\b[^>]*rel=["\']next["\'][^>]*href=["\']([^"\']+/page/\d+/)["\']', content or "", re.I)
        if not next_match:
            parsed = urllib.parse.urlparse(url)
            current_match = re.search(r'/page/(\d+)/?$', parsed.path)
            current_page = int(current_match.group(1)) if current_match else 1
            wanted = current_page + 1
            next_match = re.search(r'<a\b[^>]*href=["\']([^"\']+/page/{}/)["\']'.format(wanted), content or "", re.I)
        if next_match:
            self.add_dir("Next Page", html.unescape(next_match.group(1)), 2, self.icon)
        self.end_directory("videos")

    def process_categories(self, url):
        content = self._get(self.base_url)
        seen = set()
        for target, title in re.findall(r'<a\b[^>]*href=["\'](https?://www\.freepornsex\.net/[^"\']+/)["\'][^>]*>([^<]{2,60})</a>', content or "", re.I):
            title = html.unescape(title).strip()
            if target in seen or title.lower() in ("home", "next", "older posts"):
                continue
            if any(marker in target for marker in ("/wp-", "/page/", "/feed/")):
                continue
            seen.add(target)
            self.add_dir(title, target, 2, self.icons.get("categories", self.icon))
        self.end_directory("videos")

    def search(self, query):
        if query:
            self.process_content(self.search_url.format(urllib.parse.quote_plus(query.strip())))

    def resolve_recording_stream(self, url):
        content = self._get(url, self.base_url)
        hash_match = re.search(r'var\s+videoHash\s*=\s*["\']([A-F0-9]+)', content or "", re.I)
        if not hash_match:
            return None
        try:
            response = self.session.post(
                self.base_url + "tools/api/hls.php",
                data={"videoHash": hash_match.group(1)},
                headers=self._headers(url),
                timeout=20,
            )
            stream = response.text.strip() if response.status_code == 200 else ""
        except Exception:
            stream = ""
        if not stream.startswith("http"):
            return None
        return {"url": stream, "headers": self._headers(url), "extension": "mp4"}

    def play_video(self, url):
        resolved = self.resolve_recording_stream(url)
        if not resolved:
            return xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
        controller = ProxyController(resolved["url"], upstream_headers=resolved["headers"], session=self.session, skip_resolve=True, probe_size=True, use_urllib=True)
        local_url = controller.start()
        item = xbmcgui.ListItem(path=local_url)
        item.setProperty("IsPlayable", "true")
        item.setMimeType("video/mp4")
        item.setContentLookup(False)
        xbmcplugin.setResolvedUrl(self.addon_handle, True, item)
        PlaybackGuard(xbmc.Player(), xbmc.Monitor(), local_url, controller).start()
