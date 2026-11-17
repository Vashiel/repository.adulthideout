# -*- coding: utf-8 -*-
import html
import re
import urllib.parse

import xbmcgui
import xbmcplugin

from resources.lib.base_website import BaseWebsite
from resources.lib.resilient_http import fetch_text

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36"


class TabooDude(BaseWebsite):
    label = "TabooDude"
    sort_options = ["Latest", "Most Viewed", "Longest", "Quality"]
    sort_paths = {
        "Latest": "/",
        "Most Viewed": "/?sort_by=most-viewed",
        "Longest": "/?sort_by=longest",
        "Quality": "/?sort_by=quality",
    }

    def __init__(self, addon_handle, addon=None):
        super().__init__(
            name="taboodude",
            base_url="https://taboodude.com",
            search_url="https://taboodude.com/search?q={}",
            addon_handle=addon_handle,
            addon=addon,
        )

    def _get(self, url, referer=None):
        return fetch_text(url, headers={"User-Agent": UA, "Referer": referer or self.base_url + "/"},
                          logger=self.logger, timeout=20) or ""

    def _page_url(self, url, page):
        parts = urllib.parse.urlsplit(url)
        query = dict(urllib.parse.parse_qsl(parts.query))
        query["page"] = str(page)
        return urllib.parse.urlunsplit(parts._replace(query=urllib.parse.urlencode(query)))

    def process_content(self, url, page=1):
        if not url or url == "BOOTSTRAP":
            url, _ = self.get_start_url_and_label()
        page = int(page or 1)
        content = self._get(self._page_url(url, page) if page > 1 else url)
        if page == 1:
            self.add_dir("[COLOR blue]Search[/COLOR]", "", 5, self.icons["search"], self.fanart)
            self.add_dir("Categories", self.base_url + "/category/", 8, self.icons["categories"], self.fanart)
        count = 0
        for block in re.split(r'<div class="item\b', content)[1:]:
            link = re.search(r'<a href="(/video/[^"]+)" title="([^"]+)"', block)
            if not link:
                continue
            thumb = re.search(r'data-original="([^"]+)"', block)
            duration = re.search(r'class="duration"[^>]*>\s*([\d:]+)', block)
            title = html.unescape(link.group(2))
            label = "{} [COLOR lime]({})[/COLOR]".format(title, duration.group(1)) if duration else title
            self.add_link(label, self.base_url + link.group(1), 4, thumb.group(1) if thumb else self.icon, self.fanart,
                          info_labels={"title": title, "duration": self.convert_duration(duration.group(1)) if duration else 0})
            count += 1
        if count and re.search(r'href="[^"]*[?&]page={}\b'.format(page + 1), content):
            self.add_dir("[COLOR blue]Next Page >>>>[/COLOR]", url, 2, self.icons["default"], self.fanart, page=page + 1)
        if not count:
            self.notify_error("No TabooDude videos found")
        self.end_directory()

    def process_categories(self, url):
        content = self._get(url or self.base_url + "/category/")
        seen = set()
        for path, name in re.findall(r'<a[^>]+href="(/category/[^"]+)"[^>]*title="([^"]+)"', content):
            if path in seen:
                continue
            seen.add(path)
            self.add_dir(html.unescape(name), self.base_url + path, 2, self.icons["categories"], self.fanart)
        if not seen:
            for path in dict.fromkeys(re.findall(r'href="(/category/[a-z0-9-]+)"', content)):
                name = re.sub(r"-\d+$", "", path.rsplit("/", 1)[-1]).replace("-", " ").title()
                self.add_dir(name, self.base_url + path, 2, self.icons["categories"], self.fanart)
        self.end_directory("files")

    def search(self, query):
        if query:
            self.process_content(self.search_url.format(urllib.parse.quote_plus(query)))

    def resolve_recording_stream(self, url):
        page = self._get(url)
        match = re.search(r'https://cdn\.taboodude\.com/video/[^"\'\s<>]+\.mp4[^"\'\s<>]*', page)
        if not match:
            return None
        return {"url": html.unescape(match.group(0)), "headers": {"User-Agent": UA, "Referer": url}, "extension": "mp4"}

    def play_video(self, url):
        resolved = self.resolve_recording_stream(url)
        if not resolved:
            self.notify_error("No TabooDude stream found")
            return xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
        item = xbmcgui.ListItem(path=resolved["url"] + "|" + urllib.parse.urlencode(resolved["headers"]))
        item.setMimeType("video/mp4")
        item.setContentLookup(False)
        item.setProperty("IsPlayable", "true")
        xbmcplugin.setResolvedUrl(self.addon_handle, True, item)
