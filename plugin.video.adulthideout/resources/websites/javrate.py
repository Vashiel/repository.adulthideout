#!/usr/bin/env python
# -*- coding: utf-8 -*-

import html
import os
import re
import sys
import urllib.parse

vendor_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "lib", "vendor")
if os.path.isdir(vendor_path) and vendor_path not in sys.path:
    sys.path.insert(0, vendor_path)

import cloudscraper
import xbmc
import xbmcgui
import xbmcplugin

from resources.lib.base_website import BaseWebsite
from resources.lib.proxy_utils import HlsProxyController, PlaybackGuard


class JAVRate(BaseWebsite):
    sort_options = ["Latest", "Uncensored", "Censored", "Chinese"]
    sort_paths = {
        "Latest": "/movie/new",
        "Uncensored": "/menu/uncensored",
        "Censored": "/menu/censored",
        "Chinese": "/menu/chinese",
    }

    def __init__(self, addon_handle, addon=None):
        super().__init__(
            "javrate",
            "https://www.javrate.com/",
            "https://www.javrate.com/search/{}",
            addon_handle,
            addon,
        )
        self.ua = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
        )
        self.session = self._new_session()

    def _new_session(self):
        session = cloudscraper.create_scraper(
            browser={"browser": "chrome", "platform": "windows", "desktop": True}
        )
        session.headers.update(self._headers())
        return session

    def _headers(self, referer=None, accept=None):
        return {
            "User-Agent": self.ua,
            "Referer": referer or self.base_url,
            "Accept": accept or "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "identity",
        }

    def _get(self, url, referer=None):
        for attempt in range(2):
            try:
                response = self.session.get(url, headers=self._headers(referer), timeout=25)
                if response.status_code == 200:
                    return response.text
                self.logger.warning("JAVRate HTTP %s for %s", response.status_code, url)
            except Exception as exc:
                self.logger.warning("JAVRate request failed for %s: %s", url, exc)
            if attempt == 0:
                self.session = self._new_session()
        return ""

    def get_start_url_and_label(self):
        url, label = super().get_start_url_and_label()
        return url, label.replace("Javrate", "JAVRate")

    def _page_url(self, url, page):
        if page <= 1:
            return url
        parsed = urllib.parse.urlparse(url)
        query = urllib.parse.parse_qs(parsed.query)
        query["page"] = [str(page)]
        return urllib.parse.urlunparse(
            (parsed.scheme, parsed.netloc, parsed.path, parsed.params,
             urllib.parse.urlencode(query, doseq=True), parsed.fragment)
        )

    def _items(self, content):
        items = []
        seen = set()
        pattern = re.compile(
            r'<a\b[^>]+href=["\']([^"\']*/Movie/Detail/[^"\']+\.html)["\']'
            r'[^>]+title=["\']([^"\']+)["\'][^>]*class=["\'][^"\']*movie-card-link[^"\']*["\']'
            r'[^>]*>[\s\S]{0,500}?<img\b[^>]+src=["\']([^"\']+)["\']',
            re.IGNORECASE,
        )
        for href, title, thumb in pattern.findall(content or ""):
            video_url = urllib.parse.urljoin(self.base_url, html.unescape(href))
            if video_url in seen:
                continue
            seen.add(video_url)
            title = re.sub(r"\s+", " ", html.unescape(title)).strip()
            items.append((title, video_url, html.unescape(thumb)))
        return items

    def process_content(self, url, page=1):
        if not url or url == "BOOTSTRAP":
            url, _ = self.get_start_url_and_label()
        parsed_path = urllib.parse.urlparse(url).path.lower()
        if page == 1 and not parsed_path.startswith("/search/"):
            self.add_dir("Search", "", 5, self.icons["search"])
            self.add_dir("Categories", "JAVRATE_CATEGORIES", 8, self.icons["categories"])
        content = self._get(self._page_url(url, page))
        items = self._items(content)
        for title, video_url, thumb in items:
            self.add_link(
                title,
                video_url,
                4,
                thumb,
                self.fanart,
                info_labels={"title": title, "plot": title},
            )
        supports_pages = parsed_path.startswith(("/menu/", "/search/"))
        if supports_pages and len(items) >= 20:
            self.add_dir("Next Page", url, 2, self.icon, page=page + 1)
        if not items:
            self.notify_error("No JAVRate videos found")
        self.end_directory("videos")

    def process_categories(self, url):
        entries = [
            ("Uncensored", self.base_url + "menu/uncensored"),
            ("Censored", self.base_url + "menu/censored"),
            ("Chinese", self.base_url + "menu/chinese"),
            ("Latest", self.base_url + "movie/new"),
        ]
        for title, target in entries:
            self.add_dir(title, target, 2, self.icons["categories"])
        self.end_directory("videos")

    def search(self, query):
        if query:
            self.process_content(self.search_url.format(urllib.parse.quote(query.strip(), safe="")))

    def resolve_recording_stream(self, url):
        detail = self._get(url, referer=self.base_url)
        iframe_match = re.search(
            r'<iframe\b[^>]+id=["\']v2-player["\'][^>]+src=["\']([^"\']+)',
            detail or "",
            re.IGNORECASE,
        )
        if not iframe_match:
            return None
        iframe_url = urllib.parse.urljoin(url, html.unescape(iframe_match.group(1)))
        player = self._get(iframe_url, referer=url)
        stream_match = re.search(
            r'https://videocdn\.avking\.xyz/[^"\'\\\s]+\.m3u8[^"\'\\\s]*',
            player or "",
            re.IGNORECASE,
        )
        if not stream_match:
            return None
        stream_url = html.unescape(stream_match.group(0)).replace("\\/", "/")
        return {
            "url": stream_url,
            "headers": self._headers(iframe_url, accept="*/*"),
            "extension": "m3u8",
            "hls_proxy": True,
            "preserve_query": True,
        }

    def play_video(self, url):
        resolved = self.resolve_recording_stream(url)
        if not resolved:
            self.notify_error("Could not resolve JAVRate stream")
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
            return
        controller = HlsProxyController(
            resolved["url"],
            headers=resolved["headers"],
            session=self.session,
            preserve_query=True,
        )
        local_url = controller.start()
        item = xbmcgui.ListItem(path=local_url)
        item.setProperty("IsPlayable", "true")
        item.setMimeType("application/vnd.apple.mpegurl")
        item.setContentLookup(False)
        xbmcplugin.setResolvedUrl(self.addon_handle, True, item)
        PlaybackGuard(xbmc.Player(), xbmc.Monitor(), local_url, controller).start()
