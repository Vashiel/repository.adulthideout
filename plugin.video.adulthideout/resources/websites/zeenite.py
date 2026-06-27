# -*- coding: utf-8 -*-
import html
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


class Zeenite(BaseWebsite):
    def __init__(self, addon_handle, addon=None):
        super().__init__("zeenite", "https://zeenite.com/", "https://zeenite.com/search/{}/", addon_handle, addon)
        self.label = "Zeenite"
        self.session = requests.Session()
        self.ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
        self.sort_options = ["Latest Updates", "Most Popular"]
        self.sort_paths = {
            "Latest Updates": "/latest-updates/",
            "Most Popular":   "/most-popular/"
        }

    def _headers(self, referer=None, accept="text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"):
        return {
            "User-Agent": self.ua,
            "Accept": accept,
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": referer or self.base_url
        }

    def _get(self, url, referer=None):
        try:
            response = self.session.get(url, headers=self._headers(referer), timeout=25, allow_redirects=True)
            if response.status_code == 200:
                return response.text
            self.logger.warning("Zeenite HTTP %s for %s", response.status_code, url)
        except Exception as exc:
            self.logger.warning("Zeenite request failed for %s: %s", url, exc)
            self.session = requests.Session()
        return fetch_text(url, headers=self._headers(referer), logger=self.logger, timeout=25, use_windows_curl_fallback=True) or ""

    def _absolute(self, value, base=None):
        value = html.unescape(value or "").strip()
        if value.startswith("//"):
            value = "https:" + value
        return urllib.parse.urljoin(base or self.base_url, value)

    def _clean(self, value):
        return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", value or ""))).strip()

    def get_start_url_and_label(self):
        try:
            index = int(self.addon.getSetting("zeenite_sort_by") or "0")
        except Exception:
            index = 0
        index = index if 0 <= index < len(self.sort_options) else 0
        key = self.sort_options[index]
        return self._absolute(self.sort_paths[key]), "{} [COLOR yellow]{}[/COLOR]".format(self.label, key)

    def _context_menu(self):
        return [("Sort by...", "RunPlugin({}?mode=7&action=select_sort&website={})".format(sys.argv[0], self.name))]

    def get_page_url(self, base_url, page_num):
        if page_num <= 1:
            return base_url
        parsed = urllib.parse.urlparse(base_url)
        path = parsed.path.rstrip("/")
        # If it already ends with a page number, replace it, otherwise append
        match = re.search(r'/(\d+)$', path)
        if match:
            path = re.sub(r'/\d+$', f"/{page_num}", path)
        else:
            path = f"{path}/{page_num}/"
        return urllib.parse.urlunparse((parsed.scheme, parsed.netloc, path, parsed.params, parsed.query, parsed.fragment))

    def _items(self, content):
        items, seen = [], set()
        
        # Search for links of form: /videos/ID/slug/
        pattern = re.compile(r'href=["\']((https://zeenite\.com)?/videos/(\d+)/[^"\'/]+/)["\']', re.I)
        for m in pattern.finditer(content or ""):
            href = m.group(1)
            video_url = self._absolute(href)
            if video_url in seen:
                continue
            seen.add(video_url)
            
            ctx_start = max(0, m.start() - 500)
            ctx_end = min(len(content), m.end() + 500)
            ctx = content[ctx_start:ctx_end]
            
            # Title
            title = ""
            t_match = re.search(r'title=["\']([^"\']+)["\']', ctx)
            if t_match:
                title = self._clean(t_match.group(1))
            if not title:
                t_match = re.search(r'alt=["\']([^"\']+)["\']', ctx)
                if t_match:
                    title = self._clean(t_match.group(1))
            if not title:
                continue
                
            # Thumbnail
            thumb = ""
            img_match = re.search(r'data-original=["\']([^"\']+)["\']', ctx)
            if not img_match:
                img_match = re.search(r'src=["\']([^"\']+\.(?:jpg|jpeg|png|webp)[^"\'\s]*)["\']', ctx)
            if img_match:
                thumb = self._absolute(img_match.group(1))
                
            # Duration
            duration = ""
            dur_match = re.search(r'<span class="duration">([^<]+)</span>', ctx)
            if dur_match:
                duration = dur_match.group(1).strip()
                
            items.append((title, video_url, thumb or self.icon, {"title": title, "duration": duration}))
            
        return items

    def process_content(self, url, page=1):
        if not url or url == "BOOTSTRAP":
            url, _ = self.get_start_url_and_label()

        content = self._get(self.get_page_url(url, page))
        if not content:
            self.notify_error("Could not load Zeenite")
            return self.end_directory("videos")

        menu = self._context_menu()
        self.add_dir("Search", "", 5, self.icons.get("search", self.icon), context_menu=menu)
        
        # Check if it's the main updates or categories listings
        parsed = urllib.parse.urlparse(url)
        if parsed.path.rstrip("/") in ("", "/", "/latest-updates", "/most-popular"):
            self.add_dir("Categories", self.base_url + "categories/", 8, self.icons.get("categories", self.icon), context_menu=menu)

        items = self._items(content)
        if not items:
            self.notify_error("No Zeenite videos found")
            return self.end_directory("videos")

        for title, item_url, thumb, info in items:
            self.add_link(title, item_url, 4, thumb, self.fanart, context_menu=menu, info_labels=info)

        # Pagination: check if page+1 link or button exists
        has_next = (
            bool(re.search(r'/{}/(?:[?&][^"\']*)?["\']'.format(page + 1), content)) or
            bool(re.search(r'class=["\'][^"\']*(?:next|pagination-next)[^"\']*["\']', content, re.I))
        )
        if has_next:
            self.add_dir("Next Page", url, 2, self.icons.get("default", self.icon), context_menu=menu, page=page + 1)

        self.end_directory("videos")

    def process_categories(self, url):
        target_url = url or (self.base_url + "categories/")
        content = self._get(target_url)
        if not content:
            self.notify_error("Could not load Zeenite categories")
            return self.end_directory("videos")

        self.add_dir("Search", "", 5, self.icons.get("search", self.icon))
        
        seen = set()
        # Category links: /categories/SLUG/
        cat_pattern = re.compile(r'href=["\']((https://zeenite\.com)?/categories/[^"\'/]+/)["\']', re.I)
        for m in cat_pattern.finditer(content):
            href = m.group(1)
            full_url = self._absolute(href)
            if full_url in seen or full_url.rstrip("/") == f"{self.base_url}categories":
                continue
            seen.add(full_url)
            
            ctx_start = max(0, m.start() - 300)
            ctx_end = min(len(content), m.end() + 300)
            ctx = content[ctx_start:ctx_end]
            
            # Title
            title = ""
            t_match = re.search(r'title=["\']([^"\']+)["\']', ctx)
            if t_match:
                title = self._clean(t_match.group(1))
            if not title:
                t_match = re.search(r'<strong>([^<]+)</strong>', ctx)
                if t_match:
                    title = self._clean(t_match.group(1))
            if not title:
                continue
                
            # Thumbnail
            thumb = ""
            img_match = re.search(r'data-original=["\']([^"\']+)["\']', ctx)
            if img_match:
                thumb = self._absolute(img_match.group(1))
                
            self.add_dir(title, full_url, 2, thumb or self.icons.get("categories", self.icon), self.fanart)
            
        self.end_directory("videos")

    def search(self, query):
        if query:
            # Zeenite search replaces spaces with hyphens in path: /search/query-here/
            clean_query = re.sub(r'\s+', '-', query.strip().lower())
            search_url = "https://zeenite.com/search/{}/".format(urllib.parse.quote(clean_query))
            self.process_content(search_url)

    def resolve_recording_stream(self, url):
        content = self._get(url, referer=self.base_url)
        if not content:
            return None
            
        # Try to find <source src="..."> tags first
        sources = re.findall(r'<source\b[^>]*src=["\']([^"\']+)["\']', content, re.I)
        stream_url = ""
        if sources:
            stream_url = self._absolute(sources[0])
        else:
            # Fallback: look for direct mp4 links
            media = re.findall(r'https?://[^\s"\'<>]+\.mp4[^\s"\'<>]*', content, re.I)
            if media:
                stream_url = media[0]
                
        if stream_url:
            return {"url": stream_url, "headers": self._headers(url), "extension": "mp4"}
        return None

    def play_video(self, url):
        resolved = self.resolve_recording_stream(url)
        if not resolved:
            self.notify_error("Could not resolve Zeenite stream")
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
            self.logger.error("Zeenite playback failed: %s", exc)
            self.notify_error("Zeenite playback failed")
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
