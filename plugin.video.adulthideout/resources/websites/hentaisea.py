#!/usr/bin/env python
# -*- coding: utf-8 -*-

import html
import json
import re
import sys
import urllib.parse

import requests
import xbmcgui
import xbmcplugin

from resources.lib.base_website import BaseWebsite
from resources.lib.resilient_http import fetch_text


class Hentaisea(BaseWebsite):
    def __init__(self, addon_handle, addon=None):
        super().__init__(
            name="hentaisea",
            base_url="https://hentaisea.com/",
            search_url="https://hentaisea.com/?s={}",
            addon_handle=addon_handle,
            addon=addon,
        )
        self.label = "Hentaisea"
        self.session = requests.Session()
        self.ua = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/125.0.0.0 Safari/537.36"
        )
        self.ajax_url = "https://hentaisea.com/wp-admin/admin-ajax.php"
        self.sort_options = ["Latest Episodes", "Series"]
        self.sort_paths = {
            "Latest Episodes": "/episodes/",
            "Series": "/free/",
        }
        self.blocked_terms = ("shota", "loli", "yaoi")

    def _headers(self, referer=None, accept="text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"):
        return {
            "User-Agent": self.ua,
            "Accept": accept,
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "identity",
            "Referer": referer or self.base_url,
        }

    def _get(self, url, referer=None):
        try:
            response = self.session.get(url, headers=self._headers(referer), timeout=20, allow_redirects=True)
            if response.status_code == 200:
                return response.text
            self.logger.warning("Hentaisea HTTP %s for %s", response.status_code, url)
        except Exception as exc:
            self.logger.warning("Hentaisea request failed for %s: %s", url, exc)
            self.session = requests.Session()

        return fetch_text(
            url,
            headers=self._headers(referer),
            scraper=None,
            logger=self.logger,
            timeout=20,
            use_windows_curl_fallback=True,
        ) or ""

    def _post(self, url, data, referer):
        headers = self._headers(referer, accept="*/*")
        headers["X-Requested-With"] = "XMLHttpRequest"
        try:
            response = self.session.post(url, headers=headers, data=data, timeout=20)
            if response.status_code == 200:
                return response.text
            self.logger.warning("Hentaisea POST HTTP %s for %s", response.status_code, url)
        except Exception as exc:
            self.logger.warning("Hentaisea POST failed for %s: %s", url, exc)
        return ""

    def _absolute(self, value, base=None):
        if not value:
            return ""
        value = html.unescape(value).strip()
        if value.startswith("//"):
            value = "https:" + value
        return urllib.parse.urljoin(base or self.base_url, value)

    def _clean(self, value):
        value = re.sub(r"<[^>]+>", " ", value or "")
        return re.sub(r"\s+", " ", html.unescape(value)).strip()

    def _context_menu(self):
        return [
            (
                "Sort by...",
                "RunPlugin({}?mode=7&action=select_sort&website={})".format(sys.argv[0], self.name),
            )
        ]

    def _get_sort_key(self):
        try:
            idx = int(self.addon.getSetting("hentaisea_sort_by") or "0")
        except Exception:
            idx = 0
        if idx < 0 or idx >= len(self.sort_options):
            idx = 0
        return self.sort_options[idx]

    def get_start_url_and_label(self):
        sort_key = self._get_sort_key()
        return self._absolute(self.sort_paths.get(sort_key, "/episodes/")), "{} [COLOR yellow]{}[/COLOR]".format(self.label, sort_key)

    def get_page_url(self, base_url, page_num):
        if page_num <= 1:
            return base_url
        parsed = urllib.parse.urlparse(base_url)
        if parsed.query and "s=" in parsed.query:
            path = "/page/{}/".format(page_num)
            return urllib.parse.urlunparse((parsed.scheme, parsed.netloc, path, parsed.params, parsed.query, parsed.fragment))
        path = parsed.path.rstrip("/")
        if re.search(r"/page/\d+$", path):
            path = re.sub(r"/page/\d+$", "/page/{}".format(page_num), path)
        else:
            path = path + "/page/{}".format(page_num)
        return urllib.parse.urlunparse((parsed.scheme, parsed.netloc, path + "/", parsed.params, parsed.query, parsed.fragment))

    def _is_top_listing(self, url):
        parsed = urllib.parse.urlparse(url or self.base_url)
        return parsed.path.rstrip("/") in ("", "/episodes", "/free")

    def _is_allowed(self, text):
        text = (text or "").lower()
        return not any(term in text for term in self.blocked_terms)

    def _extract_videos(self, html_content):
        videos = []
        seen = set()
        blocks = re.findall(r"<article\b[^>]*>[\s\S]{0,16000}?</article>", html_content or "", re.IGNORECASE)
        for block in blocks:
            href_match = re.search(r'<a\b[^>]+href=["\']([^"\']*/(?:episodes|watch)/[^"\']+/)["\']', block, re.IGNORECASE)
            if not href_match:
                continue
            video_url = self._absolute(href_match.group(1))
            if not video_url or video_url in seen:
                continue

            img_match = re.search(r"<img\b[^>]*>", block, re.IGNORECASE)
            img_tag = img_match.group(0) if img_match else ""
            title_match = re.search(r'<h3\b[^>]*>\s*<a\b[^>]*>([\s\S]*?)</a>\s*</h3>', block, re.IGNORECASE)
            if not title_match:
                title_match = re.search(r'\s(?:alt|title)=["\']([^"\']+)["\']', img_tag, re.IGNORECASE)
            title = self._clean(title_match.group(1) if title_match else "")
            if not title or not self._is_allowed(title + " " + video_url):
                continue

            seen.add(video_url)
            thumb = ""
            for attr in ("data-src", "data-lazy-src", "src"):
                thumb_match = re.search(r'\s{}=["\']([^"\']+)["\']'.format(attr), img_tag, re.IGNORECASE)
                if thumb_match:
                    thumb = self._absolute(thumb_match.group(1), video_url)
                    break
            if thumb.startswith("data:image/"):
                thumb = self.icon

            duration_match = re.search(r'<span\b[^>]+class=["\'][^"\']*\b(?:runtime|duration)\b[^"\']*["\'][^>]*>([\s\S]*?)</span>', block, re.IGNORECASE)
            duration = self._clean(duration_match.group(1)) if duration_match else ""
            seconds = self.convert_duration(duration)
            label = "{} [COLOR lime]({})[/COLOR]".format(title, duration) if duration else title
            info = {"title": title, "plot": title}
            if seconds:
                info["duration"] = seconds
            videos.append({"label": label, "url": video_url, "thumb": thumb or self.icon, "info": info})
        return videos

    def _extract_next_page(self, html_content, current_url, page):
        next_url = self.get_page_url(current_url, page + 1)
        next_path = urllib.parse.urlparse(next_url).path
        if re.search(r'href=["\'][^"\']*{}[^"\']*["\']'.format(re.escape(next_path)), html_content or "", re.IGNORECASE):
            return next_url
        if re.search(r'>\s*{}\s*<'.format(page + 1), html_content or ""):
            return next_url
        return None

    def process_content(self, url, page=1):
        if not url or url == "BOOTSTRAP":
            url, _ = self.get_start_url_and_label()
        target_url = self.get_page_url(url, page)
        html_content = self._get(target_url)
        if not html_content:
            self.notify_error("Could not load Hentaisea listing")
            return self.end_directory("videos")

        context_menu = self._context_menu()
        if page == 1 and self._is_top_listing(url):
            self.add_dir("Search", "", 5, self.icons.get("search", self.icon), context_menu=context_menu)
            self.add_dir("Categories", self.base_url + "genre/", 8, self.icons.get("categories", self.icon), context_menu=context_menu)

        videos = self._extract_videos(html_content)
        if not videos:
            self.notify_error("No Hentaisea videos found")
            return self.end_directory("videos")

        for item in videos:
            self.add_link(item["label"], item["url"], 4, item["thumb"], self.fanart, context_menu=context_menu, info_labels=item["info"])

        if self._extract_next_page(html_content, target_url, page):
            self.add_dir("Next Page", url, 2, self.icons.get("default", self.icon), context_menu=context_menu, page=page + 1)
        self.end_directory("videos")

    def process_categories(self, url):
        html_content = self._get(self.base_url)
        if not html_content:
            self.notify_error("Could not load Hentaisea categories")
            return self.end_directory("videos")

        seen = set()
        for href, title_html in re.findall(r'<a\b[^>]+href=["\']([^"\']*/genre/[^"\']+/)["\'][^>]*>([\s\S]*?)</a>', html_content, re.IGNORECASE):
            category_url = self._absolute(href)
            title = self._clean(title_html)
            marker = "{} {}".format(title, category_url)
            if not title or category_url in seen or not self._is_allowed(marker):
                continue
            seen.add(category_url)
            self.add_dir(title, category_url, 2, self.icons.get("categories", self.icon), self.fanart)
        self.end_directory("videos")

    def search(self, query):
        if query:
            self.process_content(self.search_url.format(urllib.parse.quote_plus(query.strip())))

    def _first_episode_url(self, html_content, base_url):
        match = re.search(r'href=["\']([^"\']*/episodes/[^"\']+/)["\']', html_content or "", re.IGNORECASE)
        return self._absolute(match.group(1), base_url) if match else ""

    def _extract_player_options(self, html_content):
        options = []
        for li in re.findall(r'<li\b[^>]+class=["\'][^"\']*\bdooplay_player_option\b[^"\']*["\'][^>]*>', html_content or "", re.IGNORECASE):
            post = re.search(r'\bdata-post=["\']([^"\']+)["\']', li, re.IGNORECASE)
            nume = re.search(r'\bdata-nume=["\']([^"\']+)["\']', li, re.IGNORECASE)
            kind = re.search(r'\bdata-type=["\']([^"\']+)["\']', li, re.IGNORECASE)
            if post and nume and kind:
                options.append({"post": post.group(1), "nume": nume.group(1), "type": kind.group(1)})
        return options

    def _extract_iframe_src(self, ajax_html, referer):
        match = re.search(r'<iframe\b[^>]+src=["\']([^"\']+)["\']', ajax_html or "", re.IGNORECASE)
        return self._absolute(match.group(1), referer) if match else ""

    def _extract_jw_file(self, iframe_html):
        match = re.search(r"var\s+jw\s*=\s*(\{[\s\S]*?\});", iframe_html or "", re.IGNORECASE)
        if match:
            try:
                data = json.loads(match.group(1))
                return html.unescape(data.get("file") or "").replace("\\/", "/")
            except Exception:
                pass
        match = re.search(r'"file"\s*:\s*"((?:\\.|[^"\\])*)"', iframe_html or "", re.IGNORECASE)
        if match:
            try:
                return html.unescape(json.loads('"{}"'.format(match.group(1))))
            except Exception:
                return html.unescape(match.group(1)).replace("\\/", "/")
        return ""

    def _resolve_episode(self, episode_url):
        page_html = self._get(episode_url, referer=self.base_url)
        for option in self._extract_player_options(page_html):
            ajax_html = self._post(
                self.ajax_url,
                {"action": "doo_player_ajax", "post": option["post"], "nume": option["nume"], "type": option["type"]},
                episode_url,
            )
            iframe_url = self._extract_iframe_src(ajax_html, episode_url)
            if not iframe_url:
                continue
            iframe_html = self._get(iframe_url, referer=episode_url)
            stream_url = self._extract_jw_file(iframe_html)
            if stream_url:
                return {
                    "url": stream_url,
                    "headers": self._headers(iframe_url, accept="*/*"),
                    "extension": "mp4",
                }
        return None

    def resolve_recording_stream(self, url):
        target_url = url
        if "/watch/" in target_url:
            watch_html = self._get(target_url, referer=self.base_url)
            target_url = self._first_episode_url(watch_html, target_url)
        if not target_url or "/episodes/" not in target_url:
            return None
        return self._resolve_episode(target_url)

    def play_video(self, url):
        resolved = self.resolve_recording_stream(url)
        if not resolved:
            self.notify_error("Could not resolve Hentaisea stream")
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
            return
        play_url = resolved["url"]
        headers = resolved.get("headers") or {}
        if headers:
            play_url = "{}|{}".format(play_url, urllib.parse.urlencode(headers))
        item = xbmcgui.ListItem(path=play_url)
        item.setProperty("IsPlayable", "true")
        item.setMimeType("video/mp4")
        item.setContentLookup(False)
        xbmcplugin.setResolvedUrl(self.addon_handle, True, item)
