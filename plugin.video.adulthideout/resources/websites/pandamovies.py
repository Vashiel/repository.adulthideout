# -*- coding: utf-8 -*-
import html
import re
import urllib.parse

from resources.lib.resolvers import resolver
from resources.websites.xopenload import XopenloadWebsite


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
        self.base_url = "https://pandamovies.pw"
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

    def _extract_studios(self, page_html):
        return self._extract_directory(page_html, "actors")

    def _extract_directory(self, page_html, directory):
        entries = []
        seen = set()
        pattern = r'<a\s+[^>]*href=["\'](https?://pandamovies\.pw/{}/[^"\']+)["\'][^>]*>([\s\S]*?)</a>'.format(directory)
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
        seen = set()
        for target in re.findall(r'(?:data-fl-url|href)=["\'](https?://[^"\']+)["\']', page_html, re.IGNORECASE):
            target = html.unescape(target).strip()
            lowered = target.lower()
            if "deleted" in lowered or "/api/" in lowered:
                continue
            if resolver.resolver_entry_for_url(target) and target not in seen:
                seen.add(target)
                links.append(target)
        links.sort(key=lambda value: resolver.resolver_sort_key_for_url(value, self.addon))
        return links
