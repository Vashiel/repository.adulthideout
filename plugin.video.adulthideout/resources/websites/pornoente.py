#!/usr/bin/env python
# -*- coding: utf-8 -*-

import html
import os
import re
import sys
import urllib.parse
import urllib.request

import xbmc
import xbmcgui
import xbmcplugin

from resources.lib.base_website import BaseWebsite
from resources.lib.thumb_proxy import build_thumb_url


class PornoEnte(BaseWebsite):
    label = "PornoEnte"
    sort_options = ["Latest", "Most Viewed", "Best Rated"]
    sort_paths = {
        "Latest": "/neue-pornofilme/",
        "Most Viewed": "/meist-gesehene-pornofilme/",
        "Best Rated": "/best-bewertete-pornofilme/",
    }
    categories_path = "/kategorien/"

    def __init__(self, addon_handle, addon=None):
        super().__init__(
            name="pornoente",
            base_url="https://www.pornoente.net/",
            search_url="https://www.pornoente.net/suche/?q={}",
            addon_handle=addon_handle,
            addon=addon,
        )
        self.ua = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/130.0.0.0 Safari/537.36"
        )
        self.icon = os.path.join(
            self.addon.getAddonInfo("path"), "resources", "logos", "pornoente.png"
        )
        self.icons["default"] = self.icon

    def _headers(self, referer=None, accept=None):
        return {
            "User-Agent": self.ua,
            "Referer": referer or self.base_url,
            "Accept": accept or "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7",
        }

    def _get(self, url, referer=None):
        try:
            request = urllib.request.Request(url, headers=self._headers(referer))
            with urllib.request.urlopen(request, timeout=20) as response:
                return response.read().decode("utf-8", errors="replace")
        except Exception as exc:
            self.logger.warning("[pornoente] Request failed: %s", exc)
            return ""

    @staticmethod
    def _clean(value):
        value = re.sub(r"<[^>]+>", " ", value or "")
        return re.sub(r"\s+", " ", html.unescape(value)).strip()

    @staticmethod
    def _attribute(tag, name):
        match = re.search(
            r"\b%s\s*=\s*(?:\"([^\"]*)\"|'([^']*)'|([^\s>]+))"
            % re.escape(name),
            tag or "",
            re.I,
        )
        return next((value for value in match.groups() if value is not None), "") if match else ""

    @staticmethod
    def _duration_seconds(value):
        try:
            parts = [int(part) for part in value.split(":")]
        except (AttributeError, ValueError):
            return 0
        if len(parts) == 2:
            return parts[0] * 60 + parts[1]
        if len(parts) == 3:
            return parts[0] * 3600 + parts[1] * 60 + parts[2]
        return 0

    def get_start_url_and_label(self):
        saved = self.addon.getSetting("pornoente_sort_by")
        try:
            index = int(saved)
        except (TypeError, ValueError):
            index = 0
        if not 0 <= index < len(self.sort_options):
            index = 0
        sort_key = self.sort_options[index]
        url = urllib.parse.urljoin(self.base_url, self.sort_paths[sort_key])
        return url, "{} [COLOR yellow]{}[/COLOR]".format(self.label, sort_key)

    def is_primary_listing_url(self, url):
        if not url or url == "BOOTSTRAP":
            return True
        parsed = urllib.parse.urlparse(urllib.parse.urljoin(self.base_url, url))
        actual_query = sorted(
            (key, value)
            for key, value in urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
            if key.lower() != "p"
        )
        candidates = [self.base_url] + [
            urllib.parse.urljoin(self.base_url, path)
            for path in self.sort_paths.values()
        ]
        for candidate in candidates:
            expected = urllib.parse.urlparse(candidate)
            expected_query = sorted(
                urllib.parse.parse_qsl(expected.query, keep_blank_values=True)
            )
            if (
                parsed.netloc.lower() == expected.netloc.lower()
                and parsed.path.rstrip("/") == expected.path.rstrip("/")
                and actual_query == expected_query
            ):
                return True
        return False

    def get_page_url(self, url, page):
        parsed = urllib.parse.urlsplit(url)
        query = [
            (key, value)
            for key, value in urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
            if key.lower() != "p"
        ]
        if page > 1:
            query.append(("p", str(page)))
        return urllib.parse.urlunsplit(
            (parsed.scheme, parsed.netloc, parsed.path, urllib.parse.urlencode(query), parsed.fragment)
        )

    def _normalize_thumb(self, source):
        if not source:
            return ""
        return urllib.parse.urljoin(self.base_url, html.unescape(source.strip()))

    def _extract_videos(self, page_html):
        videos = []
        seen = set()
        cards = re.split(
            r"<div\b(?=[^>]*\bclass\s*=\s*['\"][^'\"]*\bcard\b[^'\"]*['\"])[^>]*>",
            page_html or "",
            flags=re.I,
        )
        for card in cards[1:]:
            href = re.search(r"<a\b[^>]*href=['\"]([^'\"]*/filme/[^'\"]+)['\"]", card, re.I)
            if not href:
                continue
            video_url = urllib.parse.urljoin(self.base_url, html.unescape(href.group(1)))
            if video_url in seen:
                continue

            title_block = re.search(
                r"<div\b[^>]*class=['\"][^'\"]*\btitle\b[^'\"]*['\"][^>]*>([\s\S]*?)</div>",
                card,
                re.I,
            )
            title = self._clean(title_block.group(1)) if title_block else ""
            image = re.search(r"<img\b[^>]*>", card, re.I)
            image_tag = image.group(0) if image else ""
            if not title:
                title = self._clean(self._attribute(image_tag, "alt"))
            if not title:
                continue

            thumb_source = (
                self._attribute(image_tag, "data-src")
                or self._attribute(image_tag, "data-original")
                or self._attribute(image_tag, "src")
            )
            thumb = self._normalize_thumb(thumb_source)
            if thumb:
                thumb = build_thumb_url(thumb, referer=self.base_url)

            duration_match = re.search(
                r"<span\b[^>]*class=['\"][^'\"]*\bdur\b[^'\"]*['\"][^>]*>([\s\S]*?)</span>",
                card,
                re.I,
            )
            duration_text = self._clean(duration_match.group(1)) if duration_match else ""
            duration = self._duration_seconds(duration_text)
            info = {"title": title, "plot": title}
            if duration:
                info["duration"] = duration

            seen.add(video_url)
            videos.append({"label": title, "url": video_url, "thumb": thumb, "info": info})
        return videos

    def _has_next_page(self, page_html, page):
        target = str(page + 1)
        for attrs, inner in re.findall(r"<a\b([^>]*)>([\s\S]*?)</a>", page_html or "", re.I):
            if "page" not in self._attribute(attrs, "class").split():
                continue
            href = self._attribute(attrs, "href")
            parsed = urllib.parse.urlparse(urllib.parse.urljoin(self.base_url, html.unescape(href)))
            values = urllib.parse.parse_qs(parsed.query).get("p", [])
            if target in values and self._clean(inner) == target:
                return True
        return False

    def _context_menu(self, original_url=None):
        suffix = ""
        if original_url:
            suffix = "&original_url={}".format(urllib.parse.quote_plus(original_url))
        return [
            (
                "Sort by...",
                "RunPlugin({}?mode=7&action=select_sort&website={}{})".format(
                    sys.argv[0], self.name, suffix
                ),
            )
        ]

    def process_content(self, url, page=1):
        url = self.base_url if not url or url == "BOOTSTRAP" else url
        if self.is_primary_listing_url(url):
            self.add_dir("Search", "", 5, self.icons.get("search", self.icon))
            self.add_dir("Categories", "CATEGORIES", 8, self.icons.get("categories", self.icon))

        page_html = self._get(self.get_page_url(url, page), referer=self.base_url)
        videos = self._extract_videos(page_html)
        if not videos:
            self.notify_error("Could not load PornoEnte videos")
            self.end_directory("videos")
            return

        context_menu = self._context_menu(url)
        for video in videos:
            self.add_link(
                video["label"], video["url"], 4, video["thumb"], self.fanart,
                info_labels=video["info"], context_menu=context_menu,
            )
        if self._has_next_page(page_html, page):
            self.add_dir("Next Page", url, 2, self.icons.get("default", self.icon), page=page + 1)
        self.end_directory("videos")

    def process_categories(self, url=None):
        page_html = self._get(urllib.parse.urljoin(self.base_url, self.categories_path), referer=self.base_url)
        categories = {}
        for attrs, inner in re.findall(r"<a\b([^>]*)>([\s\S]*?)</a>", page_html or "", re.I):
            href = html.unescape(self._attribute(attrs, "href"))
            parsed = urllib.parse.urlparse(urllib.parse.urljoin(self.base_url, href))
            if parsed.netloc.lower() != urllib.parse.urlparse(self.base_url).netloc.lower():
                continue
            if not parsed.path.startswith("/kategorie/"):
                continue
            image = re.search(r"<img\b[^>]*>", inner, re.I)
            image_tag = image.group(0) if image else ""
            title = self._clean(inner) or self._clean(self._attribute(image_tag, "alt"))
            if not title:
                title = urllib.parse.unquote(parsed.path.rstrip("/").split("/")[-1]).replace("-", " ").title()
            thumb_source = self._attribute(image_tag, "data-src") or self._attribute(image_tag, "src")
            thumb = self._normalize_thumb(thumb_source)
            if thumb:
                thumb = build_thumb_url(thumb, referer=self.base_url)
            categories[parsed.path] = (title, thumb)

        for path, (title, thumb) in sorted(categories.items(), key=lambda item: item[1][0].lower()):
            self.add_dir(title, urllib.parse.urljoin(self.base_url, path), 2, thumb or self.icons.get("categories", self.icon))
        self.end_directory("categories")

    def search(self, query):
        if query:
            self.process_content(self.search_url.format(urllib.parse.quote_plus(query.strip())))

    def resolve_recording_stream(self, url):
        page_html = self._get(url, referer=self.base_url)
        candidates = []
        for source_tag in re.findall(r"<source\b[^>]*>", page_html or "", re.I):
            source = self._attribute(source_tag, "src")
            if not source or not re.search(r"\.mp4(?:$|\?)", html.unescape(source), re.I):
                continue
            if "trailer" in source.lower():
                continue
            try:
                resolution = int(self._attribute(source_tag, "data-res") or 0)
            except ValueError:
                resolution = 0
            candidates.append((resolution, urllib.parse.urljoin(url, html.unescape(source))))
        if not candidates:
            return None
        stream_url = max(candidates, key=lambda item: item[0])[1]
        return {
            "url": stream_url,
            "headers": {"User-Agent": self.ua, "Referer": url},
            "extension": "mp4",
        }

    def play_video(self, url):
        resolved = self.resolve_recording_stream(url)
        if not resolved:
            self.notify_error("Could not resolve PornoEnte stream")
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
            return
        play_url = resolved["url"] + "|" + urllib.parse.urlencode(resolved["headers"])
        item = xbmcgui.ListItem(path=play_url)
        item.setProperty("IsPlayable", "true")
        item.setMimeType("video/mp4")
        item.setContentLookup(False)
        xbmcplugin.setResolvedUrl(self.addon_handle, True, item)
