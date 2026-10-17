# -*- coding: utf-8 -*-
import html
import re
import urllib.parse

from resources.lib.resolvers import resolver
from resources.websites.xopenload import XopenloadWebsite


class JustFullPornWebsite(XopenloadWebsite):
    SORT_OPTIONS = ["Latest"]
    SORT_PATHS = {"Latest": "/"}

    def __init__(self, addon_handle, addon=None):
        super().__init__(addon_handle, addon)
        self.name = "justfullporn"
        self.base_url = "https://bestporn4free.com"
        self.search_url = self.base_url + "/?s={}"
        self.directory_source_url = self.base_url + "/"
        self.show_studios = False

    def _get_sort_index(self):
        return 0

    def _extract_videos(self, page_html):
        items = []
        for block in re.findall(r'<article\b[\s\S]*?</article>', page_html, re.I):
            if "More Premium XXX Videos" in block:
                continue
            link = re.search(r'<a[^>]+href=["\']([^"\']+)', block, re.I)
            image = re.search(r'<img[^>]+(?:data-src|src)=["\']([^"\']+)["\'][^>]+alt=["\']([^"\']+)', block, re.I)
            if link and image:
                title = self._clean(image.group(2))
                items.append({"title": title, "url": html.unescape(link.group(1)), "thumb": html.unescape(image.group(1)), "info": {"title": title}})
        return items

    def _extract_next_page(self, page_html, current_url):
        match = re.search(r'<link[^>]+rel=["\']next["\'][^>]+href=["\']([^"\']+)', page_html, re.I)
        return html.unescape(match.group(1)) if match else None

    def _extract_genres(self, page_html):
        return self._directory(page_html, "/category/")

    def _extract_studios(self, page_html):
        return []

    def _directory(self, page_html, marker):
        result, seen = [], set()
        for target, label in re.findall(r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>([^<]+)</a>', page_html, re.I):
            if marker in target and target not in seen:
                seen.add(target); result.append((self._clean(label), html.unescape(target)))
        return result

    def _extract_host_links(self, page_html):
        links, seen = [], set()
        for url in re.findall(r'<iframe[^>]+src=["\'](https?://[^"\']+)', page_html, re.I):
            clean_url = html.unescape(url).strip()
            if clean_url not in seen and (resolver.resolver_entry_for_url(clean_url) or "vsonic" in clean_url.lower()):
                seen.add(clean_url)
                links.append(clean_url)
        return links

    def search(self, query):
        if query:
            self.process_content(self.search_url.format(urllib.parse.quote_plus(query.strip())))
