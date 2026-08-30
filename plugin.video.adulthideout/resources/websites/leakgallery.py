#!/usr/bin/env python
# -*- coding: utf-8 -*-

import html
import json
import re
import urllib.parse

import requests
import xbmc
import xbmcgui
import xbmcplugin

from resources.lib.base_website import BaseWebsite
from resources.lib.proxy_utils import PlaybackGuard, ProxyController
from resources.lib.resilient_http import fetch_text


class LeakGallery(BaseWebsite):
    def __init__(self, addon_handle, addon=None):
        super().__init__(
            "leakgallery",
            "https://leakgallery.com/",
            "https://leakgallery.com/search?search={}",
            addon_handle,
            addon,
        )
        self.label = "LeakGallery"
        self.ua = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
        )
        self.session = requests.Session()
        self.api_url = "https://api.leakgallery.com/home/user-posts/{}"

    def _headers(self, referer=None, accept=None):
        return {
            "User-Agent": self.ua,
            "Referer": referer or self.base_url,
            "Accept": accept or "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "identity",
        }

    def _get(self, url, referer=None):
        try:
            response = self.session.get(url, headers=self._headers(referer), timeout=20)
            if response.status_code == 200:
                return response.text
        except Exception:
            pass
        return fetch_text(
            url,
            headers=self._headers(referer),
            logger=self.logger,
            timeout=20,
        ) or ""

    def get_start_url_and_label(self):
        return self.base_url + "user-posts", "LeakGallery [COLOR yellow]Latest Videos[/COLOR]"

    def _cdn_url(self, value):
        value = html.unescape(value or "").replace("\\u002F", "/").replace("\\/", "/")
        if value.startswith("http"):
            return value
        return urllib.parse.urljoin("https://cdn.leakgallery.com/", value.lstrip("/"))

    def _user_post_items(self, content):
        items = []
        seen = set()
        content = html.unescape(content or "").replace('\\"', '"')
        pattern = re.compile(
            r'"id"\s*:\s*(\d+)[\s\S]{0,120}?"file_path"\s*:\s*"([^"]+\.mp4)"'
            r'[\s\S]{0,180}?"is_video"\s*:\s*true[\s\S]{0,180}?'
            r'"thumbnail_path"\s*:\s*"([^"]+)"[\s\S]{0,600}?'
            r'"profile"\s*:\s*\{[\s\S]{0,120}?"username"\s*:\s*"([^"]+)"',
            re.IGNORECASE,
        )
        for item_id, file_path, thumb_path, username in pattern.findall(content or ""):
            stream = self._cdn_url(file_path)
            if stream in seen:
                continue
            seen.add(stream)
            username = html.unescape(username)
            title = "{} #{}".format(username, item_id)
            items.append((
                title,
                stream,
                self._cdn_url(thumb_path),
                username,
                "{}{}/Videos".format(self.base_url, urllib.parse.quote(username)),
            ))
        return items

    def _profile_video_items(self, content):
        items = []
        seen = set()
        pattern = re.compile(
            r'"@type":"VideoObject","identifier":(\d+),"name":"([^"]*)",'
            r'"contentUrl":"([^"]+\.mp4)","thumbnailUrl":"([^"]+)"',
            re.IGNORECASE,
        )
        for item_id, raw_name, stream, thumb in pattern.findall(content or ""):
            stream = self._cdn_url(stream)
            if stream in seen:
                continue
            seen.add(stream)
            title = re.sub(r"\s+", " ", html.unescape(raw_name)).strip()
            if not title:
                title = "LeakGallery #{}".format(item_id)
            items.append((title, stream, self._cdn_url(thumb)))
        return items

    def _api_video_items(self, data):
        items = []
        seen = set()
        for group in (data or {}).get("content", []):
            for media in group.get("medias", []):
                if not media.get("is_video"):
                    continue
                stream = self._cdn_url(media.get("file_path"))
                if not stream or stream in seen:
                    continue
                seen.add(stream)
                profile = media.get("profile") or {}
                username = html.unescape(profile.get("username") or "LeakGallery")
                item_id = media.get("id")
                title = "{} #{}".format(username, item_id) if item_id else username
                items.append((
                    title,
                    stream,
                    self._cdn_url(media.get("thumbnail_path")),
                    username,
                    "{}{}/Videos".format(self.base_url, urllib.parse.quote(username)),
                ))
        return items

    def _user_posts_page(self, page):
        bootstrap_url = self.base_url + "user-posts"
        bootstrap = self._get(bootstrap_url)
        token_match = re.search(r'"APP_TOKEN":"([^"]+)"', bootstrap or "")
        if not token_match:
            return self._user_post_items(bootstrap), False, None

        headers = self._headers(bootstrap_url, accept="application/json")
        headers.update({
            "X-App-Token": token_match.group(1),
            "Origin": self.base_url.rstrip("/"),
        })
        # LeakGallery paginates mixed image/video groups. A valid API page can
        # contain no videos at all, so advance to the next video-bearing page
        # instead of presenting an empty Kodi directory.
        try:
            api_page = max(0, int(page) - 1)
        except (TypeError, ValueError):
            api_page = 0
        for candidate_page in range(api_page, api_page + 6):
            try:
                response = self.session.get(
                    self.api_url.format(candidate_page),
                    headers=headers,
                    timeout=20,
                )
                if response.status_code != 200:
                    continue
                data = response.json()
                items = self._api_video_items(data)
                if items:
                    return items, bool(data.get("content")), candidate_page + 2
                if not data.get("content"):
                    break
            except (TypeError, ValueError, json.JSONDecodeError):
                continue
            except Exception as exc:
                self.logger.warning("LeakGallery API request failed: %s", exc)
        return self._user_post_items(bootstrap), False, None

    def _add_navigation(self):
        entries = (
            ("Search", "", 5, self.icons["search"]),
            ("Discover", self.base_url + "discover", 2, self.icon),
            ("Trending", self.base_url + "trending-medias/Day", 2, self.icon),
            ("Most Liked", self.base_url + "most-liked", 2, self.icon),
            ("Random", self.base_url + "random/medias", 2, self.icon),
            ("Models", self.base_url + "new-models", 2, self.icons["pornstars"]),
            ("Categories", self.base_url + "tags", 2, self.icons["categories"]),
        )
        for label, target, mode, icon in entries:
            self.add_dir(label, target, mode, icon)

    def _add_categories(self, content):
        seen = set()
        for href, raw_label in re.findall(
            r'<a[^>]+href=["\'](/tag/[^"\']+)["\'][^>]*>([\s\S]*?)</a>',
            content or "",
            re.IGNORECASE,
        ):
            label = re.sub(r"<[^>]+>", " ", raw_label)
            label = re.sub(r"\s+", " ", html.unescape(label)).strip()
            target = urllib.parse.urljoin(self.base_url, href)
            if label and target not in seen:
                seen.add(target)
                self.add_dir(label, target, 2, self.icons["categories"])

    def _add_models(self, content):
        seen = set()
        for href, raw_label in re.findall(
            r'<a[^>]+href=["\']/([A-Za-z0-9._-]+)["\'][^>]*>([\s\S]*?)</a>',
            content or "",
            re.IGNORECASE,
        ):
            label = re.sub(r"<[^>]+>", " ", raw_label)
            label = re.sub(r"\s+", " ", html.unescape(label)).strip()
            if not label.lower().startswith("new "):
                continue
            label = label[4:].strip()
            target = "{}{}/Videos".format(self.base_url, urllib.parse.quote(href))
            if label and target not in seen:
                seen.add(target)
                self.add_dir(label, target, 2, self.icons["pornstars"])

    def _add_items(self, items):
        for entry in items:
            title, stream, thumb = entry[:3]
            uploader_name = entry[3] if len(entry) > 3 else None
            uploader_url = entry[4] if len(entry) > 4 else None
            self.add_link(
                title,
                stream,
                4,
                thumb,
                self.fanart,
                info_labels={"title": title, "plot": title},
                uploader_name=uploader_name,
                uploader_url=uploader_url,
            )

    def process_content(self, url, page=1):
        if not url or url == "BOOTSTRAP":
            url, _ = self.get_start_url_and_label()
        is_user_posts = (
            urllib.parse.urlparse(url).path.rstrip("/").lower() == "/user-posts"
        )
        path = urllib.parse.urlparse(url).path.rstrip("/").lower()
        if page == 1 and is_user_posts:
            self._add_navigation()
        if path == "/tags":
            self._add_categories(self._get(url))
            self.end_directory("videos")
            return
        if path in ("/new-models", "/trending-profiles/day"):
            self._add_models(self._get(url))
            self.end_directory("videos")
            return
        has_more = False
        next_page = None
        if is_user_posts:
            items, has_more, next_page = self._user_posts_page(page)
        else:
            content = self._get(url)
            if "/videos" in urllib.parse.urlparse(url).path.lower():
                items = self._profile_video_items(content)
            else:
                items = self._user_post_items(content)
        self._add_items(items)
        if items and has_more:
            self.add_dir("Next Page", url, 2, self.icon, page=next_page or page + 1)
        if not items:
            self.notify_error("No public LeakGallery videos found")
        self.end_directory("videos")

    def search(self, query):
        if not query:
            return
        search_url = self.search_url.format(urllib.parse.quote_plus(query.strip()))
        content = self._get(search_url, referer=self.base_url)
        usernames = []
        for username in re.findall(
            r'href=["\']/([A-Za-z0-9._-]+)["\'][^>]*>',
            content or "",
            re.IGNORECASE,
        ):
            lowered = username.lower()
            if lowered in (
                "search", "discover", "user-posts", "tiktok", "login", "register",
                "comments", "contact", "dmca", "terms", "trust-and-safety",
                "daily-search-ranking", "most-liked", "welcome-to-leakgallery",
                "about-leakgallery",
            ):
                continue
            if username not in usernames:
                usernames.append(username)
        found = []
        for username in usernames[:4]:
            profile_url = "{}{}/Videos".format(self.base_url, username)
            found.extend(self._profile_video_items(self._get(profile_url, referer=search_url))[:8])
        self._add_items(found)
        if not found:
            self.notify_error("No LeakGallery video results found")
        self.end_directory("videos")

    def resolve_recording_stream(self, url):
        if not url or ".mp4" not in url.lower():
            return None
        return {
            "url": url,
            "headers": {},
            "extension": "mp4",
        }

    def _warm_stream(self, url):
        response = None
        try:
            response = self.session.get(
                url,
                headers={
                    "Range": "bytes=0-65535",
                    "Accept": "*/*",
                    "Accept-Encoding": "identity",
                },
                stream=True,
                timeout=(3, 5),
            )
            if response.status_code in (200, 206):
                next(response.iter_content(65536), b"")
        except Exception:
            pass
        finally:
            if response is not None:
                response.close()

    def play_video(self, url):
        resolved = self.resolve_recording_stream(url)
        if not resolved:
            self.notify_error("Could not resolve LeakGallery stream")
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
            return
        try:
            controller = ProxyController(
                resolved["url"],
                upstream_headers=resolved.get("headers") or {},
                session=self.session,
                probe_size=True,
            )
            play_url = controller.start()
            PlaybackGuard(xbmc.Player(), xbmc.Monitor(), play_url, controller).start()
            item = xbmcgui.ListItem(path=play_url)
            item.setProperty("IsPlayable", "true")
            item.setMimeType("video/mp4")
            item.setContentLookup(False)
            xbmcplugin.setResolvedUrl(self.addon_handle, True, item)
        except Exception as exc:
            self.logger.error("LeakGallery proxy playback failed: %s", exc)
            self.notify_error("LeakGallery playback failed")
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
