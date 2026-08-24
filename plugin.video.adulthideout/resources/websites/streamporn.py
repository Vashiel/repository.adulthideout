# -*- coding: utf-8 -*-
import html
import re
import urllib.parse

import requests
import xbmcgui
import xbmcplugin

from resources.lib.base_website import BaseWebsite
from resources.lib.resolvers import resolver


class StreamPorn(BaseWebsite):
    HOST_PRIORITY = ("voe.sx", "mixdrop", "lulustream", "dood", "doply")

    def __init__(self, addon_handle, addon=None):
        super().__init__("streamporn", "https://streamporn.li/", "https://streamporn.li/?s={}", addon_handle, addon=addon)
        self.session = requests.Session()
        self.ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/128 Safari/537.36"

    def _get(self, url, referer=None):
        try:
            response = self.session.get(url, headers={"User-Agent": self.ua, "Referer": referer or self.base_url}, timeout=25)
            # WordPress currently returns a custom 404 status for valid archives/posts.
            if response.text and (response.status_code == 200 or "Watch Online" in response.text or "Watch Movie" in response.text):
                return response.text
            self.logger.warning("[StreamPorn] HTTP %s for %s", response.status_code, url)
        except Exception as exc:
            self.logger.warning("[StreamPorn] Request failed for %s: %s", url, exc)
        return ""

    @staticmethod
    def _clean(value):
        return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", value or ""))).strip()

    @staticmethod
    def _duration_seconds(value):
        hours = re.search(r'(\d+)\s*(?:h|hr|hrs|hour|hours)\b', value or "", re.I)
        minutes = re.search(r'(\d+)\s*(?:m|min|mins|minute|minutes)\b', value or "", re.I)
        if hours or minutes:
            return int(hours.group(1) if hours else 0) * 3600 + int(minutes.group(1) if minutes else 0) * 60
        parts = [int(part) for part in re.findall(r'\d+', value or "")]
        if len(parts) == 3:
            return parts[0] * 3600 + parts[1] * 60 + parts[2]
        return 0

    def _videos(self, page):
        items, seen = [], set()
        for match in re.finditer(r'<a[^>]+href="(https://streamporn\.li/watch-xxx-[^"]+/)"[^>]*>([\s\S]*?)</a>', page or "", re.I):
            url, block = match.group(1), match.group(2)
            if url in seen:
                continue
            seen.add(url)
            image = re.search(r'<img[^>]+(?:data-src|data-lazy-src|src)="([^"]+)"', block, re.I)
            title_match = re.search(r'(?:alt|title)="([^"]+)"', block, re.I)
            title = self._clean(title_match.group(1)) if title_match else ""
            if not title or title.lower() == "watch porn online free":
                slug = url.split("/watch-xxx-", 1)[1].rsplit("-adult-movie-online-free", 1)[0]
                title = slug.replace("-", " ").title()
            thumb = html.unescape(image.group(1)) if image else self.icon
            duration_match = re.search(r'(\d+\s*(?:hrs?\.?|hours?)[^<]{0,25}|\d{1,2}:\d{2}:\d{2})', block, re.I)
            duration = self._clean(duration_match.group(1)) if duration_match else ""
            seconds = self._duration_seconds(duration)
            info = {"title": title, "plot": title}
            if seconds:
                info["duration"] = seconds
            label = "{} [COLOR lime]({})[/COLOR]".format(title, duration) if duration else title
            items.append((label, url, thumb, info))
        return items

    def process_content(self, url, page=1):
        if not url or url == "BOOTSTRAP":
            url = self.base_url
        if "?s=" not in url:
            self.add_dir("Search", "", 5, self.icons.get("search", self.icon))
            self.add_dir("Categories", self.base_url + "genre/all-sex/", 8, self.icons.get("categories", self.icon))
        page_html = self._get(url)
        for title, target, thumb, info in self._videos(page_html):
            self.add_link(title, target, 4, thumb, self.fanart, info_labels=info)
        next_match = re.search(r'<a[^>]+(?:class="[^"]*next[^"]*"[^>]+href|href)="([^"]+/page/\d+/)"', page_html, re.I)
        if next_match:
            self.add_dir("[COLOR blue]Next Page >>>[/COLOR]", next_match.group(1), 2, self.icons.get("default", self.icon))
        self.end_directory("videos")

    def process_categories(self, url):
        page_html = self._get(self.base_url)
        seen = set()
        for target, label in re.findall(r'<a[^>]+href="(https://streamporn\.li/genre/[^"]+/)"[^>]*>(.*?)</a>', page_html, re.I | re.S):
            name = self._clean(label)
            if name and target not in seen:
                seen.add(target)
                self.add_dir(name, target, 2, self.icons.get("categories", self.icon))
        self.end_directory("videos")

    def search(self, query):
        self.process_content(self.search_url.format(urllib.parse.quote_plus(query.strip())))

    def _host_links(self, page):
        links = []
        for raw in re.findall(r'<a[^>]+href="(https?://[^"]+)"[^>]+(?:id="#iframe"|title="[^"]+on [^"]+")', page or "", re.I):
            url = html.unescape(raw).replace("&amp;", "&")
            url = re.sub(r"(doodstream\.[^/]+|doply\.net)/d/", r"\1/e/", url, flags=re.I)
            url = re.sub(r"(mixdrop\.[^/]+)/f/", r"\1/e/", url, flags=re.I)
            if any(host in url.lower() for host in self.HOST_PRIORITY) and not any(dead in url.lower() for dead in ("deleted", "nitroflare", "rapidgator", "frdl")):
                links.append(url)
        links = list(dict.fromkeys(links))
        links.sort(key=lambda value: next((i for i, host in enumerate(self.HOST_PRIORITY) if host in value.lower()), 99))
        return links

    def resolve_recording_stream(self, url):
        page = self._get(url, referer=self.base_url)
        for host_url in self._host_links(page):
            try:
                result = resolver.resolve(host_url, referer=url, headers={"User-Agent": self.ua, "Referer": url})
                stream, headers = (result[0], result[1] if len(result) > 1 else {}) if isinstance(result, tuple) else (result, {})
                if stream and stream.startswith("http"):
                    return {"url": stream, "headers": headers or {}, "extension": "m3u8" if ".m3u8" in stream else "mp4"}
            except Exception as exc:
                self.logger.warning("[StreamPorn] Resolver failed for %s: %s", host_url, exc)
        return None

    def play_video(self, url):
        resolved = self.resolve_recording_stream(url)
        if not resolved:
            self.notify_error("Could not resolve StreamPorn stream")
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
            return
        play_url = resolved["url"]
        if resolved["headers"]:
            play_url += "|" + urllib.parse.urlencode(resolved["headers"])
        item = xbmcgui.ListItem(path=play_url)
        item.setProperty("IsPlayable", "true")
        item.setContentLookup(False)
        xbmcplugin.setResolvedUrl(self.addon_handle, True, item)
