# -*- coding: utf-8 -*-

import html
import os
import re
import time
import urllib.parse

import requests
import xbmc
import xbmcgui
import xbmcplugin

from resources.lib.base_website import BaseWebsite
from resources.lib.proxy_utils import PlaybackGuard, ProxyController
from resources.lib.thumb_proxy import build_thumb_url


class HdEasyPorn(BaseWebsite):
    sort_options = ("Newest", "Most Viewed", "Top Rated", "Longest")
    sort_values = ("n", "v", "r", "d")

    def __init__(self, addon_handle, addon=None):
        super().__init__("hdeasyporn", "https://www.hd-easyporn.com/", "https://www.hd-easyporn.com/search/?k={}", addon_handle, addon)
        self.session = requests.Session()
        self.ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131 Safari/537.36"
        self.icon = os.path.join(self.addon.getAddonInfo("path"), "resources", "logos", "hdeasyporn.png")
        self.icons["default"] = self.icon

    def _headers(self, referer=None):
        return {"User-Agent": self.ua, "Referer": referer or self.base_url, "Accept-Encoding": "identity"}

    def _get(self, url, referer=None):
        mirror_url = url.replace("www.hd-easyporn.com", "www.hdpornos.xxx", 1)
        candidates = (url, mirror_url, url) if mirror_url != url else (url,)
        for attempt, candidate in enumerate(candidates):
            try:
                response = self.session.get(candidate, headers=self._headers(referer), timeout=20)
                if response.status_code == 200 and "grid_box" in response.text:
                    return response.text
            except Exception as exc:
                if attempt == len(candidates) - 1:
                    self.logger.warning("HD-EasyPorn request failed: %s", exc)
            time.sleep(0.15)
        return ""

    def get_start_url_and_label(self):
        try:
            index = int(self.addon.getSetting("hdeasyporn_sort_by") or "0")
        except Exception:
            index = 0
        index = index if 0 <= index < len(self.sort_options) else 0
        return self.base_url + "?o=" + self.sort_values[index], "HD-EasyPorn [COLOR yellow]{}[/COLOR]".format(self.sort_options[index])

    def _items(self, content):
        items, seen = [], set()
        for block in re.findall(r'<div\b[^>]*class=["\']grid_box["\'][^>]*>([\s\S]*?)(?=<div\b[^>]*class=["\']grid_box["\']|$)', content or "", re.I):
            link = re.search(r'href=["\']([^"\']*/(?:videos|filme)/[^"\']+)["\']', block, re.I)
            image = re.search(r'<img\b[^>]*(?:data-src|src)=["\']([^"\']+)["\'][^>]*alt=["\']([^"\']+)["\']', block, re.I)
            if not image:
                image = re.search(r'<img\b[^>]*alt=["\']([^"\']+)["\'][^>]*(?:data-src|src)=["\']([^"\']+)["\']', block, re.I)
                if image:
                    thumb, title = image.group(2), image.group(1)
                else:
                    continue
            else:
                thumb, title = image.group(1), image.group(2)
            if not link:
                continue
            url = urllib.parse.urljoin(self.base_url, html.unescape(link.group(1)))
            if url in seen:
                continue
            seen.add(url)
            duration = re.search(r'class=["\']duration["\'][^>]*>\s*([^<]+)', block, re.I)
            clean_title = html.unescape(title).strip()
            label = "{} [COLOR lime]({})[/COLOR]".format(clean_title, duration.group(1).strip()) if duration else clean_title
            image_tag = re.search(r'<img\b[^>]*>', block, re.I)
            if image_tag:
                for attr in ("data-src", "data-original", "src"):
                    candidate = re.search(r'\s{}=["\']([^"\']+)'.format(attr), image_tag.group(0), re.I)
                    if candidate and not candidate.group(1).startswith("data:"):
                        thumb = candidate.group(1)
                        break
            thumb = build_thumb_url(urllib.parse.urljoin(self.base_url, html.unescape(thumb)), referer=self.base_url)
            items.append((label, clean_title, url, thumb))
        return items

    def process_content(self, url, page=1):
        if not url or url == "BOOTSTRAP":
            url, _ = self.get_start_url_and_label()
        parsed = urllib.parse.urlparse(url)
        query = urllib.parse.parse_qs(parsed.query)
        current_page = int(query.get("p", [page])[0] or page or 1)
        query["p"] = [str(current_page)]
        target = urllib.parse.urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", urllib.parse.urlencode(query, doseq=True), ""))
        content = self._get(target)
        self.add_dir("Search", "", 5, self.icons.get("search", self.icon))
        self.add_dir("Categories", self.base_url + "categories/", 8, self.icons.get("categories", self.icon))
        items = self._items(content)
        for label, title, item_url, thumb in items:
            self.add_link(label, item_url, 4, thumb, self.fanart, info_labels={"title": title, "plot": title})
        if re.search(r'href=["\'][^"\']*\?[^"\']*p={}["\']'.format(current_page + 1), content or "", re.I):
            next_query = dict(query)
            next_query["p"] = [str(current_page + 1)]
            next_url = urllib.parse.urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", urllib.parse.urlencode(next_query, doseq=True), ""))
            self.add_dir("Next Page", next_url, 2, self.icon)
        self.end_directory("videos")

    def process_categories(self, url):
        content = self._get(url)
        seen = set()
        for path, title in re.findall(r'<a\b[^>]*href=["\'](/category/[^"\']+/)["\'][^>]*>[\s\S]{0,500}?<img\b[^>]*alt=["\']([^"\']+)', content or "", re.I):
            target = urllib.parse.urljoin(self.base_url, path)
            if target not in seen:
                seen.add(target)
                self.add_dir(html.unescape(title), target, 2, self.icons.get("categories", self.icon))
        self.end_directory("videos")

    def search(self, query):
        if query:
            self.process_content(self.search_url.format(urllib.parse.quote_plus(query.strip())))

    def resolve_recording_stream(self, url):
        content = self._get(url, self.base_url)
        urls = re.findall(r'https://[^"\' ]+_[0-9]{3,4}p\.mp4', content or "", re.I)
        if not urls:
            return None
        stream = max(urls, key=lambda value: int(re.search(r'_([0-9]{3,4})p\.mp4', value).group(1)))
        return {"url": html.unescape(stream), "headers": self._headers(url), "extension": "mp4"}

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
