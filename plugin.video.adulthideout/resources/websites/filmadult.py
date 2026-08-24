# -*- coding: utf-8 -*-
import html
import re
import urllib.parse
from concurrent.futures import ThreadPoolExecutor

import requests
import xbmc
import xbmcgui
import xbmcplugin

from resources.lib.base_website import BaseWebsite
from resources.lib.resolvers import resolver
from resources.lib.proxy_utils import HlsProxyController, PlaybackGuard


class FilmAdult(BaseWebsite):
    def __init__(self, addon_handle, addon=None):
        super().__init__(
            name="filmadult",
            base_url="https://film-adult.video/en/",
            search_url="https://film-adult.video/en/index.php?do=search&subaction=search&story={}",
            addon_handle=addon_handle,
            addon=addon,
        )
        self.session = requests.Session()
        self.ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/128 Safari/537.36"
        self._duration_cache = {}

    def _get(self, url, referer=None):
        try:
            response = self.session.get(url, headers={
                "User-Agent": self.ua,
                "Referer": referer or self.base_url,
                "Accept-Language": "en-US,en;q=0.9",
            }, timeout=25)
            if response.status_code == 200:
                return response.text
            self.logger.warning("[FilmAdult] HTTP %s for %s", response.status_code, url)
        except Exception as exc:
            self.logger.warning("[FilmAdult] Request failed for %s: %s", url, exc)
        return ""

    @staticmethod
    def _clean(value):
        return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", value or ""))).strip()

    def _absolute(self, value):
        return urllib.parse.urljoin(self.base_url, html.unescape(value or ""))

    def _videos(self, page):
        items, seen = [], set()
        pattern = re.compile(
            r'<a[^>]+class="[^"]*\bposter\b[^"]*"[^>]+href="([^"]+/\d+[^"/]*\.html)"[^>]*>([\s\S]*?)</a>',
            re.I,
        )
        for target, block in pattern.findall(page or ""):
            url = self._absolute(target)
            if url in seen:
                continue
            seen.add(url)
            title_match = re.search(r'(?:alt|title)="([^"]+)"', block, re.I)
            if not title_match:
                title_match = re.search(r'class="[^"]*title[^"]*"[^>]*>(.*?)</', block, re.I | re.S)
            title = self._clean(title_match.group(1)) if title_match else ""
            if not title:
                continue
            image = re.search(r'<img[^>]+(?:data-src|src)="([^"]+)"', block, re.I)
            thumb = self._absolute(image.group(1)) if image else self.icon
            duration = ""
            duration_match = re.search(r'(\d{1,2}:\d{2}:\d{2}|\d+\s*(?:h|hr|hours?)[^<]{0,20})', block, re.I)
            if duration_match:
                duration = self._clean(duration_match.group(1))
            info = {"title": title, "plot": title}
            seconds = self.convert_duration(duration)
            if seconds:
                info["duration"] = seconds
            items.append((title, url, thumb, info))
        return items

    def _duration_for(self, url):
        if url in self._duration_cache:
            return self._duration_cache[url]
        detail = self._get(url, referer=self.base_url + "movies/")
        match = re.search(r'itemprop="duration"\s+content="PT(\d+)S"', detail, re.I)
        seconds = int(match.group(1)) if match else 0
        self._duration_cache[url] = seconds
        return seconds

    def process_content(self, url, page=1):
        if not url or url == "BOOTSTRAP":
            url = self.base_url + "movies/"
        if "do=search" not in url:
            self.add_dir("Search", "", 5, self.icons.get("search", self.icon))
            self.add_dir("Categories", self.base_url + "movies/", 8, self.icons.get("categories", self.icon))
        page_html = self._get(url)
        videos = self._videos(page_html)
        if getattr(self, "adult_hideout_full_movie_mode", False) and videos:
            with ThreadPoolExecutor(max_workers=min(6, len(videos))) as executor:
                durations = list(executor.map(lambda item: self._duration_for(item[1]), videos))
            videos = [
                (title, target, thumb, dict(info, duration=duration) if duration else info)
                for (title, target, thumb, info), duration in zip(videos, durations)
            ]
        for title, target, thumb, info in videos:
            self.add_link(title, target, 4, thumb, self.fanart, info_labels=info)
        next_match = re.search(r'<a[^>]+href="([^"]+)"[^>]*>(?:\s*Next|\s*&gt;|\s*»)', page_html, re.I)
        if not next_match:
            current = int(re.search(r'/page/(\d+)/', url).group(1)) if re.search(r'/page/(\d+)/', url) else 1
            next_match = re.search(r'href="([^"]+/page/{}/)"'.format(current + 1), page_html, re.I)
        if next_match:
            self.add_dir("[COLOR blue]Next Page >>>[/COLOR]", self._absolute(next_match.group(1)), 2, self.icons.get("default", self.icon))
        self.end_directory("videos")

    def process_categories(self, url):
        page_html = self._get(self.base_url + "movies/")
        seen = set()
        for target, label in re.findall(r'<a[^>]+href="([^"]+/(?:watch/(?:genre|studio|country|year)|movies/hd-)[^"]+/?)"[^>]*>(.*?)</a>', page_html, re.I | re.S):
            name = self._clean(label)
            target = self._absolute(target)
            if name and target not in seen:
                seen.add(target)
                self.add_dir(name, target, 2, self.icons.get("categories", self.icon))
        self.end_directory("videos")

    def search(self, query):
        self.process_content(self.search_url.format(urllib.parse.quote_plus(query.strip())))

    def _host_links(self, page):
        links = re.findall(r'https?://(?:[^/"\']+)/(?:e|embed)/[^"\'<>\s]+', page or "", re.I)
        supported = ("filmcdn", "hgcloud", "hglink", "playmogo", "dood", "voe", "mixdrop", "streamtape", "lulustream")
        return list(dict.fromkeys(html.unescape(link) for link in links if any(host in link.lower() for host in supported)))

    def resolve_recording_stream(self, url):
        page = self._get(url, referer=self.base_url)
        for host_url in self._host_links(page):
            try:
                result = resolver.resolve(host_url, referer=url, headers={"User-Agent": self.ua, "Referer": url})
                if isinstance(result, tuple):
                    stream, headers = result[0], result[1] if len(result) > 1 else {}
                else:
                    stream, headers = result, {}
                if stream and stream.startswith("http"):
                    lowered = stream.lower().split("?", 1)[0]
                    is_hls = ".m3u8" in lowered or "/hls" in lowered or lowered.endswith("master.txt")
                    return {"url": stream, "headers": headers or {}, "extension": "m3u8" if is_hls else "mp4"}
            except Exception as exc:
                self.logger.warning("[FilmAdult] Resolver failed for %s: %s", host_url, exc)
        return None

    def play_video(self, url):
        resolved = self.resolve_recording_stream(url)
        if not resolved:
            self.notify_error("Could not resolve FilmAdult stream")
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
            return
        play_url = resolved["url"]
        if resolved["extension"] == "m3u8" and not xbmc.getCondVisibility("System.Platform.Android"):
            controller = HlsProxyController(
                play_url, headers=resolved["headers"], session=self.session
            )
            play_url = controller.start()
            PlaybackGuard(xbmc.Player(), xbmc.Monitor(), play_url, controller).start()
        elif resolved["headers"]:
            play_url += "|" + urllib.parse.urlencode(resolved["headers"])
        item = xbmcgui.ListItem(path=play_url)
        item.setProperty("IsPlayable", "true")
        if resolved["extension"] == "m3u8":
            item.setMimeType("application/vnd.apple.mpegurl")
            if xbmc.getCondVisibility("System.Platform.Android"):
                item.setProperty("inputstream", "inputstream.adaptive")
                item.setProperty("inputstream.adaptive.manifest_type", "hls")
                encoded_headers = urllib.parse.urlencode(resolved["headers"] or {})
                item.setProperty("inputstream.adaptive.manifest_headers", encoded_headers)
                item.setProperty("inputstream.adaptive.stream_headers", encoded_headers)
        item.setContentLookup(False)
        xbmcplugin.setResolvedUrl(self.addon_handle, True, item)
