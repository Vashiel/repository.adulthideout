# -*- coding: utf-8 -*-

import html
import re
import urllib.parse

import requests
import xbmcgui
import xbmcplugin

from resources.lib.base_website import BaseWebsite
from resources.lib.resolvers import resolver
from resources.lib.resilient_http import fetch_text


class LatestLeaks(BaseWebsite):
    def __init__(self, addon_handle, addon=None):
        super().__init__("latestleaks", "https://latestleaks.co/", "https://latestleaks.co/?s={}", addon_handle, addon=addon)
        self.label = "LatestLeaks"
        self.session = requests.Session()
        self.ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
        self.sort_options = ["Latest"]

    def _headers(self, referer=None):
        return {"User-Agent": self.ua, "Referer": referer or self.base_url, "Accept-Encoding": "identity"}

    def _get(self, url, referer=None):
        try:
            response = self.session.get(url, headers=self._headers(referer), timeout=20)
            if response.status_code == 200:
                return response.text
        except Exception:
            pass
        return fetch_text(url, headers=self._headers(referer), logger=self.logger, timeout=20) or ""

    def get_page_url(self, url, page):
        if page <= 1:
            return url
        parsed = urllib.parse.urlparse(url)
        if parsed.query:
            query = dict(urllib.parse.parse_qsl(parsed.query))
            query["paged"] = str(page)
            return urllib.parse.urlunparse(parsed._replace(query=urllib.parse.urlencode(query)))
        return urllib.parse.urljoin(url.rstrip("/") + "/", "page/{}/".format(page))

    def _videos(self, content):
        output, seen = [], set()
        for match in re.finditer(r'<a[^>]+href=["\'](https?://latestleaks\.co/[^"\']+/)["\'][^>]*>[\s\S]{0,500}?<img[^>]+(?:data-src|data-lazy-src|src)=["\']([^"\']+)["\'][^>]*alt=["\']([^"\']+)', content or "", re.I):
            url, thumb, title = match.groups()
            if url in seen or "/page/" in url or "/category/" in url or "/tag/" in url:
                continue
            seen.add(url)
            title = html.unescape(title).strip()
            if thumb.startswith("data:"):
                continue
            output.append((title, url, html.unescape(thumb), {"title": title, "plot": title}))
        return output

    def process_content(self, url, page=1, **kwargs):
        if not url or url == "BOOTSTRAP":
            url = self.base_url
        if page == 1:
            self.add_dir("[COLOR blue]Search[/COLOR]", "", 5, self.icons["search"])
        content = self._get(self.get_page_url(url, page))
        videos = self._videos(content)
        for title, video_url, thumb, info in videos:
            self.add_link(title, video_url, 4, thumb, self.fanart, info_labels=info)
        if videos and re.search(r'(?:rel=["\']next["\']|/page/{}/)'.format(page + 1), content, re.I):
            self.add_dir("[COLOR blue]Next Page >>[/COLOR]", url, 2, self.icons["default"], page=page + 1)
        if not videos:
            self.notify_error("No LatestLeaks videos found")
        self.end_directory("videos")

    def search(self, query):
        if query:
            self.process_content(self.search_url.format(urllib.parse.quote_plus(query.strip())))

    def resolve_recording_stream(self, url):
        content = self._get(url, self.base_url)
        if not content:
            return None

        links, seen = [], set()
        for iframe_src in re.findall(r'<iframe\b[^>]+src=["\']([^"\']+)["\']', content, re.I):
            clean_url = html.unescape(iframe_src).strip()
            if clean_url not in seen and resolver.resolver_entry_for_url(clean_url):
                seen.add(clean_url)
                links.append(clean_url)

        if not links:
            for m in re.finditer(r'<iframe[^>]+src=["\'](https?://[^"\']+)', content, re.I):
                clean_url = html.unescape(m.group(1)).strip()
                if clean_url not in seen:
                    seen.add(clean_url)
                    links.append(clean_url)

        stream_url, headers, _ = resolver.resolve_first_working(
            links,
            referer=url,
            headers={"User-Agent": self.ua, "Referer": url},
            addon=self.addon,
        )
        if stream_url:
            ext = "m3u8" if ".m3u8" in stream_url.lower() else "mp4"
            return {"url": stream_url, "headers": headers or {}, "extension": ext}
        return None

    def play_video(self, url):
        resolved = self.resolve_recording_stream(url)
        if not resolved:
            self.notify_error("Could not resolve LatestLeaks stream")
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
            return
        play_url = resolved["url"]
        if resolved.get("headers"):
            play_url += "|" + urllib.parse.urlencode(resolved["headers"])
        item = xbmcgui.ListItem(path=play_url)
        item.setProperty("IsPlayable", "true")
        mime = "application/vnd.apple.mpegurl" if resolved["extension"] == "m3u8" else "video/mp4"
        item.setMimeType(mime)
        item.setContentLookup(False)
        xbmcplugin.setResolvedUrl(self.addon_handle, True, item)
