# -*- coding: utf-8 -*-
import html
import json
import re
import urllib.parse

import requests
import xbmcgui
import xbmcplugin

from resources.lib.base_website import BaseWebsite


class PmvhavenWebsite(BaseWebsite):
    API_VIDEOS_URL = "https://pmvhaven.com/api/videos"
    API_SEARCH_URL = "https://pmvhaven.com/api/videos/search"
    SEARCH_PREFIX = "PMVH_SEARCH:"
    PLAYBACK_PREFIX = "PMVVIDEO:"

    def __init__(self, addon_handle, addon=None):
        super().__init__(
            name="pmvhaven",
            base_url="https://pmvhaven.com",
            search_url="https://pmvhaven.com/search?q={}",
            addon_handle=addon_handle,
            addon=addon,
        )
        self.session = requests.Session()
        self.ua = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/126.0.0.0 Safari/537.36"
        )
        self.sort_options = ["Newest", "Most Popular", "Trending"]
        self.sort_paths = {
            "Newest": "/browse",
            "Most Popular": "/popular",
            "Trending": "/trending",
        }
        self.videos_per_page = 32

    def make_request(self, url, referer=None):
        try:
            headers = {
                "User-Agent": self.ua,
                "Referer": referer or (self.base_url + "/"),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
            }
            response = self.session.get(url, headers=headers, timeout=20)
            if response.status_code == 200:
                return response.text
            self.logger.error("[PMVHaven] HTTP %s for %s", response.status_code, url)
        except Exception as exc:
            self.logger.error("[PMVHaven] Request error for %s: %s", url, exc)
        return None

    def _fetch_json(self, url, params=None, referer=None):
        try:
            headers = {
                "User-Agent": self.ua,
                "Referer": referer or (self.base_url + "/"),
                "Accept": "application/json, text/plain, */*",
                "Accept-Language": "en-US,en;q=0.9",
            }
            response = self.session.get(url, headers=headers, params=params or {}, timeout=20)
            if response.status_code == 200:
                return response.json()
            self.logger.error("[PMVHaven] JSON HTTP %s for %s", response.status_code, response.url)
        except Exception as exc:
            self.logger.error("[PMVHaven] JSON request error for %s: %s", url, exc)
        return None

    def _get_sort_value_for_url(self, url):
        lowered = (url or "").lower()
        if "/popular" in lowered:
            return "-views"
        if "/trending" in lowered:
            return "-trendingScore"
        return "-uploadDate"

    def _extract_search_query(self, url):
        if not url:
            return ""

        if url.startswith(self.SEARCH_PREFIX):
            return urllib.parse.unquote_plus(url[len(self.SEARCH_PREFIX):]).strip()

        parsed = urllib.parse.urlparse(url)
        query_params = urllib.parse.parse_qs(parsed.query)
        return (query_params.get("q", [""])[0] or "").strip()

    def _get_listing_payload(self, url, page):
        query = self._extract_search_query(url)
        params = {
            "page": max(1, int(page or 1)),
            "limit": self.videos_per_page,
        }

        if query:
            params["search"] = query
            params["sort"] = self._get_sort_value_for_url(self.base_url + "/browse")
            return self._fetch_json(self.API_SEARCH_URL, params=params, referer=self.base_url + "/search")

        params["sort"] = self._get_sort_value_for_url(url)
        referer = url if isinstance(url, str) and url.startswith("http") else (self.base_url + "/browse")
        return self._fetch_json(self.API_VIDEOS_URL, params=params, referer=referer)

    def _build_playback_token(self, video):
        payload = {
            "mp4": video.get("videoUrl"),
            "hls": video.get("hlsMasterPlaylistUrl"),
        }
        return self.PLAYBACK_PREFIX + urllib.parse.quote(json.dumps(payload, separators=(",", ":")))

    def process_content(self, url, page=1):
        if not url or url == "BOOTSTRAP":
            url, _ = self.get_start_url_and_label()

        self.add_dir("Search", "", 5, self.icons.get("search", self.icon))
        self.add_dir("Categories", urllib.parse.urljoin(self.base_url, "/browse"), 8, self.icons.get("categories", self.icon))
        self._render_listing(url, page=page)

    def search(self, query):
        if not query:
            return
        self._render_listing(self.SEARCH_PREFIX + urllib.parse.quote_plus(query), page=1)

    def _render_listing(self, url, page=1):
        payload = self._get_listing_payload(url, page)
        if not payload or not payload.get("success"):
            self.end_directory("videos")
            return

        seen = set()
        added = 0
        videos = payload.get("videos") or payload.get("data") or []
        pagination = payload.get("pagination") if isinstance(payload.get("pagination"), dict) else {}

        for video in videos:
            playback_url = self._build_playback_token(video)
            if playback_url in seen:
                continue

            title = html.unescape((video.get("title") or "").strip())
            thumb = (video.get("thumbnailUrl") or self.icon).strip()
            duration_seconds = int(video.get("durationSeconds") or 0)
            duration = (video.get("duration") or "").strip()

            if not title:
                continue

            seen.add(playback_url)
            plot_bits = []
            uploader = (video.get("uploader") or video.get("uploaderUsername") or "").strip()
            if uploader:
                plot_bits.append("Uploader: {}".format(uploader))
            if video.get("views") is not None:
                plot_bits.append("Views: {}".format(video.get("views")))
            if duration:
                plot_bits.append("Duration: {}".format(duration))

            info = {
                "title": title,
                "plot": " | ".join(plot_bits) if plot_bits else title,
            }
            if duration_seconds:
                info["duration"] = duration_seconds

            self.add_link(title, playback_url, 4, thumb, self.fanart, info_labels=info)
            added += 1

        if added == 0:
            self.notify_error("No PMVHaven videos found")
        else:
            current_page = int(pagination.get("page") or page or 1)
            total_pages = int(pagination.get("totalPages") or current_page)
            if current_page < total_pages:
                self.add_dir(
                    "[COLOR blue]Next Page ({})[/COLOR]".format(current_page + 1),
                    url,
                    2,
                    self.icons.get("default", self.icon),
                    page=current_page + 1,
                )

        self.end_directory("videos")

    def process_categories(self, url):
        html_content = self.make_request(url or urllib.parse.urljoin(self.base_url, "/browse"))
        if not html_content:
            self.end_directory("videos")
            return

        seen = set()
        tag_matches = re.findall(r'title="Search for: #([^"]+)"', html_content, re.IGNORECASE)
        for raw_tag in tag_matches:
            tag = html.unescape(raw_tag).strip()
            tag_key = tag.lower()
            if not tag or tag_key in seen:
                continue
            seen.add(tag_key)
            tag_url = self.SEARCH_PREFIX + urllib.parse.quote_plus(tag)
            self.add_dir(tag, tag_url, 2, self.icons.get("categories", self.icon))

        self.end_directory("videos")

    def _score_stream(self, candidate):
        lowered = candidate.lower()
        if lowered.endswith(".mp4") or ".mp4?" in lowered:
            base = 1000
        elif lowered.endswith(".m3u8") or ".m3u8?" in lowered:
            base = 100
        else:
            base = 0

        for quality in (4320, 2160, 1440, 1080, 720, 480, 360, 240):
            if str(quality) in lowered:
                return base + quality
        return base

    def _build_header_url(self, stream_url, referer):
        headers = {
            "User-Agent": self.ua,
            "Referer": referer,
            "Origin": self.base_url,
            "Accept": "*/*",
        }
        return stream_url + "|" + "&".join(
            "{}={}".format(
                urllib.parse.quote(str(key), safe=""),
                urllib.parse.quote(str(value), safe=""),
            )
            for key, value in headers.items()
        )

    def play_video(self, url):
        candidates = []

        if url.startswith(self.PLAYBACK_PREFIX):
            try:
                payload = json.loads(urllib.parse.unquote(url[len(self.PLAYBACK_PREFIX):]))
                for candidate in (payload.get("mp4"), payload.get("hls")):
                    if candidate and candidate not in candidates:
                        candidates.append(candidate)
            except Exception as exc:
                self.logger.error("[PMVHaven] Could not decode playback payload: %s", exc)
        else:
            html_content = self.make_request(url, referer=self.base_url + "/")
            if not html_content:
                xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
                return

            patterns = [
                r'https://video\.pmvhaven\.com/[^\s"\'<>]+\.mp4[^\s"\'<>]*',
                r'https://video\.pmvhaven\.com/[^\s"\'<>]+\.m3u8[^\s"\'<>]*',
            ]
            for pattern in patterns:
                for match in re.findall(pattern, html_content, re.IGNORECASE):
                    cleaned = html.unescape(match.strip()).replace("\\/", "/")
                    if cleaned not in candidates:
                        candidates.append(cleaned)

        if not candidates:
            self.notify_error("No PMVHaven stream found")
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
            return

        stream_url = max(candidates, key=self._score_stream)
        referer = self.base_url + "/" if url.startswith(self.PLAYBACK_PREFIX) else url
        playback_url = self._build_header_url(stream_url, referer)

        list_item = xbmcgui.ListItem(path=playback_url)
        list_item.setProperty("IsPlayable", "true")
        list_item.setMimeType("application/vnd.apple.mpegurl" if ".m3u8" in stream_url else "video/mp4")
        list_item.setContentLookup(False)
        xbmcplugin.setResolvedUrl(self.addon_handle, True, list_item)
