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


class BananaMovies(BaseWebsite):
    def __init__(self, addon_handle, addon=None):
        super().__init__(
            name="bananamovies",
            base_url="https://bananamovies.org",
            search_url="https://bananamovies.org/?s={}",
            addon_handle=addon_handle,
            addon=addon,
        )
        self.session = requests.Session()
        self.ua = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/128.0.0.0 Safari/537.36"
        )

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
            self.logger.error("[BananaMovies] HTTP %s for %s", response.status_code, url)
        except Exception as exc:
            self.logger.error("[BananaMovies] Request error for %s: %s", url, exc)
        return None

    def _build_header_url(self, stream_url, headers):
        return stream_url + "|" + urllib.parse.urlencode(headers)

    def _get_context_menu(self, original_url):
        return [
            (
                "Sort by...",
                "RunPlugin({}?mode=7&action=select_sort_order&website={}&original_url={})".format(
                    sys.argv[0],
                    self.name,
                    urllib.parse.quote_plus(original_url),
                ),
            )
        ]

    def _extract_sort_options(self, html_content, current_url):
        block_match = re.search(
            r'<div class="SrtdBy AADrpd">.*?<ul class="List AACont">(.*?)</ul>',
            html_content,
            re.IGNORECASE | re.DOTALL,
        )
        if not block_match:
            return []

        options = []
        for href, label in re.findall(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', block_match.group(1), re.IGNORECASE | re.DOTALL):
            clean_label = html.unescape(re.sub(r"<[^>]+>", "", label)).strip()
            if not clean_label:
                continue
            option_url = urllib.parse.urljoin(current_url, html.unescape(href.strip()))
            if not any(existing[0] == clean_label for existing in options):
                options.append((clean_label, option_url))
        return options

    def select_sort_order(self, original_url=None):
        target_url = original_url or (self.base_url + "/")
        html_content = self.make_request(target_url)
        if not html_content:
            return

        sort_options = self._extract_sort_options(html_content, target_url)
        if not sort_options:
            xbmcgui.Dialog().notification(
                "AdultHideout",
                "No sort options found.",
                xbmcgui.NOTIFICATION_INFO,
                2500,
            )
            return

        labels = [label for label, _ in sort_options]
        idx = xbmcgui.Dialog().select("Sort by...", labels)
        if idx == -1:
            return

        xbmc.executebuiltin(
            "Container.Update({}?mode=2&website={}&url={},replace)".format(
                sys.argv[0],
                self.name,
                urllib.parse.quote_plus(sort_options[idx][1]),
            )
        )

    def process_content(self, url):
        if not url or url == "BOOTSTRAP":
            url = self.base_url + "/"

        context_menu = self._get_context_menu(url)
        self.add_dir("Search", "", 5, self.icons.get("search", self.icon), context_menu=context_menu)
        self.add_dir(
            "Categories",
            self.base_url + "/",
            8,
            self.icons.get("categories", self.icon),
            context_menu=context_menu,
        )
        self.add_dir(
            "Pornstars",
            urllib.parse.urljoin(self.base_url, "/cast/"),
            9,
            self.icons.get("pornstars", self.icon),
            context_menu=context_menu,
        )
        self._render_listing(url, context_menu=context_menu)

    def _render_listing(self, url, context_menu=None):
        html_content = self.make_request(url)
        if not html_content:
            return self.end_directory("videos")

        pattern = re.compile(
            r'<li class="TPostMv[^"]*">.*?'
            r'<a href="(https://bananamovies\.org/[^"]+/)">.*?'
            r'<img src="([^"]+)" alt="([^"]+)".*?'
            r'<div class="Title">([^<]+)</div>.*?'
            r'<div class="mli-info1">\s*([^<]+)\s*</div>',
            re.IGNORECASE | re.DOTALL,
        )

        seen = set()
        for video_url, thumb, alt_text, title_text, duration_text in pattern.findall(html_content):
            if video_url in seen:
                continue
            seen.add(video_url)

            title = html.unescape((title_text or alt_text).strip())
            thumb = html.unescape(thumb.strip()) if thumb else self.icon
            if thumb.startswith("//"):
                thumb = "https:" + thumb
            elif thumb.startswith("/"):
                thumb = urllib.parse.urljoin(self.base_url, thumb)

            duration = re.sub(r"\s+", " ", duration_text).strip()
            info = {"title": title, "plot": title}
            duration_seconds = self.convert_duration(duration.replace("min.", "min").replace(".", "").strip())
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
        next_match = re.search(r'rel="next" href="([^"]+)"', html_content, re.IGNORECASE)
        if not next_match:
            next_match = re.search(r'<a[^>]+href="([^"]+)"[^>]*>\s*Next', html_content, re.IGNORECASE)
        if next_match:
            next_url = urllib.parse.urljoin(url, html.unescape(next_match.group(1).strip()))

        if next_url and next_url != url:
            self.add_dir("Next Page", next_url, 2, self.icons.get("default", self.icon), context_menu=context_menu)

        self.end_directory("videos")

    def process_categories(self, url):
        html_content = self.make_request(self.base_url + "/")
        if not html_content:
            return self.end_directory("videos")

        pattern = re.compile(
            r'<a[^>]+href="(https://bananamovies\.org/genre/[^"]+/)"[^>]*>([^<]+)</a>',
            re.IGNORECASE,
        )

        seen = set()
        for cat_url, label in pattern.findall(html_content):
            clean_label = html.unescape(re.sub(r"\s+", " ", label)).strip()
            if clean_label in ("Latest", "Next", "Years", "Pornstars", "Studios"):
                continue
            if not clean_label or clean_label.isdigit():
                continue
            if cat_url in seen:
                continue
            seen.add(cat_url)
            self.add_dir(
                clean_label,
                cat_url,
                2,
                self.icons.get("categories", self.icon),
                context_menu=self._get_context_menu(cat_url),
            )

        self.end_directory("videos")

    def process_pornstars(self, url):
        html_content = self.make_request(url)
        if not html_content:
            return self.end_directory("videos")

        pattern = re.compile(
            r'<a[^>]+href="(https://bananamovies\.org/cast/[^"]+/)"[^>]*>([^<]+)</a>',
            re.IGNORECASE,
        )

        seen = set()
        for star_url, label in pattern.findall(html_content):
            clean_label = html.unescape(re.sub(r"\s+", " ", label)).strip()
            if not clean_label or clean_label in seen:
                continue
            seen.add(clean_label)
            self.add_dir(
                clean_label,
                star_url,
                2,
                self.icons.get("pornstars", self.icon),
                context_menu=self._get_context_menu(star_url),
            )

        self.end_directory("videos")

    def search(self, query):
        if not query:
            return
        self.process_content(self.search_url.format(urllib.parse.quote_plus(query)))

    def _extract_hoster_candidates(self, html_content):
        candidates = []

        for host_url in re.findall(r'data-fl-url="([^"]+)"', html_content, re.IGNORECASE):
            host_url = html.unescape(host_url).replace("&amp;", "&").strip()
            if "/d/" in host_url:
                host_url = host_url.replace("/d/", "/e/")
            candidates.append(host_url)

        for href in re.findall(r'<a[^>]+href="(https?://[^"]+)"[^>]*>\s*(?:<img[^>]*>)?\s*DoodStream', html_content, re.IGNORECASE):
            host_url = html.unescape(href).replace("&amp;", "&").strip()
            if "doply.net/e/" in host_url:
                code = host_url.rstrip("/").split("/")[-1]
                host_url = "https://doodstream.com/e/{}/".format(code)
            candidates.append(host_url)

        unique = []
        seen = set()
        for item in candidates:
            if not item or item in seen:
                continue
            seen.add(item)
            unique.append(item)
        return unique

    def play_video(self, url):
        html_content = self.make_request(url)
        if not html_content:
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
            return

        hosters = self._extract_hoster_candidates(html_content)
        self.logger.info("[BananaMovies] Found %d host candidates", len(hosters))

        stream_url = None
        stream_headers = {}
        for hoster_url in hosters:
            try:
                result = resolver.resolve(hoster_url, referer=url)
                if isinstance(result, tuple):
                    candidate_url = result[0]
                    candidate_headers = result[1] if len(result) > 1 else {}
                else:
                    candidate_url = result
                    candidate_headers = {}

                if candidate_url and candidate_url.startswith("http"):
                    stream_url = candidate_url
                    stream_headers = candidate_headers
                    break
            except Exception as exc:
                self.logger.error("[BananaMovies] Resolver failed for %s: %s", hoster_url, exc)

        if not stream_url:
            xbmcgui.Dialog().notification(
                "AdultHideout",
                "No playable host found on this page.",
                xbmcgui.NOTIFICATION_ERROR,
                3000,
            )
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
            return

        playback_url = stream_url
        if "|" not in playback_url:
            headers = {
                "User-Agent": self.ua,
                "Referer": url,
            }
            headers.update(stream_headers or {})
            playback_url = self._build_header_url(stream_url, headers)

        list_item = xbmcgui.ListItem(path=playback_url)
        list_item.setProperty("IsPlayable", "true")
        list_item.setContentLookup(False)
        xbmcplugin.setResolvedUrl(self.addon_handle, True, list_item)
