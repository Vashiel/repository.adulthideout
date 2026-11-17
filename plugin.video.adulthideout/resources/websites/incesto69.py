# -*- coding: utf-8 -*-
import json
import urllib.parse

import xbmcgui
import xbmcplugin

from resources.lib.base_website import BaseWebsite
from resources.lib.resilient_http import fetch_text

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36"


class Incesto69(BaseWebsite):
    """Next.js site with a JSON API: /api/videos?q=&category=&cursor=, /api/categories."""

    label = "Incesto69"

    def __init__(self, addon_handle, addon=None):
        super().__init__(
            name="incesto69",
            base_url="https://incesto69.com",
            search_url="https://incesto69.com/api/videos?q={}",
            addon_handle=addon_handle,
            addon=addon,
        )

    def get_start_url_and_label(self):
        return self.base_url + "/api/videos", "Incesto69"

    def _json(self, url):
        text = fetch_text(url, headers={"User-Agent": UA, "Referer": self.base_url + "/", "Accept": "application/json"},
                          logger=self.logger, timeout=20)
        try:
            return json.loads(text or "null")
        except ValueError:
            return None

    def process_content(self, url, page=1):
        if not url or url == "BOOTSTRAP" or url.rstrip("/") == self.base_url:
            url, _ = self.get_start_url_and_label()
        data = self._json(url) or {}
        first_page = "cursor=" not in url
        if first_page:
            self.add_dir("[COLOR blue]Search[/COLOR]", "", 5, self.icons["search"], self.fanart)
            self.add_dir("Categories", self.base_url + "/api/categories", 8, self.icons["categories"], self.fanart)
        videos = data.get("data") or []
        for video in videos:
            if not video.get("cdnUrl"):
                continue
            seconds = int(video.get("duration") or 0)
            title = video.get("title") or "Incesto69"
            label = "{} [COLOR lime]({}:{:02d})[/COLOR]".format(title, seconds // 60, seconds % 60) if seconds else title
            self.add_link(label, video["cdnUrl"], 4, video.get("thumbnailUrl") or self.icon, self.fanart,
                          info_labels={"title": title, "duration": seconds, "plot": ", ".join(video.get("tags") or [])})
        if videos and data.get("hasMore") and data.get("nextCursor"):
            parts = urllib.parse.urlsplit(url)
            query = dict(urllib.parse.parse_qsl(parts.query))
            query["cursor"] = data["nextCursor"]
            next_url = urllib.parse.urlunsplit(parts._replace(query=urllib.parse.urlencode(query)))
            self.add_dir("[COLOR blue]Next Page >>>>[/COLOR]", next_url, 2, self.icons["default"], self.fanart)
        if not videos:
            self.notify_error("No Incesto69 videos found")
        self.end_directory()

    def process_categories(self, url):
        for category in self._json(self.base_url + "/api/categories") or []:
            if not category.get("slug"):
                continue
            name = "{} ({})".format(category.get("name"), category["videoCount"]) if category.get("videoCount") else category.get("name")
            self.add_dir(name, "{}/api/videos?{}".format(self.base_url, urllib.parse.urlencode({"category": category["slug"]})), 2,
                         category.get("thumbnailUrl") or self.icons["categories"], self.fanart)
        self.end_directory("files")

    def search(self, query):
        if query:
            self.process_content(self.search_url.format(urllib.parse.quote_plus(query)))

    def resolve_recording_stream(self, url):
        # Listings link the CDN file itself (stream.incesto69.com/videos/...mp4).
        return {"url": url, "headers": {"User-Agent": UA, "Referer": self.base_url + "/"}, "extension": "mp4"}

    def play_video(self, url):
        resolved = self.resolve_recording_stream(url)
        item = xbmcgui.ListItem(path=resolved["url"] + "|" + urllib.parse.urlencode(resolved["headers"]))
        item.setMimeType("video/mp4")
        item.setContentLookup(False)
        item.setProperty("IsPlayable", "true")
        xbmcplugin.setResolvedUrl(self.addon_handle, True, item)
