# -*- coding: utf-8 -*-
import html
import os
import re
import sys
import urllib.parse

vendor_path = os.path.join(os.path.dirname(__file__), "vendor")
if os.path.isdir(vendor_path) and vendor_path not in sys.path:
    sys.path.insert(0, vendor_path)
try:
    import cloudscraper
except Exception:
    cloudscraper = None
import requests
import xbmc
import xbmcgui
import xbmcplugin

from resources.lib.base_website import BaseWebsite
from resources.lib.proxy_utils import HlsProxyController, PlaybackGuard, ProxyController
from resources.lib.resolvers import resolver


class WPSTubeMoviesWebsite(BaseWebsite):
    """Shared parser for movie-focused sites using the WP-Script tube theme."""

    def __init__(self, name, label, base_url, addon_handle, addon=None):
        super().__init__(name, base_url.rstrip("/"), base_url.rstrip("/") + "/?s={}", addon_handle, addon)
        self.label = label
        self.ua = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
        )
        if cloudscraper:
            try:
                self.session = cloudscraper.create_scraper(browser={"custom": self.ua})
            except Exception:
                self.session = requests.Session()
        else:
            self.session = requests.Session()
        self.sort_options = ["Latest", "Most Viewed", "Longest", "Top Rated"]
        self.sort_paths = {
            "Latest": "/",
            "Most Viewed": "/?filter=most-viewed",
            "Longest": "/?filter=longest",
            "Top Rated": "/?filter=popular",
        }
        self.extra_categories = []

    def _get(self, url, referer=None):
        request_headers = {
            "User-Agent": self.ua,
            "Referer": referer or self.base_url + "/",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "same-origin" if referer else "none",
        }
        for attempt in range(2):
            try:
                response = self.session.get(
                    url, headers=request_headers, timeout=12, allow_redirects=True
                )
                if response.status_code == 200:
                    return response.content.decode("utf-8", "replace")
                self.logger.warning("[%s] HTTP %s for %s", self.name, response.status_code, url)
            except Exception as exc:
                if attempt:
                    self.logger.warning("[%s] Request failed for %s: %s", self.name, url, exc)
        return ""

    @staticmethod
    def _attr(block, attribute):
        match = re.search(
            r"\b{}\s*=\s*(?:\"([^\"]*)\"|'([^']*)'|([^\s>]+))".format(re.escape(attribute)),
            block or "", re.I,
        )
        if not match:
            return ""
        return html.unescape(next((value for value in match.groups() if value is not None), "")).strip()

    @staticmethod
    def _clean(value):
        return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", value or ""))).strip()

    def _absolute(self, value):
        return urllib.parse.urljoin(self.base_url + "/", (value or "").strip())

    def get_start_url_and_label(self):
        try:
            index = int(self.addon.getSetting(self.name + "_sort_by") or "0")
        except (TypeError, ValueError):
            index = 0
        index = index if 0 <= index < len(self.sort_options) else 0
        option = self.sort_options[index]
        return self._absolute(self.sort_paths[option]), "{} [COLOR yellow]{}[/COLOR]".format(self.label, option)

    def _videos(self, page_html):
        videos, seen = [], set()
        for block in re.findall(r"<article\b[\s\S]*?</article>", page_html or "", re.I):
            link_match = re.search(r"<a\b[^>]*\bhref\s*=\s*(?:\"([^\"]+)\"|'([^']+)'|([^\s>]+))", block, re.I)
            if not link_match:
                continue
            target = self._absolute(next(value for value in link_match.groups() if value is not None))
            if target in seen or urllib.parse.urlparse(target).netloc not in urllib.parse.urlparse(self.base_url).netloc:
                continue
            title = self._attr(link_match.group(0), "title")
            if not title:
                title_match = re.search(r"<header\b[^>]*>[\s\S]*?<span[^>]*>(.*?)</span>", block, re.I)
                title = self._clean(title_match.group(1)) if title_match else ""
            if not title:
                continue
            thumb = self._attr(block, "data-main-thumb")
            if not thumb:
                image = re.search(r"<img\b[^>]+>", block, re.I)
                thumb = self._attr(image.group(0), "data-src") or self._attr(image.group(0), "src") if image else ""
            if thumb.startswith("data:"):
                thumb = ""
            duration_match = re.search(r"class\s*=\s*(?:\"[^\"]*duration[^\"]*\"|'[^']*duration[^']*'|duration)[^>]*>[\s\S]*?((?:\d{1,2}:)?\d{1,2}:\d{2})", block, re.I)
            duration = duration_match.group(1) if duration_match else ""
            seconds = self.convert_duration(duration)
            info = {"title": title, "plot": title}
            if seconds:
                info["duration"] = seconds
            seen.add(target)
            videos.append((title, target, self._absolute(thumb) if thumb else self.icon, duration, info))
        return videos

    def process_content(self, url, page=1):
        start_url, _ = self.get_start_url_and_label()
        is_root = (
            not url
            or url == "BOOTSTRAP"
            or url.rstrip("/") == start_url.rstrip("/")
        )
        if not url or url == "BOOTSTRAP":
            url = start_url
        is_search = "?s=" in url or "&s=" in url
        is_category = "/category/" in url
        if is_root or (not is_search and not is_category):
            self.add_dir("Search", "", 5, self.icons.get("search", self.icon), name_param=self.name)
            self.add_dir("Categories", self.base_url + "/", 8, self.icons.get("categories", self.icon))
        page_html = self._get(url)
        if not page_html:
            self.end_directory("videos")
            return
        main_match = re.search(r"<main\b[^>]*id\s*=\s*['\"]?main['\"]?[^>]*>([\s\S]*?)</main>", page_html, re.I)
        listing_html = main_match.group(1) if main_match else page_html
        for title, target, thumb, duration, info in self._videos(listing_html):
            label = title + (" [COLOR lime]({})[/COLOR]".format(duration) if duration else "")
            self.add_link(label, target, 4, thumb, self.fanart, info_labels=info)
        next_url = self._next_url(listing_html, url)
        if next_url:
            self.add_dir("[COLOR blue]Next Page >>>[/COLOR]", next_url, 2, self.icons.get("default", self.icon))
        self.end_directory("videos")

    def _next_url(self, page_html, current_url):
        patterns = (
            r"<a[^>]+rel\s*=\s*['\"]next['\"][^>]+href\s*=\s*['\"]([^'\"]+)",
            r"<a[^>]+href\s*=\s*['\"]([^'\"]+)['\"][^>]+rel\s*=\s*['\"]next['\"]",
            r"<a[^>]+class\s*=\s*['\"][^'\"]*next[^'\"]*['\"][^>]+href\s*=\s*['\"]([^'\"]+)",
            r"<a[^>]+href\s*=\s*['\"]([^'\"]+)['\"][^>]*>\s*Next\s*</a>",
        )
        for pattern in patterns:
            match = re.search(pattern, page_html or "", re.I)
            if match:
                return self._absolute(match.group(1))
        current = re.search(r"/page/(\d+)/?", current_url)
        page_number = int(current.group(1)) if current else 1
        query = urllib.parse.urlsplit(current_url).query
        candidate = self.base_url + "/page/{}/".format(page_number + 1)
        if query:
            candidate += "?" + query
        if re.search(r"href\s*=\s*['\"]?{}(?:['\"\s>])".format(re.escape(candidate)), page_html or "", re.I):
            return candidate
        return ""

    def process_categories(self, url):
        page_html = self._get(self.base_url + "/")
        seen = set()
        for label, target in self.extra_categories:
            target = self._absolute(target)
            seen.add(target)
            self.add_dir(label, target, 2, self.icons.get("categories", self.icon))
        pattern = (
            r"<a[^>]+href\s*=\s*(?:\"([^\"]*/category/[^\"]+)\"|'([^']*/category/[^']+)'|"
            r"([^\s>]+/category/[^\s>]+))[^>]*>([\s\S]*?)</a>"
        )
        for double_url, single_url, plain_url, label in re.findall(pattern, page_html, re.I):
            target = double_url or single_url or plain_url
            target = self._absolute(target)
            name = self._clean(label)
            if not name:
                slug = urllib.parse.urlsplit(target).path.rstrip("/").rsplit("/", 1)[-1]
                name = slug.replace("-", " ").title()
            if name and target not in seen:
                seen.add(target)
                self.add_dir(name, target, 2, self.icons.get("categories", self.icon))
        self.end_directory("videos")

    def search(self, query):
        if query:
            self.process_content(self.search_url.format(urllib.parse.quote_plus(query.strip())))

    def _mirrors(self, page_html):
        mirrors = []
        for value in re.findall(r"<iframe[^>]+src\s*=\s*(?:\"([^\"]+)\"|'([^']+)'|([^\s>]+))", page_html or "", re.I):
            target = self._absolute(next(item for item in value if item))
            if resolver.resolver_entry_for_url(target) and target not in mirrors:
                mirrors.append(target)
        return resolver.sort_urls_by_resolver_preference(mirrors, self.addon)

    def resolve_recording_stream(self, url):
        page_html = self._get(url, referer=self.base_url + "/")
        stream, headers, _ = resolver.resolve_first_working(
            self._mirrors(page_html), referer=url,
            headers={"User-Agent": self.ua, "Referer": url}, addon=self.addon,
        )
        if not stream:
            return None
        lowered = stream.lower().split("?", 1)[0]
        is_hls = ".m3u8" in lowered or "/hls" in lowered or lowered.endswith("master.txt")
        return {"url": stream, "headers": headers or {}, "extension": "m3u8" if is_hls else "mp4"}

    def play_video(self, url):
        resolved = self.resolve_recording_stream(url)
        if not resolved:
            self.notify_error("Could not resolve a working stream")
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
            return
        if resolved["extension"] == "m3u8":
            if xbmc.getCondVisibility("System.Platform.Android"):
                play_url = resolved["url"]
                if resolved["headers"]:
                    play_url += "|" + urllib.parse.urlencode(resolved["headers"])
                item = xbmcgui.ListItem(path=play_url)
                item.setProperty("IsPlayable", "true")
                item.setProperty("inputstream", "inputstream.adaptive")
                item.setProperty("inputstream.adaptive.manifest_type", "hls")
                encoded_headers = urllib.parse.urlencode(resolved["headers"] or {})
                item.setProperty("inputstream.adaptive.manifest_headers", encoded_headers)
                item.setProperty("inputstream.adaptive.stream_headers", encoded_headers)
                item.setMimeType("application/vnd.apple.mpegurl")
                item.setContentLookup(False)
                xbmcplugin.setResolvedUrl(self.addon_handle, True, item)
                return
            controller = HlsProxyController(
                resolved["url"], headers=resolved["headers"], session=self.session
            )
            play_url = controller.start()
            PlaybackGuard(xbmc.Player(), xbmc.Monitor(), play_url, controller).start()
            item = xbmcgui.ListItem(path=play_url)
            item.setProperty("IsPlayable", "true")
            item.setMimeType("application/vnd.apple.mpegurl")
            item.setContentLookup(False)
            xbmcplugin.setResolvedUrl(self.addon_handle, True, item)
            return
        controller = ProxyController(
            resolved["url"],
            upstream_headers=resolved["headers"],
            session=self.session,
            skip_resolve=True,
            probe_size=True,
            use_urllib=False,
        )
        play_url = controller.start()
        PlaybackGuard(xbmc.Player(), xbmc.Monitor(), play_url, controller).start()
        item = xbmcgui.ListItem(path=play_url)
        item.setProperty("IsPlayable", "true")
        item.setMimeType("video/mp4")
        item.setContentLookup(False)
        xbmcplugin.setResolvedUrl(self.addon_handle, True, item)
