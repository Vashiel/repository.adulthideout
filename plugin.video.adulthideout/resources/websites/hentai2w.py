#!/usr/bin/env python
# -*- coding: utf-8 -*-

import json
import re
import urllib.parse

import xbmcgui
import xbmcplugin

from resources.lib.kvs_tube import KVSTubeWebsite


class Hentai2W(KVSTubeWebsite):
    label = "Hentai2W"
    use_playback_proxy = True
    sort_options = ["Most Recent", "Most Viewed", "Top Rated", "Longest"]
    sort_paths = {
        "Most Recent": "/videos/",
        "Most Viewed": "/most-viewed/",
        "Top Rated": "/top-rated/",
        "Longest": "/longest/",
    }
    categories_path = "/channels/"
    models_path = None
    video_path_markers = ("/video/",)
    category_path_markers = ("/channels/",)

    def __init__(self, addon_handle, addon=None):
        super().__init__(
            name="hentai2w",
            base_url="https://hentai2w.com/",
            search_url="https://hentai2w.com/search/{}/",
            addon_handle=addon_handle,
            addon=addon,
        )

    def _is_top_listing(self, url):
        return urllib.parse.urlparse(url or self.base_url).path.rstrip("/") in (
            "", "/videos", "/most-viewed", "/top-rated", "/longest"
        )

    @staticmethod
    def _page_props(content):
        for attrs, body in re.findall(r'<script\b([^>]*)>([\s\S]*?)</script>', content or "", re.I):
            if "application/json" in attrs:
                try:
                    value = json.loads(body)
                    if isinstance(value.get("props"), dict):
                        return value["props"]
                except (ValueError, AttributeError):
                    continue
        return {}

    def process_content(self, url, page=1):
        target = self._absolute("/browse") if not url or url == "BOOTSTRAP" or urllib.parse.urlsplit(url).path.rstrip("/") in ("", "/videos") else url
        if page > 1:
            parsed = urllib.parse.urlsplit(target)
            query = dict(urllib.parse.parse_qsl(parsed.query))
            query["page"] = str(page)
            target = urllib.parse.urlunsplit(parsed._replace(query=urllib.parse.urlencode(query)))
        content = self._get(target)
        props = self._page_props(content)
        if not props:
            return super().process_content(url, page=page)
        if isinstance(props.get("episodes"), list):
            series = props.get("series") or {}
            for episode in props["episodes"]:
                title = self._clean("{} - {}".format(series.get("title", ""), episode.get("title") or episode.get("number", "")))
                if any(term in title.lower() for term in ("loli", "shota")):
                    continue
                video_url = self._absolute("/watch/{}".format(episode["id"]))
                self.add_link(title, video_url, 4, episode.get("thumbnail_url") or series.get("cover_url") or self.icon,
                              self.fanart, info_labels={"title": title, "plot": title, "duration": episode.get("duration_seconds", 0)})
        else:
            self.add_dir("Search", "", 5, self.icons.get("search", self.icon))
            series = props.get("series") or {}
            records = series.get("data", []) if isinstance(series, dict) else series
            for entry in records:
                title = self._clean(entry.get("title"))
                if entry.get("is_licensed") or any(term in title.lower() for term in ("loli", "shota")):
                    continue
                self.add_dir(title, self._absolute("/series/" + entry["slug"]), 2, entry.get("cover_url") or self.icon)
            if isinstance(series, dict) and series.get("next_page_url"):
                self.add_dir("Next Page", self._absolute(series["next_page_url"]), 2, self.icon)
        self.end_directory("videos")

    def resolve_recording_stream(self, url):
        self._age_gate_blocked = False
        props = self._page_props(self._get(url))
        playlist = props.get("playlist")
        if isinstance(playlist, str) and playlist.startswith("https://"):
            if props.get("ageGate") and not self.session.cookies.get("age_confirmed"):
                self._confirm_age_gate(url)
            headers = self._headers(
                url,
                accept="application/vnd.apple.mpegurl,application/x-mpegURL,*/*",
            )
            headers["Origin"] = urllib.parse.urlsplit(self.base_url).scheme + "://" + urllib.parse.urlsplit(self.base_url).netloc
            if self.session.cookies:
                headers["Cookie"] = "; ".join("{}={}".format(c.name, c.value) for c in self.session.cookies)
            try:
                response = self.session.get(
                    playlist,
                    headers=headers,
                    allow_redirects=False,
                    timeout=8,
                )
                if response.is_redirect:
                    destination = urllib.parse.urljoin(playlist, response.headers.get("Location", ""))
                    if urllib.parse.urlsplit(destination).path.rstrip("/").lower() == "/age-gate":
                        self._age_gate_blocked = True
                        self.logger.warning("[Hentai2W] Stream is blocked by the site's age-gate route")
                        return None
            except Exception as exc:
                self.logger.debug("[Hentai2W] Playlist preflight unavailable: %s", exc)
            return {"url": playlist, "headers": headers, "extension": "m3u8"}
        return super().resolve_recording_stream(url)

    def _confirm_age_gate(self, video_url):
        xsrf = None
        for cookie in self.session.cookies:
            if cookie.name == "XSRF-TOKEN":
                xsrf = urllib.parse.unquote(cookie.value)
                break
        if not xsrf:
            return False

        headers = self._headers(video_url, accept="text/html,application/xhtml+xml,*/*")
        headers["Origin"] = urllib.parse.urlsplit(self.base_url).scheme + "://" + urllib.parse.urlsplit(self.base_url).netloc
        headers["X-XSRF-TOKEN"] = xsrf
        headers["X-Requested-With"] = "XMLHttpRequest"
        try:
            response = self.session.post(
                self._absolute("/age-gate"),
                data={},
                headers=headers,
                allow_redirects=False,
                timeout=8,
            )
            if self.session.cookies.get("age_confirmed"):
                return True
            destination = urllib.parse.urljoin(self.base_url, response.headers.get("Location", ""))
            return response.is_redirect and urllib.parse.urlsplit(destination).path == urllib.parse.urlsplit(video_url).path
        except Exception as exc:
            self.logger.warning("[Hentai2W] Age confirmation request failed: %s", exc)
            return False

    def play_video(self, url):
        if not urllib.parse.urlsplit(url).path.startswith("/watch/"):
            return super().play_video(url)
        resolved = self.resolve_recording_stream(url)
        item = xbmcgui.ListItem()
        if resolved:
            item.setPath(resolved["url"] + "|" + urllib.parse.urlencode(resolved["headers"]))
            item.setMimeType("application/vnd.apple.mpegurl")
            item.setContentLookup(False)
        xbmcplugin.setResolvedUrl(self.addon_handle, bool(resolved), item)

    def get_page_url(self, base_url, page_num):
        if page_num <= 1:
            return base_url
        parsed = urllib.parse.urlparse(base_url)
        path = re.sub(r"/page\d+\.html$", "/", parsed.path)
        path = path.rstrip("/") + "/page{}.html".format(page_num)
        return urllib.parse.urlunparse(
            (parsed.scheme, parsed.netloc, path, parsed.params, parsed.query, parsed.fragment)
        )

    def _extract_videos(self, html_content):
        videos = []
        seen = set()
        for block in re.findall(
            r'<div\b[^>]+class=["\'][^"\']*\bitem-col\b[^"\']*-video[^"\']*["\'][^>]*>'
            r'[\s\S]{0,5000}?<!--\s*item END\s*-->',
            html_content or "",
            re.IGNORECASE,
        ):
            href_match = re.search(
                r'<a\b[^>]+href=["\']([^"\']*/video/[^"\']+\.html)["\'][^>]*'
                r'title=["\']([^"\']+)["\']',
                block,
                re.IGNORECASE,
            )
            if not href_match:
                continue
            video_url = self._absolute(href_match.group(1))
            title = self._clean(href_match.group(2))
            if not video_url or video_url in seen or not title:
                continue
            img_match = re.search(r"<img\b[^>]*>", block, re.IGNORECASE)
            thumb = self._pick_thumb(img_match.group(0) if img_match else "")
            duration_match = re.search(
                r'class=["\'][^"\']*\bitem-time\b[^"\']*["\'][^>]*>([^<]+)',
                block,
                re.IGNORECASE,
            )
            duration = self._clean(duration_match.group(1) if duration_match else "")
            seconds = self.convert_duration(duration)
            label = "{} [COLOR lime]({})[/COLOR]".format(title, duration) if duration else title
            info = {"title": title, "plot": title}
            if seconds:
                info["duration"] = seconds
            seen.add(video_url)
            videos.append({"label": label, "url": video_url, "thumb": thumb or self.icon, "info": info})
        return videos

    def _extract_next_page(self, html_content, current_url, page):
        expected = self.get_page_url(current_url, page + 1)
        filename = urllib.parse.urlparse(expected).path.rsplit("/", 1)[-1]
        if re.search(r'(?:rel=["\']next["\'][^>]+href|href)=["\'][^"\']*{}["\']'.format(
                re.escape(filename)), html_content or "", re.IGNORECASE):
            return expected
        return None

    def process_categories(self, url):
        current_url = url or self._absolute(self.categories_path)
        html_content = self._get(current_url)
        seen = set()
        for block in re.findall(
            r'<div\b[^>]+class=["\'][^"\']*\bitem-col\b[^"\']*-channel[^"\']*["\'][^>]*>'
            r'[\s\S]{0,2600}?<!--\s*item END\s*-->',
            html_content or "",
            re.IGNORECASE,
        ):
            match = re.search(
                r'<a\b[^>]+href=["\']([^"\']*/channels/\d+/[^"\']+/)["\'][^>]*'
                r'title=["\']([^"\']+)["\']',
                block,
                re.IGNORECASE,
            )
            if not match:
                continue
            target = self._absolute(match.group(1))
            title = self._clean(match.group(2))
            if target in seen or not title or any(term in title.lower() for term in ("shota", "loli")):
                continue
            img_match = re.search(r"<img\b[^>]*>", block, re.IGNORECASE)
            thumb = self._pick_thumb(img_match.group(0) if img_match else "")
            seen.add(target)
            self.add_dir(title, target, 2, thumb or self.icons.get("categories", self.icon), self.fanart)
        self.end_directory("videos")

    def search(self, query):
        if query:
            self.process_content(self._absolute("/browse?q={}".format(urllib.parse.quote_plus(query.strip()))))
