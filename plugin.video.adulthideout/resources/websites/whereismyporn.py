#!/usr/bin/env python
# -*- coding: utf-8 -*-

import html
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

import xbmc
import xbmcaddon
import xbmcgui
import xbmcplugin

from resources.lib.base_website import BaseWebsite
from resources.lib.resolvers import resolver


class WhereIsMyPornWebsite(BaseWebsite):
    def __init__(self, addon_handle):
        addon = xbmcaddon.Addon()
        name = "whereismyporn"
        base_url = "https://whereismyporn.com/"
        search_url = "https://whereismyporn.com/?s={}"
        super(WhereIsMyPornWebsite, self).__init__(
            name, base_url, search_url, addon_handle, addon=addon
        )
        self.label = "WhereIsMyPorn"
        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/126.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }

    def get_start_url_and_label(self):
        return self.base_url, self.label

    def _http_get(self, url, referer=None, timeout=20):
        target = urllib.parse.urljoin(self.base_url, url or self.base_url)
        headers = self.headers.copy()
        headers["Referer"] = referer or self.base_url
        try:
            req = urllib.request.Request(target, headers=headers)
            with urllib.request.urlopen(req, timeout=timeout) as response:
                return response.read().decode("utf-8", errors="ignore")
        except urllib.error.HTTPError as exc:
            self.logger.warning("HTTP %s while loading %s", exc.code, target)
        except Exception as exc:
            self.logger.warning("Request failed for %s: %s", target, exc)
        return ""

    def process_content(self, url):
        current_url = url if url and url != "BOOTSTRAP" else self.base_url

        self.add_dir("[COLOR blue]Search[/COLOR]", "", 5, self.icons["search"])
        self.add_dir("[COLOR blue]Categories[/COLOR]", self.base_url, 8, self.icons["categories"])

        page = self._http_get(current_url)
        if not page:
            self.notify_error("Failed to load page.")
            self.end_directory()
            return

        items = self._parse_listing(page)
        for item in items:
            self.add_link(
                item["title"],
                item["url"],
                4,
                item.get("thumb") or self.icon,
                self.fanart,
                info_labels={"title": item["title"]},
            )

        if not items:
            self.notify_info("No videos found.")

        next_url = self._find_next_page(page)
        if next_url:
            self.add_dir("[COLOR blue]Next Page >>>>[/COLOR]", next_url, 2, self.icons["default"])

        self.end_directory()

    def process_categories(self, url=None):
        page = self._http_get(url or self.base_url)
        if not page:
            self.notify_error("Failed to load categories.")
            self.end_directory()
            return

        seen = set()
        pattern = re.compile(
            r'<a[^>]+href=["\']([^"\']*/archives/category/[^"\']+)["\'][^>]*>(.*?)</a>',
            re.IGNORECASE | re.DOTALL,
        )
        for href, label in pattern.findall(page):
            title = self._clean_text(label)
            full_url = urllib.parse.urljoin(self.base_url, html.unescape(href))
            if not title or full_url in seen:
                continue
            seen.add(full_url)
            self.add_dir(title, full_url, 2, self.icons["categories"])

        for slug in re.findall(r"\bcategory-([a-z0-9-]+)\b", page, re.IGNORECASE):
            if slug in ("post", "format-standard"):
                continue
            full_url = urllib.parse.urljoin(self.base_url, "/archives/category/" + slug)
            if full_url in seen:
                continue
            seen.add(full_url)
            self.add_dir(self._title_from_slug(slug), full_url, 2, self.icons["categories"])

        self.end_directory()

    def play_video(self, url):
        page = self._http_get(url, referer=self.base_url)
        if not page:
            self.notify_error("Failed to load video page.")
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem(path=url))
            return

        hosts = self._extract_host_links(page)
        if not hosts:
            self.notify_error("No playable hoster found.")
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem(path=url))
            return

        for host_url in hosts:
            try:
                stream_url, headers = resolver.resolve(host_url, referer=url, headers=self.headers.copy())
                if stream_url:
                    li = xbmcgui.ListItem(path=self._append_headers(stream_url, headers))
                    li.setProperty("IsPlayable", "true")
                    xbmcplugin.setResolvedUrl(self.addon_handle, True, li)
                    return
            except Exception as exc:
                self.logger.warning("Hoster resolve failed for %s: %s", host_url, exc)

        self.notify_error("No working stream found.")
        xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem(path=url))

    def search(self, query):
        if not query:
            return
        search_url = self.search_url.format(urllib.parse.quote_plus(query))
        self.process_content(search_url)

    def _parse_listing(self, page):
        items = []
        for block in re.findall(r"<article\b.*?</article>", page, re.IGNORECASE | re.DOTALL):
            link_match = re.search(r'<a[^>]+href=["\']([^"\']+)["\']', block, re.IGNORECASE)
            if not link_match:
                continue
            href = urllib.parse.urljoin(self.base_url, html.unescape(link_match.group(1)))
            if "/archives/" not in href or "/archives/category/" in href:
                continue

            title = ""
            title_match = re.search(r'<a[^>]+title=["\']([^"\']+)["\']', block, re.IGNORECASE)
            if title_match:
                title = title_match.group(1)
            if not title:
                title_match = re.search(r"<header[^>]*class=[\"'][^\"']*entry-header[^\"']*[\"'][^>]*>.*?<span>(.*?)</span>", block, re.IGNORECASE | re.DOTALL)
                if title_match:
                    title = title_match.group(1)
            if not title:
                alt_match = re.search(r'<img[^>]+alt=["\']([^"\']+)["\']', block, re.IGNORECASE)
                if alt_match:
                    title = alt_match.group(1)

            thumb = ""
            thumb_match = re.search(r'data-main-thumb=["\']([^"\']+)["\']', block, re.IGNORECASE)
            if not thumb_match:
                thumb_match = re.search(r'<img[^>]+(?:data-src|src)=["\']([^"\']+)["\']', block, re.IGNORECASE)
            if thumb_match:
                thumb = urllib.parse.urljoin(self.base_url, html.unescape(thumb_match.group(1)))

            clean_title = self._clean_text(title)
            if clean_title:
                items.append({"title": clean_title, "url": href, "thumb": thumb})

        return items

    def _extract_host_links(self, page):
        links = []
        player_match = re.search(
            r'<div[^>]+class=["\'][^"\']*video-player[^"\']*["\'][^>]*>(.*?)</div>\s*</div>',
            page,
            re.IGNORECASE | re.DOTALL,
        )
        source = player_match.group(1) if player_match else page
        for match in re.findall(r'<iframe[^>]+src=["\']([^"\']+)["\']', source, re.IGNORECASE):
            link = html.unescape(match)
            if link.startswith("//"):
                link = "https:" + link
            link = urllib.parse.urljoin(self.base_url, link)
            host = urllib.parse.urlparse(link).netloc.lower()
            if not host or "whereismyporn.com" in host:
                continue
            if any(ad_host in host for ad_host in ("willingcease", "doubleclick", "google")):
                continue
            if link not in links:
                links.append(link)
        return links

    def _find_next_page(self, page):
        patterns = (
            r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>\s*Next\s*</a>',
            r'<link[^>]+rel=["\']next["\'][^>]+href=["\']([^"\']+)["\']',
            r'<a[^>]+class=["\'][^"\']*next[^"\']*["\'][^>]+href=["\']([^"\']+)["\']',
            r'<a[^>]+href=["\']([^"\']+)["\'][^>]+class=["\'][^"\']*next[^"\']*["\']',
        )
        for pattern in patterns:
            match = re.search(pattern, page, re.IGNORECASE)
            if match:
                return urllib.parse.urljoin(self.base_url, html.unescape(match.group(1)))
        return None

    def _append_headers(self, stream_url, headers):
        if not headers or "|" in stream_url:
            return stream_url
        return stream_url + "|" + urllib.parse.urlencode(headers)

    def _clean_text(self, value):
        value = html.unescape(value or "")
        value = re.sub(r"<[^>]+>", " ", value)
        value = re.sub(r"\s+", " ", value)
        return value.strip()

    def _title_from_slug(self, slug):
        words = [part for part in re.split(r"[-_]+", slug or "") if part]
        return " ".join(word.capitalize() for word in words) or slug
