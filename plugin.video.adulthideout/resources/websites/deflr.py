# -*- coding: utf-8 -*-

import base64
import concurrent.futures
import html
import json
import re
import urllib.parse

import requests

from resources.lib.wordpress_api_tube import WordPressApiTube


class DEFLR(WordPressApiTube):
    def __init__(self, addon_handle, addon=None):
        super().__init__("deflr", "DEFLR", "https://deflr.com/", addon_handle, addon)

    def _post_artwork(self, post):
        url = self._absolute(post.get("link"))
        if not url:
            return url, "", 0
        try:
            response = requests.get(url, headers=self._headers(self.base_url), timeout=20)
            page = response.text if response.status_code == 200 else ""
        except Exception:
            page = ""
        poster = ""
        stream_url = ""
        payload = re.search(r'<iframe\b[^>]+src=["\'][^"\']*[?&]d=([^&"\']+)', page, re.I)
        if payload:
            try:
                data = json.loads(
                    base64.b64decode(html.unescape(payload.group(1)) + "===").decode("utf-8")
                )
                poster = data.get("p") or ""
                stream_url = data.get("l") or ""
            except (TypeError, ValueError, UnicodeDecodeError):
                poster = ""
        if poster and "media.xhot.cloud" in poster:
            poster = poster.replace("https://", "http://")
        if stream_url and "media.xhot.cloud" in stream_url:
            stream_url = stream_url.replace("https://", "http://")
        duration = 0
        if stream_url:
            try:
                playlist = requests.get(stream_url, headers=self._headers(url, "*/*"), timeout=20).text
                if "#EXT-X-STREAM-INF" in playlist:
                    lines = [line.strip() for line in playlist.splitlines()]
                    variants = [
                        lines[index + 1] for index, line in enumerate(lines[:-1])
                        if line.startswith("#EXT-X-STREAM-INF") and lines[index + 1] and not lines[index + 1].startswith("#")
                    ]
                    if variants:
                        media_url = urllib.parse.urljoin(stream_url, variants[-1])
                        playlist = requests.get(media_url, headers=self._headers(url, "*/*"), timeout=20).text
                duration = int(round(sum(float(value) for value in re.findall(r"#EXTINF:([0-9.]+)", playlist))))
            except Exception:
                duration = 0
        return url, poster, duration

    def _video_items(self, posts):
        items = super()._video_items(posts)
        if not items:
            return items
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
            details = dict(
                (url, (poster, duration))
                for url, poster, duration in executor.map(self._post_artwork, posts or [])
            )
        for item in items:
            poster, duration = details.get(item["url"], ("", 0))
            if poster:
                item["thumb"] = self._absolute(poster)
            if duration:
                plain_title = item["info"]["title"]
                hours, remainder = divmod(duration, 3600)
                minutes, seconds = divmod(remainder, 60)
                duration_text = "{}:{:02d}:{:02d}".format(hours, minutes, seconds) if hours else "{}:{:02d}".format(minutes, seconds)
                item["title"] = "{} [COLOR lime]({})[/COLOR]".format(plain_title, duration_text)
                item["info"]["duration"] = duration
        return items

    def resolve_recording_stream(self, url):
        page = self._get(url, referer=self.base_url)
        match = re.search(r'<iframe\b[^>]+src=["\'][^"\']*[?&]d=([^&"\']+)', page or "", re.I)
        if not match:
            return None
        try:
            payload = base64.b64decode(html.unescape(match.group(1)) + "===").decode("utf-8")
            stream_url = json.loads(payload).get("l")
        except (TypeError, ValueError, UnicodeDecodeError):
            return None
        if not stream_url or ".m3u8" not in stream_url.lower():
            return None
        if "media.xhot.cloud" in stream_url:
            stream_url = stream_url.replace("https://", "http://")
        return {"url": stream_url, "headers": self._headers(url, "*/*"), "extension": "m3u8"}
