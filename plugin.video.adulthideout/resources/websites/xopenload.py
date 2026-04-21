# -*- coding: utf-8 -*-
import html
import re
import sys
import urllib.parse

import xbmc
import xbmcgui
import xbmcplugin

import requests

from resources.lib.base_website import BaseWebsite
from resources.lib.resolvers import resolver


class XopenloadWebsite(BaseWebsite):
    """Scraper for xopenload.net – full-length movie site.

    Video pages contain links to multiple hosters (MixDrop, StreamTape,
    DoodStream, Voe) that are resolved via the existing resolver stack.
    """

    # Preferred host order (first match wins for auto-play)
    HOST_PRIORITY = ["mixdrop", "streamtape", "doodstream", "voe.sx", "lulustream"]

    SORT_OPTIONS = ["Latest", "Most Viewed", "Most Rating"]
    SORT_PATHS = {
        "Latest": "/movies/",
        "Most Viewed": "/most-viewed/",
        "Most Rating": "/most-rating/",
    }

    def __init__(self, addon_handle, addon=None):
        super().__init__(
            name="xopenload",
            base_url="https://xopenload.net",
            search_url="https://xopenload.net/?s={}",
            addon_handle=addon_handle,
            addon=addon,
        )
        self.session = requests.Session()
        self.ua = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/128.0.0.0 Safari/537.36"
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _headers(self, referer=None):
        return {
            "User-Agent": self.ua,
            "Referer": referer or (self.base_url + "/"),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }

    def _make_request(self, url, referer=None):
        try:
            response = self.session.get(
                url, headers=self._headers(referer=referer), timeout=20
            )
            if response.status_code == 200:
                return response.text
            self.logger.error(
                "[XOpenload] HTTP %s for %s", response.status_code, url
            )
        except Exception as exc:
            self.logger.error("[XOpenload] Request error for %s: %s", url, exc)
        return None

    def _clean(self, text):
        if not text:
            return ""
        return re.sub(r"\s+", " ", html.unescape(str(text))).strip()

    # ------------------------------------------------------------------
    # Sort / start URL
    # ------------------------------------------------------------------
    def _get_sort_index(self):
        try:
            idx = int(self.addon.getSetting("xopenload_sort_by") or "0")
            if 0 <= idx < len(self.SORT_OPTIONS):
                return idx
        except (ValueError, TypeError):
            pass
        return 0

    def get_start_url_and_label(self):
        sort_option = self.SORT_OPTIONS[self._get_sort_index()]
        path = self.SORT_PATHS.get(sort_option, "/movies/")
        url = self.base_url + path
        label = "XOpenload [COLOR yellow]{}[/COLOR]".format(sort_option)
        return url, label

    def _build_context_menu(self):
        return [
            (
                "Sort by...",
                "RunPlugin({}?mode=7&action=select_sort&website={})".format(
                    sys.argv[0], self.name
                ),
            ),
        ]

    def select_sort(self, original_url=None):
        dialog = xbmcgui.Dialog()
        current = self._get_sort_index()
        idx = dialog.select("Sort by...", self.SORT_OPTIONS, preselect=current)
        if idx == -1:
            return
        self.addon.setSetting("xopenload_sort_by", str(idx))
        new_url, _ = self.get_start_url_and_label()
        xbmc.executebuiltin(
            "Container.Update({}?mode=2&website={}&url={},replace)".format(
                sys.argv[0], self.name, urllib.parse.quote_plus(new_url)
            )
        )

    # ------------------------------------------------------------------
    # Listing extraction
    # ------------------------------------------------------------------
    def _extract_videos(self, page_html):
        """Parse video items from an HTML listing page."""
        items = []
        # Each video card: <a class="ml-mask jt" href="...">...<img src>...<h2>...<span class="mli-info1">
        blocks = re.findall(
            r'<a[^>]+href="([^"]+)"[^>]+class="[^"]*ml-mask[^"]*"[^>]*>'
            r"([\s\S]*?)</a>",
            page_html,
            re.IGNORECASE,
        )
        for href, inner in blocks:
            # Title
            h2 = re.search(r"<h2>([^<]+)</h2>", inner, re.IGNORECASE)
            if not h2:
                continue
            title = self._clean(h2.group(1))
            if not title:
                continue

            # Thumbnail
            thumb_match = re.search(
                r'<img[^>]+src="([^"]+)"', inner, re.IGNORECASE
            )
            thumb = thumb_match.group(1) if thumb_match else self.icon

            # Duration
            dur_match = re.search(
                r'<span[^>]+class="[^"]*mli-info1[^"]*"[^>]*>([^<]+)</span>',
                inner,
                re.IGNORECASE,
            )
            duration = self._clean(dur_match.group(1)) if dur_match else ""

            # Label
            label = title
            if duration:
                label += " [COLOR lime]({})[/COLOR]".format(duration)

            video_url = urllib.parse.urljoin(self.base_url + "/", href)
            items.append(
                {
                    "title": label,
                    "url": video_url,
                    "thumb": thumb,
                    "info": {"title": title, "plot": title, "duration": duration},
                }
            )
        return items

    def _extract_next_page(self, page_html, current_url):
        """Find the next-page link from pagination."""
        # xopenload uses: <li class='active'><a>N</a></li><li><a href='...'>N+1</a></li>
        m = re.search(
            r"""<li[^>]+class=['"]active['"][^>]*>.*?</li>\s*<li>\s*<a[^>]+href=['"]([^'"]+)['"]""",
            page_html,
            re.IGNORECASE | re.DOTALL,
        )
        if m:
            return html.unescape(m.group(1))
        return None

    # ------------------------------------------------------------------
    # Category / Genre extraction
    # ------------------------------------------------------------------
    def _extract_genres(self, page_html):
        """Extract genre links from the nav/menu."""
        genres = []
        seen = set()
        for slug, name in re.findall(
            r'<a\s+href="https?://xopenload\.net/genre/([^/]+)/?"[^>]*>([^<]+)</a>',
            page_html,
            re.IGNORECASE,
        ):
            if slug not in seen:
                seen.add(slug)
                genres.append((self._clean(name), self.base_url + "/genre/" + slug + "/"))
        return genres

    def _extract_studios(self, page_html):
        """Extract studio/director links from the nav/menu."""
        studios = []
        seen = set()
        for slug, name in re.findall(
            r'<a\s+href="https?://xopenload\.net/director/([^/]+)/?"[^>]*>([^<]+)</a>',
            page_html,
            re.IGNORECASE,
        ):
            if slug not in seen:
                seen.add(slug)
                studios.append((self._clean(name), self.base_url + "/director/" + slug + "/"))
        return studios

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------
    def process_content(self, url):
        if not url or url == "BOOTSTRAP":
            url, _ = self.get_start_url_and_label()

        page_html = self._make_request(url)
        if not page_html:
            self.notify_error("Could not load XOpenload page")
            self.end_directory("videos")
            return

        context_menu = self._build_context_menu()

        # Search + Categories links (not on search result pages)
        if "?s=" not in url:
            self.add_dir(
                "Search", "", 5, self.icons.get("search", self.icon),
                context_menu=context_menu,
            )
            self.add_dir(
                "Genres", "XOPL_GENRES", 8, self.icons.get("categories", self.icon),
                context_menu=context_menu,
            )
            self.add_dir(
                "Studios", "XOPL_STUDIOS", 9, self.icons.get("pornstars", self.icon),
                context_menu=context_menu,
            )

        videos = self._extract_videos(page_html)
        if not videos:
            self.notify_error("No XOpenload videos found")
            self.end_directory("videos")
            return

        for v in videos:
            self.add_link(
                v["title"],
                v["url"],
                4,
                v["thumb"],
                self.fanart,
                context_menu=context_menu,
                info_labels=v["info"],
            )

        next_url = self._extract_next_page(page_html, url)
        if next_url:
            self.add_dir(
                "[COLOR blue]Next Page >>>[/COLOR]",
                next_url,
                2,
                self.icons.get("default", self.icon),
                context_menu=context_menu,
            )

        self.end_directory("videos")

    def process_categories(self, url):
        """Show genre list."""
        page_html = self._make_request(self.base_url + "/movies/")
        if not page_html:
            self.notify_error("Could not load XOpenload genres")
            self.end_directory("videos")
            return

        genres = self._extract_genres(page_html)
        for name, target in genres:
            self.add_dir(name, target, 2, self.icons.get("categories", self.icon))

        self.end_directory("videos")

    def process_pornstars(self, url):
        """Show studio list (mapped to mode=9 / pornstars slot)."""
        page_html = self._make_request(self.base_url + "/movies/")
        if not page_html:
            self.notify_error("Could not load XOpenload studios")
            self.end_directory("videos")
            return

        studios = self._extract_studios(page_html)
        for name, target in studios:
            self.add_dir(name, target, 2, self.icons.get("pornstars", self.icon))

        self.end_directory("videos")

    def search(self, query):
        if not query:
            return
        search_url = "{}/?s={}".format(self.base_url, urllib.parse.quote_plus(query.strip()))
        self.process_content(search_url)

    # ------------------------------------------------------------------
    # Playback
    # ------------------------------------------------------------------
    def _extract_host_links(self, page_html):
        """Collect embed/stream links from the video page, ordered by priority."""
        links = []
        seen = set()

        # Primary pattern: data-fl-url attributes (verified links)
        for url in re.findall(r'data-fl-url="([^"]+)"', page_html, re.IGNORECASE):
            url = html.unescape(url).strip()
            if url and url.startswith("http") and url not in seen:
                seen.add(url)
                links.append(url)

        # Secondary: href inside pettabs / smart-container
        for url in re.findall(
            r'<a[^>]+href="([^"]+)"[^>]+id="#iframe"', page_html, re.IGNORECASE
        ):
            url = html.unescape(url).strip()
            if url and url.startswith("http") and url not in seen:
                seen.add(url)
                links.append(url)

        # Tertiary: any remaining hoster URLs in page
        for url in re.findall(
            r'(https?://(?:mixdrop|streamtape|doodstream|dood\.|voe\.sx|lulustream)[^\s"\'<>]+)',
            page_html,
            re.IGNORECASE,
        ):
            url = html.unescape(url).strip()
            if url not in seen and "deleted" not in url.lower() and "api" not in url.lower():
                seen.add(url)
                links.append(url)

        # Sort by priority
        def priority(u):
            u_lower = u.lower()
            for i, host in enumerate(self.HOST_PRIORITY):
                if host in u_lower:
                    return i
            return len(self.HOST_PRIORITY)

        links.sort(key=priority)
        return links

    def play_video(self, url):
        page_html = self._make_request(url)
        if not page_html:
            self.notify_error("Could not load XOpenload video page")
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
            return

        host_links = self._extract_host_links(page_html)
        if not host_links:
            self.notify_error("No playable links found on this page")
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
            return

        self.logger.info("[XOpenload] Found %d host links, trying in priority order", len(host_links))

        # Convert /d/ and /v/ links to embed /e/ format for resolving
        for i, link in enumerate(host_links):
            # DoodStream: /d/ -> /e/
            link = re.sub(r"(doodstream\.\w+)/d/", r"\1/e/", link)
            # StreamTape: /v/ -> /e/
            link = re.sub(r"(streamtape\.\w+)/v/", r"\1/e/", link)
            # MixDrop: /f/ -> /e/
            link = re.sub(r"(mixdrop\.\w+)/f/", r"\1/e/", link)
            host_links[i] = link

        stream_url = None
        headers = {}
        for link in host_links:
            self.logger.info("[XOpenload] Trying: %s", link[:80])
            try:
                result = resolver.resolve(link, referer=url, headers={"User-Agent": self.ua, "Referer": url})
                if isinstance(result, tuple):
                    resolved_url, resolved_headers = result
                else:
                    resolved_url, resolved_headers = result, {}

                if resolved_url and resolved_url.startswith("http"):
                    stream_url = resolved_url
                    headers = resolved_headers or {}
                    self.logger.info("[XOpenload] Resolved: %s", stream_url[:80])
                    break
            except Exception as exc:
                self.logger.warning("[XOpenload] Resolver failed for %s: %s", link[:60], exc)
                continue

        if not stream_url:
            self.notify_error("Could not resolve any XOpenload stream")
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
            return

        play_url = stream_url
        if "|" not in play_url and headers:
            play_url = self._append_headers(play_url, headers)

        list_item = xbmcgui.ListItem(path=play_url)
        list_item.setProperty("IsPlayable", "true")
        if ".m3u8" in stream_url:
            list_item.setMimeType("application/vnd.apple.mpegurl")
            list_item.setContentLookup(False)
        xbmcplugin.setResolvedUrl(self.addon_handle, True, list_item)

    def _append_headers(self, url, headers):
        if not headers:
            return url
        parts = []
        for key, value in headers.items():
            if value is not None:
                parts.append("{}={}".format(key, urllib.parse.quote(str(value))))
        return url + "|" + "&".join(parts) if parts else url
