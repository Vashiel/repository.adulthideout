#!/usr/bin/env python
# -*- coding: utf-8 -*-

import base64
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
from resources.lib.vendor import byse_crypto


class FullEroticMovies(BaseWebsite):
    label = "Full Erotic Movies"
    sort_options = ["Newest", "Trending", "Most Viewed", "Top Rated"]
    sort_paths = {
        "Newest": "/videos/",
        "Trending": "/trending/",
        "Most Viewed": "/most-viewed/",
        "Top Rated": "/top-rated/",
    }
    categories_path = "/categories/"
    studios_path = "/studios/"
    pornstars_path = "/pornstars/"
    _VIDEO_PATH = re.compile(r"^/video/[^/]+/?$", re.IGNORECASE)

    def __init__(self, addon_handle, addon=None):
        super().__init__(
            name="fulleroticmovies",
            base_url="https://www.fulleroticmovies.net/",
            search_url="https://www.fulleroticmovies.net/search/{}/",
            addon_handle=addon_handle,
            addon=addon,
        )
        self.session = requests.Session()
        self.user_agent = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/132.0.0.0 Safari/537.36"
        )
        self.last_url = self.base_url

    def _get(self, url, referer=None):
        try:
            response = self.session.get(
                url,
                headers={
                    "User-Agent": self.user_agent,
                    "Referer": referer or self.base_url,
                    "Accept-Language": "en-US,en;q=0.9",
                },
                timeout=(6, 18),
            )
            if response.status_code == 200:
                self.last_url = response.url
                return response.text
            self.logger.warning("[FullEroticMovies] HTTP %s for %s", response.status_code, url)
        except Exception as exc:
            self.logger.warning("[FullEroticMovies] Request failed: %s", exc)
        return ""

    def _absolute(self, value):
        value = (value or "").replace("\\/", "/")
        # Decode HTML-escaped ampersands only. html.unescape() also interprets
        # a literal query parameter beginning with "&times" as the × entity.
        value = re.sub(r"&(?:amp|#0*38|#x0*26);", "&", value, flags=re.IGNORECASE)
        return urllib.parse.urljoin(self.base_url, value)

    @staticmethod
    def _clean(value):
        value = re.sub(r"<[^>]+>", " ", value or "")
        return re.sub(r"\s+", " ", html.unescape(value)).strip()

    def get_page_url(self, base_url, page_num):
        parsed = urllib.parse.urlparse(base_url or self.base_url)
        path = re.sub(r"/\d+/?$", "/", parsed.path or "/")
        if page_num <= 1:
            return urllib.parse.urlunparse(parsed._replace(path=path))
        if not path.endswith("/"):
            path += "/"
        path += "{}/".format(page_num)
        return urllib.parse.urlunparse(parsed._replace(path=path))

    def _is_primary(self, url):
        return self.is_primary_listing_url(url)

    def _extract_thumb(self, img_tag):
        for attr in ("data-original", "data-src", "data-lazy-src", "src", "srcset"):
            match = re.search(r'\b{}=["\']([^"\']+)'.format(attr), img_tag or "", re.IGNORECASE)
            if not match:
                continue
            value = match.group(1).strip()
            if attr == "srcset":
                value = value.split(",", 1)[0].strip().split(" ", 1)[0]
            if not value or value.lower().startswith("data:image/"):
                continue
            if any(token in value.lower() for token in ("placeholder", "spacer", "blank.gif", "loading")):
                continue
            return self._absolute(value)
        return self.icon

    def _extract_videos(self, content):
        videos = []
        seen = set()
        anchor_pattern = re.compile(
            r'<a\b([^>]*?)href=["\']([^"\']+)["\']([^>]*)>([\s\S]{0,1800}?)</a>',
            re.IGNORECASE,
        )
        for match in anchor_pattern.finditer(content or ""):
            href = self._absolute(match.group(2))
            parsed = urllib.parse.urlparse(href)
            if parsed.netloc.lower() not in ("www.fulleroticmovies.net", "fulleroticmovies.net"):
                continue
            if not self._VIDEO_PATH.match(parsed.path) or href in seen:
                continue
            body = match.group(4)
            img_match = re.search(r"<img\b[^>]*>", body, re.IGNORECASE)
            img_tag = img_match.group(0) if img_match else ""
            title_match = re.search(r'\b(?:alt|title)=["\']([^"\']+)', img_tag or match.group(1) + match.group(3), re.IGNORECASE)
            title = self._clean(title_match.group(1)) if title_match else self._clean(body)
            if not title:
                continue
            seen.add(href)

            card_start = max(content.rfind("<article", 0, match.start()), content.rfind("<li", 0, match.start()), content.rfind("<div", 0, match.start()))
            card_end = content.find("</article>", match.end())
            if card_end < 0 or card_end - card_start > 5000:
                card_end = min(len(content), match.end() + 1800)
            card = content[card_start:card_end]
            duration_match = re.search(
                r'\b(?:duration|runtime)[^>]*>\s*([^<]{1,30})<|\bdata-duration=["\']([^"\']+)',
                card,
                re.IGNORECASE,
            )
            duration = self._clean(next((value for value in duration_match.groups() if value), "")) if duration_match else ""
            thumb = self._extract_thumb(img_tag)
            info = {"title": title, "plot": title}
            seconds = self.convert_duration(duration)
            if seconds:
                info["duration"] = seconds
            label = "{} [COLOR lime]({})[/COLOR]".format(title, duration) if duration else title
            videos.append({"url": href, "title": label, "thumb": thumb, "info": info})
        return videos

    def _next_page(self, content, current_url):
        current = urllib.parse.urlparse(current_url)
        current_path = urllib.parse.unquote(current.path)
        current_root = re.sub(r"/\d+/?$", "/", current_path)
        current_page_match = re.search(r"/(\d+)/?$", current_path)
        current_page = int(current_page_match.group(1)) if current_page_match else 1
        candidates = []
        anchor_pattern = re.compile(
            r'<a\b([^>]*?)href=["\']([^"\']+)["\']([^>]*)>([\s\S]{0,300}?)</a>',
            re.IGNORECASE,
        )
        for match in anchor_pattern.finditer(content or ""):
            href = self._absolute(match.group(2))
            parsed = urllib.parse.urlparse(href)
            if parsed.netloc.lower() not in ("www.fulleroticmovies.net", "fulleroticmovies.net"):
                continue
            label = self._clean(match.group(4)).lower()
            attrs = (match.group(1) + " " + match.group(3)).lower()
            if label in ("next", "next page", "»", "›") or 'rel="next"' in attrs or "aria-label=\"next" in attrs:
                return href
            candidate_path = urllib.parse.unquote(parsed.path)
            if re.sub(r"/\d+/?$", "/", candidate_path) != current_root:
                continue
            page_match = re.search(r"/(\d+)/?$", candidate_path)
            if page_match and int(page_match.group(1)) > current_page:
                candidates.append((int(page_match.group(1)), href))
        return min(candidates)[1] if candidates else None

    def process_content(self, url, page=1):
        if not url or url == "BOOTSTRAP":
            url, _ = self.get_start_url_and_label()
        target_url = self.get_page_url(url, page) if page > 1 else url
        if self._is_primary(url):
            context = self._context_menu(url)
            self.add_dir("Search", "", 5, self.icons.get("search", self.icon), context_menu=context)
            self.add_dir("Categories", self._absolute(self.categories_path), 8, self.icons.get("categories", self.icon), context_menu=context)
            self.add_dir("Studios", self._absolute(self.studios_path), 8, self.icons.get("groups", self.icon), context_menu=context)
            self.add_dir("Pornstars", self._absolute(self.pornstars_path), 8, self.icons.get("pornstars", self.icon), context_menu=context)

        content = self._get(target_url)
        if not content:
            self.notify_error("Could not load Full Erotic Movies")
            self.end_directory("videos")
            return
        videos = self._extract_videos(content)
        if not videos:
            self.notify_error("No videos found")
            self.end_directory("videos")
            return
        for video in videos:
            self.add_link(video["title"], video["url"], 4, video["thumb"], self.fanart, info_labels=video["info"])
        next_url = self._next_page(content, self.last_url or target_url)
        if next_url:
            self.add_dir("Next Page", next_url, 2, self.icon)
        self.end_directory("videos")

    def process_categories(self, url):
        target = url or self._absolute(self.categories_path)
        parsed = urllib.parse.urlparse(target)
        path = parsed.path.lower()
        if path.startswith("/categories"):
            prefix = "/category/"
        elif path.startswith("/studios"):
            prefix = "/studio/"
        else:
            prefix = "/pornstar/"
        content = self._get(target)
        if not content:
            self.notify_error("Could not load Full Erotic Movies directory")
            self.end_directory("videos")
            return
        seen = set()
        pattern = re.compile(
            r'<a\b([^>]*?)href=["\']([^"\']+)["\']([^>]*)>([\s\S]{0,1200}?)</a>',
            re.IGNORECASE,
        )
        for match in pattern.finditer(content):
            href = self._absolute(match.group(2))
            parsed_href = urllib.parse.urlparse(href)
            if parsed_href.netloc.lower() not in ("www.fulleroticmovies.net", "fulleroticmovies.net"):
                continue
            if not parsed_href.path.lower().startswith(prefix) or href in seen:
                continue
            name = self._clean(match.group(4))
            if not name or name.lower() in ("all categories", "all studios", "all pornstars", "next", "previous"):
                continue
            seen.add(href)
            self.add_dir(name, href, 2, self._extract_thumb(match.group(4)))
        next_url = self._next_page(content, target)
        if next_url:
            self.add_dir("Next Page", next_url, 8, self.icon)
        self.end_directory("videos")

    def search(self, query):
        query = (query or "").strip()
        if not query:
            return
        self.save_query(query)
        search_url = self.search_url.format(urllib.parse.quote(query, safe=""))
        self.process_content(search_url)

    def resolve_recording_stream(self, url, content=None):
        if content is None:
            content = self._get(url, referer=self.base_url)
        if not content:
            return None
        sources = []
        for field in ("video_url", "video_alt_url"):
            match = re.search(r'\b{}\s*:\s*["\']([^"\']+)["\']'.format(field), content, re.IGNORECASE)
            if not match:
                continue
            stream = self._absolute(match.group(1))
            stream_parsed = urllib.parse.urlparse(stream)
            if stream_parsed.netloc.lower() not in ("www.fulleroticmovies.net", "fulleroticmovies.net"):
                continue
            quality_match = re.search(
                r'\b{}_text\s*:\s*["\']([^"\']*)["\']'.format(field), content, re.IGNORECASE
            )
            quality = quality_match.group(1) if quality_match else ""
            resolution = re.search(r"(\d{3,4})", quality)
            if not resolution:
                resolution = re.search(r"-(\d{3,4})\.mp4(?:$|\?)", stream_parsed.path, re.IGNORECASE)
            sources.append((int(resolution.group(1)) if resolution else 0, stream))
        if not sources:
            self.logger.warning("[FullEroticMovies] No first-party stream found on video page")
            return None
        stream = sorted(sources, key=lambda item: item[0])[-1][1]
        headers = {"User-Agent": self.user_agent, "Referer": url}
        cookies = self.session.cookies.get_dict()
        if cookies:
            headers["Cookie"] = "; ".join("{}={}".format(key, value) for key, value in cookies.items())
        return {"url": stream, "headers": headers, "extension": "mp4", "mirror": self.base_url}

    def _resolve_player_api_stream(self, page_url, content):
        match = re.search(
            r"generate_mp4\(\s*(['\"])([^'\"]+)\1\s*,\s*(['\"])([^'\"]+)\3\s*,\s*(['\"])([^'\"]+)\5\s*,\s*(['\"])([^'\"]+)\7",
            content or "",
            re.IGNORECASE,
        )
        if not match:
            self.logger.warning("[FullEroticMovies] No supported player API call found")
            return None

        encrypted_config, password, video_id, site_video_id = (
            match.group(2), match.group(4), match.group(6), match.group(8)
        )
        try:
            config = json.loads(base64.b64decode(encrypted_config))
            iterations = int(config.get("iterations", 999))
            if iterations < 1 or iterations > 10000:
                raise ValueError("Unexpected player key-derivation cost")
            key = byse_crypto.pbkdf2_sha512(
                password.encode("utf-8"),
                bytes.fromhex(config["salt"]),
                32,
                iterations,
            )
            decrypted = byse_crypto.cbc_decrypt(
                key,
                bytes.fromhex(config["iv"]),
                base64.b64decode(config["ciphertext"]),
            )
            session_key = byse_crypto.pkcs7_unpad(decrypted).decode("utf-8").strip()
            if not session_key:
                raise ValueError("Player session key is empty")
        except Exception as exc:
            self.logger.warning("[FullEroticMovies] Player config decode failed: %s", exc)
            return None

        fields = (
            "video.url_tiny,video.url_low,video.url_high,video.url_medium,"
            "video.url_quadhd,video.url_mobile,video.url_ultrahd,video.url_fullhd,"
        )
        try:
            response = self.session.get(
                "https://api.ok.ru/fb.do",
                params={
                    "application_key": "CBAFJIICABABABABA",
                    "fields": fields,
                    "method": "video.get",
                    "session_key": session_key,
                    "vids": video_id,
                },
                headers={
                    "User-Agent": self.user_agent,
                    "Referer": page_url,
                    "Accept": "application/json, */*;q=0.8",
                },
                timeout=(6, 15),
            )
            if response.status_code != 200:
                self.logger.warning(
                    "[FullEroticMovies] Player API returned HTTP %s", response.status_code
                )
                return None
            videos = response.json().get("videos") or []
        except Exception as exc:
            self.logger.warning("[FullEroticMovies] Player API request failed: %s", exc)
            return None

        quality_map = {
            "mobile": 144,
            "tiny": 240,
            "low": 360,
            "medium": 480,
            "high": 720,
            "quadhd": 1440,
            "fullhd": 1080,
            "ultrahd": 2160,
        }
        allowed_hosts = (
            "vkuser.net", "okcdn.ru", "mycdn.me", "ok.ru",
            "odnoklassniki.ru", "userapi.com",
        )
        sources = []
        for video in videos:
            if not isinstance(video, dict):
                continue
            for name, resolution in quality_map.items():
                stream = video.get("url_" + name)
                parsed = urllib.parse.urlparse(stream or "")
                host = (parsed.hostname or "").lower()
                if (
                    parsed.scheme == "https"
                    and any(host == suffix or host.endswith("." + suffix) for suffix in allowed_hosts)
                ):
                    sources.append((resolution, stream))
        if not sources:
            self.logger.warning(
                "[FullEroticMovies] Player API returned no supported MP4 source for video %s",
                site_video_id,
            )
            return None

        resolution, stream = max(sources, key=lambda source: source[0])
        self.logger.info(
            "[FullEroticMovies] Resolved player API source (%dp) for video %s",
            resolution,
            site_video_id,
        )
        return {
            "url": stream,
            "headers": {
                "User-Agent": self.user_agent,
                "Referer": "https://ok.ru/",
            },
            "extension": "mp4",
        }

    def play_video(self, url):
        content = self._get(url, referer=self.base_url)
        has_player_api = bool(re.search(r"\bgenerate_mp4\s*\(", content or "", re.IGNORECASE))
        if has_player_api:
            resolved = self._resolve_player_api_stream(url, content)
        else:
            resolved = self.resolve_recording_stream(url, content)
        if not resolved:
            self.notify_error("Could not resolve Full Erotic Movies stream")
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
            return

        headers = resolved.get("headers") or {}
        play_url = resolved["url"]
        if headers:
            play_url = "{}|{}".format(play_url, urllib.parse.urlencode(headers))
        item = xbmcgui.ListItem(path=play_url)
        item.setProperty("IsPlayable", "true")
        item.setMimeType("video/mp4")
        item.setContentLookup(False)
        xbmcplugin.setResolvedUrl(self.addon_handle, True, item)

    def _context_menu(self, original_url=None):
        suffix = ""
        if original_url:
            suffix = "&original_url={}".format(urllib.parse.quote_plus(original_url))
        return [("Sort by...", "RunPlugin({}?mode=7&action=select_sort&website={}{} )".format(
            sys.argv[0], self.name, suffix
        ).replace(" )", ")"))]
