# -*- coding: utf-8 -*-
import html
import re
import urllib.parse

from resources.lib.resolvers import resolver
from resources.websites.xopenload import XopenloadWebsite


class SiskaWebsite(XopenloadWebsite):
    SORT_OPTIONS = ["Latest", "Most Viewed"]
    SORT_PATHS = {"Latest": "/", "Most Viewed": "/top.php"}

    def __init__(self, addon_handle, addon=None):
        super().__init__(addon_handle, addon)
        self.name = "siska"
        self.base_url = "https://siska.tv"
        self.search_url = self.base_url + "/search.php?s={}"
        self.directory_source_url = self.base_url + "/category.php"

    def _get_sort_index(self):
        try:
            value = int(self.addon.getSetting("siska_sort_by") or "0")
            return value if value in range(len(self.SORT_OPTIONS)) else 0
        except (TypeError, ValueError):
            return 0

    def _extract_videos(self, page_html):
        items = []
        pattern = r'<a[^>]+title=["\']([^"\']*)["\'][^>]+href=["\']([^"\']*video\.php\?videoID=\d+)["\'][^>]*>([\s\S]*?)</a>'
        for title, target, body in re.findall(pattern, page_html, re.IGNORECASE):
            thumb = re.search(r'data-src=["\'](https?://[^"\']+)["\']', body, re.IGNORECASE)
            if not thumb:
                thumb = re.search(r'src=["\'](https?://[^"\']+)["\']', body, re.IGNORECASE)
            duration = re.search(r'class=["\']th_video_duration["\'][^>]*>([^<]+)', body, re.IGNORECASE)
            clean_title = self._clean(title)
            if clean_title and thumb:
                items.append({"title": clean_title, "url": urllib.parse.urljoin(self.base_url, target), "thumb": html.unescape(thumb.group(1)), "info": {"title": clean_title, "duration": self._clean(duration.group(1)) if duration else ""}})
        return items

    def _extract_next_page(self, page_html, current_url):
        match = re.search(r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>\s*(?:Next|&gt;|»)', page_html, re.IGNORECASE)
        return urllib.parse.urljoin(current_url, html.unescape(match.group(1))) if match else None

    def _extract_genres(self, page_html):
        return self._directory(page_html, "category.php?c=")

    def _extract_studios(self, page_html):
        return self._directory(page_html, "chanells.php")

    def _directory(self, page_html, marker):
        found, seen = [], set()
        for target, label in re.findall(r'<a[^>]+href=["\']([^"\']*{}[^"\']*)["\'][^>]*>([\s\S]*?)</a>'.format(re.escape(marker)), page_html, re.IGNORECASE):
            name = self._clean(re.sub(r'<[^>]+>', ' ', label))
            url = urllib.parse.urljoin(self.base_url, html.unescape(target))
            if name and url not in seen:
                seen.add(url); found.append((name, url))
        return found

    def _extract_host_links(self, page_html):
        links = []
        for target in re.findall(r'<iframe[^>]+src=["\']([^"\']+)', page_html, re.IGNORECASE):
            target = html.unescape(target)
            if resolver.resolver_entry_for_url(target):
                links.append(target)
        links.sort(key=lambda value: resolver.resolver_sort_key_for_url(value, self.addon))
        return links

    def search(self, query):
        if query:
            self.process_content(self.search_url.format(urllib.parse.quote_plus(query.strip())))
