# -*- coding: utf-8 -*-
import html
import os
import re
import urllib.parse
import requests
import xbmcgui
import xbmcplugin

from resources.lib.base_website import BaseWebsite
from resources.lib.resolvers import resolver


class PornoBae(BaseWebsite):
    def __init__(self, addon_handle, addon=None):
        super().__init__(
            name="pornobae",
            base_url="https://pornobae.com/",
            search_url="https://pornobae.com/?s={}",
            addon_handle=addon_handle,
            addon=addon,
        )
        self.session = requests.Session()
        self.ua = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/126.0.0.0 Safari/537.36"
        )
        self.icon = os.path.join(self.addon.getAddonInfo("path"), "resources", "logos", "pornobae.png")
        self.icons["default"] = self.icon

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
            response = self.session.get(url, headers=self._headers(referer), timeout=20)
            if response.status_code == 200:
                return response.text
            self.logger.warning("[pornobae] HTTP %s for %s", response.status_code, url)
        except Exception as exc:
            self.logger.warning("[pornobae] Request failed for %s: %s", url, exc)
        return ""

    def _absolute(self, url):
        if not url:
            return ""
        return urllib.parse.urljoin(self.base_url, html.unescape(url).strip())

    def _clean(self, value):
        value = html.unescape(value or "")
        value = re.sub(r"<[^>]+>", " ", value)
        value = re.sub(r"\s+", " ", value)
        return value.strip()

    def _thumbnail_url(self, value):
        thumb = self._absolute(value)
        if not thumb:
            return self.icon
        try:
            from resources.lib.thumb_proxy import build_thumb_url
            proxied = build_thumb_url(thumb, referer=self.base_url)
            if proxied != thumb:
                return proxied
            return "{}|User-Agent={}&Referer={}".format(
                thumb,
                urllib.parse.quote(self.ua),
                urllib.parse.quote(self.base_url),
            )
        except Exception:
            return thumb

    def _get_api_page(self, page):
        url = self._absolute(
            "/wp-json/wp/v2/posts?per_page=36&page={}&_embed=wp:featuredmedia".format(page)
        )
        try:
            response = self.session.get(url, headers=self._headers(), timeout=20)
            if response.status_code != 200:
                self.logger.warning("[pornobae] API HTTP %s for page %s", response.status_code, page)
                return [], 0
            return response.json(), int(response.headers.get("X-WP-TotalPages") or 0)
        except (ValueError, TypeError, requests.RequestException) as exc:
            self.logger.warning("[pornobae] API page %s failed: %s", page, exc)
            return [], 0

    def _extract_api_videos(self, posts):
        videos = []
        for post in posts or []:
            title = self._clean((post.get("title") or {}).get("rendered"))
            video_url = self._absolute(post.get("link"))
            if not title or not video_url:
                continue
            thumb = ""
            media = ((post.get("_embedded") or {}).get("wp:featuredmedia") or [])
            if media:
                details = media[0].get("media_details") or {}
                sizes = details.get("sizes") or {}
                selected = sizes.get("post-thumbnail") or sizes.get("medium") or {}
                thumb = selected.get("source_url") or media[0].get("source_url") or ""
            videos.append({
                "label": title,
                "url": video_url,
                "thumb": self._thumbnail_url(thumb),
                "info": {"title": title, "plot": self._clean((post.get("excerpt") or {}).get("rendered")) or title},
            })
        return videos

    def _is_top_listing(self, url):
        parsed = urllib.parse.urlparse(url or self.base_url)
        query = urllib.parse.parse_qs(parsed.query)
        return parsed.path.strip("/") in ("", "page/1") and "s" not in query

    def get_page_url(self, base_url, page_num):
        if page_num <= 1:
            return base_url
        parsed = urllib.parse.urlparse(base_url)
        path = parsed.path or "/"
        path = re.sub(r"/page/\d+/?$", "/", path)
        if path == "/":
            path = "/page/{}/".format(page_num)
        else:
            path = path.rstrip("/") + "/page/{}/".format(page_num)
        return urllib.parse.urlunparse((parsed.scheme, parsed.netloc, path, parsed.params, parsed.query, ""))

    def _extract_videos(self, html_content):
        chunks = html_content.split('<div class="post-thumbnail">')
        videos = []
        seen = set()
        
        for i in range(1, len(chunks)):
            prev_part = chunks[i-1]
            curr_part = chunks[i]
            
            a_matches = list(re.finditer(
                r'<a\b[^>]+href=["\'](https?://pornobae\.com/[^"\']+)["\'][^>]*title=["\']([^"\']+)["\']',
                prev_part,
                re.IGNORECASE
            ))
            if not a_matches:
                continue
            
            last_a = a_matches[-1]
            video_url = last_a.group(1)
            title = self._clean(last_a.group(2))
            
            if video_url in seen:
                continue
            seen.add(video_url)
            
            img_match = re.search(r'<img\b[^>]+src=["\']([^"\']+)["\']', curr_part, re.IGNORECASE)
            thumb = self._thumbnail_url(img_match.group(1)) if img_match else ""
            
            duration_match = re.search(r'class=["\']duration["\'][^>]*>([\s\S]*?)</span>', curr_part, re.IGNORECASE)
            duration = self._clean(duration_match.group(1)) if duration_match else ""
            
            seconds = self.convert_duration(duration)
            label = "{} [COLOR lime]({})[/COLOR]".format(title, duration) if duration else title
            
            info = {"title": title, "plot": title}
            if seconds:
                info["duration"] = seconds
                
            videos.append({
                "label": label,
                "url": video_url,
                "thumb": thumb or self.icon,
                "info": info
            })
            
        return videos

    def _extract_next_page(self, page_html, current_url, page):
        next_url = self.get_page_url(current_url, page + 1)
        next_parsed = urllib.parse.urlparse(next_url)
        next_path = next_parsed.path
        if next_path in page_html or urllib.parse.quote(next_path) in page_html:
            return next_url
        return ""

    def process_content(self, url, page=1):
        if not url or url == "BOOTSTRAP":
            url = self.base_url

        if page == 1 and self._is_top_listing(url):
            self.add_dir("Search", "", 5, self.icons.get("search", self.icon))
            self.add_dir("Categories", self._absolute("/categories/"), 8, self.icons.get("categories", self.icon))

        use_api = self._is_top_listing(url) and page > 1
        api_total_pages = 0
        if use_api:
            posts, api_total_pages = self._get_api_page(page)
            videos = self._extract_api_videos(posts)
            page_html = ""
        else:
            target_url = self.get_page_url(url, page)
            page_html = self._get(target_url)
            videos = self._extract_videos(page_html) if page_html else []
        if not page_html and not use_api:
            self.notify_error("Could not load PornoBae content")
            self.end_directory("videos")
            return

        if not videos:
            self.notify_error("No PornoBae videos found")
            self.end_directory("videos")
            return

        for item in videos:
            self.add_link(
                item["label"],
                item["url"],
                4,
                item["thumb"],
                self.fanart,
                info_labels=item["info"]
            )

        if self._is_top_listing(url):
            next_url = url if page == 1 or page < api_total_pages else ""
        else:
            next_url = self._extract_next_page(page_html, url, page)
        if next_url:
            self.add_dir("Next Page", url, 2, self.icons.get("default", self.icon), page=page + 1)

        self.end_directory("videos")

    def process_categories(self, url):
        current_url = url or self._absolute("/categories/")
        page_html = self._get(current_url)
        if not page_html:
            self.notify_error("Could not load PornoBae categories")
            self.end_directory("videos")
            return

        seen = set()
        matches = re.findall(
            r'<a\b[^>]+href=["\'](https?://pornobae\.com/category/[^"\']+)["\'][^>]*>([\s\S]*?)</a>',
            page_html,
            re.IGNORECASE
        )
        for link, label in matches:
            href = self._absolute(link)
            title = self._clean(label)
            if not href or not title or href in seen:
                continue
            seen.add(href)
            self.add_dir(title, href, 2, self.icons.get("default", self.icon), self.fanart)

        self.end_directory("videos")

    def resolve_recording_stream(self, url):
        page_html = self._get(url)
        if not page_html:
            return None

        # 1. Look for iframes
        iframes = re.findall(r'<iframe\b[^>]+src=["\']([^"\']+)["\']', page_html, re.IGNORECASE)
        for iframe in iframes:
            if "adtng" in iframe or "doubleclick" in iframe:
                continue
            embed_url = html.unescape(iframe).strip()
            try:
                from resources.lib.resolvers import resolver
                stream_url, play_headers = resolver.resolve(embed_url, referer=url)
                if stream_url:
                    ext = "m3u8" if ".m3u8" in stream_url else "mp4"
                    return {"url": stream_url, "headers": play_headers or {}, "extension": ext}
            except Exception:
                pass

        # 2. Try general resolver for whole page
        try:
            from resources.lib.resolvers import resolver
            res = resolver.resolve_first_working(page_html, referer=url)
            if res and isinstance(res, tuple) and res[0]:
                ext = "m3u8" if ".m3u8" in res[0] else "mp4"
                return {"url": res[0], "headers": res[1] or {}, "extension": ext}
        except Exception:
            pass

        return None

    def play_video(self, url):
        resolved = self.resolve_recording_stream(url)
        if not resolved or not resolved.get("url"):
            self.notify_error("Could not resolve video stream (Hoster may be offline)")
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
            return

        play_url = resolved["url"]
        headers = resolved.get("headers", {})
        header_str = urllib.parse.urlencode(headers) if headers else ""
        if "|" not in play_url and header_str:
            play_url += "|" + header_str

        list_item = xbmcgui.ListItem(path=play_url)
        list_item.setProperty("IsPlayable", "true")
        if resolved.get("extension") == "m3u8" or ".m3u8" in play_url:
            list_item.setMimeType("application/vnd.apple.mpegurl")
            import xbmc
            if xbmc.getCondVisibility("System.HasAddon(inputstream.adaptive)"):
                list_item.setProperty("inputstream", "inputstream.adaptive")
                list_item.setProperty("inputstream.adaptive.manifest_type", "hls")
                if header_str:
                    list_item.setProperty("inputstream.adaptive.manifest_headers", header_str)
                    list_item.setProperty("inputstream.adaptive.stream_headers", header_str)
        else:
            list_item.setMimeType("video/mp4")
        list_item.setContentLookup(False)
        xbmcplugin.setResolvedUrl(self.addon_handle, True, list_item)
