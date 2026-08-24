# -*- coding: utf-8 -*-
import html
import base64
import os
import re
import urllib.parse

import requests
import xbmcgui
import xbmcplugin

from resources.lib.base_website import BaseWebsite


class WordPressApiTube(BaseWebsite):
    """Small reusable WordPress REST listing engine for first-party tube sites."""

    POSTS_PER_PAGE = 24

    def __init__(self, name, label, base_url, addon_handle, addon=None):
        super().__init__(name, base_url, base_url + "?s={}", addon_handle, addon)
        self.label = label
        self.session = requests.Session()
        self.ua = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/128.0.0.0 Safari/537.36"
        )
        self.icon = os.path.join(
            self.addon.getAddonInfo("path"), "resources", "logos", name + ".png"
        )
        self.icons["default"] = self.icon

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
            response = self._request(url, referer=referer, timeout=20)
            if response.status_code == 200:
                return response.text
            self.logger.warning("[%s] HTTP %s for %s", self.name, response.status_code, url)
        except Exception as exc:
            self.logger.warning("[%s] Request failed for %s: %s", self.name, url, exc)
        return ""

    def _request(self, url, referer=None, timeout=25):
        headers = self._headers(referer)
        response = self.session.get(url, headers=headers, timeout=timeout)
        body = response.text or ""
        if response.status_code == 200 and "Checking your browser before accessing" in body:
            token = ""
            encoded = re.search(r"innerHTML\s*=\s*window\.atob\(['\"]([^'\"]+)", body, re.I)
            if encoded:
                try:
                    form = base64.b64decode(encoded.group(1)).decode("utf-8", "replace")
                    token_match = re.search(r'name=["\']antibot["\'][^>]*value=["\']([^"\']+)', form, re.I)
                    token = token_match.group(1) if token_match else ""
                except Exception:
                    token = ""
            if token:
                post_headers = self._headers(url)
                response = self.session.post(
                    url,
                    data={"antibot": token, "submit": "Click to continue"},
                    headers=post_headers,
                    timeout=timeout,
                    allow_redirects=True,
                )
        return response

    def _get_json(self, url, referer=None):
        try:
            response = self._request(url, referer=referer, timeout=25)
            if response.status_code == 200:
                return response.json(), response.headers
            self.logger.warning("[%s] API HTTP %s for %s", self.name, response.status_code, url)
        except Exception as exc:
            self.logger.warning("[%s] API request failed for %s: %s", self.name, url, exc)
        return None, {}

    def _clean(self, value):
        value = re.sub(r"<[^>]+>", " ", value or "")
        return re.sub(r"\s+", " ", html.unescape(value)).strip()

    def _absolute(self, value, base=None):
        return urllib.parse.urljoin(base or self.base_url, html.unescape(value or "").strip())

    def get_start_url_and_label(self):
        return self.base_url, self.label

    def _post_api_url(self, url, page):
        parsed = urllib.parse.urlparse(url or self.base_url)
        query = urllib.parse.parse_qs(parsed.query)
        params = {
            "per_page": str(self.POSTS_PER_PAGE),
            "page": str(max(1, int(page))),
            "_embed": "wp:featuredmedia",
            "orderby": "date",
            "order": "desc",
        }
        if query.get("s"):
            params["search"] = query["s"][0]
        if query.get("ah_category"):
            params["categories"] = query["ah_category"][0]
        if query.get("ah_tag"):
            params["tags"] = query["ah_tag"][0]
        return self._absolute("wp-json/wp/v2/posts?" + urllib.parse.urlencode(params))

    def _thumbnail(self, post):
        media = ((post.get("_embedded") or {}).get("wp:featuredmedia") or [])
        if not media:
            return self.icon
        item = media[0] or {}
        sizes = ((item.get("media_details") or {}).get("sizes") or {})
        for key in ("medium_large", "large", "medium", "post-thumbnail"):
            if (sizes.get(key) or {}).get("source_url"):
                return self._absolute(sizes[key]["source_url"])
        return self._absolute(item.get("source_url")) or self.icon

    def _video_items(self, posts):
        items = []
        for post in posts or []:
            title = self._clean((post.get("title") or {}).get("rendered"))
            url = self._absolute(post.get("link"))
            if not title or not url:
                continue
            items.append({
                "title": title,
                "url": url,
                "thumb": self._thumbnail(post),
                "info": {
                    "title": title,
                    "plot": self._clean((post.get("excerpt") or {}).get("rendered")) or title,
                },
            })
        return items

    def _html_listing_url(self, url, page):
        parsed = urllib.parse.urlparse(url or self.base_url)
        query = urllib.parse.parse_qs(parsed.query)
        source = (query.get("ah_source") or [""])[0]
        target = urllib.parse.urlparse(source or url or self.base_url)
        target_query = urllib.parse.parse_qs(target.query)
        for internal_key in ("ah_category", "ah_tag", "ah_source"):
            target_query.pop(internal_key, None)
        path = re.sub(r"/page/\d+/?$", "/", target.path or "/")
        if page > 1:
            path = path.rstrip("/") + "/page/{}/".format(page)
        return urllib.parse.urlunparse(target._replace(
            path=path,
            query=urllib.parse.urlencode(target_query, doseq=True),
        ))

    def _html_video_items(self, url, page):
        page_html = self._get(self._html_listing_url(url, page), referer=self.base_url)
        items = []
        seen = set()
        for block in re.findall(
            r'<article\b[^>]+class=["\'][^"\']*loop-video[^"\']*["\'][^>]*>([\s\S]*?)</article>',
            page_html or "", re.IGNORECASE,
        ):
            link = re.search(
                r'<a\b[^>]+href=["\']([^"\']+)["\'][^>]*(?:title=["\']([^"\']*)["\'])?',
                block, re.IGNORECASE,
            )
            if not link:
                continue
            video_url = self._absolute(link.group(1))
            if not video_url or video_url in seen:
                continue
            title = self._clean(link.group(2))
            image = re.search(
                r'<img\b[^>]+(?:data-src|src)=["\']([^"\']+)', block, re.IGNORECASE,
            )
            if not title and image:
                image_tag = re.search(r'<img\b[^>]*>', block, re.IGNORECASE)
                alt = re.search(r'\balt=["\']([^"\']+)', image_tag.group(0), re.IGNORECASE) if image_tag else None
                title = self._clean(alt.group(1)) if alt else ""
            if not title:
                continue
            seen.add(video_url)
            thumb = self._absolute(image.group(1)) if image else self.icon
            items.append({
                "title": title,
                "url": video_url,
                "thumb": thumb,
                "info": {"title": title, "plot": title},
            })
        next_page = page + 1
        has_next = bool(re.search(
            r'href=["\'][^"\']*/page/{}/'.format(next_page),
            page_html or "", re.IGNORECASE,
        ))
        return items, has_next

    def process_content(self, url, page=1):
        url = self.base_url if not url or url == "BOOTSTRAP" else url
        if self.is_primary_listing_url(url):
            self.add_dir("Search", "", 5, self.icons.get("search", self.icon))
            self.add_dir("Categories", "WP_CATEGORIES", 8, self.icons.get("categories", self.icon))
            if getattr(self, "show_pornstars", False):
                self.add_dir("Pornstars", "WP_TAGS", 9, self.icons.get("pornstars", self.icon))

        posts, headers = self._get_json(self._post_api_url(url, page), referer=self.base_url)
        has_next = False
        if isinstance(posts, list):
            items = self._video_items(posts)
            try:
                total_pages = int(headers.get("X-WP-TotalPages") or 0)
            except (TypeError, ValueError):
                total_pages = 0
            has_next = bool(items and page < total_pages)
        else:
            items, has_next = self._html_video_items(url, page)

        if not items:
            self.notify_error("Could not load {} content".format(self.label))
            self.end_directory("videos")
            return

        for item in items:
            self.add_link(
                item["title"], item["url"], 4, item["thumb"], self.fanart,
                info_labels=item["info"],
            )

        if has_next:
            self.add_dir("Next Page", url, 2, self.icons.get("default", self.icon), page=page + 1)
        self.end_directory("videos")

    def _taxonomy_page(self, taxonomy, url, mode, icon):
        page = 1
        if url and url not in ("WP_CATEGORIES", "WP_TAGS"):
            try:
                page = max(1, int(urllib.parse.parse_qs(urllib.parse.urlparse(url).query).get("page", [1])[0]))
            except (TypeError, ValueError):
                page = 1
        params = {"per_page": "100", "page": str(page), "orderby": "count", "order": "desc", "hide_empty": "true"}
        data, headers = self._get_json(
            self._absolute("wp-json/wp/v2/{}?{}".format(taxonomy, urllib.parse.urlencode(params))),
            referer=self.base_url,
        )
        if data is None:
            self.notify_error("Could not load {} directory".format(self.label))
            self.end_directory("videos")
            return
        key = "ah_category" if taxonomy == "categories" else "ah_tag"
        for entry in data:
            name = self._clean(entry.get("name"))
            if name and name.lower() != "uncategorized":
                target = self.base_url + "?" + urllib.parse.urlencode({
                    key: entry.get("id"),
                    "ah_source": self._absolute(entry.get("link")),
                })
                self.add_dir(name, target, 2, icon)
        try:
            total_pages = int(headers.get("X-WP-TotalPages") or 0)
        except (TypeError, ValueError):
            total_pages = 0
        if page < total_pages:
            self.add_dir("Next Page", "WP_DIRECTORY?page={}".format(page + 1), mode, icon)
        self.end_directory("videos")

    def process_categories(self, url):
        self._taxonomy_page("categories", url, 8, self.icons.get("categories", self.icon))

    def process_pornstars(self, url):
        self._taxonomy_page("tags", url, 9, self.icons.get("pornstars", self.icon))

    def search(self, query):
        if query:
            self.process_content(self.base_url + "?" + urllib.parse.urlencode({"s": query.strip()}))

    def _play_resolved(self, resolved):
        if not resolved or not resolved.get("url"):
            self.notify_error("Could not resolve {} stream".format(self.label))
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
            return
        stream_url = resolved["url"]
        headers = resolved.get("headers") or {}
        play_url = stream_url
        if headers:
            play_url += "|" + urllib.parse.urlencode(headers)
        item = xbmcgui.ListItem(path=play_url)
        item.setProperty("IsPlayable", "true")
        if ".m3u8" in stream_url.lower() or resolved.get("extension") == "m3u8":
            item.setMimeType("application/vnd.apple.mpegurl")
        else:
            item.setMimeType("video/mp4")
        item.setContentLookup(False)
        xbmcplugin.setResolvedUrl(self.addon_handle, True, item)

    def play_video(self, url):
        self._play_resolved(self.resolve_recording_stream(url))
