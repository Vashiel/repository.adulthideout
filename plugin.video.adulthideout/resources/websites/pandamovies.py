# -*- coding: utf-8 -*-
import html
import re
import urllib.parse
from html.parser import HTMLParser

from resources.lib.resolvers import resolver
from resources.lib.host_links import extract_host_links
from resources.lib.movie_cards import parse_movie_cards
from resources.websites.xopenload import XopenloadWebsite


class _MovieCards(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.items = []
        self.card = None
        self.depth = 0
        self.capture = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        classes = attrs.get("class", "").split()
        if tag == "div":
            if self.card is not None:
                self.depth += 1
            elif "ml-item" in classes:
                self.card = {"url": "", "thumb": "", "title": "", "duration": ""}
                self.depth = 1
        if self.card is None:
            return
        if tag == "a" and "ml-mask" in classes:
            self.card["url"] = attrs.get("href", "")
        elif tag == "img" and not self.card["thumb"]:
            self.card["thumb"] = attrs.get("data-src") or attrs.get("src", "")
        elif tag == "h2":
            self.capture = "title"
        elif tag == "span" and any(c in classes for c in ("mli-meta", "mli-info1")):
            self.capture = "duration"

    def handle_data(self, data):
        if self.card is not None and self.capture:
            self.card[self.capture] += data

    def handle_endtag(self, tag):
        if tag in ("h2", "span"):
            self.capture = None
        if tag == "div" and self.card is not None:
            self.depth -= 1
            if self.depth == 0:
                if self.card["url"] and self.card["title"]:
                    self.items.append(self.card)
                self.card = None


class PandaMoviesWebsite(XopenloadWebsite):
    """Full-length movies with several supported embed mirrors."""

    HOST_PRIORITY = ["voe.sx", "mixdrop", "lulustream", "doodstream", "doply.net"]
    SORT_OPTIONS = ["Latest", "Most Viewed"]
    SORT_PATHS = {
        "Latest": "/",
        "Most Viewed": "/most-viewed",
    }

    def __init__(self, addon_handle, addon=None):
        super().__init__(addon_handle, addon)
        self.name = "pandamovies"
        self.base_url = "https://pandamovies.org"
        self.search_url = self.base_url + "/?s={}"
        self.directory_source_url = self.base_url + "/"

    def _get_sort_index(self):
        try:
            index = int(self.addon.getSetting("pandamovies_sort_by") or "0")
            return index if 0 <= index < len(self.SORT_OPTIONS) else 0
        except (TypeError, ValueError):
            return 0

    def get_start_url_and_label(self):
        option = self.SORT_OPTIONS[self._get_sort_index()]
        return self.base_url + self.SORT_PATHS[option], "PandaMovies [COLOR yellow]{}[/COLOR]".format(option)

    def _extract_genres(self, page_html):
        return self._extract_directory(page_html, "genre")

    def _extract_videos(self, page_html):
        parser = _MovieCards()
        parser.feed(page_html)
        items = []
        seen = set()
        for card in parser.items:
            target = urllib.parse.urljoin(self.base_url + "/", card["url"])
            if target in seen:
                continue
            seen.add(target)
            title = self._clean(card["title"])
            duration = self._clean(card["duration"])
            items.append({
                "title": title + (" [COLOR lime]({})[/COLOR]".format(duration) if duration else ""),
                "url": target,
                "thumb": urllib.parse.urljoin(self.base_url + "/", card["thumb"]) if card["thumb"] else self.icon,
                "info": {"title": title, "plot": title, "duration": duration},
            })
        return items or parse_movie_cards(page_html, self.base_url)

    def _extract_studios(self, page_html):
        return self._extract_directory(page_html, "actors")

    def _extract_directory(self, page_html, directory):
        entries = []
        seen = set()
        pattern = r'<a\s+[^>]*href=["\'](https?://pandamovies\.(?:org|pw)/{}/[^"\']+)["\'][^>]*>([\s\S]*?)</a>'.format(directory)
        for target, label_html in re.findall(pattern, page_html, re.IGNORECASE):
            target = html.unescape(target).rstrip("/")
            label = self._clean(re.sub(r"<[^>]+>", " ", label_html))
            if label and target not in seen:
                seen.add(target)
                entries.append((label, target))
        return entries

    def search(self, query):
        if query:
            self.process_content(self.search_url.format(urllib.parse.quote_plus(query.strip())))

    def _extract_host_links(self, page_html):
        links = []
        for target in extract_host_links(page_html):
            lowered = target.lower()
            if "deleted" in lowered or "/api/" in lowered:
                continue
            if resolver.resolver_entry_for_url(target):
                links.append(target)
        links.sort(key=lambda value: resolver.resolver_sort_key_for_url(value, self.addon))
        return links
