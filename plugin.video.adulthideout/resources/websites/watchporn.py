# -*- coding: utf-8 -*-
import html
import re
import sys
import urllib.parse

import requests
import xbmcgui
import xbmcplugin

from resources.lib.base_website import BaseWebsite
from resources.lib.decoders.kvs_decoder import kvs_decode_url


class WatchPorn(BaseWebsite):
    def __init__(self, addon_handle, addon=None):
        super().__init__(
            name="watchporn",
            base_url="https://watchporn.to",
            search_url="https://watchporn.to/search/{}/",
            addon_handle=addon_handle,
            addon=addon,
        )
        self.session = requests.Session()
        self.ua = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/128.0.0.0 Safari/537.36"
        )

        self.video_sort_options = [
            "Latest",
            "Most Popular",
            "Top Rated",
        ]
        self.video_sort_paths = {
            "Latest": "/latest-updates/",
            "Most Popular": "/most-popular/",
            "Top Rated": "/top-rated/",
        }

        self.pornstar_sort_options = [
            "Alphabet",
            "Most Viewed",
            "Most Videos",
        ]
        self.pornstar_sort_params = {
            "Alphabet": "title",
            "Most Viewed": "avg_videos_popularity",
            "Most Videos": "total_videos",
        }

    def make_request(self, url, referer=None):
        headers = {
            "User-Agent": self.ua,
            "Referer": referer or (self.base_url + "/"),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }
        try:
            response = self.session.get(url, headers=headers, timeout=20)
            if response.status_code == 200:
                return response.text
            self.logger.error("[WatchPorn] HTTP %s for %s", response.status_code, url)
        except Exception as exc:
            self.logger.error("[WatchPorn] Request error for %s: %s", url, exc)
        return None

    def _get_video_sort_key(self):
        try:
            idx = int(self.addon.getSetting("watchporn_sort_by") or "0")
        except Exception:
            idx = 0
        if not 0 <= idx < len(self.video_sort_options):
            idx = 0
        return self.video_sort_options[idx]

    def _get_pornstar_sort_key(self):
        try:
            idx = int(self.addon.getSetting("watchporn_pornstar_sort_by") or "0")
        except Exception:
            idx = 0
        if not 0 <= idx < len(self.pornstar_sort_options):
            idx = 0
        return self.pornstar_sort_options[idx]

    def _apply_sort_param(self, url, param_value):
        parsed = urllib.parse.urlparse(url)
        query = urllib.parse.parse_qs(parsed.query)
        if param_value:
            query["sort_by"] = [param_value]
        else:
            query.pop("sort_by", None)
        return parsed._replace(query=urllib.parse.urlencode(query, doseq=True)).geturl()

    def _get_start_url(self):
        return urllib.parse.urljoin(
            self.base_url,
            self.video_sort_paths.get(self._get_video_sort_key(), "/latest-updates/"),
        )

    def _get_pornstars_url(self):
        return self._apply_sort_param(
            urllib.parse.urljoin(self.base_url, "/models/"),
            self.pornstar_sort_params.get(self._get_pornstar_sort_key(), ""),
        )

    def _get_video_context_menu(self, original_url):
        return [
            (
                "Sort by...",
                "RunPlugin({}?mode=7&action=select_sort_order&website={}&original_url={})".format(
                    sys.argv[0], self.name, urllib.parse.quote_plus(original_url)
                ),
            )
        ]

    def _get_pornstar_context_menu(self, original_url):
        return [
            (
                "Sort pornstars by...",
                "RunPlugin({}?mode=7&action=select_pornstar_sort_order&website={}&original_url={})".format(
                    sys.argv[0], self.name, urllib.parse.quote_plus(original_url)
                ),
            )
        ]

    def select_sort_order(self, original_url=None):
        current = self._get_video_sort_key()
        try:
            preselect = self.video_sort_options.index(current)
        except ValueError:
            preselect = 0
        idx = xbmcgui.Dialog().select("Sort by...", self.video_sort_options, preselect=preselect)
        if idx == -1:
            return

        self.addon.setSetting("watchporn_sort_by", str(idx))
        target = urllib.parse.unquote_plus(original_url) if original_url else self._get_start_url()
        if not target or target == "BOOTSTRAP":
            target = self._get_start_url()

        parsed = urllib.parse.urlparse(target)
        path = parsed.path or "/"
        if path in ("/", "/latest-updates/", "/most-popular/", "/top-rated/"):
            target = urllib.parse.urljoin(
                self.base_url,
                self.video_sort_paths.get(self.video_sort_options[idx], "/latest-updates/"),
            )
        elif "/search/" in path:
            sort_param = {
                "Latest": "",
                "Most Popular": "video_viewed",
                "Top Rated": "rating",
            }.get(self.video_sort_options[idx], "")
            target = self._apply_sort_param(target, sort_param)
        else:
            target = urllib.parse.urljoin(
                self.base_url,
                self.video_sort_paths.get(self.video_sort_options[idx], "/latest-updates/"),
            )
        xbmc.executebuiltin(
            "Container.Update({}?mode=2&website={}&url={})".format(
                sys.argv[0], self.name, urllib.parse.quote_plus(target)
            )
        )

    def select_pornstar_sort_order(self, original_url=None):
        current = self._get_pornstar_sort_key()
        try:
            preselect = self.pornstar_sort_options.index(current)
        except ValueError:
            preselect = 0
        idx = xbmcgui.Dialog().select("Sort pornstars by...", self.pornstar_sort_options, preselect=preselect)
        if idx == -1:
            return

        self.addon.setSetting("watchporn_pornstar_sort_by", str(idx))
        target = urllib.parse.unquote_plus(original_url) if original_url else self._get_pornstars_url()
        if not target or target == "BOOTSTRAP":
            target = self._get_pornstars_url()
        target = self._apply_sort_param(target, self.pornstar_sort_params.get(self.pornstar_sort_options[idx], ""))
        xbmc.executebuiltin(
            "Container.Update({}?mode=9&website={}&url={})".format(
                sys.argv[0], self.name, urllib.parse.quote_plus(target)
            )
        )

    def process_content(self, url):
        if not url or url == "BOOTSTRAP" or url.rstrip("/") == self.base_url.rstrip("/"):
            url = self._get_start_url()

        video_context = self._get_video_context_menu(url)
        pornstar_context = self._get_pornstar_context_menu(self._get_pornstars_url())

        self.add_dir("Search", "", 5, self.icons.get("search", self.icon), context_menu=video_context)
        self.add_dir(
            "Categories",
            urllib.parse.urljoin(self.base_url, "/categories/"),
            8,
            self.icons.get("categories", self.icon),
            context_menu=video_context,
        )
        self.add_dir(
            "Pornstars",
            self._get_pornstars_url(),
            9,
            self.icons.get("pornstars", self.icon),
            context_menu=pornstar_context,
        )
        self._render_listing(url, context_menu=video_context)

    def _render_listing(self, url, context_menu=None):
        html_content = self.make_request(url)
        if not html_content:
            return self.end_directory("videos")

        item_pattern = re.compile(
            r'<div class="thumb item\s*[^"]*">\s*'
            r'<a href="(https://watchporn\.to/video/[^"]+/)" title="([^"]+)".*?'
            r'<img[^>]+class="thumb[^"]*"[^>]+(?:data-original|src)="([^"]+)"[^>]+alt="([^"]+)".*?'
            r'<span class="thumb__info-item">([^<]+)</span>',
            re.IGNORECASE | re.DOTALL,
        )

        seen = set()
        for video_url, title_attr, thumb, alt_text, duration in item_pattern.findall(html_content):
            if video_url in seen:
                continue
            seen.add(video_url)

            title = html.unescape((title_attr or alt_text).strip())
            thumb = html.unescape(thumb.strip()) if thumb else self.icon
            if thumb.startswith("//"):
                thumb = "https:" + thumb
            elif thumb.startswith("/"):
                thumb = urllib.parse.urljoin(self.base_url, thumb)

            info = {"title": title, "plot": title}
            duration_seconds = self.convert_duration(duration.strip() if duration else "")
            if duration_seconds:
                info["duration"] = duration_seconds

            self.add_link(
                title,
                video_url,
                4,
                thumb,
                self.fanart,
                context_menu=context_menu,
                info_labels=info,
            )

        next_url = None
        next_matches = re.findall(r'<a[^>]+href="([^"]+)"[^>]*>\s*Next\s*</a>', html_content, re.IGNORECASE)
        for candidate in next_matches:
            if "/latest-updates/" in candidate or "/search/" in candidate or "/categories/" in url or "/models/" in url:
                next_url = urllib.parse.urljoin(self.base_url, html.unescape(candidate.strip()))
                break

        if next_url and next_url != url:
            self.add_dir("Next Page", next_url, 2, self.icons.get("default", self.icon), context_menu=context_menu)

        self.end_directory("videos")

    def process_categories(self, url):
        html_content = self.make_request(url)
        if not html_content:
            return self.end_directory("videos")

        seen = set()
        blocks = re.findall(
            r'(<a class="item thumb" href="https://watchporn\.to/categories/[^"]+/".*?</a>)',
            html_content,
            re.IGNORECASE | re.DOTALL,
        )
        for block in blocks:
            match = re.search(r'href="(https://watchporn\.to/categories/[^"]+/)" title="([^"]+)"', block, re.IGNORECASE)
            if not match:
                continue
            cat_url, title_attr = match.groups()
            if cat_url in seen:
                continue
            seen.add(cat_url)
            thumb_match = re.search(r'<img[^>]+src="([^"]+)"', block, re.IGNORECASE)
            title_match = re.search(r'<div class="thumb__title">([^<]+)</div>', block, re.IGNORECASE)
            count_match = re.search(r'<div class="thumb__info-item">\s*(?:<svg.*?</svg>)?\s*([^<]+)\s*</div>', block, re.IGNORECASE | re.DOTALL)
            title = html.unescape((title_match.group(1) if title_match else title_attr).strip())
            thumb = thumb_match.group(1).strip() if thumb_match else self.icons.get("categories", self.icon)
            count = re.sub(r"\s+", " ", count_match.group(1)).strip() if count_match else ""
            label = "{} ({})".format(title, count.strip()) if count else title
            self.add_dir(
                label,
                cat_url,
                2,
                thumb,
            )

        self.end_directory("videos")

    def process_pornstars(self, url):
        if not url or url == "BOOTSTRAP":
            url = self._get_pornstars_url()
        else:
            url = self._apply_sort_param(
                url,
                self.pornstar_sort_params.get(self._get_pornstar_sort_key(), ""),
            )

        html_content = self.make_request(url)
        if not html_content:
            return self.end_directory("videos")

        context_menu = self._get_pornstar_context_menu(url)
        seen = set()
        blocks = re.findall(
            r'(<a class="item thumb thumb--model" href="https://watchporn\.to/models/[^"]+/".*?</a>)',
            html_content,
            re.IGNORECASE | re.DOTALL,
        )
        for block in blocks:
            match = re.search(r'href="(https://watchporn\.to/models/[^"]+/)" title="([^"]+)"', block, re.IGNORECASE)
            if not match:
                continue
            star_url, title_attr = match.groups()
            if star_url in seen:
                continue
            seen.add(star_url)
            thumb_match = re.search(r'<img[^>]+src="([^"]+)"', block, re.IGNORECASE)
            title_match = re.search(r'<div class="thumb__title">([^<]+)</div>', block, re.IGNORECASE)
            count_match = re.search(r'(\d+\s+videos?)', block, re.IGNORECASE)
            title = html.unescape((title_match.group(1) if title_match else title_attr).strip())
            thumb = thumb_match.group(1).strip() if thumb_match else self.icons.get("pornstars", self.icon)
            count = count_match.group(1).strip() if count_match else ""
            label = "{} ({})".format(title, count.strip()) if count else title
            self.add_dir(
                label,
                star_url,
                2,
                thumb,
                self.fanart,
                context_menu=context_menu,
            )

        next_match = re.search(r'<a[^>]+href="([^"]+)"[^>]*>\s*Next\s*</a>', html_content, re.IGNORECASE)
        if next_match:
            next_url = urllib.parse.urljoin(self.base_url, html.unescape(next_match.group(1).strip()))
            next_url = self._apply_sort_param(
                next_url,
                self.pornstar_sort_params.get(self._get_pornstar_sort_key(), ""),
            )
            self.add_dir("Next Page", next_url, 9, self.icons.get("default", self.icon), context_menu=context_menu)

        self.end_directory("videos")

    def search(self, query):
        if not query:
            return
        search_url = self.search_url.format(urllib.parse.quote_plus(query))
        sort_param = {
            "Latest": "",
            "Most Popular": "video_viewed",
            "Top Rated": "rating",
        }.get(self._get_video_sort_key(), "")
        search_url = self._apply_sort_param(search_url, sort_param)
        self.process_content(search_url)

    def _probe_stream_candidate(self, stream_url, referer):
        headers = {
            "User-Agent": self.ua,
            "Referer": referer,
            "Origin": self.base_url,
            "Accept": "*/*",
        }
        try:
            response = self.session.get(
                stream_url,
                headers=headers,
                timeout=15,
                allow_redirects=False,
                stream=True,
            )
            status = response.status_code
            response.close()
            if status in (200, 206, 301, 302, 303, 307, 308):
                return True
        except Exception as exc:
            self.logger.error("[WatchPorn] Stream probe failed for %s: %s", stream_url, exc)
        return False

    def _choose_best_stream(self, html_content, preferred_url, referer):
        candidates = []
        if preferred_url:
            candidates.append((9999, preferred_url))

        stream_urls = re.findall(
            r'https://watchporn\.to/get_file/[^"\']+?\.mp4(?:/\?[^"\']+)?',
            html_content,
            re.IGNORECASE,
        )
        for stream_url in stream_urls:
            quality = 480
            match = re.search(r'_(\d{3,4})p\.mp4', stream_url, re.IGNORECASE)
            if match:
                quality = int(match.group(1))
            candidates.append((quality, stream_url))

        seen = set()
        for _, candidate_url in sorted(candidates, reverse=True):
            if candidate_url in seen:
                continue
            seen.add(candidate_url)
            if self._probe_stream_candidate(candidate_url, referer):
                return candidate_url

        return preferred_url

    def play_video(self, url):
        html_content = self.make_request(url)
        if not html_content:
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
            return

        video_url = None
        video_match = re.search(r"video_url\s*:\s*'([^']+)'", html_content)
        license_match = re.search(r"license_code\s*:\s*'([^']+)'", html_content)
        if video_match:
            video_url = html.unescape(video_match.group(1).replace("\\/", "/").strip())
            if license_match:
                video_url = kvs_decode_url(video_url, license_match.group(1).strip())

        video_url = self._choose_best_stream(html_content, video_url, url)

        if not video_url or not video_url.startswith("http"):
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
            return

        direct_headers = {
            "User-Agent": self.ua,
            "Referer": url,
            "Origin": self.base_url,
            "Accept": "*/*",
            "Accept-Encoding": "identity",
            "Accept-Language": "en-US,en;q=0.9",
            "Connection": "keep-alive",
        }

        playback_url = video_url + "|" + "&".join(
            "{}={}".format(
                urllib.parse.quote(str(key), safe=""),
                urllib.parse.quote(str(value), safe=""),
            )
            for key, value in direct_headers.items()
        )

        list_item = xbmcgui.ListItem(path=playback_url)
        list_item.setProperty("IsPlayable", "true")
        list_item.setMimeType("video/mp4")
        list_item.setContentLookup(False)
        xbmcplugin.setResolvedUrl(self.addon_handle, True, list_item)
