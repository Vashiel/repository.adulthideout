# -*- coding: utf-8 -*-
import html
import os
import re
import sys
import urllib.parse

import xbmcaddon

addon_path = xbmcaddon.Addon().getAddonInfo("path")
vendor_path = os.path.join(addon_path, "resources", "lib", "vendor")
if vendor_path not in sys.path:
    sys.path.insert(0, vendor_path)

import cloudscraper

from resources.lib.resolvers import resolver
from resources.websites.xopenload import XopenloadWebsite


class XXVideossWebsite(XopenloadWebsite):
    SORT_OPTIONS = ["Latest"]
    SORT_PATHS = {"Latest": "/"}

    def __init__(self, addon_handle, addon=None):
        super().__init__(addon_handle, addon)
        self.name = "xxvideoss"
        self.base_url = "https://xxvideoss.org"
        self.search_url = self.base_url + "/?s={}"
        self.directory_source_url = self.base_url + "/"
        self.show_studios = False
        self.proxy_resolved_streams = True
        self.session = cloudscraper.create_scraper(browser={"custom": self.ua})

    def _get_sort_index(self):
        return 0

    def _extract_videos(self, page_html):
        items = []
        for block in re.findall(r'<article\b[\s\S]*?</article>', page_html, re.I):
            opening = re.match(r'<article\b[^>]*>', block, re.I)
            if opening and re.search(r'\bclass=["\'][^"\']*\bsticky\b', opening.group(0), re.I):
                continue
            link = re.search(r'<a[^>]+href=["\']([^"\']+)', block, re.I)
            image = re.search(r'<img[^>]+src=["\']([^"\']+)["\'][^>]+alt=["\']([^"\']+)', block, re.I)
            if link and image:
                title = self._clean(image.group(2)).replace("\u2013", "-").replace("\u2014", "-")
                items.append({"title": title, "url": html.unescape(link.group(1)), "thumb": html.unescape(image.group(1)), "info": {"title": title}})
        return items

    def _extract_next_page(self, page_html, current_url):
        match = re.search(r'<link[^>]+rel=["\']next["\'][^>]+href=["\']([^"\']+)', page_html, re.I)
        return html.unescape(match.group(1)) if match else None

    def _extract_genres(self, page_html):
        found, seen = [], set()
        for target, label in re.findall(r'<a[^>]+href=["\']([^"\']+/category/[^"\']+)["\'][^>]*>([^<]+)</a>', page_html, re.I):
            if target not in seen:
                seen.add(target); found.append((self._clean(label), html.unescape(target)))
        return found

    def _extract_studios(self, page_html):
        return []

    def _extract_host_links(self, page_html):
        links = []
        for target in re.findall(r'<iframe[^>]+src=["\'](https?://[^"\']+)', page_html, re.I):
            target = html.unescape(target)
            if resolver.resolver_entry_for_url(target):
                links.append(target)
        return resolver.sort_urls_by_resolver_preference(links, self.addon)

    def search(self, query):
        if query:
            self.process_content(self.search_url.format(urllib.parse.quote_plus(query.strip())))
