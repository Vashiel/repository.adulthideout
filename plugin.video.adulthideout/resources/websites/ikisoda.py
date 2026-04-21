# -*- coding: utf-8 -*-
import html
import re
import urllib.parse

import requests
import xbmcgui
import xbmcplugin

from resources.lib.base_website import BaseWebsite
from resources.lib.decoders.kvs_decoder import kvs_decode_url


class IkisodaWebsite(BaseWebsite):
    def __init__(self, addon_handle):
        super().__init__(
            name="ikisoda",
            base_url="https://ikisoda.com/",
            search_url="https://ikisoda.com/search/{}/",
            addon_handle=addon_handle,
        )
        self.ua = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/123.0.0.0 Safari/537.36"
        )
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": self.ua,
                "Accept-Language": "en-US,en;q=0.9",
            }
        )
        self.sort_options = ["Recently Added", "Latest Releases", "Most Viewed", "Best Rated"]
        self.sort_paths = {
            "Recently Added": "videos/?videos_per_page=30&sort_by=post_date",
            "Latest Releases": "videos/?videos_per_page=30&sort_by=custom1",
            "Most Viewed": "videos/?videos_per_page=30&sort_by=video_viewed",
            "Best Rated": "videos/?videos_per_page=30&sort_by=rating",
        }

    def _headers(self, referer=None, accept=None):
        return {
            "User-Agent": self.ua,
            "Referer": referer or self.base_url,
            "Accept": accept or "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }

    def _fetch(self, url, referer=None):
        try:
            response = self.session.get(url, headers=self._headers(referer=referer), timeout=25)
            if response.status_code == 200:
                return response.text
            self.logger.warning("[Ikisoda] HTTP %s for %s", response.status_code, url)
        except Exception as exc:
            self.logger.warning("[Ikisoda] Fetch failed for %s: %s", url, exc)
        return None

    def _absolute(self, value):
        if not value:
            return ""
        value = re.sub(r"\s+", "", html.unescape(value.strip()))
        return urllib.parse.urljoin(self.base_url, value)

    def _clean_text(self, value):
        value = re.sub(r"<[^>]+>", " ", value or "")
        return re.sub(r"\s+", " ", html.unescape(value)).strip()

    def _is_real_thumb(self, value):
        if not value:
            return False
        lowered = html.unescape(value).strip().lower()
        if lowered.startswith("data:"):
            return False
        return lowered.startswith(("http://", "https://", "//", "/"))

    def _extract_thumbnail(self, block):
        for attr in ("data-original", "data-webp", "data-src", "data-thumb", "poster"):
            match = re.search(r'%s="([^"]+)"' % attr, block, re.IGNORECASE)
            if match and self._is_real_thumb(match.group(1)):
                return self._absolute(match.group(1))

        for attr in ("srcset", "data-srcset"):
            match = re.search(r'%s="([^"]+)"' % attr, block, re.IGNORECASE)
            if match:
                candidates = [part.strip().split(" ")[0] for part in html.unescape(match.group(1)).split(",")]
                for candidate in reversed(candidates):
                    if self._is_real_thumb(candidate):
                        return self._absolute(candidate)

        for src in re.findall(r'\ssrc="([^"]+)"', block, re.IGNORECASE):
            if self._is_real_thumb(src):
                return self._absolute(src)
        return self.icon

    def _extract_title(self, block, url):
        for pattern in (
            r'<img[^>]+alt="([^"]+)"',
            r'<div[^>]+class="[^"]*is-item-title[^"]*"[^>]*>(.*?)</div>',
            r'<a[^>]+class="[^"]*is-item-link-video[^"]*"[^>]*title="([^"]+)"',
        ):
            match = re.search(pattern, block, re.IGNORECASE | re.DOTALL)
            if match:
                title = self._clean_text(match.group(1))
                if title:
                    return title
        return urllib.parse.unquote(url.rstrip("/").split("/")[-1]).replace("-", " ").title()

    def _extract_listing_items(self, html_content):
        items = []
        seen = set()
        pattern = re.compile(
            r'(<div[^>]+class="[^"]*is-item item[^"]*"[\s\S]*?'
            r'<a[^>]+class="[^"]*is-item-link-video[^"]*"[^>]+href="([^"]+)"[\s\S]*?</div>\s*</div>)',
            re.IGNORECASE,
        )
        for block, href in pattern.findall(html_content or ""):
            url = self._absolute(href)
            if not url or "/videos/" not in url or url in seen:
                continue
            seen.add(url)

            duration_match = re.search(
                r'<div[^>]+class="[^"]*is-item-duration[^"]*"[^>]*>\s*([^<]+)',
                block,
                re.IGNORECASE,
            )
            duration_text = self._clean_text(duration_match.group(1)) if duration_match else ""
            title = self._extract_title(block, url)
            thumb = self._extract_thumbnail(block)
            info = {"title": title, "plot": title}
            duration = self.convert_duration(duration_text)
            if duration:
                info["duration"] = duration

            items.append({"title": title, "url": url, "thumb": thumb, "info": info})
        return items

    def _extract_next_page(self, html_content):
        match = re.search(
            r'<li[^>]+class="[^"]*next[^"]*"[\s\S]*?<a[^>]+href="([^"]+)"',
            html_content or "",
            re.IGNORECASE,
        )
        if match:
            return self._absolute(match.group(1))
        return None

    def _extract_categories(self, html_content):
        categories = []
        seen = set()
        pattern = re.compile(
            r'<a[^>]+class="[^"]*is-item item[^"]*"[^>]+href="([^"]*/categories/[^"]+/)"[\s\S]*?</a>',
            re.IGNORECASE,
        )
        for block in pattern.findall(html_content or ""):
            href = block
            start = html_content.rfind("<a", 0, html_content.find(href))
            end = html_content.find("</a>", html_content.find(href))
            item_block = html_content[start : end + 4] if start != -1 and end != -1 else ""
            url = self._absolute(href)
            if not url or url in seen:
                continue
            seen.add(url)

            title = ""
            title_match = re.search(r'<div[^>]+class="[^"]*is-item-title[^"]*"[^>]*>\s*([^<]+)', item_block, re.IGNORECASE)
            if title_match:
                title = self._clean_text(title_match.group(1))
            if not title:
                img_match = re.search(r'<img[^>]+alt="([^"]+)"', item_block, re.IGNORECASE)
                title = self._clean_text(img_match.group(1)) if img_match else ""
            if not title:
                title = urllib.parse.unquote(url.rstrip("/").split("/")[-1]).replace("-", " ").title()

            categories.append((title, url, self._extract_thumbnail(item_block)))
        return categories

    def process_content(self, url):
        if not url or url == "BOOTSTRAP" or url.rstrip("/") == self.base_url.rstrip("/"):
            url = urllib.parse.urljoin(self.base_url, self.sort_paths[self.sort_options[0]])

        self.add_dir("Search", "", 5, self.icons.get("search", self.icon))
        self.add_dir("Categories", "IKISODA_CATEGORIES", 8, self.icons.get("categories", self.icon))

        html_content = self._fetch(url)
        if not html_content:
            self.notify_error("Ikisoda fetch failed")
            self.end_directory("videos")
            return

        for item in self._extract_listing_items(html_content):
            self.add_link(item["title"], item["url"], 4, item["thumb"], self.fanart, info_labels=item["info"])

        next_page = self._extract_next_page(html_content)
        if next_page and next_page != url:
            self.add_dir("Next Page", next_page, 2, self.icons.get("default", self.icon))

        self.end_directory("videos")

    def process_categories(self, url):
        category_url = url if url and url != "IKISODA_CATEGORIES" else "https://ikisoda.com/categories/"
        html_content = self._fetch(category_url)
        if not html_content:
            self.notify_error("Ikisoda categories failed")
            self.end_directory("videos")
            return

        for title, target, thumb in self._extract_categories(html_content):
            self.add_dir(title, target, 2, thumb or self.icons.get("categories", self.icon))

        next_page = self._extract_next_page(html_content)
        if next_page and next_page != category_url:
            self.add_dir("Next Page", next_page, 8, self.icons.get("default", self.icon))
        self.end_directory("videos")

    def search(self, query):
        if not query:
            return
        clean_query = urllib.parse.quote_plus(query.strip()).replace("+", "-")
        self.process_content(self.search_url.format(clean_query))

    def _extract_streams(self, html_content):
        license_match = re.search(r"license_code\s*:\s*'([^']+)'", html_content or "", re.IGNORECASE)
        license_code = license_match.group(1).strip() if license_match else ""
        priority = {"video_alt_url3": 0, "video_alt_url2": 1, "video_alt_url": 2, "video_url": 3}
        streams = []
        for key, value in re.findall(r"(video(?:_alt_url\d*|_url)?)\s*:\s*'([^']+)'", html_content or "", re.IGNORECASE):
            stream_url = html.unescape(value.strip())
            if stream_url.startswith("function/0/") and license_code:
                stream_url = kvs_decode_url(stream_url, license_code)
            elif stream_url.startswith("function/0/"):
                stream_url = stream_url[len("function/0/") :]
            if stream_url.startswith("/"):
                stream_url = urllib.parse.urljoin(self.base_url, stream_url)
            if stream_url.startswith("http"):
                streams.append((priority.get(key, 99), stream_url))
        streams.sort(key=lambda item: item[0])
        return [stream for _, stream in streams]

    def play_video(self, url):
        html_content = self._fetch(url)
        streams = self._extract_streams(html_content)
        if not streams:
            self.notify_error("Ikisoda: Could not resolve video stream")
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
            return

        headers = {
            "User-Agent": self.ua,
            "Referer": url,
            "Origin": self.base_url.rstrip("/"),
            "Accept": "*/*",
            "Accept-Language": "en-US,en;q=0.9",
        }
        cookies = self.session.cookies.get_dict()
        if cookies:
            headers["Cookie"] = "; ".join("{}={}".format(key, value) for key, value in cookies.items())

        list_item = xbmcgui.ListItem(path=streams[0] + "|" + urllib.parse.urlencode(headers))
        list_item.setProperty("IsPlayable", "true")
        list_item.setMimeType("video/mp4")
        xbmcplugin.setResolvedUrl(self.addon_handle, True, list_item)
