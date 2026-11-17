# -*- coding: utf-8 -*-
import html
import re
import urllib.parse

import xbmcgui
import xbmcplugin

from resources.lib.base_website import BaseWebsite
from resources.lib.resilient_http import fetch_text

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36"
MEDIA = re.compile(r"""https?://[^"'\s<>\\]+\.(?:mp4|m3u8)[^"'\s<>\\]*""")


class AnyBunny(BaseWebsite):
    """anybunny.com, now on anybunny.org. Lists are tags (/new/<tag>); the home page is only a tag index."""

    label = "AnyBunny"

    def __init__(self, addon_handle, addon=None):
        super().__init__(
            name="anybunny",
            base_url="https://anybunny.org",
            search_url="https://anybunny.org/new/{}",
            addon_handle=addon_handle,
            addon=addon,
        )

    def get_start_url_and_label(self):
        return self.base_url + "/new/all", "AnyBunny"

    def _get(self, url, referer=None):
        return fetch_text(url, headers={"User-Agent": UA, "Referer": referer or self.base_url + "/"},
                          logger=self.logger, timeout=20) or ""

    def process_content(self, url, page=1):
        if not url or url == "BOOTSTRAP" or url.rstrip("/") == self.base_url:
            url, _ = self.get_start_url_and_label()
        page = int(page or 1)
        content = self._get("{}{}p={}".format(url, "&" if "?" in url else "?", page) if page > 1 else url)
        if page == 1:
            self.add_dir("[COLOR blue]Search[/COLOR]", "", 5, self.icons["search"], self.fanart)
            self.add_dir("Categories", self.base_url + "/", 8, self.icons["categories"], self.fanart)
        seen = set()
        # <a ... href='https://anybunny.org/view/<id>'> <div>mm:ss</div> ... <img src='thumb' alt='title'/>
        for block in re.split(r"(?=<a[^>]+href='https://anybunny\.org/view/)", content)[1:]:
            link = re.match(r"<a[^>]+href='(https://anybunny\.org/view/[A-Za-z0-9]+)'", block)
            image = re.search(r"<img[^>]+src='([^']+)'[^>]*alt='([^']*)'", block)
            if not link or not image or link.group(1) in seen:
                continue
            seen.add(link.group(1))
            duration = re.search(r">(\d{1,2}:\d{2}(?::\d{2})?)</div>", block)
            title = html.unescape(image.group(2)).strip() or "AnyBunny video"
            label = "{} [COLOR lime]({})[/COLOR]".format(title, duration.group(1)) if duration else title
            self.add_link(label, link.group(1), 4, image.group(1), self.fanart,
                          info_labels={"title": title, "duration": self.convert_duration(duration.group(1)) if duration else 0})
        if len(seen) >= 60:
            self.add_dir("[COLOR blue]Next Page >>>>[/COLOR]", url, 2, self.icons["default"], self.fanart, page=page + 1)
        if not seen:
            self.notify_error("No AnyBunny videos found")
        self.end_directory()

    def process_categories(self, url):
        content = self._get(self.base_url + "/")
        for path, name in dict.fromkeys(re.findall(r"href='/top/([a-z0-9_]+)'>([^<]+)</a>", content)):
            self.add_dir(html.unescape(name), "{}/new/{}".format(self.base_url, path), 2, self.icons["categories"], self.fanart)
        self.end_directory("files")

    def search(self, query):
        # The search form posts to search.php, which answers 404; tag pages take free words joined by "_".
        words = re.sub(r"[^a-z0-9]+", "_", (query or "").lower()).strip("_")
        if words:
            self.process_content(self.search_url.format(words))

    def resolve_recording_stream(self, url):
        view_html = self._get(url)
        frame = re.search(r"""<iframe[^>]+src=['"]?([^'"\s>]+)""", view_html)
        if not frame:
            return None
        frame_url = urllib.parse.urljoin(url, html.unescape(frame.group(1)))
        player = self._get(frame_url, referer=url)
        for candidate in MEDIA.findall(player):
            stream = candidate.split(":cast:")[0]
            return {"url": stream, "headers": {"User-Agent": UA, "Referer": frame_url},
                    "extension": "m3u8" if ".m3u8" in stream else "mp4"}
        return None

    def play_video(self, url):
        resolved = self.resolve_recording_stream(url)
        if not resolved:
            self.notify_error("No AnyBunny stream found")
            return xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
        item = xbmcgui.ListItem(path=resolved["url"] + "|" + urllib.parse.urlencode(resolved["headers"]))
        item.setMimeType("application/vnd.apple.mpegurl" if resolved["extension"] == "m3u8" else "video/mp4")
        item.setContentLookup(False)
        item.setProperty("IsPlayable", "true")
        xbmcplugin.setResolvedUrl(self.addon_handle, True, item)
