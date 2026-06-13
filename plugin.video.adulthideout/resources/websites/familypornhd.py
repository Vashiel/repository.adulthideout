# -*- coding: utf-8 -*-
import html
import os
import re
import urllib.parse

import requests
import xbmcgui
import xbmcplugin

from resources.lib.base_website import BaseWebsite
from resources.lib.resolvers import resolver


class FamilyPornHD(BaseWebsite):
    """
    Scraper for https://familypornhd.com (WordPress/Bimber theme).

    Videos are embedded via an iframe pointing to watchstreamhd.com.
    The watchstreamhd_resolver handles POST->JSON->securedLink->HLS playlist rewriting.
    """

    def __init__(self, addon_handle, addon=None):
        super().__init__(
            name="familypornhd",
            base_url="https://familypornhd.com/",
            search_url="https://familypornhd.com/?s={}",
            addon_handle=addon_handle,
            addon=addon,
        )
        self.session = requests.Session()
        self.ua = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/126.0.0.0 Safari/537.36"
        )
        self.icon = os.path.join(
            self.addon.getAddonInfo("path"), "resources", "logos", "familypornhd.png"
        )
        self.icons["default"] = self.icon

    # ------------------------------------------------------------------ #
    # Internal helpers                                                     #
    # ------------------------------------------------------------------ #

    def _headers(self, referer=None):
        return {
            "User-Agent": self.ua,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "identity",
            "Referer": referer or self.base_url,
        }

    def _get(self, url, referer=None):
        try:
            response = self.session.get(
                url, headers=self._headers(referer), timeout=20
            )
            if response.status_code == 200:
                return response.text
            self.logger.warning(
                "[familypornhd] HTTP %s for %s", response.status_code, url
            )
        except Exception as exc:
            self.logger.warning("[familypornhd] Request failed for %s: %s", url, exc)
        return ""

    def _clean(self, value):
        value = html.unescape(value or "")
        value = re.sub(r"<[^>]+>", " ", value)
        value = re.sub(r"\s+", " ", value)
        return value.strip()

    def _absolute(self, url):
        if not url:
            return ""
        return urllib.parse.urljoin(self.base_url, html.unescape(url).strip())

    def _is_top_listing(self, url):
        parsed = urllib.parse.urlparse(url or self.base_url)
        query = urllib.parse.parse_qs(parsed.query)
        path = parsed.path.strip("/")
        return path in ("", "page/1") and "s" not in query

    def get_page_url(self, base_url, page_num):
        if page_num <= 1:
            return base_url
        parsed = urllib.parse.urlparse(base_url)
        path = parsed.path or "/"
        path = re.sub(r"/page/\d+/?$", "/", path)
        if path == "/":
            path = "/page/{}/".format(page_num)
        else:
            path = path.rstrip("/") + "/page/{}/".format(page_num)
        return urllib.parse.urlunparse(
            (parsed.scheme, parsed.netloc, path, parsed.params, parsed.query, "")
        )

    # ------------------------------------------------------------------ #
    # Listing extraction                                                   #
    # ------------------------------------------------------------------ #

    def _extract_videos(self, page_html):
        """
        Parse video post cards from the WordPress Bimber grid.

        The Bimber theme uses <a class="g1-frame" title="Video Title" href="URL">
        as the wrapping anchor on each thumbnail. This title attribute is the
        most reliable extraction point.
        """
        videos = []
        seen = set()

        articles = re.findall(
            r"<article\b[^>]*>([\s\S]*?)</article>", page_html, re.IGNORECASE
        )
        for art in articles:
            # Method 1: Bimber g1-frame anchor — title attr + href
            title_match = re.search(
                r'<a[^>]+title="((?:[^"\\]|\\.)*)"\s*[^>]+href="'
                r'(https?://familypornhd\.com/(?!category/|tag/|author/|page/|reaction/)[^"]+)"',
                art, re.IGNORECASE
            )
            if title_match:
                title = self._clean(title_match.group(1))
                video_url = self._absolute(title_match.group(2).strip())
            else:
                # Method 2: single-quote variant
                title_match = re.search(
                    r"<a[^>]+title='((?:[^'\\]|\\.)*)'\\s*[^>]+href='"
                    r"(https?://familypornhd\\.com/(?!category/|tag/|author/|page/|reaction/)[^']+)'",
                    art, re.IGNORECASE
                )
                if title_match:
                    title = self._clean(title_match.group(1))
                    video_url = self._absolute(title_match.group(2).strip())
                else:
                    # Method 3: rel=bookmark heading anchor
                    m3 = re.search(
                        r'<a\s[^>]+href="(https?://familypornhd\.com/(?!category/|tag/|author/|page/|reaction/)[^"]+)"'
                        r'[^>]*rel="bookmark"[^>]*>([^<]+)</a>',
                        art, re.IGNORECASE
                    )
                    if not m3:
                        continue
                    video_url = self._absolute(m3.group(1).strip())
                    title = self._clean(m3.group(2))

            if not video_url or video_url in seen:
                continue
            seen.add(video_url)

            # Thumbnail: first wp-content img inside this article
            thumb_match = re.search(
                r'<img\b[^>]+src="(https?://familypornhd\.com/wp-content/[^"\']+)"',
                art, re.IGNORECASE
            )
            thumb = thumb_match.group(1) if thumb_match else self.icon

            # Views (e.g. "6.8k Views")
            views_match = re.search(r"([\d.,]+[kKmM]?\s*Views?)", art, re.IGNORECASE)
            views_label = views_match.group(1) if views_match else ""

            label = (
                "{} [COLOR grey]({})[/COLOR]".format(title, views_label)
                if views_label
                else title
            )

            info = {"title": title, "plot": title}
            videos.append({
                "label": label,
                "url": video_url,
                "thumb": thumb,
                "info": info,
            })

        return videos

    def _extract_next_page(self, page_html, current_url, page):
        next_url = self.get_page_url(current_url, page + 1)
        next_parsed = urllib.parse.urlparse(next_url)
        next_path = next_parsed.path
        if next_path in page_html or urllib.parse.quote(next_path) in page_html:
            return next_url
        return ""

    # ------------------------------------------------------------------ #
    # Public API                                                           #
    # ------------------------------------------------------------------ #

    def process_content(self, url, page=1):
        if not url or url == "BOOTSTRAP":
            url = self.base_url

        if page == 1 and self._is_top_listing(url):
            self.add_dir("Search", "", 5, self.icons.get("search", self.icon))
            self.add_dir(
                "Categories",
                self._absolute("/categories/"),
                8,
                self.icons.get("categories", self.icon),
            )

        target_url = self.get_page_url(url, page)
        page_html = self._get(target_url)
        if not page_html:
            self.notify_error("Could not load FamilyPornHD content")
            self.end_directory("videos")
            return

        videos = self._extract_videos(page_html)
        if not videos:
            self.notify_error("No FamilyPornHD videos found")
            self.end_directory("videos")
            return

        for item in videos:
            self.add_link(
                item["label"],
                item["url"],
                4,
                item["thumb"],
                self.fanart,
                info_labels=item["info"],
            )

        next_url = self._extract_next_page(page_html, url, page)
        if next_url:
            self.add_dir(
                "Next Page",
                url,
                2,
                self.icons.get("default", self.icon),
                page=page + 1,
            )

        self.end_directory("videos")

    def process_categories(self, url):
        current_url = url or self._absolute("/categories/")
        page_html = self._get(current_url)
        if not page_html:
            page_html = self._get(self.base_url)

        seen = set()
        matches = []
        for source_html in (page_html, "" if current_url == self.base_url else self._get(self.base_url)):
            if not source_html:
                continue
            matches = re.findall(
                r'href=["\'](https?://familypornhd\.com/category/[^"\']+)["\'][^>]*>([\s\S]*?)</a>',
                source_html,
                re.IGNORECASE,
            )
            if matches:
                break
        for link, label in matches:
            href = self._absolute(link)
            title = self._clean(label)
            if not href or not title or href in seen:
                continue
            seen.add(href)
            self.add_dir(title, href, 2, self.icons.get("default", self.icon), self.fanart)

        self.end_directory("videos")

    def play_video(self, url):
        page_html = self._get(url)
        if not page_html:
            self.notify_error("Could not load FamilyPornHD video page")
            xbmcplugin.setResolvedUrl(
                self.addon_handle, False, xbmcgui.ListItem()
            )
            return

        # Extract the WatchStreamHD embed iframe
        iframes = re.findall(
            r'<iframe\b[^>]+src="([^"]+)"',
            page_html,
            re.IGNORECASE,
        )
        embed_url = None
        for iframe in iframes:
            if "watchstreamhd.com" in iframe:
                embed_url = html.unescape(iframe).strip()
                break

        if not embed_url:
            self.notify_error("Could not find WatchStreamHD embed on video page")
            xbmcplugin.setResolvedUrl(
                self.addon_handle, False, xbmcgui.ListItem()
            )
            return

        stream_url, play_headers = resolver.resolve(embed_url, referer=url)
        if not stream_url:
            self.notify_error("Could not resolve stream from WatchStreamHD")
            xbmcplugin.setResolvedUrl(
                self.addon_handle, False, xbmcgui.ListItem()
            )
            return

        import xbmc
        header_str = urllib.parse.urlencode(play_headers or {})
        play_url = stream_url
        if header_str and "|" not in play_url:
            play_url += "|" + header_str

        list_item = xbmcgui.ListItem(path=play_url)
        list_item.setProperty("IsPlayable", "true")
        list_item.setMimeType("application/vnd.apple.mpegurl")
        list_item.setContentLookup(False)

        ua = play_headers.get("User-Agent", self.ua) if play_headers else self.ua
        list_item.setProperty("User-Agent", ua)

        xbmcplugin.setResolvedUrl(self.addon_handle, True, list_item)
