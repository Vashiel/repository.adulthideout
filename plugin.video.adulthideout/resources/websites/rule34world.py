#!/usr/bin/env python
# -*- coding: utf-8 -*-

import html
import re
import urllib.parse

import requests
import xbmcgui
import xbmcplugin

from resources.lib.base_website import BaseWebsite


class Rule34World(BaseWebsite):
    sort_options = ["Latest"]
    sort_paths = {
        "Latest": "/video",
    }
    category_queries = (
        ("3D / CGI", "3d"),
        ("Anime & Manga", "hentai"),
        ("Animated", "animated"),
        ("Cartoons", "cartoon"),
        ("Cosplay", "cosplay"),
        ("Furry", "furry"),
        ("Futanari", "futanari"),
        ("Gay", "gay"),
        ("Lesbian", "lesbian"),
        ("Monster", "monster"),
        ("Straight", "straight"),
        ("Video Games", "video game"),
    )
    popular_tags = (
        "anal",
        "blowjob",
        "bondage",
        "breasts",
        "cosplay",
        "creampie",
        "cumshot",
        "dark skin",
        "femboy",
        "femdom",
        "furry",
        "futanari",
        "gay",
        "group",
        "hentai",
        "lesbian",
        "lingerie",
        "milf",
        "monster",
        "pov",
        "pregnant",
        "schoolgirl",
        "solo",
        "stockings",
        "tentacles",
        "threesome",
        "transformation",
        "uncensored",
        "uniform",
    )

    def __init__(self, addon_handle, addon=None):
        super().__init__(
            "rule34world",
            "https://rule34.world/",
            "https://rule34.world/{}/",
            addon_handle,
            addon,
        )
        self.ua = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
        )
        self.session = requests.Session()

    def _headers(self, referer=None, accept=None):
        return {
            "User-Agent": self.ua,
            "Referer": referer or self.base_url,
            "Accept": accept or "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "identity",
        }

    def _get(self, url, referer=None):
        try:
            response = self.session.get(url, headers=self._headers(referer), timeout=20)
            if response.status_code == 200:
                return response.text
            self.logger.warning("Rule34 World HTTP %s for %s", response.status_code, url)
        except Exception as exc:
            self.logger.warning("Rule34 World request failed for %s: %s", url, exc)
        return ""

    def get_start_url_and_label(self):
        url, label = super().get_start_url_and_label()
        return url, label.replace("Rule34world", "Rule34 World")

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

    def _query_url(self, query):
        slug = urllib.parse.quote(query.strip().replace(" ", "_"), safe="")
        return "{}?type=video".format(self.search_url.format(slug))

    def _items(self, content):
        items = []
        seen = set()
        card_pattern = re.compile(
            r'(<a\b[^>]+\bdata-post-id=["\']\d+["\'][^>]*>)([\s\S]*?)</a>',
            re.IGNORECASE,
        )
        for opening, block in card_pattern.findall(content or ""):
            id_match = re.search(r'data-post-id=["\'](\d+)["\']', opening, re.IGNORECASE)
            href_match = re.search(r'href=["\'](/post/\d+)["\']', opening, re.IGNORECASE)
            thumb_match = re.search(r'<video\b[^>]+poster=["\']([^"\']+)["\']', block, re.IGNORECASE)
            preview_match = re.search(
                r'<source\b[^>]+type=["\']video/mp4["\'][^>]+src=["\']([^"\']+)["\']',
                block,
                re.IGNORECASE,
            )
            duration_match = re.search(
                r'class=["\']text["\'][^>]*>(\d{1,2}:\d{2}(?::\d{2})?)',
                block,
                re.IGNORECASE,
            )
            if not all((id_match, href_match, thumb_match, preview_match, duration_match)):
                continue
            item_id = id_match.group(1)
            post_path = href_match.group(1)
            thumb = thumb_match.group(1)
            duration = duration_match.group(1)
            post_url = urllib.parse.urljoin(self.base_url, post_path)
            if post_url in seen:
                continue
            seen.add(post_url)
            title = "Rule34 #{}".format(item_id)
            label = "{} [COLOR lime]({})[/COLOR]".format(title, duration)
            thumb_url = urllib.parse.urljoin(self.base_url, html.unescape(thumb))
            thumb_url += "|" + urllib.parse.urlencode({
                "User-Agent": self.ua,
                "Referer": self.base_url,
            })
            items.append((
                label,
                post_url,
                thumb_url,
                {"title": title, "plot": title, "duration": self.convert_duration(duration)},
            ))
        return items

    def process_content(self, url, page=1):
        if not url or url == "BOOTSTRAP":
            url, _ = self.get_start_url_and_label()
        if page == 1:
            self.add_dir("Search", "", 5, self.icons["search"])
            self.add_dir("Categories", "CATEGORIES", 8, self.icons["categories"])
            self.add_dir("Tags", "TAGS", 8, self.icons["categories"])

        content = self._get(self._page_url(url, page))
        items = self._items(content)
        for label, post_url, thumb, info in items:
            self.add_link(label, post_url, 4, thumb, self.fanart, info_labels=info)
        if items and re.search(r'"hasMore":true', content or "", re.IGNORECASE):
            self.add_dir("Next Page", url, 2, self.icon, page=page + 1)
        if not items:
            self.notify_error("No Rule34 World videos found")
        self.end_directory("videos")

    def process_categories(self, url):
        if url == "CATEGORIES":
            entries = self.category_queries
        elif url == "TAGS":
            entries = tuple(
                (tag.replace("_", " ").title(), tag)
                for tag in self.popular_tags
            )
        else:
            self.process_content(url)
            return

        for label, query in entries:
            self.add_dir(
                label,
                self._query_url(query),
                2,
                self.icons["categories"],
            )
        self.end_directory("files")

    def search(self, query):
        if query:
            self.process_content(self._query_url(query))

    def resolve_recording_stream(self, url):
        match = re.search(r"/post/(\d+)", url or "")
        if not match:
            return None
        item_id = int(match.group(1))
        stream_url = "{base}posts/{group}/{item}/{item}.mov.mp4".format(
            base=self.base_url,
            group=item_id // 1000,
            item=item_id,
        )
        return {
            "url": stream_url,
            "headers": self._headers(url, accept="*/*"),
            "extension": "mp4",
        }

    def play_video(self, url):
        resolved = self.resolve_recording_stream(url)
        if not resolved:
            self.notify_error("Could not resolve Rule34 World stream")
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
            return
        play_url = "{}|{}".format(
            resolved["url"],
            urllib.parse.urlencode(resolved["headers"]),
        )
        item = xbmcgui.ListItem(path=play_url)
        item.setProperty("IsPlayable", "true")
        item.setMimeType("video/mp4")
        item.setContentLookup(False)
        xbmcplugin.setResolvedUrl(self.addon_handle, True, item)
