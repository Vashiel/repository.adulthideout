#!/usr/bin/env python
# -*- coding: utf-8 -*-

import html
import json
import re
import sys
import urllib.parse

import requests
import xbmc
import xbmcgui
import xbmcplugin

from resources.lib.base_website import BaseWebsite
from resources.lib.proxy_utils import PlaybackGuard, ProxyController
from resources.lib.resilient_http import fetch_text


class HentaiMama(BaseWebsite):
    sort_options = ["Latest Episodes", "Hentai Series", "3D", "Uncensored"]
    sort_paths = {
        "Latest Episodes": "/episodes/",
        "Hentai Series": "/hentai-series/",
        "3D": "/genre/3d/",
        "Uncensored": "/genre/uncensored/",
    }
    blocked_terms = (
        "loli",
        "lolicon",
        "shota",
        "shotacon",
        "underage",
    )

    def __init__(self, addon_handle, addon=None):
        super().__init__(
            name="hentaimama",
            base_url="https://hentaimama.io/",
            search_url="https://hentaimama.io/?s={}",
            addon_handle=addon_handle,
            addon=addon,
        )
        self.label = "HentaiMama"
        self.ajax_url = urllib.parse.urljoin(self.base_url, "wp-admin/admin-ajax.php")
        self.ua = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/126.0.0.0 Safari/537.36"
        )
        self.session = requests.Session()

    def _headers(self, referer=None, accept=None):
        return {
            "User-Agent": self.ua,
            "Accept": accept or "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "identity",
            "Referer": referer or self.base_url,
        }

    def _get(self, url, referer=None):
        try:
            response = self.session.get(
                url,
                headers=self._headers(referer),
                timeout=20,
                allow_redirects=True,
            )
            if response.status_code == 200:
                return response.text
            self.logger.warning("HentaiMama HTTP %s for %s", response.status_code, url)
        except Exception as exc:
            self.logger.warning("HentaiMama request failed for %s: %s", url, exc)
            self.session = requests.Session()
        return fetch_text(
            url,
            headers=self._headers(referer),
            logger=self.logger,
            timeout=20,
            use_windows_curl_fallback=True,
        ) or ""

    def _post(self, data, referer):
        headers = self._headers(referer, accept="application/json, text/javascript, */*; q=0.01")
        headers["X-Requested-With"] = "XMLHttpRequest"
        try:
            response = self.session.post(
                self.ajax_url,
                headers=headers,
                data=data,
                timeout=20,
            )
            if response.status_code == 200:
                return response.text
            self.logger.warning("HentaiMama AJAX HTTP %s", response.status_code)
        except Exception as exc:
            self.logger.warning("HentaiMama AJAX failed: %s", exc)
        return ""

    def _absolute(self, value, base=None):
        value = html.unescape(value or "").strip()
        if value.startswith("//"):
            value = "https:" + value
        return urllib.parse.urljoin(base or self.base_url, value)

    def _clean(self, value):
        value = re.sub(r"<[^>]+>", " ", value or "")
        return re.sub(r"\s+", " ", html.unescape(value)).strip()

    def _allowed(self, value):
        value = (value or "").lower()
        return not any(term in value for term in self.blocked_terms)

    def _sort_key(self):
        try:
            index = int(self.addon.getSetting("hentaimama_sort_by") or "0")
        except Exception:
            index = 0
        if index < 0 or index >= len(self.sort_options):
            index = 0
        return self.sort_options[index]

    def get_start_url_and_label(self):
        key = self._sort_key()
        return self._absolute(self.sort_paths[key]), "{} [COLOR yellow]{}[/COLOR]".format(self.label, key)

    def _context_menu(self):
        return [
            (
                "Sort by...",
                "RunPlugin({}?mode=7&action=select_sort&website={})".format(sys.argv[0], self.name),
            )
        ]

    def get_page_url(self, url, page):
        if page <= 1:
            return url
        parsed = urllib.parse.urlparse(url)
        path = re.sub(r"/page/\d+/?$", "/", parsed.path)
        path = path.rstrip("/") + "/page/{}/".format(page)
        return urllib.parse.urlunparse(
            (parsed.scheme, parsed.netloc, path, parsed.params, parsed.query, parsed.fragment)
        )

    def _is_top_listing(self, url):
        parsed = urllib.parse.urlparse(url or self.base_url)
        path = parsed.path.rstrip("/")
        return not parsed.query and path in ("", "/episodes", "/hentai-series", "/genre/3d", "/genre/uncensored")

    def _extract_videos(self, content):
        videos = []
        seen = set()
        for block in re.findall(r"<article\b[^>]*>[\s\S]{0,12000}?</article>", content or "", re.IGNORECASE):
            href_match = re.search(r'href=["\']([^"\']*/episodes/[^"\']+/)["\']', block, re.IGNORECASE)
            if not href_match:
                continue
            video_url = self._absolute(href_match.group(1))
            if video_url in seen:
                continue
            image_match = re.search(r"<img\b[^>]*>", block, re.IGNORECASE)
            image_tag = image_match.group(0) if image_match else ""
            title_match = re.search(r'\salt=["\']([^"\']+)["\']', image_tag, re.IGNORECASE)
            if not title_match:
                title_match = re.search(r"<h3\b[^>]*>([\s\S]*?)</h3>", block, re.IGNORECASE)
            title = self._clean(title_match.group(1) if title_match else "")
            if not title or not self._allowed("{} {}".format(title, video_url)):
                continue
            thumb = ""
            for attr in ("data-src", "data-lazy-src", "src"):
                match = re.search(r'\s{}=["\']([^"\']+)["\']'.format(attr), image_tag, re.IGNORECASE)
                if match and not match.group(1).startswith("data:image/"):
                    thumb = self._absolute(match.group(1), video_url)
                    break
            if thumb:
                thumb = "{}|{}".format(
                    thumb,
                    urllib.parse.urlencode({
                        "User-Agent": self.ua,
                        "Referer": self.base_url,
                    }),
                )
            duration_match = re.search(r"\b(\d{1,2}:\d{2}(?::\d{2})?)\b", block)
            duration = duration_match.group(1) if duration_match else ""
            info = {"title": title, "plot": title}
            seconds = self.convert_duration(duration)
            if seconds:
                info["duration"] = seconds
            label = "{} [COLOR lime]({})[/COLOR]".format(title, duration) if duration else title
            seen.add(video_url)
            videos.append((label, video_url, thumb or self.icon, info))
        return videos

    def _series_urls(self, content):
        output = []
        for value in re.findall(r'href=["\']([^"\']*/tvshows/[^"\']+/)["\']', content or "", re.IGNORECASE):
            target = self._absolute(value)
            if target not in output:
                output.append(target)
        return output

    def process_content(self, url, page=1):
        if not url or url == "BOOTSTRAP":
            url, _ = self.get_start_url_and_label()
        target_url = self.get_page_url(url, page)
        content = self._get(target_url)
        if not content:
            self.notify_error("Could not load HentaiMama")
            return self.end_directory("videos")

        context_menu = self._context_menu()
        if page == 1 and self._is_top_listing(url):
            self.add_dir("Search", "", 5, self.icons.get("search", self.icon), context_menu=context_menu)
            self.add_dir("Categories", self._absolute("/genre/"), 8, self.icons.get("categories", self.icon), context_menu=context_menu)

        videos = self._extract_videos(content)
        if not videos:
            seen_urls = set()
            for series_url in self._series_urls(content)[:8]:
                series_html = self._get(series_url, referer=target_url)
                for item in self._extract_videos(series_html):
                    if item[1] in seen_urls:
                        continue
                    seen_urls.add(item[1])
                    videos.append(item)
                    if len(videos) >= 32:
                        break
                if len(videos) >= 32:
                    break

        for label, video_url, thumb, info in videos:
            self.add_link(label, video_url, 4, thumb, self.fanart, context_menu=context_menu, info_labels=info)

        next_page = page + 1
        if re.search(r'href=["\'][^"\']*/page/{}/'.format(next_page), content or "", re.IGNORECASE):
            self.add_dir("Next Page", url, 2, self.icons.get("default", self.icon), context_menu=context_menu, page=next_page)
        if not videos:
            self.notify_error("No HentaiMama videos found")
        self.end_directory("videos")

    def process_categories(self, url):
        content = self._get(self.base_url)
        seen = set()
        for href, body in re.findall(
            r'<a\b[^>]+href=["\']([^"\']*/genre/[^"\']+/)["\'][^>]*>([\s\S]{0,800}?)</a>',
            content or "",
            re.IGNORECASE,
        ):
            category_url = self._absolute(href)
            title = self._clean(body)
            if not title:
                title = urllib.parse.urlparse(category_url).path.rstrip("/").split("/")[-1].replace("-", " ").title()
            if not title or category_url in seen or not self._allowed("{} {}".format(title, category_url)):
                continue
            seen.add(category_url)
            self.add_dir(title, category_url, 2, self.icons.get("categories", self.icon), self.fanart)
        self.end_directory("videos")

    def search(self, query):
        if query:
            self.process_content(self.search_url.format(urllib.parse.quote_plus(query.strip())))

    def _resolve_stream(self, episode_url):
        page = self._get(episode_url, referer=self.base_url)
        post_match = re.search(r"\ba\s*:\s*['\"](\d+)['\"]", page or "", re.IGNORECASE)
        if not post_match:
            return None
        raw = self._post(
            {"action": "get_player_contents", "a": post_match.group(1)},
            episode_url,
        )
        try:
            frames = json.loads(raw)
        except (TypeError, ValueError):
            frames = []
        for frame in frames:
            iframe_match = re.search(r'src=["\']([^"\']+)["\']', frame or "", re.IGNORECASE)
            if not iframe_match:
                continue
            iframe_url = self._absolute(iframe_match.group(1), episode_url)
            iframe_html = self._get(iframe_url, referer=episode_url)
            stream_match = re.search(
                r"(?:file|src)\s*:\s*['\"](https?://[^'\"]+\.(?:mp4|m3u8)[^'\"]*)['\"]",
                iframe_html or "",
                re.IGNORECASE,
            )
            if not stream_match:
                stream_match = re.search(
                    r"(https?://[^\"'\s<]+\.(?:mp4|m3u8)[^\"'\s<]*)",
                    iframe_html or "",
                    re.IGNORECASE,
                )
            if stream_match:
                stream_url = html.unescape(stream_match.group(1)).replace("\\/", "/")
                return {
                    "url": stream_url,
                    "headers": self._headers(iframe_url, accept="*/*"),
                    "extension": "m3u8" if ".m3u8" in stream_url else "mp4",
                }
        return None

    def resolve_recording_stream(self, url):
        return self._resolve_stream(url)

    def play_video(self, url):
        resolved = self.resolve_recording_stream(url)
        if not resolved:
            self.notify_error("Could not resolve HentaiMama stream")
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
            return
        controller = ProxyController(
            resolved["url"],
            upstream_headers=resolved["headers"],
            session=self.session,
            skip_resolve=True,
            probe_size=True,
        )
        local_url = controller.start()
        item = xbmcgui.ListItem(path=local_url)
        item.setProperty("IsPlayable", "true")
        item.setMimeType("video/mp4")
        item.setContentLookup(False)
        xbmcplugin.setResolvedUrl(self.addon_handle, True, item)
        PlaybackGuard(xbmc.Player(), xbmc.Monitor(), local_url, controller).start()
