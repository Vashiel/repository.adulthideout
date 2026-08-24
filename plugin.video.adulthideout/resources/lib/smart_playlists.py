#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import re
import sys
import json
import time
import random
import threading
import urllib.parse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from importlib import import_module

import xbmc
import xbmcaddon
import xbmcgui
import xbmcplugin
import xbmcvfs
LIB_DIR = os.path.abspath(os.path.dirname(__file__))
ADDON_ROOT = os.path.abspath(os.path.join(LIB_DIR, "..", ".."))

if LIB_DIR not in sys.path:
    sys.path.insert(0, LIB_DIR)
if ADDON_ROOT not in sys.path:
    sys.path.insert(0, ADDON_ROOT)

try:
    from resources.lib.view_utils import end_directory_with_view
except ImportError:
    try:
        from view_utils import end_directory_with_view
    except Exception:
        end_directory_with_view = lambda *args, **kwargs: None

try:
    from resources.lib.personal_library import load_library, build_save_command
except ImportError:
    try:
        from personal_library import load_library, build_save_command
    except Exception:
        load_library = lambda *args, **kwargs: {}
        build_save_command = lambda *args, **kwargs: ""


def _text(message_id, fallback, *args):
    addon = xbmcaddon.Addon()
    value = addon.getLocalizedString(message_id) or fallback
    return value.format(*args) if args else value


# In-memory cache for harvested channel playlists
_CHANNEL_CACHE = {}

# These sources currently perform expensive artwork/network work or return
# unstable playback URLs. They remain available normally, but must not be able
# to stall the persistent 24/7 service.
SMART_STREAM_UNSTABLE_SOURCES = {"xhamster", "spankbang", "txxx"}

GENERIC_QUERY_STOPWORDS = {
    "white", "black", "red", "blue", "green", "pink", "gold", "brown", "grey", "gray",
    "star", "sweet", "rose", "sky", "day", "bell", "cross", "knight", "ford", "stone",
    "fox", "ass", "big", "tiny", "sparkle", "storm", "girl", "babe", "hot", "sex", "tube",
    "porn", "video", "full", "hd", "xxx", "movie", "scene", "new", "top", "best", "cum", "cock", "fuck", "hard"
}


def is_query_relevance_match(query, title):
    """Calculates relevance score and strictly verifies genuine matches to prevent fake/random video injection."""
    if not query or not title:
        return False, 0
    clean_title = re.sub(r'\[.*?\]', ' ', str(title)).lower()
    clean_title = re.sub(r'[-_.]+', ' ', clean_title)
    clean_title = ' ' + ' '.join(clean_title.split()) + ' '

    clean_query = str(query).strip().lower()
    clean_query = re.sub(r'[-_.]+', ' ', clean_query)
    clean_query = ' '.join(clean_query.split())
    if not clean_query:
        return True, 1

    phrase_pattern = r'\b' + re.escape(clean_query) + r'\b'
    if re.search(phrase_pattern, clean_title, re.IGNORECASE):
        return True, 10

    tokens = [tok for tok in clean_query.split() if tok]
    if len(tokens) == 1:
        tok_pattern = r'\b' + re.escape(tokens[0]) + r'\b'
        if re.search(tok_pattern, clean_title, re.IGNORECASE):
            return True, 8

    return False, 0



# Channel source pools with optional targeted category URLs
CHANNEL_POOLS = {
    "trans": [
        ("shemalez", None),
        ("tnaflix", "https://www.tnaflix.com/transgender/"),
        ("ashemaletube", None),
        ("pornhub", "https://www.pornhub.com/transgender"),
        ("eporner", "https://www.eporner.com/search/trans/"),
        ("xhamster", "https://xhamster.com/transgender"),
        ("xnxx", "https://www.xnxx.com/search/trans"),
        ("xvideos", "https://www.xvideos.com/?k=trans"),
        ("spankbang", "https://spankbang.com/s/transgender/"),
        ("txxx", None),
    ],
    "4k": [
        ("eporner", "https://www.eporner.com/4k/"),
        ("spankbang", "https://spankbang.com/s/4k/"),
        ("hqporner", "https://hqporner.com/hdporn/4k"),
        ("xhamster", "https://xhamster.com/4k"),
    ],
    "long": [
        ("eporner", "https://www.eporner.com/search/20min/"),
        ("spankbang", "https://spankbang.com/s/20min/"),
        ("hqporner", None),
        ("xhamster", "https://xhamster.com/longest"),
    ],
    "movies": [
        ("filmadult", None),
        ("streamporn", None),
        ("freeomovie", None),
        ("pornobae", None),
        ("fullxcinema", None),
        ("fullporner", None),
        ("superporn", "https://www.superporn.com/series/full-movies"),
        ("trannyvideosxxx", None),
        ("pandamovies", None),
        ("bananamovies", None),
        ("pornhoarder", None),
        ("pornhd3x", None),
        ("netfapx", None),
        ("xtapes", None),
        ("porngo", None),
        ("tubepornclassic", None),
        ("watchxxxfree", None),
        ("yourdailypornvideos", None),
        ("allpornstream", None),
        ("pornmz", None),
        ("javhdporn", None),
        ("missav", None),
        ("spankbang", "https://spankbang.com/s/full+movie/"),
        ("eporner", "https://www.eporner.com/search/full+movie/"),
        ("xhamster", "https://xhamster.com/movies"),
        ("pornhub", "https://www.pornhub.com/video/search?search=full+movie"),
        ("xvideos", "https://www.xvideos.com/?k=full+movie"),
        ("xnxx", "https://www.xnxx.com/search/full+movie"),
        ("tnaflix", "https://www.tnaflix.com/search?what=full+movie"),
        ("hqporner", None),
        ("txxx", None),
    ],
    "retro": [
        ("vintagepornfun", None),
        ("tubepornclassic", None),
        ("spankbang", "https://spankbang.com/s/vintage/"),
        ("eporner", "https://www.eporner.com/search/vintage/"),
    ],
    "hentai": [
        ("hentaigasm", None),
        ("hentai2w", None),
        ("hanime", None),
        ("hentaicity", None),
        ("hentaidude", None),
        ("hentaimama", None),
        ("hentaimoon", None),
        ("hentaiocean", None),
        ("hentaisea", None),
        ("watchhentai", None),
        ("rule34video", None),
    ],
    "jav": [
        ("avjoy", None),
        ("javmix", None),
        ("javtiful", None),
        ("javhdporn", None),
        ("85po", "https://www.85po.com/en/latest-updates/"),
        ("jable", None),
        ("spankbang", "https://spankbang.com/s/japanese/"),
        ("eporner", "https://www.eporner.com/search/japanese/"),
        ("pornhub", "https://www.pornhub.com/video/search?search=japanese"),
        ("xvideos", "https://www.xvideos.com/?k=japanese"),
    ],
    "trending": [
        ("eporner", None),
        ("tnaflix", None),
        ("xhamster", None),
        ("xvideos", None),
        ("hqporner", None),
        ("pornhub", None),
        ("xnxx", None),
        ("youporn", None),
        ("redtube", None),
        ("spankbang", None),
    ],
    "top_tubes": [
        ("eporner", None),
        ("tnaflix", None),
        ("xhamster", None),
        ("xvideos", None),
        ("hqporner", None),
        ("pornhub", None),
        ("xnxx", None),
        ("youporn", None),
        ("redtube", None),
        ("spankbang", None),
    ],
}

LENGTH_OPTIONS = [
    ("any", "Beliebig (Alle Längen)"),
    ("short", "Kurze Clips (< 10 Min)"),
    ("10min", "Mittlere Szenen (> 10 Min)"),
    ("20min", "Lange Szenen (> 20 Min)"),
    ("movies", "Full Movies (70+ Min)"),
]

POOL_OPTIONS = [
    ("top_tubes", "Top-Tubes (Mainstream Mix)"),
    ("all", "Alle 272 Webseiten (Mega Shuffle)"),
    ("vault", "Nur Vault-Favoriten"),
    ("4k", "Ultra HD 4K Theater"),
    ("long", "Lange Szenen (20+ min)"),
    ("movies", "Full Movies & Feature Films"),
    ("retro", "Retro & Vintage Klassiker"),
    ("hentai", "Hentai & Anime"),
    ("jav", "JAV & Asiatisch"),
    ("trans", "Trans / Shemale"),
    ("fetish", "Fetish & BDSM"),
    ("specific", "Spezifische Webseite auswählen..."),
]

SORT_OPTIONS = [
    ("trending", "Trending / Beliebteste"),
    ("newest", "Neueste Uploads (Latest)"),
    ("top_rated", "Höchstbewertet (Top-Rated)"),
    ("random", "Reiner Zufall (Shuffle)"),
]


def clean_title(t):
    cleaned = re.sub(r'\[COLOR\s+[^\]]+\]|\[/COLOR\]', '', str(t), flags=re.IGNORECASE)
    cleaned = re.sub(r'\[[^\]]*\]', '', cleaned)
    cleaned = re.sub(r'\([^\)]*\)', '', cleaned)
    return cleaned.strip()


def natural_sort_key(s):
    cleaned = clean_title(s)
    return [int(text) if text.isdigit() else text.lower() for text in re.split(r'(\d+)', cleaned)]


def parse_duration_seconds(duration_str):
    if not duration_str:
        return 0
    if isinstance(duration_str, (int, float)):
        return max(0, int(duration_str))
    s_str = str(duration_str)
    if re.fullmatch(r'\s*\d+(?:\.\d+)?\s*', s_str):
        return max(0, int(float(s_str.strip())))
    # Match hours:minutes:seconds (e.g. 1:12:30 or 01:12:30)
    m_hms = re.search(r'(\d+):(\d+):(\d+)', s_str)
    if m_hms:
        return int(m_hms.group(1))*3600 + int(m_hms.group(2))*60 + int(m_hms.group(3))
    # Match minutes:seconds (e.g. 14:41, [60:31])
    m_ms = re.search(r'(\d+):(\d+)', s_str)
    if m_ms:
        return int(m_ms.group(1))*60 + int(m_ms.group(2))
    # Match X hr / hours / h
    m_hr = re.search(r'(\d+)\s*(?:hr|hour|hours|h)\b(?:\s*(\d+)\s*(?:min|m))?', s_str, re.IGNORECASE)
    if m_hr:
        hrs = int(m_hr.group(1)) * 3600
        mins = int(m_hr.group(2) or 0) * 60
        return hrs + mins
    # Match X min / mins / m
    m_min = re.search(r'(\d+)\s*(?:min|mins|m)\b', s_str, re.IGNORECASE)
    if m_min:
        return int(m_min.group(1)) * 60
    # Match X sec / s
    m_sec = re.search(r'(\d+)\s*(?:sec|secs|s)\b', s_str, re.IGNORECASE)
    if m_sec:
        return int(m_sec.group(1))
    return 0


DEDICATED_MOVIE_SOURCES = {
    "filmadult", "streamporn", "freeomovie", "fullxcinema", "fullporner", "superporn",
    "trannyvideosxxx", "pornobae", "pornmz", "pandamovies", "bananamovies",
    "pornhoarder", "pornhd3x", "netfapx", "xtapes", "porngo",
    "javhdporn", "javsubbed", "missav", "tubepornclassic",
    "watchxxxfree", "yourdailypornvideos", "allpornstream",
    "darknessporn", "javguru", "hdshemalez", "vintagepornfun"
}


def matches_duration(duration_str, min_length_key, title="", source=""):
    if not min_length_key or min_length_key == "any":
        return True
    secs = parse_duration_seconds(duration_str)
    if secs == 0 and title:
        secs = parse_duration_seconds(title)

    if min_length_key == "short":
        return 0 < secs < 600
    if min_length_key == "10min":
        return secs >= 600
    if min_length_key == "20min":
        return secs >= 1200
    if min_length_key in ("movies", "long_movies", "full_movie"):
        if secs >= 4200: # >= 70 min (Full Feature Film — a real movie is at least 70 min)
            return True
        if secs > 0 and secs < 4200:
            return False # Strictly reject clips and long scenes (< 70 min)
        # A title or a website category is not proof of runtime. Unknown
        # durations are rejected so previews and mislabeled clips cannot enter
        # Full Movie searches or continuous streams.
        return False
    return True


class SmartPlaylists:
    def __init__(self, addon_handle, plugin_url, addon):
        self.addon_handle = addon_handle
        self.plugin_url = plugin_url
        self.addon = addon
        self.addon_path = addon.getAddonInfo("path")
        self.logos_dir = os.path.join(self.addon_path, "resources", "logos")
        self.fanart = os.path.join(self.logos_dir, "fanart.jpg")
        self.icon = os.path.join(self.logos_dir, "icon.png")
        self.playlist_icon = os.path.join(self.logos_dir, "smart_streams.png")
        if not os.path.exists(self.playlist_icon):
            self.playlist_icon = self.icon

        self.data_dir = self._profile_path("special://profile/addon_data/plugin.video.adulthideout")
        os.makedirs(self.data_dir, exist_ok=True)
        self.custom_streams_file = os.path.join(self.data_dir, "custom_streams.json")
        self.active_stream_file = os.path.join(self.data_dir, "active_smart_stream.json")
        self._temp_stream = None  # In-memory only, never persisted to Smart Stream list

    def _profile_path(self, path):
        try:
            return xbmcvfs.translatePath(path)
        except AttributeError:
            return xbmc.translatePath(path)

    def _url(self, target_action, **kwargs):
        params = {"mode": "50", "action": target_action}
        for key, value in kwargs.items():
            if key not in ("action", "mode") and value is not None:
                params[key] = str(value)
        return "{}?{}".format(self.plugin_url, urllib.parse.urlencode(params))

    def _load_custom_streams(self):
        try:
            if os.path.exists(self.custom_streams_file):
                with open(self.custom_streams_file, "r", encoding="utf-8") as f:
                    streams = json.load(f)
                return streams if isinstance(streams, list) else []
        except Exception:
            pass
        return []

    def _save_custom_streams(self, streams):
        try:
            with open(self.custom_streams_file, "w", encoding="utf-8") as f:
                json.dump(streams, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

    def _set_temp_stream(self, stream):
        self._temp_stream = dict(stream or {})
        try:
            with open(self.active_stream_file, "w", encoding="utf-8") as handle:
                json.dump(self._temp_stream, handle, ensure_ascii=False)
        except Exception as exc:
            xbmc.log(f"[AdultHideout] Could not store active Smart Stream: {exc}", xbmc.LOGDEBUG)

    def _get_temp_stream(self, channel):
        if self._temp_stream and self._temp_stream.get("id") == channel:
            return self._temp_stream
        try:
            with open(self.active_stream_file, "r", encoding="utf-8") as handle:
                stream = json.load(handle)
            if isinstance(stream, dict) and stream.get("id") == channel:
                self._temp_stream = stream
                return stream
        except Exception:
            pass
        return None

    def _add_channel_entry(self, label, channel_id, color="yellow", icon=None, is_custom=False, has_custom=False):
        colored_label = f"[COLOR {color}]{label}[/COLOR]"
        item = xbmcgui.ListItem(label=colored_label)
        art_icon = icon or self.playlist_icon
        item.setArt({"thumb": art_icon, "icon": art_icon, "fanart": self.fanart})
        
        context_menu = [
            (
                _text(30878, "Browse Channel Videos"),
                f"Container.Update({self._url('show_channel', channel=channel_id)})"
            ),
            (
                _text(30877, "Refresh Channel Videos"),
                f"RunPlugin({self._url('zap_channel', channel=channel_id, refresh=1)})"
            ),
        ]

        if is_custom:
            context_menu.append((
                _text(30889, "Delete Custom Stream"),
                f"RunPlugin({self._url('delete_custom_stream', channel=channel_id)})"
            ))

        if has_custom:
            context_menu.append((
                _text(30890, "Delete All Custom Streams"),
                f"RunPlugin({self._url('delete_all_custom_streams')})"
            ))

        item.addContextMenuItems(context_menu)
        
        # 1-Click Instant Zapping
        url = self._url("zap_channel", channel=channel_id)
        xbmcplugin.addDirectoryItem(self.addon_handle, url, item, False)

    def show_menu(self):
        custom_streams = [s for s in self._load_custom_streams() if not s.get("id", "").startswith("custom_temp_")]
        has_custom = len(custom_streams) > 0

        # 1. Interactive Custom Stream Builder
        builder_item = xbmcgui.ListItem(label="[COLOR green][B]+ {}[/B][/COLOR]".format(_text(30883, "Custom Smart Stream Builder...")))
        builder_item.setArt({"thumb": self.playlist_icon, "icon": self.playlist_icon, "fanart": self.fanart})
        if has_custom:
            builder_item.addContextMenuItems([(
                _text(30890, "Delete All Custom Streams"),
                f"RunPlugin({self._url('delete_all_custom_streams')})"
            )])
        xbmcplugin.addDirectoryItem(self.addon_handle, self._url("builder"), builder_item, True)

        # 2. Saved Custom Streams
        for cs in custom_streams:
            cs_id = cs.get("id")
            cs_name = cs.get("name", "Custom Stream")
            self._add_channel_entry(f"★ {cs_name}", cs_id, color="deepskyblue", is_custom=True, has_custom=has_custom)

        # 3. Pre-configured Smart Streams
        self._add_channel_entry(_text(30861, "Vault Favorites Shuffle (24/7)"), "vault", color="yellow", has_custom=has_custom)
        self._add_channel_entry(_text(30862, "Trending & Top-Rated Mix"), "trending", color="orange", has_custom=has_custom)
        self._add_channel_entry(_text(30863, "Mega Tube Shuffle (All Sites)"), "mega", color="cyan", has_custom=has_custom)
        self._add_channel_entry(_text(30864, "Ultra HD 4K / 1080p Theater"), "4k", color="magenta", has_custom=has_custom)
        self._add_channel_entry(_text(30879, "Long Scenes (20+ min)"), "long", color="chartreuse", has_custom=has_custom)
        self._add_channel_entry(_text(30880, "Full Movies & Feature Films (≥70 Min)"), "movies", color="gold", has_custom=has_custom)
        self._add_channel_entry(_text(30881, "Retro & Vintage Classic Movies"), "retro", color="coral", has_custom=has_custom)
        self._add_channel_entry(_text(30865, "Hentai & Anime 24/7"), "hentai", color="springgreen", has_custom=has_custom)
        self._add_channel_entry(_text(30866, "JAV & Asian 24/7"), "jav", color="pink", has_custom=has_custom)
        self._add_channel_entry(_text(30867, "Trans / Shemale 24/7"), "trans", color="lightblue", has_custom=has_custom)

        end_directory_with_view(self.addon_handle, self.addon, content_type="files")

    def show_builder(self, params):
        """Displays an interactive Settings-style Form Screen for configuring custom streams."""
        query = params.get("query", "")
        length = params.get("length", "any")
        pool = params.get("pool", "top_tubes")
        specific_site = params.get("specific_site", "")
        sort = params.get("sort", "trending")
        name = params.get("name", "")

        # Find human labels
        len_label = next((lbl for k, lbl in LENGTH_OPTIONS if k == length), "Beliebig")
        pool_label = next((lbl for k, lbl in POOL_OPTIONS if k == pool), "Top-Tubes")
        if pool == "specific" and specific_site:
            pool_label = f"Webseite: {specific_site}"
        sort_label = next((lbl for k, lbl in SORT_OPTIONS if k == sort), "Trending")

        def add_setting_row(title, value_text, action_name):
            item = xbmcgui.ListItem(label=f"[COLOR yellow]{title}:[/COLOR]   [COLOR cyan]{value_text}[/COLOR]")
            item.setArt({"thumb": self.playlist_icon, "icon": self.playlist_icon, "fanart": self.fanart})
            url = self._url(action_name, query=query, length=length, pool=pool, specific_site=specific_site, sort=sort, name=name)
            xbmcplugin.addDirectoryItem(self.addon_handle, url, item, False)

        # Field 1: Query
        add_setting_row("Suchbegriff / Query", query if query else "[Beliebig / Alle]", "builder_edit_query")
        # Field 2: Duration
        add_setting_row("Mindestlänge / Length", len_label, "builder_edit_length")
        # Field 3: Sites Pool
        add_setting_row("Seiten-Auswahl / Sites", pool_label, "builder_edit_pool")
        # Field 4: Sorting
        add_setting_row("Sortierung / Sort", sort_label, "builder_edit_sort")
        # Field 5: Custom Stream Name
        default_auto_name = f"{query.title()} Mix" if query else f"{pool_label.split('(')[0].strip()} Mix"
        disp_name = name if name else f"[{default_auto_name}]"
        add_setting_row("Kanal-Name / Title", disp_name, "builder_edit_name")

        # Action 1: Start Playback Now
        play_item = xbmcgui.ListItem(label="[COLOR lime][B]>> SMART STREAM JETZT STARTEN[/B][/COLOR]")
        play_item.setArt({"thumb": self.playlist_icon, "icon": self.playlist_icon, "fanart": self.fanart})
        play_url = self._url("builder_start", query=query, length=length, pool=pool, specific_site=specific_site, sort=sort, name=name)
        xbmcplugin.addDirectoryItem(self.addon_handle, play_url, play_item, False)

        # Action 2: Save as Channel & Start
        save_item = xbmcgui.ListItem(label="[COLOR deepskyblue][B]★ ALS EIGENEN KANAL SPEICHERN & STARTEN[/B][/COLOR]")
        save_item.setArt({"thumb": self.playlist_icon, "icon": self.playlist_icon, "fanart": self.fanart})
        save_url = self._url("builder_save", query=query, length=length, pool=pool, specific_site=specific_site, sort=sort, name=name)
        xbmcplugin.addDirectoryItem(self.addon_handle, save_url, save_item, False)

        end_directory_with_view(self.addon_handle, self.addon, content_type="files")

    def builder_edit_query(self, params):
        current = params.get("query", "")
        kb = xbmc.Keyboard(current, "Suchbegriff für Smart Stream (leer = alle)")
        kb.doModal()
        if kb.isConfirmed():
            params["query"] = kb.getText().strip()
        url = self._url("builder", **params)
        xbmc.executebuiltin(f"Container.Update({url},replace)")

    def builder_edit_length(self, params):
        labels = [lbl for _, lbl in LENGTH_OPTIONS]
        idx = xbmcgui.Dialog().select("Mindestlänge / Dauer auswählen", labels)
        if idx >= 0:
            params["length"] = LENGTH_OPTIONS[idx][0]
        url = self._url("builder", **params)
        xbmc.executebuiltin(f"Container.Update({url},replace)")

    def builder_edit_pool(self, params):
        labels = [lbl for _, lbl in POOL_OPTIONS]
        idx = xbmcgui.Dialog().select("Seiten-Auswahl / Quellen auswählen", labels)
        if idx >= 0:
            selected_key = POOL_OPTIONS[idx][0]
            if selected_key == "specific":
                all_sites = sorted(self._get_catalog_sites())
                s_idx = xbmcgui.Dialog().select("Spezifische Webseite wählen", all_sites)
                if s_idx >= 0:
                    params["pool"] = "specific"
                    params["specific_site"] = all_sites[s_idx]
            else:
                params["pool"] = selected_key
                params["specific_site"] = ""
        url = self._url("builder", **params)
        xbmc.executebuiltin(f"Container.Update({url},replace)")

    def builder_edit_sort(self, params):
        labels = [lbl for _, lbl in SORT_OPTIONS]
        idx = xbmcgui.Dialog().select("Sortierung auswählen", labels)
        if idx >= 0:
            params["sort"] = SORT_OPTIONS[idx][0]
        url = self._url("builder", **params)
        xbmc.executebuiltin(f"Container.Update({url},replace)")

    def builder_edit_name(self, params):
        current = params.get("name", "")
        kb = xbmc.Keyboard(current, "Namen für eigenen Stream eingeben")
        kb.doModal()
        if kb.isConfirmed() and kb.getText().strip():
            params["name"] = kb.getText().strip()
        url = self._url("builder", **params)
        xbmc.executebuiltin(f"Container.Update({url},replace)")

    def builder_save(self, params):
        query = params.get("query", "").strip()
        name = params.get("name", "").strip()
        if not name:
            default_auto_name = f"{query.title()} Mix" if query else "Mein Smart Stream"
            name = default_auto_name

        streams = self._load_custom_streams()
        
        # Check if an existing stream has matching name or matching query
        existing_idx = None
        for i, s in enumerate(streams):
            if s.get("name", "").strip().lower() == name.lower():
                existing_idx = i
                break
            if query and s.get("query", "").strip().lower() == query.lower():
                existing_idx = i
                break

        custom_id = streams[existing_idx].get("id") if existing_idx is not None else f"custom_{int(time.time())}"

        updated_entry = {
            "id": custom_id,
            "name": name,
            "query": query,
            "length": params.get("length", "any"),
            "pool": params.get("pool", "top_tubes"),
            "specific_site": params.get("specific_site", ""),
            "sort": params.get("sort", "trending"),
        }

        if existing_idx is not None:
            streams[existing_idx] = updated_entry
            action_msg = f"'{name}' aktualisiert & überschrieben!"
        else:
            streams.append(updated_entry)
            action_msg = f"'{name}' dauerhaft gespeichert!"

        self._save_custom_streams(streams)
        xbmcgui.Dialog().notification(
            _text(30860, "Smart Streams (Beta)"),
            action_msg,
            xbmcgui.NOTIFICATION_INFO,
            2000,
        )
        self.zap_channel(custom_id)

    def _get_paged_url(self, base_url, page=1):
        if not base_url or page <= 1:
            return base_url
        if "{}" in base_url:
            return base_url.format(page)
        parsed = urllib.parse.urlparse(base_url)
        clean_path = parsed.path.rstrip('/')
        
        # If URL has query parameters (e.g. Pornhub, Redtube, YouPorn, HQPorner search queries)
        if parsed.query:
            q_params = urllib.parse.parse_qs(parsed.query)
            q_params['page'] = [str(page)]
            return parsed._replace(query=urllib.parse.urlencode(q_params, doseq=True)).geturl()

        if "85po.com" in base_url or "eporner.com" in base_url or "spankbang.com" in base_url:
            if clean_path.rsplit('/', 1)[-1].isdigit():
                clean_path = clean_path.rsplit('/', 1)[0]
            return f"{parsed.scheme}://{parsed.netloc}{clean_path}/{page}/"
            
        if "xhamster.com" in base_url:
            if clean_path.rsplit('/', 1)[-1].isdigit():
                clean_path = clean_path.rsplit('/', 1)[0]
            return f"{parsed.scheme}://{parsed.netloc}{clean_path}/{page}"

        if clean_path.rsplit('/', 1)[-1].isdigit():
            clean_path = clean_path.rsplit('/', 1)[0]
        return f"{parsed.scheme}://{parsed.netloc}{clean_path}/{page}/"

    def _harvest_website_videos(self, website_name, max_items=10, custom_url=None, query=None, page=1, min_length="any"):
        from resources.lib.base_website import BaseWebsite

        try:
            if website_name in SMART_STREAM_UNSTABLE_SOURCES:
                return []
            module = import_module(f"resources.websites.{website_name}")
            cls = None
            for attr in dir(module):
                candidate = getattr(module, attr)
                if (
                    isinstance(candidate, type)
                    and issubclass(candidate, BaseWebsite)
                    and candidate is not BaseWebsite
                    and candidate.__module__ == module.__name__
                ):
                    cls = candidate
                    break
            if not cls:
                return []

            instance = cls(-1)
            instance.adult_hideout_full_movie_mode = min_length in ("movies", "long_movies", "full_movie")
            instance.adult_hideout_background_harvest = True
            videos = []

            def custom_add_link(name, url, mode=4, icon=None, fanart=None,
                                context_menu=None, info_labels=None, **kwargs):
                playable_url = url
                if not str(playable_url).startswith("plugin://"):
                    playable_url = f"{self.plugin_url}?url={urllib.parse.quote_plus(str(url))}&mode=4&name={urllib.parse.quote_plus(str(name))}&website={website_name}"
                
                duration_str = ""
                if info_labels and isinstance(info_labels, dict):
                    duration_str = info_labels.get("duration", "")

                videos.append(
                    {
                        "website": website_name,
                        "target_url": playable_url,
                        "title": str(name),
                        "thumbnail": str(icon or self.icon),
                        "duration": duration_str,
                    }
                )

            instance.add_link = custom_add_link
            instance.add_dir = lambda *args, **kwargs: None
            instance.end_directory = lambda *args, **kwargs: None
            instance.notify_error = lambda *args, **kwargs: None
            instance.notify_info = lambda *args, **kwargs: None

            if query:
                instance.search(query)
            else:
                start_url = custom_url or instance.base_url
                if not custom_url and hasattr(instance, "get_start_url_and_label"):
                    start_url, _ = instance.get_start_url_and_label()

                if page > 1:
                    start_url = self._get_paged_url(start_url, page)

                instance.process_content(start_url)

            if query:
                filtered = []
                for v in videos:
                    matched, score = is_query_relevance_match(query, v.get("title", ""))
                    if matched:
                        filtered.append((score, v))
                filtered.sort(key=lambda x: x[0], reverse=True)
                videos = [item[1] for item in filtered]

            if min_length and min_length != "any":
                videos = [
                    video for video in videos
                    if matches_duration(
                        video.get("duration", ""),
                        min_length,
                        video.get("title", ""),
                        source=video.get("website", website_name),
                    )
                ]

            return videos[:max_items]
        except Exception as exc:
            xbmc.log(f"[AdultHideout] Error harvesting {website_name} (Page {page}): {exc}", xbmc.LOGDEBUG)
            return []

    def _get_catalog_sites(self, category=None):
        catalog_path = os.path.join(self.addon_path, "resources", "website_catalog.json")
        try:
            with open(catalog_path, "r", encoding="utf-8") as handle:
                catalog = json.load(handle)
        except Exception:
            return ["spankbang", "pornhub", "xhamster", "eporner", "xvideos"]

        if category:
            taxonomy = catalog.get("taxonomy", {})
            content = taxonomy.get("content", {})
            types = taxonomy.get("types", {})
            sites = content.get(category, []) or types.get(category, [])
            if sites:
                return sites

        return catalog.get("websites", ["spankbang", "pornhub", "xhamster"])

    def _get_fast_seed(self, channel):
        """Quickly harvests 8-12 videos across primary scrapers for instant 1-click playback."""
        if channel == "vault":
            data = load_library()
            items = [it for it in data.get("items", []) if it.get("kind") != "folder" and it.get("target_url")]
            random.shuffle(items)
            items.sort(key=lambda item: int(item.get("rating", 0) or 0), reverse=True)
            res = []
            for it in items[:12]:
                res.append({
                    "website": it.get("source", ""),
                    "target_url": it.get("target_url", ""),
                    "title": it.get("title", "Video"),
                    "thumbnail": it.get("thumbnail", ""),
                })
            return res

        elif channel.startswith("custom_"):
            # Check in-memory temp stream first (Star Finder / builder_start streams)
            cs = self._get_temp_stream(channel)
            if cs is None:
                custom_streams = self._load_custom_streams()
                cs = next((s for s in custom_streams if s.get("id") == channel), None)
            if cs:
                q = cs.get("query")
                stars_list = cs.get("stars", [])
                spec = cs.get("specific_site")
                pool_name = cs.get("pool", "top_tubes")
                len_filter = cs.get("length", "any")
                if len_filter in ("movies", "long_movies", "full_movie"):
                    sites = [site for site, _url in CHANNEL_POOLS["movies"]]
                elif spec:
                    sites = [spec]
                elif pool_name in CHANNEL_POOLS:
                    sites = [s for s, _ in CHANNEL_POOLS[pool_name]]
                elif pool_name == "all":
                    sites = self._get_catalog_sites()
                else:
                    sites = ["spankbang", "eporner", "xhamster", "xnxx", "redtube", "tnaflix", "pornhub", "youporn", "hqporner"]
                
                available = [s for s in sites if os.path.exists(os.path.join(self.addon_path, "resources", "websites", f"{s}.py"))]
                selected = random.sample(available, min(4, len(available))) if available else ["spankbang"]
                
                seed_res = []
                if stars_list:
                    # Pick 8 random stars and query top available pool tubes concurrently
                    chosen_stars = random.sample(stars_list, min(8, len(stars_list)))
                    if len_filter in ("movies", "long_movies", "full_movie"):
                        top_search_sites = [s for s, _url in CHANNEL_POOLS["movies"] if s in available]
                    elif pool_name == "trans":
                        top_search_sites = [s for s in ["pornhub", "xhamster", "tnaflix", "xnxx", "eporner", "shemalez", "xvideos"] if s in available]
                    else:
                        top_search_sites = [s for s in ["tnaflix", "eporner", "xnxx", "xhamster", "pornhub", "hqporner", "xvideos"] if s in available]

                    tasks = []
                    for st in chosen_stars:
                        site_count = 4 if len_filter in ("movies", "long_movies", "full_movie") else 2
                        if len_filter in ("movies", "long_movies", "full_movie") and "eporner" in top_search_sites:
                            remaining_sites = [site for site in top_search_sites if site != "eporner"]
                            sites_for_star = ["eporner"] + random.sample(
                                remaining_sites,
                                min(site_count - 1, len(remaining_sites)),
                            )
                        else:
                            sites_for_star = random.sample(top_search_sites, min(site_count, len(top_search_sites))) if top_search_sites else ["eporner"]
                        for site in sites_for_star:
                            tasks.append((site, st))

                    with ThreadPoolExecutor(max_workers=min(12, len(tasks))) as executor:
                        futures = [
                            executor.submit(self._harvest_website_videos, site, 4, None, st, 1, len_filter)
                            for site, st in tasks
                        ]
                        for f in as_completed(futures):
                            seed_res.extend(f.result())



                else:
                    with ThreadPoolExecutor(max_workers=4) as executor:
                        futures = [executor.submit(self._harvest_website_videos, s, 4, None, q, 1, len_filter) for s in selected]
                        for f in as_completed(futures):
                            seed_res.extend(f.result())
                            if len(seed_res) >= 4:
                                break

                if not seed_res and (q or stars_list):
                    # Search alternative tubes specifically for this performer/query
                    target_name = stars_list[0] if stars_list else q
                    remaining = [s for s in sites if s not in selected and os.path.exists(os.path.join(self.addon_path, "resources", "websites", f"{s}.py"))]
                    for rem_site in remaining:
                        more = self._harvest_website_videos(rem_site, 4, None, target_name, 1, len_filter)
                        if more:
                            seed_res.extend(more)
                            if len(seed_res) >= 4:
                                break




                random.shuffle(seed_res)
                return seed_res

        if channel in CHANNEL_POOLS:
            pool = CHANNEL_POOLS[channel]
            available = [
                (site, curl) for site, curl in pool
                if os.path.exists(os.path.join(self.addon_path, "resources", "websites", f"{site}.py"))
            ]
            if channel == "movies":
                preferred_names = ("eporner", "xhamster", "spankbang", "xvideos", "tnaflix", "xnxx")
                preferred = [entry for entry in available if entry[0] in preferred_names]
                selected = preferred[:6] if preferred else available[:6]
            else:
                selected = random.sample(available, min(4, len(available))) if available else [("spankbang", None)]
            seed_res = []
            with ThreadPoolExecutor(max_workers=4) as executor:
                futures = [
                    executor.submit(
                        self._harvest_website_videos,
                        site,
                        4,
                        curl,
                        None,
                        1,
                        "movies" if channel == "movies" else "any",
                    )
                    for site, curl in selected
                ]
                for f in as_completed(futures):
                    seed_res.extend(f.result())
                    if len(seed_res) >= 4:
                        break

            if channel != "hentai":
                random.shuffle(seed_res)
            return seed_res

        return []

    def _get_channel_videos(self, channel, force_refresh=False, page=1):
        global _CHANNEL_CACHE
        cache_key = f"{channel}_p{page}"
        if not force_refresh and cache_key in _CHANNEL_CACHE and _CHANNEL_CACHE[cache_key]:
            return list(_CHANNEL_CACHE[cache_key])

        all_videos = []

        if channel == "vault":
            data = load_library()
            items = data.get("items", [])
            for it in items:
                if it.get("kind") != "folder" and it.get("target_url"):
                    all_videos.append({
                        "website": it.get("source", ""),
                        "target_url": it.get("target_url", ""),
                        "title": it.get("title", "Video"),
                        "thumbnail": it.get("thumbnail", ""),
                        "rating": int(it.get("rating", 0) or 0),
                    })
            random.shuffle(all_videos)
            all_videos.sort(key=lambda item: item.get("rating", 0), reverse=True)
        elif channel.startswith("custom_"):
            # Check in-memory temp stream first (Star Finder / builder_start streams)
            cs = self._get_temp_stream(channel)
            if cs is None:
                custom_streams = self._load_custom_streams()
                cs = next((s for s in custom_streams if s.get("id") == channel), None)
            if cs:
                q = cs.get("query")
                stars_list = cs.get("stars", [])
                pool_name = cs.get("pool", "top_tubes")
                spec_site = cs.get("specific_site", "")
                len_filter = cs.get("length", "any")
                sort_mode = cs.get("sort", "trending")

                if len_filter in ("movies", "long_movies", "full_movie"):
                    sites = [site for site, _url in CHANNEL_POOLS["movies"]]
                elif pool_name == "specific" and spec_site:
                    sites = [spec_site]
                elif pool_name in CHANNEL_POOLS:
                    sites = [s for s, _ in CHANNEL_POOLS[pool_name]]
                elif pool_name == "all":
                    sites = self._get_catalog_sites()
                else:
                    sites = ["spankbang", "eporner", "xhamster", "xnxx", "redtube", "tnaflix", "pornhub", "youporn", "hqporner"]

                available = [s for s in sites if os.path.exists(os.path.join(self.addon_path, "resources", "websites", f"{s}.py"))]
                selected = random.sample(available, min(8, len(available))) if available else ["spankbang"]
                
                if stars_list:
                    start_idx = ((page - 1) * 8) % len(stars_list)
                    page_stars = stars_list[start_idx : start_idx + 8]
                    if len(page_stars) < 8 and len(stars_list) >= 8:
                        page_stars.extend(stars_list[:8 - len(page_stars)])

                    if len_filter in ("movies", "long_movies", "full_movie"):
                        top_search_sites = [s for s, _url in CHANNEL_POOLS["movies"] if s in available]
                    elif pool_name == "trans":
                        top_search_sites = [s for s in ["pornhub", "xhamster", "tnaflix", "xnxx", "eporner", "shemalez", "xvideos"] if s in available]
                    else:
                        top_search_sites = [s for s in ["tnaflix", "eporner", "xnxx", "xhamster", "pornhub", "hqporner", "xvideos"] if s in available]

                    tasks = []
                    for st in page_stars:
                        site_count = 4 if len_filter in ("movies", "long_movies", "full_movie") else 2
                        if len_filter in ("movies", "long_movies", "full_movie") and "eporner" in top_search_sites:
                            remaining_sites = [site for site in top_search_sites if site != "eporner"]
                            sites_for_star = ["eporner"] + random.sample(
                                remaining_sites,
                                min(site_count - 1, len(remaining_sites)),
                            )
                        else:
                            sites_for_star = random.sample(top_search_sites, min(site_count, len(top_search_sites))) if top_search_sites else ["eporner"]
                        for site in sites_for_star:
                            tasks.append((site, st))

                    with ThreadPoolExecutor(max_workers=min(12, len(tasks))) as executor:
                        futures = [
                            executor.submit(self._harvest_website_videos, site, 4, None, st, page, len_filter)
                            for site, st in tasks
                        ]
                        for f in as_completed(futures):
                            all_videos.extend(f.result())
                else:
                    with ThreadPoolExecutor(max_workers=8) as executor:
                        futures = [executor.submit(self._harvest_website_videos, site, 8, None, q, page, len_filter) for site in selected]
                        for f in as_completed(futures):
                            all_videos.extend(f.result())

                # Filter by length
                if len_filter and len_filter != "any":
                    all_videos = [
                        v for v in all_videos
                        if matches_duration(
                            v.get("duration", ""),
                            len_filter,
                            v.get("title", ""),
                            source=v.get("website", ""),
                        )
                    ]

                # Sort mode
                if sort_mode == "random":
                    random.shuffle(all_videos)
                elif sort_mode == "newest":
                    pass # Scrapers return latest on search by default
                elif sort_mode == "top_rated":
                    all_videos.sort(key=lambda x: natural_sort_key(x.get("title", "")), reverse=True)
                else:
                    random.shuffle(all_videos)
        elif channel == "mega":
            all_sites = self._get_catalog_sites()
            available = [
                s for s in all_sites
                if os.path.exists(os.path.join(self.addon_path, "resources", "websites", f"{s}.py"))
            ]
            selected = random.sample(available, min(8, len(available)))
            with ThreadPoolExecutor(max_workers=8) as executor:
                futures = [executor.submit(self._harvest_website_videos, site, 6, None, None, page) for site in selected]
                for f in as_completed(futures):
                    all_videos.extend(f.result())
            random.shuffle(all_videos)
        elif channel in CHANNEL_POOLS:
            pool = CHANNEL_POOLS[channel]
            available = [
                (site, curl) for site, curl in pool
                if os.path.exists(os.path.join(self.addon_path, "resources", "websites", f"{site}.py"))
            ]
            if not available:
                available = [("spankbang", None), ("pornhub", None), ("xhamster", None)]
            if channel == "movies":
                preferred_names = ("eporner", "xhamster", "spankbang")
                preferred = [entry for entry in available if entry[0] in preferred_names]
                remaining = [entry for entry in available if entry[0] not in preferred_names]
                selected = preferred + random.sample(remaining, min(3, len(remaining)))
            else:
                selected = random.sample(available, min(6, len(available)))
            with ThreadPoolExecutor(max_workers=6) as executor:
                futures = [
                    executor.submit(
                        self._harvest_website_videos,
                        site,
                        8,
                        curl,
                        None,
                        page,
                        "movies" if channel == "movies" else "any",
                    )
                    for site, curl in selected
                ]
                for f in as_completed(futures):
                    all_videos.extend(f.result())

            if channel == "hentai":
                # Number identical titles from the same series
                title_counts = Counter(clean_title(v.get("title", "")) for v in all_videos)
                seen_counts = {}
                for v in all_videos:
                    ct = clean_title(v.get("title", ""))
                    if title_counts[ct] > 1:
                        seen_counts[ct] = seen_counts.get(ct, 0) + 1
                        orig = v.get("title", "")
                        v["title"] = f"{orig} - Episode {seen_counts[ct]}"

                # Deduplicate by target_url
                seen_urls = set()
                unique_videos = []
                for v in all_videos:
                    turl = v.get("target_url", "")
                    if turl not in seen_urls:
                        seen_urls.add(turl)
                        unique_videos.append(v)

                unique_videos.sort(key=lambda x: natural_sort_key(x.get("title", "")))
                all_videos = unique_videos
            else:
                random.shuffle(all_videos)
        else:
            # Fallback category lookup
            sites = self._get_catalog_sites(channel)
            available = [
                s for s in sites
                if os.path.exists(os.path.join(self.addon_path, "resources", "websites", f"{s}.py"))
            ]
            if not available:
                available = ["spankbang", "pornhub", "xhamster"]
            selected = random.sample(available, min(6, len(available)))
            with ThreadPoolExecutor(max_workers=6) as executor:
                futures = [executor.submit(self._harvest_website_videos, site, 8, None, None, page) for site in selected]
                for f in as_completed(futures):
                    all_videos.extend(f.result())
            random.shuffle(all_videos)

        _CHANNEL_CACHE[cache_key] = all_videos
        return all_videos

    def zap_channel(self, channel, force_refresh=False):
        """1-Click Instant Smart Stream Start: Starts Video 1 in 0.5s and populates playlist in background."""
        xbmcgui.Dialog().notification(
            _text(30860, "Smart Streams (Beta)"),
            "Playlist wird geladen... Bitte warten...",
            self.playlist_icon or self.icon,
            3500,
            sound=False,
        )

        # 1. Fast seed or full sorted channel
        if channel == "hentai":
            all_videos = self._get_channel_videos(channel, force_refresh=force_refresh)
            seed_videos = all_videos
        else:
            seed_videos = self._get_fast_seed(channel)
            if not seed_videos:
                seed_videos = self._get_channel_videos(channel, force_refresh=True)[:4]

        if not seed_videos:
            xbmcgui.Dialog().notification(
                _text(30860, "Smart Streams (Beta)"),
                _text(30872, "No videos found for this playlist"),
                xbmcgui.NOTIFICATION_WARNING,
                3000,
                sound=False,
            )
            if self.addon_handle >= 0:
                xbmcplugin.endOfDirectory(self.addon_handle, succeeded=False, cacheToDisc=False)
            return

        playlist = xbmc.PlayList(xbmc.PLAYLIST_VIDEO)
        playlist.clear()

        seed_urls = set()
        for item in seed_videos:
            target_url = item.get("target_url", "")
            if not target_url:
                continue
            seed_urls.add(target_url)
            label = item.get("title", "Video")
            source = item.get("website", "")
            display_label = f"[COLOR yellow][{source}][/COLOR] {label}" if (source and not label.startswith("[")) else label

            li = xbmcgui.ListItem(label=display_label, path=target_url)
            thumb = item.get("thumbnail") or self.icon
            li.setArt({"thumb": thumb, "icon": thumb, "fanart": self.fanart})
            li.setProperty("IsPlayable", "true")
            li.setInfo("video", {"title": display_label, "mediatype": "video"})
            playlist.add(target_url, li)

        # Release directory lock if called from menu
        if self.addon_handle >= 0:
            xbmcplugin.endOfDirectory(self.addon_handle, succeeded=True, cacheToDisc=False)

        # Set window property for background service
        window = xbmcgui.Window(10000)
        window.setProperty("AdultHideout.SmartChannel", channel)
        window.setProperty("AdultHideout.LastQueuedSize", str(len(seed_videos)))

        # Start instant playback
        xbmc.Player().play(playlist)
        xbmc.executebuiltin("PlayerControl(RepeatAll)" if channel == "vault" else "PlayerControl(RepeatOff)")

        # The persistent view service owns queue refills. Keeping a second
        # producer here caused duplicate harvests and oversized playlists.

    def show_channel(self, channel, force_refresh=False):
        """Displays the channel videos in standard Kodi directory browser."""
        videos = self._get_channel_videos(channel, force_refresh=force_refresh)
        
        if not videos:
            xbmcgui.Dialog().notification(
                _text(30860, "Smart Streams (Beta)"),
                _text(30872, "No videos found for this playlist"),
                xbmcgui.NOTIFICATION_WARNING,
                3000,
            )
            end_directory_with_view(self.addon_handle, self.addon, content_type="videos")
            return

        # 1. Start Auto-Play Header Item
        play_all_item = xbmcgui.ListItem(label="[COLOR lime][B]▶ {} ({})[/B][/COLOR]".format(
            _text(30876, "Start 24/7 Auto-Play"), len(videos)
        ))
        play_all_item.setArt({"thumb": self.playlist_icon, "icon": self.playlist_icon, "fanart": self.fanart})
        xbmcplugin.addDirectoryItem(
            self.addon_handle,
            self._url("zap_channel", channel=channel),
            play_all_item,
            False,
        )

        # 2. Refresh Button
        refresh_item = xbmcgui.ListItem(label="[COLOR cyan]↻ {}[/COLOR]".format(
            _text(30877, "Refresh Channel Videos")
        ))
        refresh_item.setArt({"thumb": self.icon, "icon": self.icon, "fanart": self.fanart})
        xbmcplugin.addDirectoryItem(
            self.addon_handle,
            self._url("show_channel", channel=channel, refresh=1),
            refresh_item,
            True,
        )

        # 3. Render all harvested videos
        for idx, item in enumerate(videos):
            target_url = item.get("target_url", "")
            title = item.get("title", "Video")
            source = item.get("website", "")
            thumb = item.get("thumbnail") or self.icon

            label = f"[COLOR yellow][{source}][/COLOR] {title}" if (source and not title.startswith("[")) else title
            li = xbmcgui.ListItem(label=label)
            li.setArt({"thumb": thumb, "icon": thumb, "fanart": self.fanart})
            li.setProperty("IsPlayable", "true")
            li.setInfo("video", {"title": label, "mediatype": "video"})

            context = [
                (
                    _text(30876, "Start 24/7 Auto-Play"),
                    f"RunPlugin({self._url('zap_channel', channel=channel, start_index=idx)})"
                ),
                (
                    _text(30706, "Save to Vault"),
                    build_save_command(self.plugin_url, target_url, title, source, thumb, self.fanart, "video")
                ),
            ]
            li.addContextMenuItems(context)
            xbmcplugin.addDirectoryItem(self.addon_handle, target_url, li, False)

        end_directory_with_view(self.addon_handle, self.addon, content_type="videos")

    def delete_custom_stream(self, channel_id):
        streams = self._load_custom_streams()
        new_streams = [s for s in streams if s.get("id") != channel_id]
        if len(new_streams) != len(streams):
            self._save_custom_streams(new_streams)
            xbmcgui.Dialog().notification(
                _text(30860, "Smart Streams (Beta)"),
                _text(30889, "Delete Custom Stream"),
                xbmcgui.NOTIFICATION_INFO,
                1500,
                sound=False,
            )
            xbmc.executebuiltin("Container.Refresh")

    def delete_all_custom_streams(self):
        streams = self._load_custom_streams()
        if not streams:
            return
        
        confirmed = xbmcgui.Dialog().yesno(
            _text(30860, "Smart Streams (Beta)"),
            _text(30891, "Delete all custom streams?"),
            yeslabel=_text(30890, "Delete All Custom Streams"),
            nolabel=_text(30704, "Cancel"),
        )
        if confirmed:
            self._save_custom_streams([])
            xbmcgui.Dialog().notification(
                _text(30860, "Smart Streams (Beta)"),
                _text(30890, "Delete All Custom Streams"),
                xbmcgui.NOTIFICATION_INFO,
                1500,
                sound=False,
            )
            xbmc.executebuiltin("Container.Refresh")

    def handle(self, action, params):
        if action in (None, "", "menu"):
            return self.show_menu()
        if action == "builder":
            return self.show_builder(params)
        if action == "builder_edit_query":
            return self.builder_edit_query(params)
        if action == "builder_edit_length":
            return self.builder_edit_length(params)
        if action == "builder_edit_pool":
            return self.builder_edit_pool(params)
        if action == "builder_edit_sort":
            return self.builder_edit_sort(params)
        if action == "builder_edit_name":
            return self.builder_edit_name(params)
        if action == "builder_start":
            temp_id = f"custom_temp_{int(time.time())}"
            self._set_temp_stream({
                "id": temp_id,
                "name": params.get("name") or params.get("query") or "Custom Stream",
                "query": params.get("query", ""),
                "length": params.get("length", "any"),
                "pool": params.get("pool", "top_tubes"),
                "specific_site": params.get("specific_site", ""),
                "sort": params.get("sort", "trending"),
            })
            return self.zap_channel(temp_id)
        if action == "custom_zap":
            query = params.get("query", "")
            stars_param = params.get("stars", "")
            stars_list = [s.strip() for s in stars_param.split(",") if s.strip()] if stars_param else []
            temp_id = f"custom_temp_{int(time.time() * 1000)}"
            pool = params.get("pool", "top_tubes")
            len_filter = params.get("length", "any")

            self._set_temp_stream({
                "id": temp_id,
                "name": f"{query} ({len(stars_list)} Stars)" if stars_list else (query or "Custom Stream"),
                "query": query,
                "stars": stars_list,
                "length": len_filter,
                "pool": pool,
                "specific_site": params.get("specific_site", ""),
                "sort": params.get("sort", "trending"),
            })
            return self.zap_channel(temp_id, force_refresh=True)
        if action == "builder_save":
            return self.builder_save(params)
        if action == "zap_channel":
            return self.zap_channel(
                params.get("channel", "trending"),
                force_refresh=params.get("refresh") == "1",
            )
        if action == "show_channel":
            return self.show_channel(
                params.get("channel", "trending"),
                force_refresh=params.get("refresh") == "1",
            )
        if action == "start_auto_play":
            return self.zap_channel(
                params.get("channel", "trending"),
                force_refresh=params.get("refresh") == "1",
            )
        if action == "delete_custom_stream":
            return self.delete_custom_stream(params.get("channel"))
        if action == "delete_all_custom_streams":
            return self.delete_all_custom_streams()
        return self.show_menu()
