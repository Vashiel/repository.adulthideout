# -*- coding: utf-8 -*-
import base64
import html
import re
import urllib.parse

import requests
import xbmc
import xbmcgui
import xbmcplugin

from resources.lib.base_website import BaseWebsite


class RetroStreamNetworkWebsite(BaseWebsite):
    label = "Retro Stream"
    search_param = "s"

    def __init__(self, name, label, base_url, addon_handle, addon=None, search_param="s"):
        self.label = label
        self.search_param = search_param
        base_url = base_url.rstrip("/") + "/"
        super().__init__(
            name=name,
            base_url=base_url,
            search_url=base_url + "?{}={{}}".format(search_param),
            addon_handle=addon_handle,
            addon=addon,
        )
        self.session = requests.Session()
        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "sec-ch-ua": '"Google Chrome";v="125", "Chromium";v="125", "Not.A/Brand";v="24"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
            "sec-fetch-dest": "document",
            "sec-fetch-mode": "navigate",
            "sec-fetch-site": "none",
            "sec-fetch-user": "?1",
            "upgrade-insecure-requests": "1",
        }

    def make_request(self, url, referer=None):
        headers = dict(self.headers)
        if referer:
            headers["Referer"] = referer
            headers["sec-fetch-site"] = "same-origin"
        try:
            response = self.session.get(url, headers=headers, timeout=18, allow_redirects=True)
            if response.status_code == 200 and "Just a moment" not in response.text:
                return response.text
            self.logger.warning("%s returned HTTP %s", url, response.status_code)
        except Exception as exc:
            self.logger.warning("Request failed for %s: %s", url, exc)
        return ""

    @staticmethod
    def _clean(value):
        value = re.sub(r"<[^>]+>", " ", value or "")
        return re.sub(r"\s+", " ", html.unescape(value)).strip()

    def _absolute(self, value):
        value = html.unescape(value or "").replace("\\/", "/")
        if value.startswith("//"):
            return "https:" + value
        return urllib.parse.urljoin(self.base_url, value)

    def _decode_video_url(self, click_url):
        try:
            parsed = urllib.parse.urlparse(self._absolute(click_url))
            encoded = urllib.parse.parse_qs(parsed.query).get("g", [""])[0]
            decoded = base64.b64decode(encoded[::-1] + "===").decode("utf-8")
            return self._absolute(decoded)
        except Exception as exc:
            self.logger.warning("Could not decode video URL: %s", exc)
            return ""

    @staticmethod
    def _nearest_duration(content, anchor_pos):
        matches = list(re.finditer(r"(?<!\d)(?:\d{1,2}:)?\d{1,2}:\d{2}(?!\d)", content))
        if not matches:
            return ""
        return min(matches, key=lambda item: abs(item.start() - anchor_pos)).group(0)

    def _extract_videos(self, content):
        videos = []
        seen = set()
        anchors = list(re.finditer(
            r'<a\b[^>]*href=["\']([^"\']*?/c/\?[^"\']+)["\'][^>]*>',
            content or "",
            re.IGNORECASE,
        ))
        for index, match in enumerate(anchors):
            decoded_url = self._decode_video_url(match.group(1))
            if not decoded_url or decoded_url in seen:
                continue
            left = max(0, match.start() - 260)
            right = anchors[index + 1].start() if index + 1 < len(anchors) else match.start() + 1400
            right = min(right, match.start() + 1400)
            block = content[left:right]
            local_anchor = match.start() - left

            image = re.search(r'<img\b[^>]+(?:src|data-src)=["\']([^"\']+)', block[local_anchor:], re.IGNORECASE)
            thumb = self._absolute(image.group(1)) if image else self.icon

            title = ""
            for pattern in (
                r'class=["\']?(?:ebs|bqh|wrap)["\']?[^>]*>(.*?)</(?:div|span)>',
                r'</a>\s*<div\b[^>]*>\s*<div\b[^>]*>(.*?)</div>',
                r'<img\b[^>]+(?:alt|title)=["\']([^"\']+)',
            ):
                title_match = re.search(pattern, block[local_anchor:], re.IGNORECASE | re.DOTALL)
                if title_match:
                    title = self._clean(title_match.group(1))
                    if title:
                        break
            if not title:
                continue

            duration = self._nearest_duration(block, local_anchor)
            info = {"title": title, "plot": title}
            if duration:
                info["duration"] = self.convert_duration(duration)
            label = "{} [COLOR lime]({})[/COLOR]".format(title, duration) if duration else title
            videos.append({"label": label, "url": decoded_url, "thumb": thumb, "info": info})
            seen.add(decoded_url)
        return videos

    def _add_navigation(self):
        self.add_dir("Search {}".format(self.label), "", 5, self.icons["search"], name_param=self.name)
        categories_url = self.base_url + "?ah_view=categories"
        self.add_dir("Categories", categories_url, 2, self.icons["categories"])

    def _process_categories(self):
        content = self.make_request(self.base_url)
        seen = set()
        ignored = {
            "home", "categories", "live sex", "privacy", "terms", "contact", "support",
            "english", "deutsch", "francais", "espanol", "italiano", "russian",
        }
        for href, body in re.findall(
            r'<a\b[^>]+href=["\'](/[^"\'?#]+/)["\'][^>]*>(.*?)</a>',
            content,
            re.IGNORECASE | re.DOTALL,
        ):
            title = self._clean(body)
            slug = href.strip("/").lower()
            if not title or title.lower() in ignored or slug in ignored or len(slug.split("/")) != 1:
                continue
            if title.lower() in seen or re.search(r"(?:login|sign|language|favicon|android|apple)", slug):
                continue
            seen.add(title.lower())
            self.add_dir(title, self._absolute(href), 2, self.icons["categories"])
        self.end_directory("videos")

    def process_content(self, url):
        if not url or url == "BOOTSTRAP":
            url = self.base_url
        parsed = urllib.parse.urlparse(url)
        query = urllib.parse.parse_qs(parsed.query)
        if query.get("ah_view") == ["categories"]:
            return self._process_categories()

        content = self.make_request(url)
        if not content:
            self.notify_error("Could not load website")
            return self.end_directory("videos")

        is_search = self.search_param in query
        if not is_search:
            self._add_navigation()
        for video in self._extract_videos(content):
            self.add_link(video["label"], video["url"], 4, video["thumb"], self.fanart, info_labels=video["info"])
        self.end_directory("videos")

    def _resolve(self, url):
        content = self.make_request(url)
        stream_match = re.search(
            r'<source\b[^>]+src=["\']([^"\']+\.(?:m3u8|mp4)[^"\']*)["\']',
            content or "",
            re.IGNORECASE,
        )
        if not stream_match:
            stream_match = re.search(r'(https?[^"\']+\.(?:m3u8|mp4)[^"\']*)', content or "", re.IGNORECASE)
        return self._absolute(stream_match.group(1)) if stream_match else ""

    def resolve_recording_stream(self, url):
        stream = self._resolve(url)
        if not stream:
            return None
        return {
            "url": stream,
            "headers": {"User-Agent": self.headers["User-Agent"], "Referer": url},
            "extension": "m3u8" if ".m3u8" in stream else "mp4",
        }

    def play_video(self, url):
        resolved = self.resolve_recording_stream(url)
        if not resolved:
            self.notify_error("Could not resolve stream")
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
            return
        headers = urllib.parse.urlencode(resolved["headers"])
        item = xbmcgui.ListItem(path="{}|{}".format(resolved["url"], headers))
        item.setProperty("IsPlayable", "true")
        item.setContentLookup(False)
        if resolved["extension"] == "m3u8":
            item.setMimeType("application/vnd.apple.mpegurl")
            if xbmc.getCondVisibility("System.HasAddon(inputstream.adaptive)"):
                item.setProperty("inputstream", "inputstream.adaptive")
                item.setProperty("inputstream.adaptive.manifest_type", "hls")
                item.setProperty("inputstream.adaptive.manifest_headers", headers)
                item.setProperty("inputstream.adaptive.stream_headers", headers)
        else:
            item.setMimeType("video/mp4")
        xbmcplugin.setResolvedUrl(self.addon_handle, True, item)
