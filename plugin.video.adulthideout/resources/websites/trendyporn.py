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


class Trendyporn(BaseWebsite):
    def __init__(self, addon_handle, addon=None):
        super().__init__(
            name="trendyporn",
            base_url="https://www.trendyporn.com",
            search_url="https://www.trendyporn.com/search/{}/",
            addon_handle=addon_handle,
            addon=addon,
        )
        self.session = requests.Session()
        self.ua = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/126.0.0.0 Safari/537.36"
        )

    def make_request(self, url, referer=None):
        try:
            headers = {
                "User-Agent": self.ua,
                "Referer": referer or (self.base_url + "/"),
            }
            response = self.session.get(url, headers=headers, timeout=20)
            if response.status_code == 200:
                return response.text
            self.logger.error("[TrendyPorn] HTTP %s for %s", response.status_code, url)
        except Exception as exc:
            self.logger.error("[TrendyPorn] Request error: %s", exc)
        return None

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

    def _build_header_url(self, stream_url, headers):
        parts = []
        for key, value in headers.items():
            parts.append(
                "{}={}".format(
                    urllib.parse.quote(str(key), safe=""),
                    urllib.parse.quote(str(value), safe=""),
                )
            )
        return stream_url + "|" + "&".join(parts)

    def _extract_next_url(self, html_content, current_url):
        match = re.search(r'rel="next" href="([^"]+)"', html_content, re.IGNORECASE)
        if match:
            return urllib.parse.urljoin(current_url, html.unescape(match.group(1).strip()))
        return None

    def _extract_sort_options(self, html_content, current_url):
        options = []
        menu_match = re.search(
            r'<div class="btn-group">\s*<button[^>]*>.*?</button>\s*<ul class="dropdown-menu">(.*?)</ul>',
            html_content,
            re.IGNORECASE | re.DOTALL,
        )
        if not menu_match:
            return []

        for href, label in re.findall(r"<a href='([^']+)'>([^<]+)</a>", menu_match.group(1), re.IGNORECASE):
            clean_label = html.unescape(" ".join(label.split()))
            option_url = urllib.parse.urljoin(current_url, html.unescape(href.strip()))
            if not any(clean_label == item[0] for item in options):
                options.append((clean_label, option_url))
        return options

    def select_sort_order(self, original_url=None):
        target_url = original_url or self.base_url + "/"
        html_content = self.make_request(target_url)
        if not html_content:
            return

        sort_options = self._extract_sort_options(html_content, target_url)
        if not sort_options:
            xbmcgui.Dialog().notification(
                "AdultHideout",
                "No sort options found.",
                xbmcgui.NOTIFICATION_INFO,
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

    def _render_main_dirs(self, current_url):
        context_menu = self._get_context_menu(current_url)
        self.add_dir("Search", "", 5, self.icons.get("search", self.icon), context_menu=context_menu)
        self.add_dir(
            "Categories",
            urllib.parse.urljoin(self.base_url, "/channels/"),
            8,
            self.icons.get("categories", self.icon),
            context_menu=context_menu,
        )
        self.add_dir(
            "Models",
            urllib.parse.urljoin(self.base_url, "/models/"),
            2,
            self.icons.get("pornstars", self.icon),
            context_menu=context_menu,
        )

    def process_content(self, url):
        if not url or url == "BOOTSTRAP":
            url = self.base_url + "/"

        parsed = urllib.parse.urlparse(url)
        path = parsed.path.rstrip("/")

        self._render_main_dirs(url)

        if path.startswith("/models"):
            return self._render_models_listing(url)
        if path.startswith("/model"):
            return self._render_listing(url)
        self._render_listing(url)

    def _render_listing(self, url):
        html_content = self.make_request(url)
        if not html_content:
            return self.end_directory("videos")

        context_menu = self._get_context_menu(url)
        seen = set()
        item_pattern = re.compile(
            r'<div id="vid-\d+" class="col-sm-4 col-md-4 col-lg-3 vid".*?'
            r'<a[^>]+class="video-link" href="(https://www\.trendyporn\.com/video/[^"]+\.html)" title="([^"]+)">.*?'
            r'<img[^>]+data-original="([^"]+)"[^>]+(?:title|alt)="([^"]+)".*?'
            r'<div class="duration">([^<]+)</div>.*?'
            r'<span class="video-title[^"]*">([^<]+)</span>',
            re.IGNORECASE | re.DOTALL,
        )

        for video_url, title_attr, thumb, img_title, duration, row_title in item_pattern.findall(html_content):
            if video_url in seen:
                continue
            seen.add(video_url)

            title = html.unescape((row_title or title_attr or img_title).strip())
            thumb = thumb.strip() if thumb else self.icon
            if thumb.startswith("//"):
                thumb = "https:" + thumb
            elif thumb.startswith("/"):
                thumb = urllib.parse.urljoin(self.base_url, thumb)

            info = {"title": title, "plot": title}
            duration_seconds = self.convert_duration(duration.strip() if duration else "")
            if duration_seconds:
                info["duration"] = duration_seconds

            self.add_link(title, video_url, 4, thumb, self.fanart, context_menu=context_menu, info_labels=info)

        next_url = self._extract_next_url(html_content, url)
        if next_url:
            self.add_dir("Next Page", next_url, 2, self.icons.get("default", self.icon), context_menu=context_menu)

        self.end_directory("videos")

    def process_categories(self, url):
        html_content = self.make_request(url)
        if not html_content:
            return self.end_directory("videos")

        pattern = re.compile(
            r'<a href="(https://www\.trendyporn\.com/channels/\d+/[^"]+/)" title="([^"]+)">.*?'
            r'<img class="img-responsive" src="([^"]+)" alt="([^"]+)"',
            re.IGNORECASE | re.DOTALL,
        )
        seen = set()
        for cat_url, title_attr, thumb, img_alt in pattern.findall(html_content):
            if cat_url in seen:
                continue
            seen.add(cat_url)
            label = html.unescape((title_attr or img_alt).strip())
            self.add_dir(label, cat_url, 2, thumb, self.fanart, context_menu=self._get_context_menu(cat_url))

        self.end_directory("videos")

    def _render_models_listing(self, url):
        html_content = self.make_request(url)
        if not html_content:
            return self.end_directory("videos")

        content_segment = html_content.split("<!-- cam api -->", 1)[0]
        context_menu = self._get_context_menu(url)
        pattern = re.compile(
            r'<a href="(https://www\.trendyporn\.com/model/[^"]+/)" title="([^"]+)">.*?'
            r'<img class="img-responsive(?: lazy)?"[^>]+(?:data-original|src)="([^"]+)"[^>]+alt="([^"]+)"',
            re.IGNORECASE | re.DOTALL,
        )

        seen = set()
        for model_url, title_attr, thumb, img_alt in pattern.findall(content_segment):
            if model_url in seen:
                continue
            seen.add(model_url)
            title = html.unescape((title_attr or img_alt).strip())
            self.add_dir(title, model_url, 2, thumb, self.fanart, context_menu=context_menu)

        next_url = self._extract_next_url(html_content, url)
        if next_url:
            self.add_dir("Next Page", next_url, 2, self.icons.get("default", self.icon), context_menu=context_menu)

        self.end_directory("videos")

    def search(self, query):
        if not query:
            return
        encoded_query = urllib.parse.quote(query)
        self.process_content(self.search_url.format(encoded_query))

    def play_video(self, url):
        html_content = self.make_request(url, referer=self.base_url + "/")
        if not html_content:
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
            return

        match = re.search(r'<source src="([^"]+\.mp4[^"]*)"', html_content, re.IGNORECASE)
        if not match:
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
            return

        stream_url = html.unescape(match.group(1).strip())
        headers = {
            "User-Agent": self.ua,
            "Referer": url,
            "Accept": "*/*",
            "Accept-Language": "en-US,en;q=0.9",
            "Connection": "keep-alive",
        }
        list_item = xbmcgui.ListItem(path=self._build_header_url(stream_url, headers))
        list_item.setProperty("IsPlayable", "true")
        list_item.setMimeType("video/mp4")
        list_item.setContentLookup(False)
        xbmcplugin.setResolvedUrl(self.addon_handle, True, list_item)
