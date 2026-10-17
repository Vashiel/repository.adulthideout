# -*- coding: utf-8 -*-

import base64
import html
import json
import re
import urllib.parse

import requests
import xbmcgui
import xbmcplugin

from resources.lib.base_website import BaseWebsite
from resources.lib.resilient_http import fetch_text


class PornTop(BaseWebsite):
    def __init__(self, addon_handle, addon=None):
        super().__init__("porntop", "https://porntop.com/", "https://porntop.com/search/{}/", addon_handle, addon=addon)
        self.label = "PornTop"
        self.session = requests.Session()
        self.ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
        self.sort_options = ["Latest", "Most Viewed", "Top Rated", "Longest"]
        self.sort_paths = {"Latest": "/videos.php?s=l", "Most Viewed": "/videos.php?s=v", "Top Rated": "/videos.php?s=r", "Longest": "/videos.php?s=d"}

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

    def get_start_url_and_label(self):
        try:
            index = int(self.addon.getSetting("porntop_sort_by") or "0")
        except Exception:
            index = 0
        key = self.sort_options[index] if 0 <= index < len(self.sort_options) else self.sort_options[0]
        return urllib.parse.urljoin(self.base_url, self.sort_paths[key]), "{} [COLOR yellow]{}[/COLOR]".format(self.label, key)

    def get_page_url(self, url, page):
        if page <= 1:
            return url
        parsed = urllib.parse.urlparse(url)
        query = dict(urllib.parse.parse_qsl(parsed.query, keep_blank_values=True))
        query["p"] = str(page)
        return urllib.parse.urlunparse(parsed._replace(query=urllib.parse.urlencode(query)))

    @staticmethod
    def _clean(value):
        return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", value or ""))).strip()

    def _videos(self, content):
        output, seen = [], set()
        for block in re.findall(r'<div\s+class=["\']item["\'][^>]*>([\s\S]*?)(?=<div\s+class=["\']item["\']|<span\s+class=["\']pagination|$)', content or "", re.I):
            link = re.search(r'<a[^>]+href=["\']([^"\']*/video/\d+/[^"\']*)["\'][^>]*title=["\']([^"\']+)', block, re.I)
            if not link:
                continue
            url = urllib.parse.urljoin(self.base_url, html.unescape(link.group(1)))
            if url in seen:
                continue
            seen.add(url)
            image = re.search(r'<img[^>]+(?:data-original|data-src|src)=["\']([^"\']+)', block, re.I)
            duration = re.search(r'class=["\']duration["\'][^>]*>([^<]+)', block, re.I)
            title = self._clean(link.group(2))
            thumb = urllib.parse.urljoin(self.base_url, html.unescape(image.group(1))) if image else self.icon
            info = {"title": title, "plot": title}
            if duration:
                seconds = self.convert_duration(self._clean(duration.group(1)))
                if seconds:
                    info["duration"] = seconds
            output.append((title, url, thumb, info))
        return output

    def process_content(self, url, page=1, **kwargs):
        if not url or url == "BOOTSTRAP":
            url, _ = self.get_start_url_and_label()
        if page == 1:
            self.add_dir("[COLOR blue]Search[/COLOR]", "", 5, self.icons["search"])
        content = self._get(self.get_page_url(url, page))
        videos = self._videos(content)
        for title, video_url, thumb, info in videos:
            self.add_link(title, video_url, 4, thumb, self.fanart, info_labels=info)
        if videos and (re.search(r'data-page=["\']?{}\b'.format(page), content, re.I) or "data-maxpages" in content):
            self.add_dir("[COLOR blue]Next Page >>[/COLOR]", url, 2, self.icons["default"], page=page + 1)
        if not videos:
            self.notify_error("No PornTop videos found")
        self.end_directory("videos")

    def search(self, query):
        if query:
            self.process_content(self.search_url.format(urllib.parse.quote(query.strip())))

    @staticmethod
    def _normalise(value, inner=False):
        value = value.translate({0x421: "C", 0x415: "E", 0x41C: "M", 0x410: "A", 0x412: "B"})
        if not inner:
            value = value.replace(".", "b")
        else:
            value = value.replace(",", "/")
        # PornTop randomizes the final Base64 padding character per request.
        return re.sub(r"[^A-Za-z0-9+/=]", "=", value)

    def resolve_recording_stream(self, url):
        content = self._get(url, self.base_url)
        player_start = content.find("initPlayer")
        candidates = re.findall(
            r'["\']([^"\']{300,})["\']',
            content[player_start:player_start + 6000] if player_start >= 0 else "",
        )
        if not candidates:
            return None
        sources = None
        for candidate in candidates:
            try:
                outer = self._normalise(candidate)
                outer += "=" * (-len(outer) % 4)
                decoded = json.loads(base64.b64decode(outer).decode("utf-8"))
                if isinstance(decoded, list) and decoded and "video_url" in decoded[0]:
                    sources = decoded
                    break
            except Exception:
                continue
        if not sources:
            return None
        ranked = []
        rank = {"_lq.mp4": 1, "_hq.mp4": 2, "_vhq.mp4": 3}
        for source in sources:
            try:
                inner = self._normalise(source.get("video_url", ""), inner=True)
                inner += "=" * (-len(inner) % 4)
                decoded = base64.b64decode(inner).decode("utf-8", "ignore")
                path = re.search(r'(/get_file/[^\s"\'<>]+?\.mp4/\?[A-Za-z0-9=&_%.-]+)', decoded)
                if path:
                    ranked.append((rank.get(source.get("format"), 0), urllib.parse.urljoin(self.base_url, path.group(1))))
            except Exception:
                continue
        if not ranked:
            return None
        stream = max(ranked, key=lambda item: item[0])[1]
        return {"url": stream, "headers": self._headers(url), "extension": "mp4"}

    def play_video(self, url):
        resolved = self.resolve_recording_stream(url)
        if not resolved:
            self.notify_error("Could not resolve PornTop stream")
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
            return
        play_url = resolved["url"] + "|" + urllib.parse.urlencode(resolved["headers"])
        item = xbmcgui.ListItem(path=play_url)
        item.setProperty("IsPlayable", "true")
        item.setMimeType("video/mp4")
        item.setContentLookup(False)
        xbmcplugin.setResolvedUrl(self.addon_handle, True, item)
