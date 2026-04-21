# -*- coding: utf-8 -*-
import hashlib
import html
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

import xbmc
import xbmcvfs

import requests
import xbmcgui
import xbmcplugin

from resources.lib.base_website import BaseWebsite
from resources.lib.resolvers import resolver


class ArchivebateWebsite(BaseWebsite):
    SEARCH_PREFIX = "ABSEARCH:"

    def __init__(self, addon_handle, addon=None):
        super().__init__(
            name="archivebate",
            base_url="https://archivebate.com",
            search_url="https://archivebate.com/api/v1/search",
            addon_handle=addon_handle,
            addon=addon,
        )
        self.session = requests.Session()
        self.ua = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/128.0.0.0 Safari/537.36"
        )
        self.platform_links = [
            ("YouTube", "https://archivebate.com/platform/eW91dHViZQ=="),
            ("Twitch", "https://archivebate.com/platform/dHdpdGNo"),
            ("OnlyFans", "https://archivebate.com/platform/b25seWZhbnM="),
            ("Instagram", "https://archivebate.com/platform/aW5zdGFncmFt"),
            ("TikTok", "https://archivebate.com/platform/dGlrdG9r"),
            ("BongaCams", "https://archivebate.com/platform/Ym9uZ2FjYW1z"),
            ("Cam4", "https://archivebate.com/platform/Y2FtNA=="),
            ("CamSoda", "https://archivebate.com/platform/Y2Ftc29kYQ=="),
            ("Chaturbate", "https://archivebate.com/platform/Y2hhdHVyYmF0ZQ=="),
            ("Stripchat", "https://archivebate.com/platform/c3RyaXBjaGF0"),
        ]
        self.gender_links = [
            ("All", ""),
            ("Female", "https://archivebate.com/gender/ZmVtYWxl"),
            ("Couple", "https://archivebate.com/gender/Y291cGxl"),
            ("Male", "https://archivebate.com/gender/bWFsZQ=="),
            ("Trans", "https://archivebate.com/gender/dHJhbnM="),
        ]
        self.sort_options = ["Recent", "Popular"]
        self._thumb_cache_dir = self._init_thumb_cache()

    # ------------------------------------------------------------------
    # Thumbnail cache – threaded batch download (VikiPorn pattern)
    # ------------------------------------------------------------------
    THUMB_WORKERS = 10
    THUMB_TIMEOUT = 10

    def _init_thumb_cache(self):
        addon_profile = xbmcvfs.translatePath(self.addon.getAddonInfo("profile"))
        thumb_dir = os.path.join(addon_profile, "thumbs", "archivebate")
        if not xbmcvfs.exists(thumb_dir):
            xbmcvfs.mkdirs(thumb_dir)
        return thumb_dir

    def _download_single_thumb(self, url):
        """Download one thumbnail with correct Referer. Thread-safe."""
        if not url or not url.startswith("http"):
            return None
        try:
            hashed = hashlib.md5(url.encode("utf-8")).hexdigest()
            for ext in (".jpg", ".png", ".gif", ".webp", ".bmp"):
                cached = os.path.join(self._thumb_cache_dir, hashed + ext)
                if xbmcvfs.exists(cached):
                    return cached
            req = urllib.request.Request(url, headers={
                "User-Agent": self.ua,
                "Referer": self.base_url + "/",
                "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
            })
            with urllib.request.urlopen(req, timeout=self.THUMB_TIMEOUT) as resp:
                data = resp.read()
            signatures = {
                b"\xFF\xD8\xFF": ".jpg",
                b"\x89PNG\r\n\x1a\n": ".png",
                b"GIF89a": ".gif",
                b"GIF87a": ".gif",
                b"BM": ".bmp",
            }
            ext = None
            for sig, e in signatures.items():
                if data.startswith(sig):
                    ext = e
                    break
            if ext is None and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
                ext = ".webp"
            if ext is None:
                return None
            local_path = os.path.join(self._thumb_cache_dir, hashed + ext)
            with xbmcvfs.File(local_path, "wb") as f:
                f.write(data)
            return local_path
        except Exception:
            return None

    def _batch_download_thumbs(self, urls):
        """Download multiple thumbnails in parallel.
        Returns dict {original_url: local_path_or_None}."""
        results = {}
        unique = list(set(u for u in urls if u and u.startswith("http")))
        if not unique:
            return results
        with ThreadPoolExecutor(max_workers=self.THUMB_WORKERS) as pool:
            future_map = {pool.submit(self._download_single_thumb, u): u for u in unique}
            for future in as_completed(future_map):
                orig = future_map[future]
                try:
                    results[orig] = future.result()
                except Exception:
                    results[orig] = None
        return results

    def _resolve_thumb(self, thumb_map, url):
        """Look up downloaded thumbnail, fall back to default icon."""
        path = thumb_map.get(url)
        if path and xbmcvfs.exists(path):
            return path
        return self.icons.get("default", self.icon)

    def _headers(self, referer=None, accept=None):
        return {
            "User-Agent": self.ua,
            "Referer": referer or (self.base_url + "/"),
            "Accept": accept or "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }

    def _absolute(self, url):
        if not url:
            return ""
        return urllib.parse.urljoin(self.base_url + "/", html.unescape(url.strip()))

    def _normalize_url(self, url):
        url = self._absolute(url)
        return url.replace("https://www.archivebate.cc", self.base_url).replace("https://archivebate.cc", self.base_url)

    def _cache_thumb(self, thumb_url):
        """Single-thumb wrapper for backward compat – uses batch under the hood."""
        return self._resolve_thumb(self._batch_download_thumbs([thumb_url]), thumb_url)

    def _make_request(self, url, referer=None, accept=None):
        try:
            response = self.session.get(url, headers=self._headers(referer=referer, accept=accept), timeout=20)
            if response.status_code == 200:
                return response.text
            self.logger.error("[ArchiveBate] HTTP %s for %s", response.status_code, url)
        except Exception as exc:
            self.logger.error("[ArchiveBate] Request error for %s: %s", url, exc)
        return None

    def _extract_livewire_component(self, page_html, component_name):
        matches = re.findall(r'wire:initial-data="([^"]+)"', page_html, re.IGNORECASE)
        for raw in matches:
            try:
                data = json.loads(html.unescape(raw))
            except Exception:
                continue
            fingerprint = data.get("fingerprint") or {}
            if fingerprint.get("name") == component_name:
                return data
        return None

    def _get_listing_target(self, url):
        parsed = urllib.parse.urlparse(url or "")
        path = parsed.path or "/"
        if path.startswith("/profile/"):
            return "profile.model-videos", "load_profile_videos"
        if path.startswith("/platform/") or path.startswith("/gender/"):
            return "filter.platform", "load_platform_videos"
        return "home-videos", "loadVideos"

    # ------------------------------------------------------------------
    # Context-menu filter system (Chaturbate pattern)
    # ------------------------------------------------------------------
    def _get_setting_index(self, setting_id, options):
        try:
            idx = int(self.addon.getSetting(setting_id) or "0")
            if 0 <= idx < len(options):
                return idx
        except (ValueError, TypeError):
            pass
        return 0

    def _get_filter_gender_label(self):
        idx = self._get_setting_index("archivebate_filter_gender", [lbl for lbl, _ in self.gender_links])
        return self.gender_links[idx][0] if idx > 0 else ""

    def _get_filter_gender_url(self):
        idx = self._get_setting_index("archivebate_filter_gender", [lbl for lbl, _ in self.gender_links])
        return self.gender_links[idx][1]

    def _get_filter_sort_label(self):
        idx = self._get_setting_index("archivebate_filter_sort", self.sort_options)
        return self.sort_options[idx]

    def _get_active_filter_bits(self):
        bits = []
        gender = self._get_filter_gender_label()
        if gender:
            bits.append(gender)
        sort_label = self._get_filter_sort_label()
        if sort_label != "Recent":
            bits.append(sort_label)
        return bits

    def get_start_url_and_label(self):
        filter_bits = self._get_active_filter_bits()
        suffix = " | ".join(filter_bits) if filter_bits else "Recent"
        # Build the URL based on active gender filter
        gender_url = self._get_filter_gender_url()
        if gender_url:
            url = gender_url
        else:
            url = self.base_url + "/"
        sort_label = self._get_filter_sort_label()
        if sort_label == "Popular" and "?" not in url:
            url += "?filter=popular"
        return url, "Archivebate [COLOR yellow]{}[/COLOR]".format(suffix)

    def _build_context_menu(self):
        return [
            ("Filter...", "RunPlugin({}?mode=7&action=select_filter&website={})".format(sys.argv[0], self.name)),
        ]

    def select_filter(self, original_url=None):
        dialog = xbmcgui.Dialog()
        entries = [
            "Gender: {}".format(self._get_filter_gender_label() or "All"),
            "Sort: {}".format(self._get_filter_sort_label()),
            "[COLOR red]Clear Filters[/COLOR]",
        ]

        choice = dialog.select("Filter...", entries)
        if choice == -1:
            return

        if choice == 0:
            gender_labels = [lbl for lbl, _ in self.gender_links]
            current = self._get_setting_index("archivebate_filter_gender", gender_labels)
            idx = dialog.select("Gender", gender_labels, preselect=current)
            if idx == -1:
                return
            self.addon.setSetting("archivebate_filter_gender", str(idx))
        elif choice == 1:
            current = self._get_setting_index("archivebate_filter_sort", self.sort_options)
            idx = dialog.select("Sort", self.sort_options, preselect=current)
            if idx == -1:
                return
            self.addon.setSetting("archivebate_filter_sort", str(idx))
        elif choice == 2:
            self.addon.setSetting("archivebate_filter_gender", "0")
            self.addon.setSetting("archivebate_filter_sort", "0")

        new_url, _ = self.get_start_url_and_label()
        xbmc.executebuiltin(
            "Container.Update({}?mode=2&website={}&url={},replace)".format(
                sys.argv[0], self.name, urllib.parse.quote_plus(new_url),
            )
        )

    def _fetch_listing_html(self, url):
        page_url = self._normalize_url(url or self.base_url)
        page_html = self._make_request(page_url)
        if not page_html:
            return "", None

        component_name, method_name = self._get_listing_target(page_url)
        component = self._extract_livewire_component(page_html, component_name)
        if not component:
            self.logger.error("[ArchiveBate] Could not find Livewire component %s for %s", component_name, page_url)
            return "", None

        csrf_match = re.search(r'<meta name="csrf-token" content="([^"]*)"', page_html, re.IGNORECASE)
        csrf_token = csrf_match.group(1) if csrf_match else ""
        endpoint = "{}/livewire/message/{}".format(self.base_url, component_name)
        payload = {
            "fingerprint": component.get("fingerprint", {}),
            "serverMemo": component.get("serverMemo", {}),
            "updates": [
                {
                    "type": "callMethod",
                    "payload": {
                        "id": component.get("fingerprint", {}).get("id", ""),
                        "method": method_name,
                        "params": [],
                    },
                }
            ],
        }

        try:
            response = self.session.post(
                endpoint,
                headers={
                    "User-Agent": self.ua,
                    "Referer": page_url,
                    "Accept": "application/json, text/plain, */*",
                    "X-Requested-With": "XMLHttpRequest",
                    "X-CSRF-TOKEN": csrf_token,
                    "X-Livewire": "true",
                },
                json=payload,
                timeout=30,
            )
            if response.status_code != 200:
                self.logger.error("[ArchiveBate] Livewire HTTP %s for %s", response.status_code, endpoint)
                return "", None
            data = response.json()
        except Exception as exc:
            self.logger.error("[ArchiveBate] Livewire error for %s: %s", page_url, exc)
            return "", None

        effects = data.get("effects") or {}
        if effects.get("redirect"):
            self.logger.warning("[ArchiveBate] Livewire redirected %s to %s", page_url, effects.get("redirect"))
            return "", None

        listing_html = effects.get("html") or ""
        next_url = None
        next_match = re.search(r'<a[^>]+class="page-link"[^>]+href="([^"]+)"[^>]*rel="next"', listing_html, re.IGNORECASE)
        if not next_match:
            next_match = re.search(r'<a[^>]+href="([^"]+)"[^>]*rel="next"', listing_html, re.IGNORECASE)
        if next_match:
            next_url = self._normalize_url(next_match.group(1))

        return listing_html, next_url

    def _extract_videos(self, listing_html):
        raw_items = []
        seen = set()
        blocks = re.findall(r'(<section class="video_item">[\.\s\S]*?<\/section>)', listing_html, re.IGNORECASE)
        for block in blocks:
            watch_match = re.search(r'<a href="(https://archivebate\.com/watch/\d+)"', block, re.IGNORECASE)
            profile_match = re.search(r'<a href="(https://archivebate\.com/profile/[^"]+)">([^<]+)<\/a>', block, re.IGNORECASE)
            thumb_match = re.search(r'poster="([^"]+)"', block, re.IGNORECASE)
            duration_match = re.search(r'<\/svg>\s*([^<]+)<\/span>', block, re.IGNORECASE)
            meta_match = re.search(r'<p>([^<]+)<\/p>', block, re.IGNORECASE)
            if not watch_match or not profile_match:
                continue

            video_url = self._normalize_url(watch_match.group(1))
            if video_url in seen:
                continue
            seen.add(video_url)

            raw_items.append({
                "video_url": video_url,
                "profile_url": self._normalize_url(profile_match.group(1)),
                "username": html.unescape(profile_match.group(2)).strip(),
                "raw_thumb": self._normalize_url(thumb_match.group(1)) if thumb_match else None,
                "duration_text": html.unescape(duration_match.group(1)).strip() if duration_match else "",
                "meta": html.unescape(meta_match.group(1)).replace("\u00b7", "|").strip() if meta_match else "",
            })

        # Batch-download all thumbnails in parallel
        thumb_urls = [it["raw_thumb"] for it in raw_items if it["raw_thumb"]]
        thumb_map = self._batch_download_thumbs(thumb_urls)

        items = []
        for it in raw_items:
            thumb = self._resolve_thumb(thumb_map, it["raw_thumb"]) if it["raw_thumb"] else self.icon
            meta = it["meta"]
            meta_parts = [p.strip() for p in re.split(r"&middot;|\|", meta) if p.strip()]
            platform = meta_parts[1] if len(meta_parts) >= 2 else ""
            title = "{} [{}]".format(it["username"], platform) if platform else it["username"]
            info = {"title": title, "plot": meta or title, "studio": platform}
            duration_seconds = self.convert_duration(it["duration_text"])
            if duration_seconds:
                info["duration"] = duration_seconds
            items.append({
                "title": title,
                "url": it["video_url"],
                "thumb": thumb,
                "profile_url": it["profile_url"],
                "info": info,
            })
        return items

    def _render_listing(self, url):
        listing_html, next_url = self._fetch_listing_html(url)
        if not listing_html:
            self.notify_error("No ArchiveBate videos found")
            self.end_directory("videos")
            return

        videos = self._extract_videos(listing_html)
        if not videos:
            self.notify_error("No ArchiveBate videos found")
            self.end_directory("videos")
            return

        context_menu = self._build_context_menu()
        for video in videos:
            self.add_link(
                video["title"],
                video["url"],
                4,
                video["thumb"],
                self.fanart,
                context_menu=context_menu,
                info_labels=video["info"],
            )

        if next_url and next_url != self._normalize_url(url):
            self.add_dir("Next Page", next_url, 2, self.icons.get("default", self.icon), context_menu=context_menu)

        self.end_directory("videos")

    def _search_profiles(self, query, page=1):
        home_html = self._make_request(self.base_url + "/")
        if not home_html:
            self.notify_error("ArchiveBate search unavailable")
            self.end_directory("videos")
            return

        csrf_match = re.search(r'<meta name="csrf-token" content="([^"]*)"', home_html, re.IGNORECASE)
        csrf_token = csrf_match.group(1) if csrf_match else ""

        try:
            response = self.session.get(
                self.search_url,
                params={"query": query, "page": page},
                headers={
                    "User-Agent": self.ua,
                    "Referer": self.base_url + "/",
                    "Accept": "application/json, text/plain, */*",
                    "X-Requested-With": "XMLHttpRequest",
                    "X-CSRF-TOKEN": csrf_token,
                },
                timeout=20,
            )
            if response.status_code != 200:
                self.logger.error("[ArchiveBate] Search HTTP %s for %s", response.status_code, query)
                self.notify_error("ArchiveBate search unavailable")
                self.end_directory("videos")
                return
            data = response.json()
        except Exception as exc:
            self.logger.error("[ArchiveBate] Search error for %s: %s", query, exc)
            self.notify_error("ArchiveBate search unavailable")
            self.end_directory("videos")
            return

        seen = set()
        for item in data.get("data", []):
            username = (item.get("username") or "").strip()
            if not username or username in seen:
                continue
            seen.add(username)
            platform = (item.get("platform") or "").strip()
            gender = (item.get("gender") or "").strip()
            title_bits = [username]
            if platform:
                title_bits.append(platform)
            if gender:
                title_bits.append(gender)
            title = " | ".join(title_bits)
            profile_url = "{}/profile/{}".format(self.base_url, urllib.parse.quote(username))
            self.add_dir(title, profile_url, 2, self.icons.get("pornstars", self.icon))

        meta = data.get("meta") or {}
        current_page = int(meta.get("current_page") or page or 1)
        last_page = int(meta.get("last_page") or current_page)
        if current_page < last_page:
            next_token = "{}{}:{}".format(self.SEARCH_PREFIX, urllib.parse.quote_plus(query), current_page + 1)
            self.add_dir("Next Page", next_token, 2, self.icons.get("default", self.icon))

        self.end_directory("videos")

    def _apply_sort_to_url(self, url):
        """Append ?filter=popular if sort is set to Popular."""
        sort_label = self._get_filter_sort_label()
        if sort_label == "Popular" and "filter=popular" not in url:
            sep = "&" if "?" in url else "?"
            return url + sep + "filter=popular"
        return url

    def process_content(self, url):
        if not url or url == "BOOTSTRAP":
            start_url, _ = self.get_start_url_and_label()
            url = start_url

        context_menu = self._build_context_menu()
        self.add_dir("Search", "", 5, self.icons.get("search", self.icon), context_menu=context_menu)
        self.add_dir("Platforms", self.base_url + "/platforms", 8, self.icons.get("categories", self.icon), context_menu=context_menu)

        if url == self.base_url + "/platforms":
            self.process_categories(url)
            return

        if url.startswith(self.SEARCH_PREFIX):
            payload = url[len(self.SEARCH_PREFIX):]
            if ":" in payload:
                query_encoded, page_str = payload.rsplit(":", 1)
            else:
                query_encoded, page_str = payload, "1"
            query = urllib.parse.unquote_plus(query_encoded)
            try:
                page = int(page_str)
            except Exception:
                page = 1
            self._search_profiles(query, page=page)
            return

        url = self._apply_sort_to_url(url)
        self._render_listing(url)

    def process_categories(self, url):
        context_menu = self._build_context_menu()
        for label, target in self.platform_links:
            self.add_dir(label, target, 2, self.icons.get("categories", self.icon), context_menu=context_menu)
        for label, target in self.gender_links:
            if target:  # skip "All"
                self.add_dir("Gender: {}".format(label), target, 2, self.icons.get("pornstars", self.icon), context_menu=context_menu)
        self.end_directory("videos")

    def search(self, query):
        if not query:
            return
        target = "{}{}:1".format(self.SEARCH_PREFIX, urllib.parse.quote_plus(query.strip()))
        self.process_content(target)

    def play_video(self, url):
        html_text = self._make_request(url)
        if not html_text:
            self.notify_error("Could not load ArchiveBate video page")
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
            return

        embed_match = re.search(r'<iframe[^>]+src="(https://mixdrop\.[^"]+/[ef]/[^"]+)"', html_text, re.IGNORECASE)
        if not embed_match:
            embed_match = re.search(r'<input type="hidden" name="fid" value="(https://mixdrop\.[^"]+/f/[^"]+)"', html_text, re.IGNORECASE)
        if not embed_match:
            self.notify_error("Could not resolve ArchiveBate host")
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
            return

        embed_url = html.unescape(embed_match.group(1).strip())
        stream_url, headers = resolver.resolve(embed_url, referer=url, headers={"User-Agent": self.ua, "Referer": url})
        if not stream_url:
            self.notify_error("Could not resolve MixDrop stream")
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
            return

        list_item = xbmcgui.ListItem(path=stream_url if "|" in stream_url else self._append_headers(stream_url, headers))
        list_item.setProperty("IsPlayable", "true")
        if ".m3u8" in stream_url:
            list_item.setMimeType("application/vnd.apple.mpegurl")
            list_item.setContentLookup(False)
        xbmcplugin.setResolvedUrl(self.addon_handle, True, list_item)

    def _append_headers(self, url, headers):
        if not headers:
            return url
        parts = []
        for key, value in headers.items():
            if value is None:
                continue
            parts.append("{}={}".format(key, urllib.parse.quote(str(value))))
        return url + "|" + "&".join(parts) if parts else url
