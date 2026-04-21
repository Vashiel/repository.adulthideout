# -*- coding: utf-8 -*-
import html
import json
import re
import urllib.parse
import xml.etree.ElementTree as ET

import requests
import xbmcgui
import xbmcplugin

from resources.lib.base_website import BaseWebsite


class HentaiOcean(BaseWebsite):
    def __init__(self, addon_handle):
        super().__init__(
            name="hentaiocean",
            base_url="https://hentaiocean.com",
            search_url="RSS_SEARCH:{}",
            addon_handle=addon_handle,
        )
        self.session = requests.Session()
        self.ua = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
        )
        self.session.headers.update(
            {
                "User-Agent": self.ua,
                "Accept-Language": "en-US,en;q=0.9",
            }
        )
        self.page_size = 40

    def get_start_url_and_label(self):
        return "RSS:1", "HentaiOcean"

    def _fetch_text(self, url, referer=None):
        headers = {}
        if referer:
            headers["Referer"] = referer
        response = self.session.get(url, headers=headers, timeout=25)
        response.raise_for_status()
        return response.text

    def _slug_from_url(self, url):
        path = urllib.parse.urlparse(url).path.rstrip("/")
        if "/watch/" in path:
            return path.rsplit("/", 1)[-1]
        return url.rstrip("/").rsplit("/", 1)[-1]

    def _thumbnail_for_slug(self, slug):
        return urllib.parse.urljoin(self.base_url, f"/thumbnail/{slug}.webp")

    def _parse_rss_items(self):
        rss_text = self._fetch_text(urllib.parse.urljoin(self.base_url, "/rss.xml"))
        root = ET.fromstring(rss_text)
        channel = root.find("channel")
        if channel is None:
            return []

        items = []
        seen = set()
        for node in channel.findall("item"):
            title = (node.findtext("title") or "").strip()
            link = (node.findtext("link") or "").strip()
            description = (node.findtext("description") or "").strip()
            pub_date = (node.findtext("pubDate") or "").strip()
            if not title or not link:
                continue

            slug = self._slug_from_url(link)
            if slug in seen:
                continue
            seen.add(slug)
            items.append(
                {
                    "title": html.unescape(title),
                    "url": link,
                    "slug": slug,
                    "thumb": self._thumbnail_for_slug(slug),
                    "plot": html.unescape(re.sub(r"<[^>]+>", "", description)).strip(),
                    "date": pub_date,
                }
            )
        return items

    def _parse_listing_cards(self, page_html):
        results = []
        seen = set()
        pattern = re.compile(
            r'<a href="(https://hentaiocean\.com/watch/([^"]+))" class="cell card">.*?'
            r'<img src="([^"]+)" alt="([^"]+)"',
            re.I | re.S,
        )
        for video_url, slug, thumb, title in pattern.findall(page_html):
            if slug in seen:
                continue
            seen.add(slug)
            results.append(
                {
                    "title": html.unescape(title.strip()),
                    "url": video_url,
                    "slug": slug,
                    "thumb": html.unescape(thumb.strip()) or self._thumbnail_for_slug(slug),
                    "plot": "",
                    "date": "",
                }
            )
        return results

    def _add_items(self, items, context_menu=None):
        for item in items:
            info = {"title": item["title"], "plot": item.get("plot") or item["title"]}
            self.add_link(
                item["title"],
                item["url"],
                4,
                item.get("thumb") or self.icon,
                self.fanart,
                context_menu=context_menu,
                info_labels=info,
            )

    def process_content(self, url):
        context_menu = []
        self.add_dir("[COLOR blue]Search[/COLOR]", "", 5, self.icons.get("search", self.icon), context_menu=context_menu)
        self.add_dir(
            "[COLOR blue]Genres[/COLOR]",
            urllib.parse.urljoin(self.base_url, "/genre"),
            8,
            self.icons.get("categories", self.icon),
            context_menu=context_menu,
        )

        if not url or url == "BOOTSTRAP":
            url = "RSS:1"

        if url.startswith("RSS_SEARCH:"):
            query = url.split(":", 1)[1].strip().lower()
            items = [item for item in self._parse_rss_items() if query in item["title"].lower()]
            self._add_items(items, context_menu=context_menu)
            return self.end_directory("videos")

        if url.startswith("RSS:"):
            try:
                page = max(1, int(url.split(":", 1)[1]))
            except Exception:
                page = 1
            items = self._parse_rss_items()
            start = (page - 1) * self.page_size
            chunk = items[start : start + self.page_size]
            self._add_items(chunk, context_menu=context_menu)
            if start + self.page_size < len(items):
                self.add_dir(
                    "[COLOR blue]Next Page >>[/COLOR]",
                    f"RSS:{page + 1}",
                    2,
                    self.icons.get("default", self.icon),
                    context_menu=context_menu,
                )
            return self.end_directory("videos")

        page_html = self._fetch_text(url, referer=self.base_url + "/")
        self._add_items(self._parse_listing_cards(page_html), context_menu=context_menu)

        next_match = re.search(r'<a[^>]+href="([^"]+)"[^>]*>\s*Next\s*<', page_html, re.I)
        if next_match:
            next_url = urllib.parse.urljoin(self.base_url, html.unescape(next_match.group(1)))
            self.add_dir("[COLOR blue]Next Page >>[/COLOR]", next_url, 2, self.icons.get("default", self.icon), context_menu=context_menu)
        self.end_directory("videos")

    def process_categories(self, url):
        page_html = self._fetch_text(url or urllib.parse.urljoin(self.base_url, "/genre"), referer=self.base_url + "/")
        seen = set()
        for genre_url, genre_name in re.findall(r'href="(https://hentaiocean\.com/genre/([^"]+))"', page_html, re.I):
            label = html.unescape(urllib.parse.unquote(genre_name)).strip()
            if not label or label.lower() in seen:
                continue
            seen.add(label.lower())
            self.add_dir(label, genre_url, 2, self.icons.get("categories", self.icon), self.fanart)
        self.end_directory("videos")

    def _load_embed_data(self, slug):
        embed_url = urllib.parse.urljoin(self.base_url, f"/embed/{slug}")
        embed_html = self._fetch_text(embed_url, referer=urllib.parse.urljoin(self.base_url, f"/watch/{slug}"))
        data_match = re.search(r"var\s+jsondata\s*=\s*(\{.*?\})\s*</script>", embed_html, re.I | re.S)
        if not data_match:
            return None, embed_url
        return json.loads(data_match.group(1)), embed_url

    def _select_stream(self, data):
        mirrors = (data or {}).get("mirrors") or []
        for mirror in mirrors:
            mirror_url = html.unescape((mirror.get("mirrorurl") or "").replace("\\/", "/"))
            if "hentaiocean.com/play" not in mirror_url:
                continue
            parsed = urllib.parse.urlparse(mirror_url)
            query = urllib.parse.parse_qs(urllib.parse.urlparse(mirror_url).query)
            filename = (query.get("vid") or [""])[0]
            if filename and parsed.netloc:
                return f"{parsed.scheme}://{parsed.netloc}/video/" + urllib.parse.quote(filename)
        return None

    def play_video(self, url):
        slug = self._slug_from_url(url)
        data, embed_url = self._load_embed_data(slug)
        stream_url = self._select_stream(data)
        if not stream_url:
            self.notify_error("No HentaiOcean direct stream found")
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
            return

        headers = {
            "User-Agent": self.ua,
            "Referer": embed_url,
            "Origin": self.base_url,
            "Accept": "*/*",
        }
        play_url = stream_url + "|" + urllib.parse.urlencode(headers)
        list_item = xbmcgui.ListItem(path=play_url)
        list_item.setProperty("IsPlayable", "true")
        list_item.setMimeType("video/mp4")
        list_item.setContentLookup(False)
        xbmcplugin.setResolvedUrl(self.addon_handle, True, list_item)

    def search(self, query):
        if query:
            self.process_content("RSS_SEARCH:" + query)
