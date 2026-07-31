#!/usr/bin/env python
# -*- coding: utf-8 -*-

import base64
import html
import os
import re
import sys
import urllib.parse

vendor_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "lib", "vendor")
if os.path.isdir(vendor_path) and vendor_path not in sys.path:
    sys.path.insert(0, vendor_path)

import cloudscraper
import xbmc
import xbmcgui
import xbmcplugin

from resources.lib.base_website import BaseWebsite
from resources.lib.proxy_utils import HlsProxyController, PlaybackGuard
from resources.lib.resolvers import resolver
from resources.lib.thumb_proxy import build_thumb_url


class JAVGuru(BaseWebsite):
    sort_options = ["Latest", "Trending"]
    sort_paths = {
        "Latest": "/",
        "Trending": "/category/jav/?orderby=likes-today&order=DESC",
    }

    def __init__(self, addon_handle, addon=None):
        super().__init__(
            "javguru",
            "https://jav.guru/",
            "https://jav.guru/?s={}",
            addon_handle,
            addon,
        )
        self.ua = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
        )
        self.session = cloudscraper.create_scraper(
            browser={"browser": "chrome", "platform": "windows", "desktop": True}
        )
        self.session.headers.update(self._headers())

    def _headers(self, referer=None, accept=None):
        return {
            "User-Agent": self.ua,
            "Referer": referer or self.base_url,
            "Accept": accept or "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "identity",
        }

    def _get(self, url, referer=None):
        try:
            response = self.session.get(url, headers=self._headers(referer), timeout=25)
            if response.status_code == 200:
                return response.text
            self.logger.warning("JAV Guru HTTP %s for %s", response.status_code, url)
        except Exception as exc:
            self.logger.warning("JAV Guru request failed for %s: %s", url, exc)
        return ""

    def get_start_url_and_label(self):
        url, label = super().get_start_url_and_label()
        return url, label.replace("Javguru", "JAV Guru")

    def _page_url(self, url, page):
        if page <= 1:
            return url
        parsed = urllib.parse.urlparse(url)
        if parsed.query:
            query = urllib.parse.parse_qs(parsed.query)
            query["paged"] = [str(page)]
            return urllib.parse.urlunparse(
                (parsed.scheme, parsed.netloc, parsed.path, parsed.params,
                 urllib.parse.urlencode(query, doseq=True), parsed.fragment)
            )
        path = re.sub(r"/page/\d+/?$", "/", parsed.path)
        path = path.rstrip("/") + "/page/{}/".format(page)
        return urllib.parse.urlunparse(
            (parsed.scheme, parsed.netloc, path, parsed.params, parsed.query, parsed.fragment)
        )

    def _items(self, content):
        items = []
        seen = set()
        blocks = re.findall(
            r'<div class="inside-article">([\s\S]*?)</div>\s*</div>\s*</div>',
            content or "",
            re.IGNORECASE,
        )
        for block in blocks:
            href_match = re.search(r'<a\b[^>]+href=["\'](https://jav\.guru/[^"\']+/)["\']', block, re.IGNORECASE)
            img_match = re.search(r'<img\b[^>]+src=["\']([^"\']+)["\'][^>]*>', block, re.IGNORECASE)
            title_match = re.search(r'<h2\b[^>]*>([\s\S]*?)</h2>', block, re.IGNORECASE)
            if not title_match:
                title_match = re.search(r'<img\b[^>]+alt=["\']([^"\']+)["\']', block, re.IGNORECASE)
            if not href_match or not title_match:
                continue
            video_url = html.unescape(href_match.group(1))
            if video_url in seen:
                continue
            seen.add(video_url)
            title = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html.unescape(title_match.group(1)))).strip()
            thumb = html.unescape(img_match.group(1)) if img_match else self.icon
            if thumb.startswith("http"):
                thumb = build_thumb_url(thumb, referer=self.base_url)
            items.append((title, video_url, thumb))
        return items

    def process_content(self, url, page=1):
        if not url or url == "BOOTSTRAP":
            url, _ = self.get_start_url_and_label()
        if page == 1:
            self.add_dir("Search", "", 5, self.icons["search"])
            self.add_dir("Categories", "JAVGURU_CATEGORIES", 8, self.icons["categories"])
        content = self._get(self._page_url(url, page))
        items = self._items(content)
        for title, video_url, thumb in items:
            self.add_link(
                title,
                video_url,
                4,
                thumb,
                self.fanart,
                info_labels={"title": title, "plot": title},
            )
        if items and (
            'class="next page-numbers"' in content
            or re.search(r'/page/{}/'.format(page + 1), content, re.IGNORECASE)
        ):
            self.add_dir("Next Page", url, 2, self.icon, page=page + 1)
        if not items:
            self.notify_error("No JAV Guru videos found")
        self.end_directory("videos")

    def process_categories(self, url):
        for title, path in (
            ("JAV", "category/jav/"),
            ("English Subbed", "category/english-subbed/"),
            ("Decensored", "category/decensored/"),
            ("Amateur", "category/amateur/"),
            ("Idol", "category/idol/"),
            ("4K", "category/4k/"),
        ):
            self.add_dir(title, urllib.parse.urljoin(self.base_url, path), 2, self.icons["categories"])
        self.end_directory("videos")

    def search(self, query):
        if query:
            self.process_content(self.search_url.format(urllib.parse.quote_plus(query.strip())))

    def _embed_urls(self, post_url, content):
        output = []
        for encoded in re.findall(r'"iframe_url":"([A-Za-z0-9+/=]+)"', content or ""):
            try:
                outer_url = base64.b64decode(encoded).decode("utf-8")
            except Exception:
                continue
            outer = self._get(outer_url, referer=post_url)
            config_id = re.search(r"cid:\s*'([^']+)'", outer or "")
            resolver_type = re.search(r"rtype:\s*'([^']+)'", outer or "")
            if not config_id or not resolver_type:
                continue
            container = re.search(
                r'<div id="{}"[^>]+>'.format(re.escape(config_id.group(1))),
                outer,
                re.IGNORECASE,
            )
            if not container:
                continue
            parts = re.findall(r'data-[^=]+="([^"]+)"', container.group(0), re.IGNORECASE)
            if len(parts) < 3:
                continue
            token = "".join(parts)[::-1]
            redirect_url = "{}?{}r={}".format(
                urllib.parse.urljoin(outer_url, "/searcho/"),
                resolver_type.group(1),
                token,
            )
            try:
                response = self.session.get(
                    redirect_url,
                    headers=self._headers(outer_url),
                    allow_redirects=True,
                    stream=True,
                    timeout=20,
                )
                final_url = response.url
                response.close()
            except Exception:
                continue
            if resolver.resolver_entry_for_url(final_url) and final_url not in output:
                output.append(final_url)
        return output

    def resolve_recording_stream(self, url):
        page = self._get(url, referer=self.base_url)
        embeds = self._embed_urls(url, page)
        stream, headers, _ = resolver.resolve_first_working(
            embeds,
            referer=url,
            headers=self._headers(url),
            addon=self.addon,
        )
        if not stream:
            return None
        return {"url": stream, "headers": headers or {}, "extension": "m3u8"}

    def play_video(self, url):
        resolved = self.resolve_recording_stream(url)
        if not resolved:
            self.notify_error("Could not resolve a public JAV Guru mirror")
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
            return
        controller = HlsProxyController(
            resolved["url"],
            headers=resolved["headers"],
            session=self.session,
        )
        local_url = controller.start()
        item = xbmcgui.ListItem(path=local_url)
        item.setProperty("IsPlayable", "true")
        item.setMimeType("application/vnd.apple.mpegurl")
        item.setContentLookup(False)
        xbmcplugin.setResolvedUrl(self.addon_handle, True, item)
        PlaybackGuard(xbmc.Player(), xbmc.Monitor(), local_url, controller).start()
