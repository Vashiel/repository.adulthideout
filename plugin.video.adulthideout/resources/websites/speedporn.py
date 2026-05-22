# -*- coding: utf-8 -*-
import html
import re
import sys
import urllib.parse

import requests
import xbmc
import xbmcgui
import xbmcplugin

from resources.lib.base_website import BaseWebsite
from resources.lib.resolvers import resolver


class SpeedpornWebsite(BaseWebsite):
    HOST_PRIORITY = [
        "lulustream",
        "luluvid",
        "streamtape",
        "voe.sx",
        "mixdrop",
        "doodstream",
        "doply",
    ]

    def __init__(self, addon_handle, addon=None):
        super().__init__(
            name="speedporn",
            base_url="https://speedporn.net",
            search_url="https://speedporn.net/?s={}",
            addon_handle=addon_handle,
            addon=addon,
        )
        self.session = requests.Session()
        self.ua = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/128.0.0.0 Safari/537.36"
        )

    def _headers(self, referer=None):
        return {
            "User-Agent": self.ua,
            "Referer": referer or (self.base_url + "/"),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }

    def _make_request(self, url, referer=None):
        try:
            response = self.session.get(url, headers=self._headers(referer), timeout=25)
            if response.status_code == 200:
                return response.text
            self.logger.error("[SpeedPorn] HTTP %s for %s", response.status_code, url)
        except Exception as exc:
            self.logger.error("[SpeedPorn] Request error for %s: %s", url, exc)
        return None

    def _clean(self, value):
        value = re.sub(r"<[^>]+>", " ", value or "")
        return re.sub(r"\s+", " ", html.unescape(value)).strip()

    def _absolute(self, value):
        if not value:
            return ""
        return urllib.parse.urljoin(self.base_url + "/", html.unescape(value.strip()))

    def get_start_url_and_label(self):
        return self.base_url + "/", "SpeedPorn [COLOR yellow]Latest[/COLOR]"

    def _extract_videos(self, page_html):
        items = []
        seen = set()
        blocks = re.findall(
            r'(<div[^>]+class="[^"]*video-block[^"]*"[\s\S]*?</div>\s*</div>)',
            page_html or "",
            re.IGNORECASE,
        )

        for block in blocks:
            url_match = re.search(r'<a[^>]+class="[^"]*thumb[^"]*"[^>]+href="([^"]+)"', block, re.IGNORECASE)
            if not url_match:
                url_match = re.search(r'<a[^>]+href="([^"]+)"[^>]+class="[^"]*thumb[^"]*"', block, re.IGNORECASE)
            if not url_match:
                continue

            video_url = self._absolute(url_match.group(1))
            if not video_url or video_url in seen or self.base_url not in video_url:
                continue
            seen.add(video_url)

            title = ""
            title_match = re.search(r'<a[^>]+class="[^"]*infos[^"]*"[^>]+title="([^"]+)"', block, re.IGNORECASE)
            if title_match:
                title = self._clean(title_match.group(1))
            if not title:
                title_match = re.search(r'<span[^>]+class="[^"]*title[^"]*"[^>]*>(.*?)</span>', block, re.IGNORECASE | re.DOTALL)
                title = self._clean(title_match.group(1)) if title_match else ""
            if not title:
                img_alt = re.search(r'<img[^>]+alt="([^"]+)"', block, re.IGNORECASE)
                title = self._clean(img_alt.group(1)) if img_alt else ""
            if not title:
                title = urllib.parse.unquote(video_url.rstrip("/").split("/")[-1]).replace("-", " ").title()

            thumb = self.icon
            thumb_match = re.search(r'<img[^>]+(?:data-src|data-original|src)="([^"]+)"', block, re.IGNORECASE)
            if thumb_match:
                thumb = self._absolute(thumb_match.group(1))

            duration_text = ""
            duration_match = re.search(r'<span[^>]+class="[^"]*duration[^"]*"[^>]*>(.*?)</span>', block, re.IGNORECASE | re.DOTALL)
            if duration_match:
                duration_text = self._clean(duration_match.group(1))

            views_text = ""
            views_match = re.search(r'<span[^>]+class="[^"]*views-number[^"]*"[^>]*>(.*?)</span>', block, re.IGNORECASE | re.DOTALL)
            if views_match:
                views_text = self._clean(views_match.group(1))

            info = {"title": title, "plot": title}
            duration = self.convert_duration(duration_text)
            if duration:
                info["duration"] = duration
            if views_text:
                info["plot"] = "{} | {}".format(title, views_text)

            label = title
            if duration_text:
                label = "{} [COLOR lime]({})[/COLOR]".format(title, duration_text)

            items.append({"title": label, "url": video_url, "thumb": thumb, "info": info})

        return items

    def _extract_next_page(self, page_html, current_url):
        candidates = []
        for pattern in (
            r'<a[^>]+class="[^"]*next[^"]*"[^>]+href="([^"]+)"',
            r'<a[^>]+href="([^"]+)"[^>]+class="[^"]*next[^"]*"',
            r'<a[^>]+href="([^"]+)"[^>]*>\s*(?:Next|Older|>)\s*</a>',
            r'<link[^>]+rel=["\']next["\'][^>]+href=["\']([^"\']+)["\']',
        ):
            candidates.extend(re.findall(pattern, page_html or "", re.IGNORECASE))
        for candidate in candidates:
            next_url = self._absolute(candidate)
            if next_url and next_url != current_url:
                return next_url
        return None

    def process_content(self, url, page=1):
        if not url or url == "BOOTSTRAP":
            url, _ = self.get_start_url_and_label()

        if "?s=" not in url:
            self.add_dir("Search", "", 5, self.icons.get("search", self.icon))
            self.add_dir("Categories", self.base_url + "/categories/", 8, self.icons.get("categories", self.icon))
            self.add_dir("Pornstars", "SPEEDPORN_PORNSTARS", 9, self.icons.get("pornstars", self.icon))
            self.add_dir("Studios", "SPEEDPORN_STUDIOS", 9, self.icons.get("pornstars", self.icon))
            self.add_dir("Release Years", "SPEEDPORN_YEARS", 9, self.icons.get("default", self.icon))

        page_html = self._make_request(url)
        if not page_html:
            self.end_directory("videos")
            return

        videos = self._extract_videos(page_html)
        if not videos:
            self.notify_error("No SpeedPorn videos found")
            self.end_directory("videos")
            return

        for item in videos:
            self.add_link(item["title"], item["url"], 4, item["thumb"], self.fanart, info_labels=item["info"])

        next_url = self._extract_next_page(page_html, url)
        if next_url:
            self.add_dir("[COLOR blue]Next Page >>>[/COLOR]", next_url, 2, self.icons.get("default", self.icon))

        self.end_directory("videos")

    def _extract_taxonomy_links(self, page_html, path_part):
        links = []
        seen = set()
        for match in re.finditer(r'<a[^>]+href="([^"]*%s[^"]*)"[^>]*>(.*?)</a>' % re.escape(path_part), page_html or "", re.IGNORECASE | re.DOTALL):
            target = self._absolute(match.group(1))
            label = self._clean(match.group(2))
            if not target or target in seen or not label:
                continue
            if label.lower() in ("skip to content", "speedporn"):
                continue
            seen.add(target)
            links.append((label, target))
        return links

    def process_categories(self, url):
        target = url or (self.base_url + "/categories/")
        page_html = self._make_request(target)
        if not page_html:
            self.end_directory("videos")
            return

        links = self._extract_taxonomy_links(page_html, "/genres/")
        for label, target_url in links:
            self.add_dir(label, target_url, 2, self.icons.get("categories", self.icon))

        self.end_directory("videos")

    def process_pornstars(self, url):
        if url == "SPEEDPORN_STUDIOS":
            source_url = self.base_url + "/all-porn-movie-studios/"
            path_part = "/director/"
            icon = self.icons.get("pornstars", self.icon)
        elif url == "SPEEDPORN_YEARS":
            source_url = self.base_url + "/releasing-years/"
            path_part = "/release-year/"
            icon = self.icons.get("default", self.icon)
        else:
            source_url = self.base_url + "/pornstars/"
            path_part = "/cast/"
            icon = self.icons.get("pornstars", self.icon)

        page_html = self._make_request(source_url)
        if not page_html:
            self.end_directory("videos")
            return

        links = self._extract_taxonomy_links(page_html, path_part)
        for label, target_url in links:
            self.add_dir(label, target_url, 2, icon)

        self.end_directory("videos")

    def search(self, query):
        if not query:
            return
        self.process_content(self.search_url.format(urllib.parse.quote_plus(query.strip())))

    def _normalize_hoster_url(self, url):
        url = html.unescape(url or "").replace("\\/", "/").strip()
        url = re.sub(r"(doodstream\.\w+|doply\.net)/d/", r"\1/e/", url)
        url = re.sub(r"(streamtape\.\w+)/v/", r"\1/e/", url)
        url = re.sub(r"(mixdrop\.\w+)/f/", r"\1/e/", url)
        url = url.replace("https://lulustream.com/", "https://lulustream.com/e/")
        url = url.replace("https://luluvid.com/", "https://lulustream.com/e/")
        url = re.sub(r"/e/e/", "/e/", url)
        return url

    def _extract_host_links(self, page_html):
        links = []
        seen = set()

        for pattern in (
            r'<a[^>]+href="([^"]+)"[^>]+id="#iframe"',
            r'data-fl-source="([^"]+)"',
            r'data-fl-url="([^"]+)"',
        ):
            for raw_url in re.findall(pattern, page_html or "", re.IGNORECASE):
                url = self._normalize_hoster_url(raw_url)
                lower_url = url.lower()
                if not url or not url.startswith("http") or "deleted" in lower_url or "api/" in lower_url or "://api." in lower_url:
                    continue
                if url not in seen:
                    seen.add(url)
                    links.append(url)

        host_pattern = r'https?://(?:[^/\s"\']*\.)?(?:lulustream|luluvid|streamtape|voe\.sx|mixdrop|doodstream|doply)[^\s"\'<>]+'
        for raw_url in re.findall(host_pattern, page_html or "", re.IGNORECASE):
            url = self._normalize_hoster_url(raw_url)
            lower_url = url.lower()
            if url and url not in seen and "deleted" not in lower_url and "api/" not in lower_url and "://api." not in lower_url:
                seen.add(url)
                links.append(url)

        def priority(value):
            lower = value.lower()
            for idx, host in enumerate(self.HOST_PRIORITY):
                if host in lower:
                    return idx
            return len(self.HOST_PRIORITY)

        links.sort(key=priority)
        return links

    def play_video(self, url):
        page_html = self._make_request(url)
        if not page_html:
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
            return

        host_links = self._extract_host_links(page_html)
        if not host_links:
            self.notify_error("No SpeedPorn host links found")
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
            return

        self.logger.info("[SpeedPorn] Found %d host links", len(host_links))
        stream_url = None
        stream_headers = {}

        for link in host_links:
            try:
                self.logger.info("[SpeedPorn] Trying hoster: %s", link[:100])
                result = resolver.resolve(link, referer=url, headers={"User-Agent": self.ua, "Referer": url})
                if isinstance(result, tuple):
                    candidate, headers = result
                else:
                    candidate, headers = result, {}
                if candidate and candidate.startswith("http"):
                    stream_url = candidate
                    stream_headers = headers or {}
                    break
            except Exception as exc:
                self.logger.warning("[SpeedPorn] Resolver failed for %s: %s", link[:80], exc)

        if not stream_url:
            self.notify_error("Could not resolve SpeedPorn stream")
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
            return

        play_url = stream_url
        if "|" not in play_url and stream_headers:
            play_url = play_url + "|" + urllib.parse.urlencode(stream_headers)

        list_item = xbmcgui.ListItem(path=play_url)
        list_item.setProperty("IsPlayable", "true")
        if ".m3u8" in stream_url:
            list_item.setMimeType("application/vnd.apple.mpegurl")
        else:
            list_item.setMimeType("video/mp4")
        list_item.setContentLookup(False)
        xbmcplugin.setResolvedUrl(self.addon_handle, True, list_item)
