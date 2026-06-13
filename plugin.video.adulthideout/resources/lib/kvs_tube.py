#!/usr/bin/env python
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
from resources.lib.decoders.kvs_decoder import kvs_decode_url
from resources.lib.proxy_utils import PlaybackGuard, ProxyController


class KVSTubeWebsite(BaseWebsite):
    label = ""
    video_path_markers = ("/video/", "/videos/")
    category_path_markers = ("/categories/", "/category/")
    sort_options = ["Latest", "Most Viewed", "Top Rated", "Longest"]
    sort_paths = {}
    search_path = "/search/{}/"
    categories_path = "/categories/"
    models_path = None
    use_playback_proxy = False
    use_urllib_proxy = True
    prefer_default_stream = False
    request_retries = 2
    next_page_full_count = 0

    def __init__(self, name, base_url, search_url, addon_handle, addon=None):
        super().__init__(
            name=name,
            base_url=base_url,
            search_url=search_url,
            addon_handle=addon_handle,
            addon=addon,
        )
        self.session = requests.Session()
        self.ua = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/125.0.0.0 Safari/537.36"
        )

    def _headers(self, referer=None, accept="text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"):
        return {
            "User-Agent": self.ua,
            "Referer": referer or self.base_url,
            "Accept": accept,
            "Accept-Language": "en-US,en;q=0.9",
        }

    def _get(self, url, referer=None, max_retries=None):
        if max_retries is None:
            max_retries = self.request_retries
        last_error = None
        for attempt in range(1, max_retries + 1):
            try:
                response = self.session.get(url, headers=self._headers(referer), timeout=15)
                if response.status_code == 200:
                    return response.text
                last_error = "HTTP {}".format(response.status_code)
                self.logger.warning("%s HTTP %s for %s", self.label or self.name, response.status_code, url)
            except Exception as exc:
                last_error = exc
                self.logger.warning("%s request error for %s: %s", self.label or self.name, url, exc)
                self.session = requests.Session()
            if attempt < max_retries:
                xbmc.sleep(650 * attempt)
        self.logger.error("%s failed to fetch %s: %s", self.label or self.name, url, last_error)
        return ""

    def _absolute(self, value):
        if not value:
            return ""
        return urllib.parse.urljoin(self.base_url, html.unescape(value).strip())

    def _clean(self, value):
        value = re.sub(r"<[^>]+>", " ", value or "")
        return re.sub(r"\s+", " ", html.unescape(value)).strip()

    def _get_sort_key(self):
        try:
            idx = int(self.addon.getSetting("{}_sort_by".format(self.name)) or "0")
        except Exception:
            idx = 0
        if not 0 <= idx < len(self.sort_options):
            idx = 0
        return self.sort_options[idx]

    def get_start_url_and_label(self):
        sort_key = self._get_sort_key()
        path = self.sort_paths.get(sort_key) or self.sort_paths.get(self.sort_options[0]) or "/"
        return self._absolute(path), "{} [COLOR yellow]{}[/COLOR]".format(self.label or self.name, sort_key)

    def _context_menu(self, original_url=None):
        suffix = ""
        if original_url:
            suffix = "&original_url={}".format(urllib.parse.quote_plus(original_url))
        return [
            (
                "Sort by...",
                "RunPlugin({}?mode=7&action=select_sort&website={}{} )".format(
                    sys.argv[0], self.name, suffix
                ).replace(" )", ")"),
            )
        ]

    def _is_top_listing(self, url):
        parsed = urllib.parse.urlparse(url or self.base_url)
        path = parsed.path.strip("/")
        return path in ("", "latest-updates", "video", "videos", "new", "recent") and "q" not in urllib.parse.parse_qs(parsed.query)

    def get_page_url(self, base_url, page_num):
        if page_num <= 1:
            return base_url
        parsed = urllib.parse.urlparse(base_url)
        query = urllib.parse.parse_qs(parsed.query)
        if "q" in query or "/search/" in parsed.path:
            query["from_videos"] = [str(page_num)]
            return urllib.parse.urlunparse(
                (parsed.scheme, parsed.netloc, parsed.path, parsed.params, urllib.parse.urlencode(query, doseq=True), parsed.fragment)
            )
        path = parsed.path
        if not path.endswith("/"):
            path += "/"
        if re.search(r"/\d+/$", path):
            path = re.sub(r"/\d+/$", "/{}/".format(page_num), path)
        else:
            path += "{}/".format(page_num)
        return urllib.parse.urlunparse((parsed.scheme, parsed.netloc, path, parsed.params, parsed.query, parsed.fragment))

    def _is_video_href(self, href):
        if not href:
            return False
        return any(marker in href for marker in self.video_path_markers)

    def _extract_videos(self, html_content):
        videos = []
        seen = set()
        blocks = re.split(r'(?=<div\b[^>]+class=["\'][^"\']*(?:item|thumb|video)[^"\']*["\'])', html_content or "", flags=re.IGNORECASE)
        for block in blocks:
            if not any(marker in block for marker in self.video_path_markers):
                continue
            href_match = None
            for match in re.finditer(r'<a\b[^>]+href=["\']([^"\']+)["\'][^>]*>', block, re.IGNORECASE):
                href = match.group(1)
                if self._is_video_href(href):
                    href_match = match
                    break
            if not href_match:
                continue
            video_url = self._absolute(href_match.group(1))
            if not video_url or video_url in seen:
                continue
            seen.add(video_url)

            anchor = href_match.group(0)
            img_match = re.search(r"<img\b[^>]*>", block, re.IGNORECASE)
            img_tag = img_match.group(0) if img_match else ""
            title_match = re.search(r'\stitle=["\']([^"\']+)["\']', anchor, re.IGNORECASE)
            if not title_match:
                title_match = re.search(r'\s(?:alt|title)=["\']([^"\']+)["\']', img_tag, re.IGNORECASE)
            if not title_match:
                title_match = re.search(r"<a\b[^>]+href=[\"'][^\"']+[\"'][^>]*>([\s\S]{0,200}?)</a>", block, re.IGNORECASE)

            title = self._clean(title_match.group(1) if title_match else "")
            if not title or title.lower() in ("videos", "rss"):
                continue

            thumb = ""
            for attr in ("data-original", "data-webp", "data-src", "src"):
                thumb_match = re.search(r'\s{}=["\']([^"\']+)["\']'.format(attr), img_tag, re.IGNORECASE)
                if thumb_match:
                    thumb = self._absolute(thumb_match.group(1))
                    break
            if thumb.startswith("data:image/"):
                thumb = self.icon

            duration_match = re.search(
                r'<(?:div|span)\b[^>]*class=["\'][^"\']*(?:duration|time)[^"\']*["\'][^>]*>([\s\S]*?)</(?:div|span)>',
                block,
                re.IGNORECASE,
            )
            duration = self._clean(duration_match.group(1)) if duration_match else ""
            seconds = self.convert_duration(duration)
            label = "{} [COLOR lime]({})[/COLOR]".format(title, duration) if duration else title
            info = {"title": title, "plot": title}
            if seconds:
                info["duration"] = seconds
            videos.append({"label": label, "url": video_url, "thumb": thumb or self.icon, "info": info})
        return videos

    def _extract_next_page(self, html_content, current_url, page):
        next_page = page + 1
        if "from_videos:{}\"".format(next_page) in html_content or "from_videos:{}".format(next_page) in html_content:
            return self.get_page_url(current_url, next_page)
        if re.search(r'data-parameters=["\'][^"\']*from:0?{}(?:["\';]|$)'.format(next_page), html_content or "", re.IGNORECASE):
            return self.get_page_url(current_url, next_page)
        next_url = self.get_page_url(current_url, next_page)
        parsed_next = urllib.parse.urlparse(next_url)
        if re.search(r'href=["\'][^"\']*{}["\']'.format(re.escape(parsed_next.path)), html_content or "", re.IGNORECASE):
            return next_url
        return None

    def process_content(self, url, page=1):
        if not url or url == "BOOTSTRAP":
            url, _ = self.get_start_url_and_label()
        context_menu = self._context_menu(url)
        if self._is_top_listing(url):
            self.add_dir("Search", "", 5, self.icons.get("search", self.icon), context_menu=context_menu)
            if self.categories_path:
                self.add_dir("Categories", self._absolute(self.categories_path), 8, self.icons.get("categories", self.icon), context_menu=context_menu)
            if self.models_path:
                self.add_dir("Models", self._absolute(self.models_path), 8, self.icons.get("pornstars", self.icon), context_menu=context_menu)

        target_url = self.get_page_url(url, page)
        html_content = self._get(target_url)
        if not html_content:
            self.notify_error("Could not load {} listing".format(self.label or self.name))
            self.end_directory("videos")
            return
        videos = self._extract_videos(html_content)
        if not videos:
            self.notify_error("No {} videos found".format(self.label or self.name))
            return self.end_directory("videos")
        for item in videos:
            self.add_link(item["label"], item["url"], 4, item["thumb"], self.fanart, context_menu=context_menu, info_labels=item["info"])
        next_url = self._extract_next_page(html_content, target_url, page)
        if not next_url and self.next_page_full_count and len(videos) >= self.next_page_full_count:
            next_url = self.get_page_url(target_url, page + 1)
        if next_url:
            self.add_dir("Next Page", url, 2, self.icons.get("default", self.icon), context_menu=context_menu, page=page + 1)
        self.end_directory("videos")

    def process_categories(self, url):
        current_url = url or self._absolute(self.categories_path or "/categories/")
        html_content = self._get(current_url)
        if not html_content:
            self.notify_error("Could not load {} categories".format(self.label or self.name))
            self.end_directory("videos")
            return
        seen = set()
        next_url = ""
        current_path = urllib.parse.urlparse(current_url).path.rstrip("/")
        models_only = current_path.startswith("/models")
        for anchor_match in re.finditer(r'<a\b([^>]*)href=["\']([^"\']+)["\']([^>]*)>([\s\S]{0,1800}?)</a>', html_content, re.IGNORECASE):
            attrs = "{} {}".format(anchor_match.group(1), anchor_match.group(3))
            href = anchor_match.group(2)
            body = anchor_match.group(4)
            clean_body = self._clean(body)
            from_match = re.search(r"from:(\d+)", attrs, re.IGNORECASE)
            if clean_body.lower() == "next" or from_match:
                if href and not href.startswith("#"):
                    next_url = self._absolute(href)
                elif from_match:
                    next_url = self.get_page_url(current_url, int(from_match.group(1)))
                continue
            if models_only and "/models/" not in href:
                continue
            if not any(marker in href for marker in self.category_path_markers) and "/models/" not in href and "/tags/" not in href:
                continue
            cat_url = self._absolute(href)
            if not cat_url or cat_url in seen or urllib.parse.urlparse(cat_url).path.rstrip("/") in ("/categories", "/models", "/tags"):
                continue
            seen.add(cat_url)
            title_match = re.search(r"<img\b[^>]*\s(?:alt|title)=['\"]([^'\"]+)['\"]", body, re.IGNORECASE)
            if not title_match:
                title_match = re.search(r'class=["\'][^"\']*\btitle\b[^"\']*["\'][^>]*>([\s\S]{0,120}?)</', body, re.IGNORECASE)
            title = self._clean(title_match.group(1) if title_match else clean_body)
            if not title:
                continue
            if title.isdigit():
                continue
            if title.lower() in ("next", "last"):
                continue
            if title.lower() in getattr(self, "skip_category_titles", set()):
                continue
            self.add_dir(title, cat_url, 2, self.icons.get("categories", self.icon), self.fanart)
        if next_url:
            self.add_dir("Next Page", next_url, 8, self.icons.get("default", self.icon), self.fanart)
        self.end_directory("videos")

    def search(self, query):
        if query:
            self.process_content(self.search_url.format(urllib.parse.quote_plus(query.strip())))

    def _is_stream_candidate(self, value):
        if not value:
            return False
        value = value.lower()
        return ".mp4" in value and ("get_file/" in value or value.startswith("http"))

    def _normalize_stream(self, value, license_code=None):
        value = html.unescape(value or "").replace("\\/", "/").strip()
        if value.startswith("function/0/") and license_code:
            try:
                value = kvs_decode_url(value, license_code)
            except Exception as exc:
                self.logger.warning("%s KVS URL decode failed: %s", self.label or self.name, exc)
                value = value[len("function/0/"):]
        elif value.startswith("function/0/"):
            value = value[len("function/0/"):]
        return self._absolute(value)

    def _probe_stream(self, stream_url, referer):
        try:
            headers = self._headers(referer, accept="*/*")
            headers["Range"] = "bytes=0-0"
            response = self.session.get(stream_url, headers=headers, timeout=15, stream=True, allow_redirects=True)
            response.close()
            ctype = response.headers.get("Content-Type", "").lower()
            return response.status_code in (200, 206) and ("video" in ctype or "octet-stream" in ctype or ".mp4" in stream_url)
        except Exception as exc:
            self.logger.warning("%s stream probe failed for %s: %s", self.label or self.name, stream_url, exc)
            return False

    def _extract_stream_url(self, html_content, referer=None):
        urls = {}
        license_match = re.search(r'license_code\s*:\s*[\'"]([^\'"]+)[\'"]', html_content or "", re.IGNORECASE)
        license_code = html.unescape(license_match.group(1)).strip() if license_match else ""
        for key, value in re.findall(r'(video_url|video_alt_url\d*|event_reporting2):\s*[\'"]([^\'"]+)["\']', html_content or "", re.IGNORECASE):
            stream_url = self._normalize_stream(value, license_code)
            if self._is_stream_candidate(stream_url):
                urls[key] = stream_url
        for href in re.findall(r'href=["\']([^"\']+\.mp4/?[^"\']*)["\']', html_content or "", re.IGNORECASE):
            stream_url = self._normalize_stream(href, license_code)
            if self._is_stream_candidate(stream_url):
                urls.setdefault("download", stream_url)
        if self.prefer_default_stream:
            order = ["video_url", "video_alt_url", "video_alt_url2", "video_alt_url3", "video_alt_url4", "video_alt_url5", "download", "event_reporting2"]
        else:
            order = ["video_alt_url5", "video_alt_url4", "video_alt_url3", "video_alt_url2", "video_alt_url", "video_url", "download", "event_reporting2"]
        for key in order:
            if key in urls and "get_file/" in urls[key]:
                return urls[key]
            if key in urls and self._probe_stream(urls[key], referer or self.base_url):
                return urls[key]
        for key in order:
            if key in urls:
                return urls[key]
        return None

    def resolve_recording_stream(self, url):
        html_content = self._get(url, referer=self.base_url)
        stream_url = self._extract_stream_url(html_content, referer=url)
        if not stream_url:
            return None
        headers = self._headers(url, accept="*/*")
        cookies = self.session.cookies.get_dict() if self.session else {}
        if cookies:
            headers["Cookie"] = "; ".join("{}={}".format(key, value) for key, value in cookies.items())
        return {"url": stream_url, "headers": headers, "extension": "mp4"}

    def play_video(self, url):
        resolved = self.resolve_recording_stream(url)
        if not resolved:
            self.notify_error("Could not resolve stream URL")
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
            return
        play_url = resolved["url"]
        headers = resolved.get("headers") or {}
        playback_controller = None
        if self.use_playback_proxy:
            try:
                playback_controller = ProxyController(
                    upstream_url=play_url,
                    upstream_headers=headers,
                    cookies=self.session.cookies.get_dict() if self.session else None,
                    session=self.session,
                    skip_resolve=True,
                    probe_size=True,
                    use_urllib=self.use_urllib_proxy,
                )
                play_url = playback_controller.start()
                self.logger.info("%s using in-process Range proxy for playback", self.label or self.name)
            except Exception as exc:
                playback_controller = None
                self.logger.warning("%s Range proxy failed, falling back direct: %s", self.label or self.name, exc)
        if headers:
            if playback_controller is None:
                play_url = "{}|{}".format(play_url, urllib.parse.urlencode(headers))
        list_item = xbmcgui.ListItem(path=play_url)
        list_item.setProperty("IsPlayable", "true")
        list_item.setMimeType("video/mp4")
        list_item.setContentLookup(False)
        xbmcplugin.setResolvedUrl(self.addon_handle, True, list_item)
        if playback_controller:
            PlaybackGuard(xbmc.Player(), xbmc.Monitor(), play_url, playback_controller).start()
