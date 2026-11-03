# -*- coding: utf-8 -*-
import base64
import hashlib
import html
import json
import os
import re
import time
import urllib.parse

import requests
import xbmc
import xbmcgui
import xbmcplugin
import xbmcvfs

from resources.lib.base_website import BaseWebsite


class RetroStreamNetworkWebsite(BaseWebsite):
    label = "Retro Stream"
    search_param = "s"

    def __init__(self, name, label, base_url, addon_handle, addon=None, search_param="s"):
        self.label = label
        self.search_param = search_param
        base_url = base_url.rstrip("/") + "/"
        super().__init__(
            name=name,
            base_url=base_url,
            search_url=base_url + "?{}={{}}".format(search_param),
            addon_handle=addon_handle,
            addon=addon,
        )
        self.session = requests.Session()
        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }

    def _get_cache_file(self):
        try:
            profile_dir = xbmcvfs.translatePath(self.addon.getAddonInfo("profile"))
            if not os.path.exists(profile_dir):
                os.makedirs(profile_dir, exist_ok=True)
            return os.path.join(profile_dir, f"clearance_{self.name}.json")
        except Exception:
            return ""

    def _load_cached_cookies(self):
        try:
            cached = None
            prop = xbmcgui.Window(10000).getProperty(f"AdultHideout.Clearance.{self.name}")
            if prop:
                cached = json.loads(prop)
                self.logger.info("[%s] Loaded clearance from Window property", self.name)
            else:
                cache_file = self._get_cache_file()
                self.logger.info("[%s] Checking cache file: %s (exists=%s)", self.name, cache_file, os.path.isfile(cache_file) if cache_file else False)
                if cache_file and os.path.isfile(cache_file):
                    with open(cache_file, "r", encoding="utf-8") as f:
                        cached = json.load(f)
                    if cached:
                        xbmcgui.Window(10000).setProperty(f"AdultHideout.Clearance.{self.name}", json.dumps(cached))
                        self.logger.info("[%s] Loaded clearance from file into property", self.name)

            if cached:
                age = time.time() - cached.get("ts", 0)
                if age < 86400:
                    domain = cached.get("domain", "")
                    if domain and not domain.startswith("."):
                        domain = "." + domain
                    self.session.cookies.clear()
                    for name, val in cached.get("cookies", {}).items():
                        if domain:
                            self.session.cookies.set(name, val, domain=domain)
                        else:
                            self.session.cookies.set(name, val)
                    if cached.get("ua"):
                        self.headers["User-Agent"] = cached["ua"]
                    self.logger.info("[%s] Applied cached clearance (age=%.1fs, cookies=%s, ua=%s)",
                                     self.name, age, list(cached.get("cookies", {}).keys()), self.headers.get("User-Agent"))
                else:
                    self.logger.warning("[%s] Cached clearance expired (age=%.1fs)", self.name, age)
            else:
                self.logger.warning("[%s] No cached clearance found", self.name)
        except Exception as exc:
            self.logger.error("[%s] Error in _load_cached_cookies: %s", self.name, exc)

    def _save_cached_cookies(self, cookies, domain, ua):
        if not cookies:
            return
        cookie_dict = {c["name"]: c["value"] for c in cookies if c.get("name") and c.get("value")}
        if not cookie_dict:
            return
        try:
            payload = {
                "cookies": cookie_dict,
                "domain": domain,
                "ua": ua,
                "ts": time.time(),
            }
            raw = json.dumps(payload)
            xbmcgui.Window(10000).setProperty(f"AdultHideout.Clearance.{self.name}", raw)
            cache_file = self._get_cache_file()
            if cache_file:
                with open(cache_file, "w", encoding="utf-8") as f:
                    f.write(raw)
            self.logger.info("[%s] Saved cached clearance (%d cookies) to %s", self.name, len(cookie_dict), cache_file)
        except Exception as exc:
            self.logger.error("[%s] Error in _save_cached_cookies: %s", self.name, exc)

    def _get_page_cache_file(self, url):
        try:
            profile_dir = xbmcvfs.translatePath(self.addon.getAddonInfo("profile"))
            cache_dir = os.path.join(profile_dir, "page_cache")
            if not os.path.exists(cache_dir):
                os.makedirs(cache_dir, exist_ok=True)
            url_hash = hashlib.md5(url.encode("utf-8")).hexdigest()
            return os.path.join(cache_dir, f"{self.name}_{url_hash}.html")
        except Exception:
            return ""

    def _get_cached_page(self, url, ttl=1800):
        cache_file = self._get_page_cache_file(url)
        if cache_file and os.path.isfile(cache_file):
            try:
                age = time.time() - os.path.getmtime(cache_file)
                if age < ttl:
                    with open(cache_file, "r", encoding="utf-8") as f:
                        data = f.read()
                    if data and "Just a moment" not in data:
                        self.logger.info("[%s] Serving cached page for %s (age=%.1fs, len=%d)", self.name, url, age, len(data))
                        return data
            except Exception as exc:
                self.logger.debug("[%s] Cache read error: %s", self.name, exc)
        return None

    def _save_cached_page(self, url, content):
        if not content or "Just a moment" in content:
            return
        cache_file = self._get_page_cache_file(url)
        if cache_file:
            try:
                with open(cache_file, "w", encoding="utf-8") as f:
                    f.write(content)
                self.logger.info("[%s] Cached page saved for %s (%d bytes)", self.name, url, len(content))
            except Exception as exc:
                self.logger.debug("[%s] Cache write error: %s", self.name, exc)

    def make_request(self, url, referer=None, cache_ttl=1800):
        # 0. Check fast page cache (instant 0.001s response when stopping video / going back)
        if cache_ttl > 0:
            cached_page = self._get_cached_page(url, ttl=cache_ttl)
            if cached_page:
                return cached_page

        self._load_cached_cookies()
        headers = dict(self.headers)
        if referer:
            headers["Referer"] = referer

        # 1. Fast direct path with cached cookies
        try:
            cookie_names = [c.name for c in self.session.cookies]
            self.logger.info("[%s] Fast direct GET %s with cookies=%s, UA=%s",
                             self.name, url, cookie_names, headers.get("User-Agent"))
            resp = self.session.get(url, headers=headers, timeout=5, allow_redirects=True)
            self.logger.info("[%s] Direct GET %s -> HTTP %s (ray=%s, mitigated=%s, len=%dB, preview=%.60s)",
                             self.name, url, resp.status_code, resp.headers.get("cf-ray"),
                             resp.headers.get("cf-mitigated"), len(resp.text), resp.text.strip().replace("\n", " "))
            if resp.status_code == 200 and "Just a moment" not in resp.text:
                if cache_ttl > 0:
                    self._save_cached_page(url, resp.text)
                return resp.text
            self.logger.warning("%s returned HTTP %s (mitigated=%s), trying PhantomFlare fallback",
                                url, resp.status_code, resp.headers.get("cf-mitigated"))
        except Exception as exc:
            self.logger.warning("Request failed for %s: %s, trying PhantomFlare fallback", url, exc)

        # 2. Solver fallback (fast timeout for background search, 120s for interactive TV hardware)
        from resources.lib.resilient_http import fetch_text_with_solution
        req_timeout = 4 if getattr(self, "adult_hideout_background_harvest", False) else 120
        sol = fetch_text_with_solution(url, headers=headers, logger=self.logger, timeout=req_timeout)
        if sol and sol.get("response") and "Just a moment" not in sol.get("response", ""):
            parsed_host = urllib.parse.urlsplit(url).hostname or ""
            parts = parsed_host.split(".")
            root_domain = "." + ".".join(parts[-2:]) if len(parts) >= 2 else parsed_host
            cookies_list = sol.get("cookies", [])
            self.session.cookies.clear()
            for c in cookies_list:
                self.session.cookies.set(c["name"], c["value"], domain=root_domain)
            ua = sol.get("userAgent")
            if ua:
                self.headers["User-Agent"] = ua
            self._save_cached_cookies(cookies_list, root_domain, ua or self.headers.get("User-Agent", ""))
            body = sol["response"]
            if cache_ttl > 0:
                self._save_cached_page(url, body)
            return body
        return ""

    @staticmethod
    def _clean(value):
        value = re.sub(r"<[^>]+>", " ", value or "")
        return re.sub(r"\s+", " ", html.unescape(value)).strip()

    def _thumb(self, thumb):
        if not thumb or not thumb.startswith("http"):
            return thumb or self.icon
        try:
            from resources.lib.thumb_proxy import build_thumb_url
            return build_thumb_url(thumb, referer=self.base_url)
        except Exception:
            return thumb

    def _absolute(self, value):
        value = html.unescape(value or "").replace("\\/", "/")
        if value.startswith("//"):
            return "https:" + value
        return urllib.parse.urljoin(self.base_url, value)

    def _decode_video_url(self, click_url):
        try:
            parsed = urllib.parse.urlparse(self._absolute(click_url))
            encoded = urllib.parse.parse_qs(parsed.query).get("g", [""])[0]
            decoded = base64.b64decode(encoded[::-1] + "===").decode("utf-8")
            return self._absolute(decoded)
        except Exception as exc:
            self.logger.warning("Could not decode video URL: %s", exc)
            return ""

    @staticmethod
    def _nearest_duration(content, anchor_pos):
        matches = list(re.finditer(r"(?<!\d)(?:\d{1,2}:)?\d{1,2}:\d{2}(?!\d)", content))
        if not matches:
            return ""
        return min(matches, key=lambda item: abs(item.start() - anchor_pos)).group(0)

    def _extract_videos(self, content):
        videos = []
        seen = set()
        anchors = list(re.finditer(
            r'<a\b[^>]*href=["\']([^"\']*?/c/\?[^"\']+)["\'][^>]*>',
            content or "",
            re.IGNORECASE,
        ))
        for index, match in enumerate(anchors):
            decoded_url = self._decode_video_url(match.group(1))
            if not decoded_url or decoded_url in seen:
                continue
            left = max(0, match.start() - 260)
            right = anchors[index + 1].start() if index + 1 < len(anchors) else match.start() + 1400
            right = min(right, match.start() + 1400)
            block = content[left:right]
            local_anchor = match.start() - left

            image = re.search(r'<img\b[^>]+data-src=["\']([^"\']+)', block[local_anchor:], re.IGNORECASE)
            if not image:
                image = re.search(r'<img\b[^>]+src=["\']([^"\']+)', block[local_anchor:], re.IGNORECASE)
            raw_thumb = image.group(1) if image else ""
            if raw_thumb.startswith("data:image/"):
                raw_thumb = ""
            thumb = self._thumb(self._absolute(raw_thumb)) if raw_thumb else self.icon

            title = ""
            for pattern in (
                r'class=["\']?(?:ebs|bqh|wrap)["\']?[^>]*>(.*?)</(?:div|span)>',
                r'</a>\s*<div\b[^>]*>\s*<div\b[^>]*>(.*?)</div>',
                r'<img\b[^>]+(?:alt|title)=["\']([^"\']+)',
            ):
                title_match = re.search(pattern, block[local_anchor:], re.IGNORECASE | re.DOTALL)
                if title_match:
                    title = self._clean(title_match.group(1))
                    if title:
                        break
            if not title:
                continue

            duration = self._nearest_duration(block, local_anchor)
            info = {"title": title, "plot": title}
            if duration:
                info["duration"] = self.convert_duration(duration)
            label = "{} [COLOR lime]({})[/COLOR]".format(title, duration) if duration else title
            videos.append({"label": label, "url": decoded_url, "thumb": thumb, "info": info})
            seen.add(decoded_url)
        return videos

    def _add_navigation(self):
        self.add_dir("Search {}".format(self.label), "", 5, self.icons["search"], name_param=self.name)
        categories_url = self.base_url + "?ah_view=categories"
        self.add_dir("Categories", categories_url, 2, self.icons["categories"])

    def _process_categories(self):
        content = self.make_request(self.base_url)
        seen = set()
        ignored = {
            "home", "categories", "live sex", "privacy", "terms", "contact", "support",
            "english", "deutsch", "francais", "espanol", "italiano", "russian",
        }
        for href, body in re.findall(
            r'<a\b[^>]+href=["\'](/[^"\'?#]+/)["\'][^>]*>(.*?)</a>',
            content,
            re.IGNORECASE | re.DOTALL,
        ):
            title = self._clean(body)
            slug = href.strip("/").lower()
            if not title or title.lower() in ignored or slug in ignored or len(slug.split("/")) != 1:
                continue
            if title.lower() in seen or re.search(r"(?:login|sign|language|favicon|android|apple)", slug):
                continue
            seen.add(title.lower())
            self.add_dir(title, self._absolute(href), 2, self.icons["categories"])
        self.end_directory("videos")

    def get_start_url_and_label(self):
        return self.base_url + "?s=", self.label

    def process_content(self, url, page=1):
        if not url or url == "BOOTSTRAP" or url.rstrip("/") == self.base_url.rstrip("/"):
            url = self.base_url + "?s="
        parsed = urllib.parse.urlparse(url)
        query = urllib.parse.parse_qs(parsed.query)
        if query.get("ah_view") == ["categories"]:
            return self._process_categories()

        content = self.make_request(url)
        if not content:
            self.notify_error("Could not load website")
            return self.end_directory("videos")

        is_search = self.search_param in query
        if not is_search and page == 1:
            self._add_navigation()

        all_videos = self._extract_videos(content)
        per_page = 36
        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        page_videos = all_videos[start_idx:end_idx] if len(all_videos) > per_page else all_videos

        for video in page_videos:
            self.add_link(video["label"], video["url"], 4, video["thumb"], self.fanart, info_labels=video["info"])

        if end_idx < len(all_videos):
            next_page = page + 1
            self.add_dir(f"Next Page ({next_page}) >>", url, 2, self.icons["default"], page=next_page)

        self.end_directory("videos")

    def _resolve(self, url):
        content = self.make_request(url, referer=self.base_url, cache_ttl=600)
        stream_match = re.search(
            r'<source\b[^>]+src=["\']([^"\']+\.(?:m3u8|mp4)[^"\']*)["\']',
            content or "",
            re.IGNORECASE,
        )
        if not stream_match:
            stream_match = re.search(r'(https?[^"\']+\.(?:m3u8|mp4)[^"\']*)', content or "", re.IGNORECASE)
        return self._absolute(stream_match.group(1)) if stream_match else ""

    def resolve_recording_stream(self, url):
        stream = self._resolve(url)
        if not stream:
            return None
        return {
            "url": stream,
            "headers": {"User-Agent": self.headers["User-Agent"], "Referer": url},
            "extension": "m3u8" if ".m3u8" in stream else "mp4",
        }

    def play_video(self, url):
        resolved = self.resolve_recording_stream(url)
        if not resolved:
            self.notify_error("Could not resolve stream")
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
            return
        headers = urllib.parse.urlencode(resolved["headers"])
        item = xbmcgui.ListItem(path="{}|{}".format(resolved["url"], headers))
        item.setProperty("IsPlayable", "true")
        item.setContentLookup(False)
        if resolved["extension"] == "m3u8":
            item.setMimeType("application/vnd.apple.mpegurl")
            if xbmc.getCondVisibility("System.HasAddon(inputstream.adaptive)"):
                item.setProperty("inputstream", "inputstream.adaptive")
                item.setProperty("inputstream.adaptive.manifest_type", "hls")
                item.setProperty("inputstream.adaptive.manifest_headers", headers)
                item.setProperty("inputstream.adaptive.stream_headers", headers)
        else:
            item.setMimeType("video/mp4")
        xbmcplugin.setResolvedUrl(self.addon_handle, True, item)
