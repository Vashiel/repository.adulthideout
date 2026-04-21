# -*- coding: utf-8 -*-
import html
import os
import re
import socket
import sys
import threading
import time
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler
from socketserver import TCPServer, ThreadingMixIn

import requests
import xbmc
import xbmcgui
import xbmcplugin
import xbmcvfs

from resources.lib.base_website import BaseWebsite

_CB_PROXY = None


class ChaturbateWebsite(BaseWebsite):
    API_URL = "https://chaturbate.com/api/ts/roomlist/room-list/"
    HLS_URL = "https://chaturbate.com/get_edge_hls_url_ajax/"
    LIST_PREFIX = "CHB_LIST:"
    SEARCH_PREFIX = "CHB_SEARCH:"

    def __init__(self, addon_handle, addon=None):
        super().__init__(
            name="chaturbate",
            base_url="https://chaturbate.com",
            search_url="https://chaturbate.com/?keywords={}",
            addon_handle=addon_handle,
            addon=addon,
        )
        self.session = requests.Session()
        self.ua = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/128.0.0.0 Safari/537.36"
        )
        self.rooms_per_page = 20
        self.sort_options = ["Most Relevant", "Most Viewers", "Random"]
        self.sort_paths = {
            "Most Relevant": self.LIST_PREFIX + "all",
            "Most Viewers": self.LIST_PREFIX + "all",
            "Random": self.LIST_PREFIX + "all",
        }
        self.category_map = {
            "all": ("All Rooms", {}),
            "female": ("Female", {"genders": "f"}),
            "male": ("Male", {"genders": "m"}),
            "couple": ("Couple", {"genders": "c"}),
            "trans": ("Trans", {"genders": "t"}),
            "new": ("New", {"new_cams": "true"}),
        }
        self.filter_gender_options = ["All", "Female", "Male", "Couple", "Trans"]
        self.filter_gender_map = {
            "All": "",
            "Female": "f",
            "Male": "m",
            "Couple": "c",
            "Trans": "t",
        }
        self.filter_special_options = ["None", "New", "Exhibitionist", "Private Previews"]
        self.filter_special_map = {
            "None": {},
            "New": {"new_cams": "true"},
            "Exhibitionist": {"exhib": "true"},
            "Private Previews": {"private": "true"},
        }
        self.filter_region_options = ["All", "North America", "South America", "Asia", "Euro/Russia", "Other"]
        self.filter_region_map = {
            "All": "",
            "North America": "NA",
            "South America": "SA",
            "Asia": "AS",
            "Euro/Russia": "ER",
            "Other": "O",
        }
        self.filter_age_options = ["All", "18-20", "18-21", "20-30", "30-50", "50+"]
        self.filter_age_map = {
            "All": "",
            "18-20": ("18", "20"),
            "18-21": ("18", "21"),
            "20-30": ("20", "30"),
            "30-50": ("30", "50"),
            "50+": ("50", "100"),
        }
        self.filter_room_size_options = ["All", "Small", "Medium", "Large"]
        self.filter_room_size_map = {
            "All": "",
            "Small": "sm",
            "Medium": "md",
            "Large": "lg",
        }
        self.filter_private_price_options = ["All", "6", "12-18", "30-42", "60-72", "90+"]
        self.filter_private_price_map = {
            "All": "",
            "6": "6",
            "12-18": "12,18",
            "30-42": "30,42",
            "60-72": "60,72",
            "90+": "90,120,150,180,240,360,480,720,960,1200,1440,1920",
        }
        self.filter_spy_price_options = ["All", "6", "12-18", "30-42", "54-66", "90+"]
        self.filter_spy_price_map = {
            "All": "",
            "6": "6",
            "12-18": "12,18",
            "30-42": "30,42",
            "54-66": "54,66",
            "90+": "90,120,150,180,240,360",
        }

    def _request_json(self, url, params=None, referer=None, method="get", data=None):
        try:
            headers = {
                "User-Agent": self.ua,
                "Referer": referer or (self.base_url + "/"),
                "X-Requested-With": "XMLHttpRequest",
                "Accept": "application/json, text/plain, */*",
                "Accept-Language": "en-US,en;q=0.9",
            }
            if method.lower() == "post":
                response = self.session.post(url, headers=headers, data=data or {}, timeout=20)
            else:
                response = self.session.get(url, headers=headers, params=params or {}, timeout=20)
            if response.status_code == 200:
                return response.json()
            self.logger.error("[Chaturbate] JSON HTTP %s for %s", response.status_code, response.url)
        except Exception as exc:
            self.logger.error("[Chaturbate] JSON request error for %s: %s", url, exc)
        return None

    def _make_request(self, url, referer=None):
        try:
            headers = {
                "User-Agent": self.ua,
                "Referer": referer or (self.base_url + "/"),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
            }
            response = self.session.get(url, headers=headers, timeout=20)
            if response.status_code == 200:
                return response.text
            self.logger.error("[Chaturbate] HTTP %s for %s", response.status_code, url)
        except Exception as exc:
            self.logger.error("[Chaturbate] Request error for %s: %s", url, exc)
        return None

    def get_start_url_and_label(self):
        sort_option = self.sort_options[0]
        try:
            idx = int(self.addon.getSetting("chaturbate_sort_by") or "0")
            if 0 <= idx < len(self.sort_options):
                sort_option = self.sort_options[idx]
        except (ValueError, TypeError):
            pass
        filter_bits = self._get_active_filter_bits()
        suffix = sort_option
        if filter_bits:
            suffix = "{} | {}".format(sort_option, " | ".join(filter_bits))
        return self.LIST_PREFIX + "all", "Chaturbate [COLOR yellow]{}[/COLOR]".format(suffix)

    def _clean_text(self, value):
        if not value:
            return ""
        cleaned = re.sub(r"<[^>]+>", "", html.unescape(str(value)))
        return re.sub(r"\s+", " ", cleaned).strip()

    def _get_sort_params(self, is_search=False):
        sort_option = self.sort_options[0]
        try:
            idx = int(self.addon.getSetting("chaturbate_sort_by") or "0")
            if 0 <= idx < len(self.sort_options):
                sort_option = self.sort_options[idx]
        except (ValueError, TypeError):
            pass

        if is_search:
            if sort_option == "Most Viewers":
                return {"search_sort": "pop"}
            return {}

        if sort_option == "Most Viewers":
            return {"sort": "rv"}
        if sort_option == "Random":
            return {"sort": "rand"}
        return {}

    def _get_setting_index(self, setting_id, options):
        try:
            idx = int(self.addon.getSetting(setting_id) or "0")
            if 0 <= idx < len(options):
                return idx
        except (ValueError, TypeError):
            pass
        return 0

    def _get_filter_gender_value(self):
        option = self.filter_gender_options[self._get_setting_index("chaturbate_filter_gender", self.filter_gender_options)]
        return self.filter_gender_map.get(option, "")

    def _get_filter_gender_label(self):
        option = self.filter_gender_options[self._get_setting_index("chaturbate_filter_gender", self.filter_gender_options)]
        return option if option != "All" else ""

    def _get_filter_special_params(self):
        option = self.filter_special_options[self._get_setting_index("chaturbate_filter_special", self.filter_special_options)]
        return dict(self.filter_special_map.get(option, {}))

    def _get_filter_special_label(self):
        option = self.filter_special_options[self._get_setting_index("chaturbate_filter_special", self.filter_special_options)]
        return option if option != "None" else ""

    def _get_filter_region_value(self):
        option = self.filter_region_options[self._get_setting_index("chaturbate_filter_region", self.filter_region_options)]
        return self.filter_region_map.get(option, "")

    def _get_filter_region_label(self):
        option = self.filter_region_options[self._get_setting_index("chaturbate_filter_region", self.filter_region_options)]
        return option if option != "All" else ""

    def _get_filter_age_value(self):
        option = self.filter_age_options[self._get_setting_index("chaturbate_filter_age", self.filter_age_options)]
        return self.filter_age_map.get(option, "")

    def _get_filter_age_label(self):
        option = self.filter_age_options[self._get_setting_index("chaturbate_filter_age", self.filter_age_options)]
        return option if option != "All" else ""

    def _get_filter_room_size_value(self):
        option = self.filter_room_size_options[self._get_setting_index("chaturbate_filter_room_size", self.filter_room_size_options)]
        return self.filter_room_size_map.get(option, "")

    def _get_filter_room_size_label(self):
        option = self.filter_room_size_options[self._get_setting_index("chaturbate_filter_room_size", self.filter_room_size_options)]
        return option if option != "All" else ""

    def _get_filter_private_price_value(self):
        option = self.filter_private_price_options[self._get_setting_index("chaturbate_filter_private_price", self.filter_private_price_options)]
        return self.filter_private_price_map.get(option, "")

    def _get_filter_private_price_label(self):
        option = self.filter_private_price_options[self._get_setting_index("chaturbate_filter_private_price", self.filter_private_price_options)]
        return option if option != "All" else ""

    def _get_filter_spy_price_value(self):
        option = self.filter_spy_price_options[self._get_setting_index("chaturbate_filter_spy_price", self.filter_spy_price_options)]
        return self.filter_spy_price_map.get(option, "")

    def _get_filter_spy_price_label(self):
        option = self.filter_spy_price_options[self._get_setting_index("chaturbate_filter_spy_price", self.filter_spy_price_options)]
        return option if option != "All" else ""

    def _get_filter_keywords(self):
        return (self.addon.getSetting("chaturbate_filter_keywords") or "").strip()

    def _compose_keywords(self, query=""):
        parts = []
        if query:
            parts.append(query.strip())
        filter_keywords = self._get_filter_keywords()
        if filter_keywords:
            parts.append(filter_keywords)
        return " ".join(part for part in parts if part).strip()

    def _get_active_filter_bits(self):
        bits = []
        gender = self._get_filter_gender_label()
        if gender:
            bits.append(gender)
        keywords = self._get_filter_keywords()
        if keywords:
            bits.append("#{}".format(keywords))
        special = self._get_filter_special_label()
        if special:
            bits.append(special)
        region = self._get_filter_region_label()
        if region:
            bits.append(region)
        age = self._get_filter_age_label()
        if age:
            bits.append(age)
        room_size = self._get_filter_room_size_label()
        if room_size:
            bits.append(room_size)
        private_price = self._get_filter_private_price_label()
        if private_price:
            bits.append("P{}".format(private_price))
        spy_price = self._get_filter_spy_price_label()
        if spy_price:
            bits.append("S{}".format(spy_price))
        return bits

    def _extract_context(self, url):
        if not url or url == "BOOTSTRAP":
            return {"kind": "list", "key": "all"}
        if url.startswith(self.SEARCH_PREFIX):
            return {"kind": "search", "query": urllib.parse.unquote_plus(url[len(self.SEARCH_PREFIX):]).strip()}
        if url.startswith(self.LIST_PREFIX):
            return {"kind": "list", "key": url[len(self.LIST_PREFIX):].strip() or "all"}
        return {"kind": "room", "url": url}

    def _build_listing_params(self, context, page):
        offset = max(0, (max(1, int(page)) - 1) * self.rooms_per_page)
        params = {"offset": offset, "limit": self.rooms_per_page}

        filter_gender = self._get_filter_gender_value()
        if filter_gender:
            params["genders"] = filter_gender
        params.update(self._get_filter_special_params())
        region = self._get_filter_region_value()
        if region:
            params["regions"] = region
        age_range = self._get_filter_age_value()
        if age_range:
            params["from_age"] = age_range[0]
            params["to_age"] = age_range[1]
        room_size = self._get_filter_room_size_value()
        if room_size:
            params["room_size"] = room_size
        private_price = self._get_filter_private_price_value()
        if private_price:
            params["private_prices"] = private_price
        spy_price = self._get_filter_spy_price_value()
        if spy_price:
            params["spy_show_prices"] = spy_price

        if context["kind"] == "search":
            params["keywords"] = self._compose_keywords(context["query"])
            params.update(self._get_sort_params(is_search=True))
            return params

        category = self.category_map.get(context.get("key") or "all", self.category_map["all"])[1]
        params.update(category)
        if "genders" not in category and filter_gender:
            params["genders"] = filter_gender
        if "new_cams" in category:
            params.pop("new_cams", None)
            params["new_cams"] = "true"
        elif category:
            for conflicting_key in ("exhib", "private"):
                if conflicting_key in category:
                    params.pop(conflicting_key, None)
                    params[conflicting_key] = category[conflicting_key]

        keyword_blob = self._compose_keywords("")
        if keyword_blob:
            params["keywords"] = keyword_blob
        params.update(self._get_sort_params(is_search=False))
        return params

    def _build_context_menu(self):
        return [
            ("Filter...", "RunPlugin({}?mode=7&action=select_filter&website={})".format(sys.argv[0], self.name)),
        ]

    def select_filter(self, original_url=None):
        dialog = xbmcgui.Dialog()
        keywords = self._get_filter_keywords() or "None"
        entries = [
            "Gender: {}".format(self._get_filter_gender_label() or "All"),
            "Keywords / Tags: {}".format(keywords),
            "Special: {}".format(self._get_filter_special_label() or "None"),
            "Region: {}".format(self._get_filter_region_label() or "All"),
            "Age: {}".format(self._get_filter_age_label() or "All"),
            "Room Size: {}".format(self._get_filter_room_size_label() or "All"),
            "Private Price: {}".format(self._get_filter_private_price_label() or "All"),
            "Spy Price: {}".format(self._get_filter_spy_price_label() or "All"),
            "[COLOR red]Clear Filters[/COLOR]",
        ]

        choice = dialog.select("Filter...", entries)
        if choice == -1:
            return

        if choice == 0:
            current = self._get_setting_index("chaturbate_filter_gender", self.filter_gender_options)
            idx = dialog.select("Gender", self.filter_gender_options, preselect=current)
            if idx == -1:
                return
            self.addon.setSetting("chaturbate_filter_gender", str(idx))
        elif choice == 1:
            keyboard = xbmc.Keyboard(self._get_filter_keywords(), "Keywords / Tags")
            keyboard.doModal()
            if not keyboard.isConfirmed():
                return
            self.addon.setSetting("chaturbate_filter_keywords", keyboard.getText().strip())
        elif choice == 2:
            current = self._get_setting_index("chaturbate_filter_special", self.filter_special_options)
            idx = dialog.select("Special", self.filter_special_options, preselect=current)
            if idx == -1:
                return
            self.addon.setSetting("chaturbate_filter_special", str(idx))
        elif choice == 3:
            current = self._get_setting_index("chaturbate_filter_region", self.filter_region_options)
            idx = dialog.select("Region", self.filter_region_options, preselect=current)
            if idx == -1:
                return
            self.addon.setSetting("chaturbate_filter_region", str(idx))
        elif choice == 4:
            current = self._get_setting_index("chaturbate_filter_age", self.filter_age_options)
            idx = dialog.select("Age", self.filter_age_options, preselect=current)
            if idx == -1:
                return
            self.addon.setSetting("chaturbate_filter_age", str(idx))
        elif choice == 5:
            current = self._get_setting_index("chaturbate_filter_room_size", self.filter_room_size_options)
            idx = dialog.select("Room Size", self.filter_room_size_options, preselect=current)
            if idx == -1:
                return
            self.addon.setSetting("chaturbate_filter_room_size", str(idx))
        elif choice == 6:
            current = self._get_setting_index("chaturbate_filter_private_price", self.filter_private_price_options)
            idx = dialog.select("Private Price", self.filter_private_price_options, preselect=current)
            if idx == -1:
                return
            self.addon.setSetting("chaturbate_filter_private_price", str(idx))
        elif choice == 7:
            current = self._get_setting_index("chaturbate_filter_spy_price", self.filter_spy_price_options)
            idx = dialog.select("Spy Price", self.filter_spy_price_options, preselect=current)
            if idx == -1:
                return
            self.addon.setSetting("chaturbate_filter_spy_price", str(idx))
        elif choice == 8:
            self.addon.setSetting("chaturbate_filter_gender", "0")
            self.addon.setSetting("chaturbate_filter_keywords", "")
            self.addon.setSetting("chaturbate_filter_special", "0")
            self.addon.setSetting("chaturbate_filter_region", "0")
            self.addon.setSetting("chaturbate_filter_age", "0")
            self.addon.setSetting("chaturbate_filter_room_size", "0")
            self.addon.setSetting("chaturbate_filter_private_price", "0")
            self.addon.setSetting("chaturbate_filter_spy_price", "0")

        new_url, _ = self.get_start_url_and_label()
        xbmc.executebuiltin(
            "Container.Update({}?mode=2&website={}&url={},replace)".format(
                sys.argv[0],
                self.name,
                urllib.parse.quote_plus(new_url),
            )
        )

    def _room_title(self, room):
        username = (room.get("username") or "").strip()
        viewers = room.get("num_users")
        if viewers:
            return "{} [COLOR yellow]({})[/COLOR]".format(username, viewers)
        return username

    def _room_plot(self, room):
        bits = []
        subject = self._clean_text(room.get("subject") or room.get("room_subject"))
        if subject:
            bits.append(subject)
        tags = room.get("tags") or []
        if tags:
            bits.append("Tags: {}".format(", ".join("#{}".format(tag) for tag in tags[:6])))
        viewers = room.get("num_users")
        if viewers is not None:
            bits.append("Viewers: {}".format(viewers))
        private_price = room.get("private_price")
        if private_price:
            bits.append("Private: {} tk/min".format(private_price))
        spy_price = room.get("spy_show_price")
        if spy_price:
            bits.append("Spy: {} tk/min".format(spy_price))
        return " | ".join(bits) if bits else (room.get("username") or "Live room")

    def _render_rooms(self, payload, url, page):
        rooms = payload.get("rooms") or []
        total_count = int(payload.get("total_count") or 0)
        context_menu = self._build_context_menu()

        added = 0
        for room in rooms:
            username = (room.get("username") or "").strip()
            if not username:
                continue

            room_url = "{}/{}/".format(self.base_url.rstrip("/"), username)
            thumb = (room.get("img") or self.icon).strip()
            info = {
                "title": username,
                "plot": self._room_plot(room),
            }
            self.add_link(
                self._room_title(room),
                room_url,
                4,
                thumb,
                self.fanart,
                context_menu=context_menu,
                info_labels=info,
            )
            added += 1

        if added == 0:
            self.notify_error("No Chaturbate rooms found")
        elif (page * self.rooms_per_page) < total_count:
            self.add_dir(
                "[COLOR blue]Next Page ({})[/COLOR]".format(page + 1),
                url,
                2,
                self.icons.get("default", self.icon),
                context_menu=context_menu,
                page=page + 1,
            )

        self.end_directory("videos")

    def process_content(self, url, page=1):
        context = self._extract_context(url)
        if context["kind"] == "room":
            self.end_directory("videos")
            return

        context_menu = self._build_context_menu()
        self.add_dir("Search", "", 5, self.icons.get("search", self.icon), context_menu=context_menu)
        self.add_dir("Categories", self.LIST_PREFIX + "categories", 8, self.icons.get("categories", self.icon), context_menu=context_menu)

        payload = self._request_json(
            self.API_URL,
            params=self._build_listing_params(context, page),
            referer=self.base_url + "/",
        )
        if not payload:
            self.end_directory("videos")
            return

        self._render_rooms(payload, url, max(1, int(page or 1)))

    def process_categories(self, url):
        context_menu = self._build_context_menu()
        for key in ("all", "female", "male", "couple", "trans", "new"):
            label, _params = self.category_map[key]
            self.add_dir(label, self.LIST_PREFIX + key, 2, self.icons.get("categories", self.icon), context_menu=context_menu)
        self.end_directory("videos")

    def search(self, query):
        if not query:
            return
        self.process_content(self.SEARCH_PREFIX + urllib.parse.quote_plus(query.strip()), page=1)

    def _resolve_hls(self, username):
        room_url = "{}/{}/".format(self.base_url.rstrip("/"), username)
        self._make_request(room_url, referer=self.base_url + "/")
        payload = self._request_json(
            self.HLS_URL,
            referer=room_url,
            method="post",
            data={
                "room_slug": username,
                "bandwidth": "high",
                "current_edge": "",
                "exclude_edge": "",
            },
        )
        if payload and payload.get("success") and payload.get("url"):
            return payload.get("url"), room_url
        return None, room_url

    def _get_stream_headers(self, referer=None):
        return {
            "User-Agent": self.ua,
            "Referer": referer or (self.base_url + "/"),
            "Accept": "*/*",
            "Accept-Language": "en-US,en;q=0.9",
        }

    def _fetch_url_text(self, url, headers=None, timeout=20):
        req = urllib.request.Request(url, headers=headers or {})
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return response.read().decode("utf-8", "replace")

    def _absolutize_playlist_text(self, raw_text, base_url):
        fixed = re.sub(
            r'^(?!https?://)(?!#)(\S+)$',
            lambda m: urllib.parse.urljoin(base_url, m.group(1)),
            raw_text,
            flags=re.MULTILINE,
        )
        fixed = re.sub(
            r'URI="(?!https?://)([^"]+)"',
            lambda m: 'URI="{}"'.format(urllib.parse.urljoin(base_url, m.group(1))),
            fixed,
            flags=re.IGNORECASE,
        )
        return fixed

    def _normalize_chunklist_text(self, raw_text, base_url):
        fixed = self._absolutize_playlist_text(raw_text, base_url)
        lines = []
        for line in fixed.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            # ISA gets noisy with Chaturbate's rolling discontinuity and LL-HLS
            # helper tags when we proxy a constantly moving live window.
            if stripped.startswith("#EXT-X-DISCONTINUITY-SEQUENCE"):
                continue
            if stripped.startswith("#EXT-X-PROGRAM-DATE-TIME"):
                continue
            if stripped.startswith("#EXT-X-RENDITION-REPORT"):
                continue
            if stripped.startswith("#EXT-X-PART:"):
                continue
            if stripped.startswith("#EXT-X-PRELOAD-HINT:"):
                continue
            lines.append(stripped)
        return "\n".join(lines) + "\n"

    def _shutdown_proxy(self):
        global _CB_PROXY
        if _CB_PROXY is not None:
            try:
                _CB_PROXY.shutdown()
            except Exception:
                pass
            try:
                _CB_PROXY.server_close()
            except Exception:
                pass
            _CB_PROXY = None

    def _extract_best_variant_url(self, master_url):
        try:
            response = self.session.get(master_url, timeout=20)
            if response.status_code != 200:
                self.logger.error("[Chaturbate] Master playlist HTTP %s for %s", response.status_code, master_url)
                return None

            best_url = None
            best_bandwidth = -1
            lines = [line.strip() for line in response.text.splitlines()]
            for idx, line in enumerate(lines):
                if not line.startswith("#EXT-X-STREAM-INF:"):
                    continue

                match = re.search(r"BANDWIDTH=(\d+)", line, re.IGNORECASE)
                bandwidth = int(match.group(1)) if match else 0

                next_idx = idx + 1
                while next_idx < len(lines) and not lines[next_idx]:
                    next_idx += 1

                if next_idx >= len(lines):
                    continue

                variant_line = lines[next_idx]
                if variant_line.startswith("#"):
                    continue

                variant_url = urllib.parse.urljoin(master_url, variant_line)
                if bandwidth >= best_bandwidth:
                    best_bandwidth = bandwidth
                    best_url = variant_url

            return best_url
        except Exception as exc:
            self.logger.error("[Chaturbate] Could not extract master variant: %s", exc)
            return None

    def _extract_preferred_variant_data(self, master_url, master_text=None):
        try:
            if master_text is None:
                response = self.session.get(master_url, timeout=20)
                if response.status_code != 200:
                    self.logger.error("[Chaturbate] Master playlist HTTP %s for %s", response.status_code, master_url)
                    return None
                master_text = response.text

            lines = [line.strip() for line in master_text.splitlines() if line.strip()]
            audio_groups = {}
            variants = []

            for line in lines:
                if not line.startswith("#EXT-X-MEDIA:"):
                    continue
                if "TYPE=AUDIO" not in line:
                    continue
                group_match = re.search(r'GROUP-ID="([^"]+)"', line)
                uri_match = re.search(r'URI="([^"]+)"', line)
                if not group_match or not uri_match:
                    continue
                audio_groups[group_match.group(1)] = urllib.parse.urljoin(master_url, uri_match.group(1))

            for idx, line in enumerate(lines):
                if not line.startswith("#EXT-X-STREAM-INF:"):
                    continue

                next_idx = idx + 1
                while next_idx < len(lines) and not lines[next_idx]:
                    next_idx += 1
                if next_idx >= len(lines):
                    continue

                variant_line = lines[next_idx]
                if variant_line.startswith("#"):
                    continue

                bandwidth_match = re.search(r"BANDWIDTH=(\d+)", line, re.IGNORECASE)
                resolution_match = re.search(r"RESOLUTION=(\d+)x(\d+)", line, re.IGNORECASE)
                frame_rate_match = re.search(r"FRAME-RATE=([\d.]+)", line, re.IGNORECASE)
                audio_match = re.search(r'AUDIO="([^"]+)"', line)
                codecs_match = re.search(r'CODECS="([^"]+)"', line)

                width = int(resolution_match.group(1)) if resolution_match else 0
                height = int(resolution_match.group(2)) if resolution_match else 0
                frame_rate = float(frame_rate_match.group(1)) if frame_rate_match else 0.0
                bandwidth = int(bandwidth_match.group(1)) if bandwidth_match else 0
                audio_group = audio_match.group(1) if audio_match else ""

                variants.append(
                    {
                        "stream_inf": line,
                        "url": urllib.parse.urljoin(master_url, variant_line),
                        "bandwidth": bandwidth,
                        "width": width,
                        "height": height,
                        "frame_rate": frame_rate,
                        "audio_group": audio_group,
                        "audio_url": audio_groups.get(audio_group, ""),
                        "codecs": codecs_match.group(1) if codecs_match else "",
                    }
                )

            if not variants:
                return None

            def variant_rank(item):
                url = item.get("url") or ""
                height = item.get("height") or 0
                frame_rate = item.get("frame_rate") or 0.0
                bandwidth = item.get("bandwidth") or 0
                is_live_hls = 1 if "/live-hls/amlst:" in url else 0
                has_external_audio = 0 if item.get("audio_url") else 1
                stable_height = height if 0 < height <= 720 else -1
                stable_fps = 0 if frame_rate <= 30.1 else -1
                if is_live_hls:
                    return (is_live_hls, has_external_audio, stable_fps, stable_height, bandwidth)

                # The origin/llhls family with separate audio has proven fragile in Kodi.
                # For those streams, prefer a more conservative middle rendition over the
                # highest bandwidth 720p variant.
                conservative_height = -abs((height or 0) - 480)
                conservative_bandwidth = -bandwidth
                return (is_live_hls, has_external_audio, stable_fps, conservative_height, conservative_bandwidth)

            selected = max(variants, key=variant_rank)
            selected["include_audio"] = "/live-hls/amlst:" in (selected.get("url") or "")
            return selected
        except Exception as exc:
            self.logger.error("[Chaturbate] Could not parse master playlist: %s", exc)
            return None

    def _build_proxy_master_payload(self, variant_data, port):
        stream_inf = variant_data.get("stream_inf") or "#EXT-X-STREAM-INF:BANDWIDTH=1200000"
        video_url = "http://127.0.0.1:{}/chunklist?kind=video".format(port)
        audio_url = variant_data.get("audio_url") or ""
        include_audio = bool(variant_data.get("include_audio", True))

        lines = [
            "#EXTM3U",
            "#EXT-X-VERSION:6",
            "#EXT-X-INDEPENDENT-SEGMENTS",
        ]

        if audio_url and include_audio:
            lines.append(
                '#EXT-X-MEDIA:TYPE=AUDIO,GROUP-ID="audio_main",NAME="Audio",DEFAULT=YES,AUTOSELECT=YES,CHANNELS="2",URI="{}"'.format(
                    "http://127.0.0.1:{}/chunklist?kind=audio".format(port)
                )
            )
            if 'AUDIO="' in stream_inf:
                stream_inf = re.sub(r'AUDIO="[^"]+"', 'AUDIO="audio_main"', stream_inf)
            else:
                stream_inf += ',AUDIO="audio_main"'
        else:
            stream_inf = re.sub(r',?AUDIO="[^"]+"', '', stream_inf)

        lines.append(stream_inf)
        lines.append(video_url)
        return "\n".join(lines) + "\n"

    def _start_proxy_stream(self, username, stream_url, referer, variant_data):
        global _CB_PROXY
        self._shutdown_proxy()

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
        sock.close()

        state = {
            "stream_url": stream_url,
            "headers": self._get_stream_headers(referer),
            "variant_data": dict(variant_data),
            "last_refresh": 0.0,
            "lock": threading.Lock(),
        }

        def refresh_variant():
            now = time.time()
            with state["lock"]:
                if now - state["last_refresh"] < 5:
                    return False
                state["last_refresh"] = now

            try:
                master_raw = self._fetch_url_text(state["stream_url"], headers=state["headers"], timeout=10)
                refreshed_variant = self._extract_preferred_variant_data(state["stream_url"], master_text=master_raw)
                if refreshed_variant:
                    state["variant_data"] = dict(refreshed_variant)
                    self.logger.info(
                        "[Chaturbate] Refreshed session for %s -> %sp %sfps",
                        username,
                        refreshed_variant.get("height") or 0,
                        int(round(refreshed_variant.get("frame_rate") or 0)),
                    )
                    return True
            except Exception as exc:
                self.logger.warning("[Chaturbate] Session refresh failed for %s: %s", username, exc)
            return False

        def fetch_chunklist_bytes(kind):
            variant = state["variant_data"]
            target_url = ""
            if kind == "audio":
                target_url = variant.get("audio_url") or ""
            else:
                target_url = variant.get("url") or ""

            if not target_url:
                raise ValueError("No target URL for {}".format(kind))

            try:
                raw = self._fetch_url_text(target_url, headers=state["headers"], timeout=10)
            except Exception:
                if not refresh_variant():
                    raise
                variant = state["variant_data"]
                target_url = variant.get("audio_url") if kind == "audio" else variant.get("url")
                if not target_url:
                    raise
                raw = self._fetch_url_text(target_url, headers=state["headers"], timeout=10)

            base = target_url.rsplit("/", 1)[0] + "/"
            normalized = self._normalize_chunklist_text(raw, base)
            return normalized.encode("utf-8")

        class _Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path.startswith("/chunklist"):
                    parsed = urllib.parse.urlparse(self.path)
                    params = urllib.parse.parse_qs(parsed.query)
                    kind = (params.get("kind") or ["video"])[0]

                    try:
                        data = fetch_chunklist_bytes(kind)
                    except Exception as exc:
                        self.send_response(200)
                        self.send_header("Content-Type", "application/vnd.apple.mpegurl")
                        endlist = b"#EXTM3U\n#EXT-X-ENDLIST\n"
                        self.send_header("Content-Length", str(len(endlist)))
                        self.end_headers()
                        self.wfile.write(endlist)
                        self.server.website.logger.warning(
                            "[Chaturbate] %s chunklist failed for %s: %s",
                            kind,
                            username,
                            exc,
                        )
                        return

                    self.send_response(200)
                    self.send_header("Content-Type", "application/vnd.apple.mpegurl")
                    self.send_header("Content-Length", str(len(data)))
                    self.end_headers()
                    self.wfile.write(data)
                    return

                payload = self.server.website._build_proxy_master_payload(state["variant_data"], port).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/vnd.apple.mpegurl")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def do_HEAD(self):
                self.send_response(200)
                self.send_header("Content-Type", "application/vnd.apple.mpegurl")
                self.end_headers()

            def log_message(self, _format, *args):
                return

        class _Server(ThreadingMixIn, TCPServer):
            daemon_threads = True
            allow_reuse_address = True

        server = _Server(("127.0.0.1", port), _Handler)
        server.website = self
        _CB_PROXY = server
        thread = threading.Thread(target=server.serve_forever)
        thread.daemon = True
        thread.start()
        return "http://127.0.0.1:{}/master.m3u8".format(port)

    def play_video(self, url):
        parsed = urllib.parse.urlparse(url)
        path = parsed.path.strip("/")
        username = path.split("/")[0] if path else ""

        if not username:
            self.notify_error("No Chaturbate room found")
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
            return

        stream_url, referer = self._resolve_hls(username)
        if not stream_url:
            self.notify_error("No Chaturbate stream found")
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
            return

        variant_data = self._extract_preferred_variant_data(stream_url)
        if not variant_data:
            self.notify_error("Could not prepare Chaturbate stream")
            xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
            return

        proxy_master_url = self._start_proxy_stream(username, stream_url, referer, variant_data)
        self.logger.info(
            "[Chaturbate] Playback for %s via proxy master (%sp %sfps)",
            username,
            variant_data.get("height") or 0,
            int(round(variant_data.get("frame_rate") or 0)),
        )

        list_item = xbmcgui.ListItem(path=proxy_master_url)

        list_item.setProperty("IsPlayable", "true")
        list_item.setMimeType("application/vnd.apple.mpegurl")
        list_item.setContentLookup(False)
        if xbmc.getCondVisibility("System.HasAddon(inputstream.adaptive)"):
            list_item.setProperty("inputstream", "inputstream.adaptive")
            list_item.setProperty("inputstream.adaptive.manifest_type", "hls")
        xbmcplugin.setResolvedUrl(self.addon_handle, True, list_item)
