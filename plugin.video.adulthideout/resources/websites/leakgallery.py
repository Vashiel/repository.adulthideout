#!/usr/bin/env python
# -*- coding: utf-8 -*-

import html
import json
import re
import urllib.parse

import requests
import xbmcgui
import xbmcplugin

from resources.lib.base_website import BaseWebsite
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
        pattern = re.compile(
            r'"id":(\d+),"file_path":"([^"]+\.mp4)","is_video":true,'
            r'"thumbnail_path":"([^"]+)"[\s\S]{0,600}?"profile":\{"username":"([^"]+)"',
            re.IGNORECASE,
        )
        for item_id, file_path, thumb_path, username in pattern.findall(content or ""):
            stream = self._cdn_url(file_path)
            if stream in seen:
                continue
            seen.add(stream)
            username = html.unescape(username)
            title = "{} #{}".format(username, item_id)
            items.append((title, stream, self._cdn_url(thumb_path)))
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
                ))
        return items

    def _user_posts_page(self, page):
        bootstrap_url = self.base_url + "user-posts"
        bootstrap = self._get(bootstrap_url)
        token_match = re.search(r'"APP_TOKEN":"([^"]+)"', bootstrap or "")
        if not token_match:
            return self._user_post_items(bootstrap), False

        headers = self._headers(bootstrap_url, accept="application/json")
        headers.update({
            "X-App-Token": token_match.group(1),
            "Origin": self.base_url.rstrip("/"),
        })
        try:
            response = self.session.get(
                self.api_url.format(max(1, int(page))),
                headers=headers,
                timeout=20,
            )
            if response.status_code == 200:
                data = response.json()
                return self._api_video_items(data), bool(data.get("content"))
        except (TypeError, ValueError, json.JSONDecodeError):
            pass
        except Exception as exc:
            self.logger.warning("LeakGallery API request failed: %s", exc)
        return self._user_post_items(bootstrap), False

    def _add_items(self, items):
        for title, stream, thumb in items:
            self.add_link(
                title,
                stream,
                4,
                thumb,
                self.fanart,
                info_labels={"title": title, "plot": title},
            )

    def process_content(self, url, page=1):
        if not url or url == "BOOTSTRAP":
            url, _ = self.get_start_url_and_label()
        is_user_posts = (
            urllib.parse.urlparse(url).path.rstrip("/").lower() == "/user-posts"
        )
        if page == 1 and is_user_posts:
            self.add_dir("Search", "", 5, self.icons["search"])
        has_more = False
        if is_user_posts:
            items, has_more = self._user_posts_page(page)
        else:
            content = self._get(url)
            if "/videos" in urllib.parse.urlparse(url).path.lower():
                items = self._profile_video_items(content)
            else:
                items = self._user_post_items(content)
        self._add_items(items)
        if items and has_more:
            self.add_dir("Next Page", url, 2, self.icon, page=page + 1)
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
        self._warm_stream(resolved["url"])
        item = xbmcgui.ListItem(path=resolved["url"])
        item.setProperty("IsPlayable", "true")
        item.setMimeType("video/mp4")
        item.setContentLookup(False)
        xbmcplugin.setResolvedUrl(self.addon_handle, True, item)
