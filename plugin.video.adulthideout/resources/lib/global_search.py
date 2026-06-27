#!/usr/bin/env python
# -*- coding: utf-8 -*-

import json
import os
import time
import urllib.parse

import xbmc
import xbmcaddon
import xbmcgui
import xbmcplugin
import xbmcvfs

from resources.lib.view_utils import end_directory_with_view


DEFAULT_SOURCES = [
    "eporner",
    "pornhub",
    "xvideos",
    "xnxx",
    "spankbang",
    "tnaflix",
    "hclips",
    "txxx",
    "porn4fans",
    "yespornvip",
]

BROAD_RELIABLE_SOURCES = [
    "3movs", "allowflash", "area51", "ashemaletube", "avjoy",
    "blackporn24", "blowjobspro", "boundhub", "bravoporn", "camgirlfap",
    "chaturbate", "cumlouder", "daftporn", "darknessporn", "drtuber",
    "efukt", "empflix", "epawg", "eporner", "familypornhd",
    "fpo", "freeomovie", "fullporner", "fullxcinema", "goporn",
    "hclips", "hdzog", "heavy_r", "heavyfetish", "hentaigasm",
    "hqporner", "hqpornero", "hypnotube", "javhdporn", "jizzberry",
    "lesbianporn8", "milfporn8", "missav", "mylust", "myporntape",
    "noodlemagazine", "notfans", "nudez", "okxxx", "perfectgirls",
    "pervclips", "pervertium", "pimpbunny", "porcore", "porn7",
    "porndig", "porndoe", "pornflip", "pornhat", "pornhd3x",
    "pornheed", "pornhoarder", "pornhub", "pornmedium", "pornobae",
    "pornone", "pornslash", "porntrex", "pornwhite", "pornzog",
    "premiumporn", "punishbang", "punishworld", "pussyspace",
    "rapelust", "redtube", "rule34video", "sextb", "shameless",
    "shemalez", "shesfreaky", "shooshtime", "spankbang", "speedporn",
    "sunporno", "superporn", "sxyprn", "tgtsporn", "thepornbang",
    "theyarehuge", "thisvid", "thumbzilla", "tnaflix", "trendyporn",
    "tube8", "tubepornclassic", "tubev", "txxx", "upornia",
    "veporn", "vikiporn", "vjav", "voyeurhit", "watchporn",
    "whereismyporn", "wowxxx", "xbabe", "xcafe", "xhamster",
    "xmoviesforyou", "xnxx", "xopenload", "xtapes", "xvideos",
    "xxthots", "xxxfiles", "xxxtube", "yespornvip", "youjizz",
    "youporn", "yourlesbians", "zbporn",
]

SOURCE_PRESETS = [
    ("balanced", "Balanced Top Sites", DEFAULT_SOURCES),
    ("broad_reliable", "Broad Reliable Sites", BROAD_RELIABLE_SOURCES),
    ("playlist_safe", "Playlist Safe", [
        "3movs", "eporner", "pornhub", "xvideos", "xnxx", "spankbang",
        "tnaflix", "hclips", "txxx", "redtube", "tube8", "youporn",
    ]),
    ("straight", "Straight / Mainstream", [
        "eporner", "pornhub", "xvideos", "xnxx", "spankbang", "tnaflix",
        "hclips", "txxx", "tube8", "redtube", "youporn", "youjizz",
    ]),
    ("big_tubes", "Big Tube Sites", [
        "pornhub", "xvideos", "xnxx", "redtube", "youporn", "youjizz",
        "tube8", "tnaflix", "empflix", "hclips", "spankbang", "thumbzilla",
    ]),
    ("kvs_tubes", "KVS Tube Sites", [
        "porn4fans", "yespornvip", "pornmedium", "hqpornero", "tgtsporn",
        "porn300", "porn7", "pornhat", "porndoe", "pornzog",
    ]),
    ("amateur", "Amateur / Homemade", [
        "erome", "motherless", "xhamster", "spankbang", "xnxx", "xvideos",
        "thisvid", "voyeurhit", "watchporn", "upornia",
    ]),
    ("full_movies", "Full Movies / Longform", [
        "fullxcinema", "freeomovie", "familypornhd", "pornobae",
        "premiumporn", "javhdporn", "javsubbed", "missav",
    ]),
    ("jav_asian", "JAV / Asian", [
        "javhdporn", "javsubbed", "missav", "vjav", "pornmz",
        "tubepornclassic", "xvideos", "xhamster",
    ]),
    ("trans", "Trans / Shemale", [
        "ashemaletube", "shemalez", "txxx", "xnxx", "xhamster", "spankbang",
        "pornslash", "erome", "rule34video",
    ]),
    ("gay", "Gay", [
        "eporner", "xhamster", "xnxx", "spankbang", "txxx", "pornslash",
        "erome", "rule34video",
    ]),
    ("hentai_futa", "Hentai / Futa / Rule34", [
        "rule34video", "hanime", "hentaidude", "hentaiocean", "hentaigasm",
        "erome",
    ]),
    ("fetish", "Fetish / BDSM", [
        "heavy_r", "heavyfetish", "boundhub", "punishworld", "punishbang",
        "efukt", "pervertium", "pervclips", "spankbang",
    ]),
    ("cams", "Cam / Clips", [
        "chaturbate", "camgirlfap", "archivebate", "camcaps", "erome",
        "motherless", "thisvid",
    ]),
    ("new_1012", "1.0.12 New Sites", [
        "allowflash", "notfans", "wowxxx", "xxthots", "sextb", "porn4fans",
        "yespornvip", "tgtsporn", "pornmedium", "hqpornero",
    ]),
]

PROFILE_OVERRIDES = {
    "trans": {
        "ashemaletube_pf_gender": "1",
        "erome_content_type": "3",
        "pornslash_content_type": "2",
        "rule34video_content_type": "0",
        "spankbang_orientation": "2",
        "txxx_content_type": "2",
        "xhamster_category": "Shemale",
        "xnxx_content_type": "2",
    },
    "gay": {
        "eporner_gay_filter": "1",
        "erome_content_type": "2",
        "pornslash_content_type": "1",
        "rule34video_content_type": "2",
        "spankbang_orientation": "1",
        "txxx_content_type": "1",
        "xhamster_category": "Gay",
        "xnxx_content_type": "1",
    },
    "hentai_futa": {
        "erome_content_type": "4",
        "rule34video_content_type": "3",
    },
}

RESULTS_PER_PAGE = 40
PLAYLIST_SAFE_CACHE_VERSION = "playlist-safe-v6-simple"
UNSTABLE_PLAYLIST_SOURCES = {
    "analdin",
    "anysex",
    "bananamovies",
    "bdsmstreak",
    "bigassporn",
    "bigtitslust",
    "camcaps",
}


class GlobalSearch:
    def __init__(self, addon_handle, addon=None, loader=None, logger=None):
        self.addon_handle = addon_handle
        self.addon = addon or xbmcaddon.Addon()
        self.loader = loader
        self.logger = logger or (lambda msg, level=xbmc.LOGINFO: xbmc.log("[AdultHideout][GlobalSearch] {}".format(msg), level))
        self.addon_path = self.addon.getAddonInfo("path")
        self.profile_path = xbmcvfs.translatePath(self.addon.getAddonInfo("profile"))
        self.websites_dir = os.path.join(self.addon_path, "resources", "websites")
        self.logos_dir = os.path.join(self.addon_path, "resources", "logos")
        self.default_icon = os.path.join(self.logos_dir, "icon.png")
        self.search_icon = os.path.join(self.logos_dir, "search.png")
        self.fanart = os.path.join(self.logos_dir, "fanart.jpg")

    def _state_path(self):
        if not xbmcvfs.exists(self.profile_path):
            xbmcvfs.mkdirs(self.profile_path)
        return os.path.join(self.profile_path, "global_search.json")

    def _load_state(self):
        try:
            with open(self._state_path(), "r") as handle:
                state = json.load(handle)
                if isinstance(state, dict):
                    return state
        except Exception:
            pass
        return {}

    def _save_state(self, state):
        try:
            with open(self._state_path(), "w") as handle:
                json.dump(state, handle)
        except Exception as exc:
            self.logger("Could not save global search state: {}".format(exc), xbmc.LOGWARNING)

    def _history(self):
        history = self._load_state().get("history")
        return history if isinstance(history, list) else []

    def _custom_presets(self):
        presets = self._load_state().get("custom_presets")
        return presets if isinstance(presets, dict) else {}

    def _remember_query(self, query):
        state = self._load_state()
        history = state.get("history")
        if not isinstance(history, list):
            history = []
        if query in history:
            history.remove(query)
        history.insert(0, query)
        state["history"] = history[:20]
        state["last_query"] = query
        self._save_state(state)

    def _cache_key(self, query, search_mode="selected"):
        signature = "|".join(
            [PLAYLIST_SAFE_CACHE_VERSION, search_mode, self._selected_profile()] + self._selected_sources()
        )
        return "{}::{}".format(query.strip().lower(), signature)

    def _legacy_cache_prefix(self, query):
        return "{}::".format(query.strip().lower())

    def _filter_results(self, results):
        if not isinstance(results, list):
            return []
        return [
            result for result in results
            if isinstance(result, dict) and result.get("source") not in UNSTABLE_PLAYLIST_SOURCES
        ]

    def _cached_results(self, query, search_mode="selected"):
        cache = self._load_state().get("result_cache")
        if not isinstance(cache, dict):
            return None
        entry = cache.get(self._cache_key(query, search_mode))
        if not isinstance(entry, dict):
            prefix = self._legacy_cache_prefix(query)
            matches = [
                value for key, value in cache.items()
                if key.startswith(prefix) and isinstance(value, dict)
            ]
            if matches:
                matches.sort(key=lambda item: item.get("saved_at", 0), reverse=True)
                entry = matches[0]
        if not isinstance(entry, dict):
            return None
        results = entry.get("results")
        return self._filter_results(results) if isinstance(results, list) else None

    def _save_results(self, query, results, search_mode="selected", sources=None):
        state = self._load_state()
        cache = state.get("result_cache")
        if not isinstance(cache, dict):
            cache = {}
        cache[self._cache_key(query, search_mode)] = {
            "query": query,
            "search_mode": search_mode,
            "profile": self._selected_profile(),
            "sources": sources or self._selected_sources(),
            "saved_at": int(time.time()),
            "results": results,
        }
        state["result_cache"] = cache
        self._save_state(state)

    def _mark_refresh_once(self, query):
        state = self._load_state()
        state["refresh_once"] = query.strip().lower()
        self._save_state(state)

    def _consume_refresh_once(self, query):
        state = self._load_state()
        expected = query.strip().lower()
        if state.get("refresh_once") != expected:
            return False
        state.pop("refresh_once", None)
        self._save_state(state)
        return True

    def _setting_id(self, name):
        return "show_{}".format(name.lower().replace("-", "").replace("_", ""))

    def _available_sources(self):
        sources = []
        try:
            filenames = sorted(os.listdir(self.websites_dir))
        except Exception:
            filenames = []
        for filename in filenames:
            if not filename.endswith(".py") or filename == "__init__.py":
                continue
            name = filename[:-3]
            if name in UNSTABLE_PLAYLIST_SOURCES:
                continue
            if self.addon.getSetting(self._setting_id(name)) == "false":
                continue
            sources.append(name)
        return sources

    def _selected_sources(self):
        available = self._available_sources()
        state = self._load_state()
        saved = state.get("sources")
        if isinstance(saved, list):
            selected = [name for name in saved if name in available]
            if selected:
                return selected
        selected = [name for name in DEFAULT_SOURCES if name in available]
        return selected or available[:8]

    def _selected_profile(self):
        profile = self._load_state().get("profile")
        known = [preset[0] for preset in SOURCE_PRESETS]
        if profile == "custom":
            return "custom"
        return profile if profile in known else "balanced"

    def _source_label(self, name):
        return name.replace("_", " ").replace("-", " ").title()

    def _source_icon(self, name):
        for filename in ("{}.png".format(name), "{}.png".format(name.replace("_", "-"))):
            path = os.path.join(self.logos_dir, filename)
            if xbmcvfs.exists(path):
                return path
        return self.default_icon

    def _search_mode_label(self, search_mode):
        if search_mode == "deep":
            return "Search All Sites"
        return "Global Search"

    def _sources_for_search(self, query, search_mode):
        available = self._available_sources()
        selected = self._selected_sources()
        if search_mode == "deep":
            return available
        return selected

    def _add_dir(self, label, action, icon=None, **params):
        query = {
            "mode": "20",
            "website": "global_search",
            "action": action,
        }
        query.update(params)
        url = "{}?{}".format(sys_argv0(), urllib.parse.urlencode(query))
        item = xbmcgui.ListItem(label)
        item.setArt({"thumb": icon or self.search_icon, "icon": icon or self.search_icon, "fanart": self.fanart})
        xbmcplugin.addDirectoryItem(self.addon_handle, url, item, True)

    def show_menu(self):
        selected = self._selected_sources()
        self._add_dir("[COLOR yellow]Search[/COLOR] [COLOR grey]{} sources[/COLOR]".format(len(selected)), "new_search", search_mode="selected")
        self._add_dir("Source Presets [COLOR yellow]{}[/COLOR]".format(self._preset_label(self._selected_profile())), "show_presets", self.search_icon)
        self._add_dir("Choose Sources [COLOR yellow]{} selected[/COLOR]".format(len(selected)), "choose_sources", self.search_icon)
        self._add_dir("Search All Sites [COLOR yellow]slow[/COLOR]", "new_search", self.search_icon, search_mode="deep")
        self._add_dir("Show Selected Sources", "show_sources", self.search_icon)
        history = self._history()
        if history:
            self._add_dir("[COLOR red]Clear Search History[/COLOR]", "clear_history", self.search_icon)
        for query in history:
            context_url = "{}?mode=20&website=global_search&action=edit_search&query={}".format(
                sys_argv0(), urllib.parse.quote_plus(query)
            )
            label = "[COLOR yellow]{}[/COLOR]".format(query)
            item = xbmcgui.ListItem(label)
            item.setArt({"thumb": self.search_icon, "icon": self.search_icon, "fanart": self.fanart})
            item.addContextMenuItems([("Edit", "RunPlugin({})".format(context_url))])
            url = "{}?mode=21&website=global_search&query={}&search_mode=selected".format(sys_argv0(), urllib.parse.quote_plus(query))
            xbmcplugin.addDirectoryItem(self.addon_handle, url, item, True)
        end_directory_with_view(self.addon_handle, self.addon)

    def clear_history(self):
        state = self._load_state()
        state["history"] = []
        state["result_cache"] = {}
        self._save_state(state)
        return self.show_menu()

    def edit_search(self, query, search_mode="selected"):
        keyboard = xbmc.Keyboard(query or "", "[COLOR yellow]Edit Global Search[/COLOR]")
        keyboard.doModal()
        if not keyboard.isConfirmed():
            return self.show_menu()
        new_query = keyboard.getText().strip()
        if not new_query:
            return self.show_menu()
        self._remember_query(new_query)
        self._open_results(new_query, refresh=True, search_mode=search_mode)

    def refresh_search(self, query, page=1, search_mode="selected"):
        query = (query or "").strip()
        if not query:
            return self.show_menu()
        self._open_results(query, refresh=True, page=page, search_mode=search_mode)

    def _preset_label(self, profile):
        if profile == "custom":
            label = self._load_state().get("custom_label")
            return label if label else "Custom"
        for key, label, _ in SOURCE_PRESETS:
            if key == profile:
                return label
        return "Balanced Top Sites"

    def show_presets(self):
        current = self._selected_profile()
        available = set(self._available_sources())
        for key, label, sources in SOURCE_PRESETS:
            valid = [source for source in sources if source in available]
            marker = "[COLOR lime][x][/COLOR] " if key == current else "[ ] "
            self._add_dir("{}{} [COLOR yellow]{} sources[/COLOR]".format(marker, label, len(valid)), "apply_preset", self.search_icon, profile=key)
        self._add_dir("[COLOR cyan]Combine Presets[/COLOR]", "combine_presets", self.search_icon)
        self._add_dir("[COLOR cyan]Save Current Selection as Custom Preset[/COLOR]", "save_custom_preset", self.search_icon)
        custom_presets = self._custom_presets()
        if custom_presets:
            self._add_dir("Custom Presets [COLOR yellow]{}[/COLOR]".format(len(custom_presets)), "show_custom_presets", self.search_icon)
        end_directory_with_view(self.addon_handle, self.addon)

    def apply_preset(self, profile):
        available = set(self._available_sources())
        for key, _, sources in SOURCE_PRESETS:
            if key == profile:
                chosen = [source for source in sources if source in available]
                if chosen:
                    state = self._load_state()
                    state["profile"] = key
                    state["sources"] = chosen
                    state.pop("custom_label", None)
                    self._save_state(state)
                break
        return self.show_menu()

    def combine_presets(self):
        available = set(self._available_sources())
        usable = []
        for key, label, sources in SOURCE_PRESETS:
            valid = [source for source in sources if source in available]
            if valid:
                usable.append((key, label, valid))
        if not usable:
            xbmcgui.Dialog().notification("Global Search", "No presets available", xbmcgui.NOTIFICATION_WARNING, 3000)
            return self.show_presets()

        labels = ["{} [COLOR yellow]{} sources[/COLOR]".format(label, len(sources)) for _, label, sources in usable]
        dialog = xbmcgui.Dialog()
        if hasattr(dialog, "multiselect"):
            indexes = dialog.multiselect("Combine Presets", labels)
        else:
            single = dialog.select("Combine Presets", labels)
            indexes = [] if single == -1 else [single]
        if indexes is None or indexes == -1:
            return self.show_presets()

        combined = []
        names = []
        for idx in indexes:
            if 0 <= idx < len(usable):
                _, label, sources = usable[idx]
                names.append(label)
                for source in sources:
                    if source not in combined:
                        combined.append(source)
        if not combined:
            xbmcgui.Dialog().notification("Global Search", "No sources selected", xbmcgui.NOTIFICATION_WARNING, 3000)
            return self.show_presets()

        state = self._load_state()
        state["sources"] = combined
        state["profile"] = "custom"
        state["custom_label"] = " + ".join(names[:3])
        if len(names) > 3:
            state["custom_label"] += " +{}".format(len(names) - 3)
        self._save_state(state)
        xbmcgui.Dialog().notification(
            "Global Search",
            "{} sources combined".format(len(combined)),
            xbmcgui.NOTIFICATION_INFO,
            3000,
        )
        return self.show_menu()

    def save_custom_preset(self):
        selected = self._selected_sources()
        if not selected:
            xbmcgui.Dialog().notification("Global Search", "No sources selected", xbmcgui.NOTIFICATION_WARNING, 3000)
            return self.show_presets()

        keyboard = xbmc.Keyboard("", "[COLOR yellow]Custom Preset Name[/COLOR]")
        keyboard.doModal()
        if not keyboard.isConfirmed():
            return self.show_presets()
        label = keyboard.getText().strip()
        if not label:
            return self.show_presets()

        preset_id = "custom_{}".format(int(time.time()))
        state = self._load_state()
        presets = state.get("custom_presets")
        if not isinstance(presets, dict):
            presets = {}
        presets[preset_id] = {
            "label": label,
            "sources": selected,
            "saved_at": int(time.time()),
        }
        state["custom_presets"] = presets
        state["profile"] = "custom"
        state["custom_label"] = label
        state["sources"] = selected
        self._save_state(state)
        xbmcgui.Dialog().notification("Global Search", "Preset saved", xbmcgui.NOTIFICATION_INFO, 3000)
        return self.show_presets()

    def show_custom_presets(self):
        available = set(self._available_sources())
        presets = self._custom_presets()
        for preset_id, preset in sorted(presets.items(), key=lambda item: item[1].get("label", "").lower()):
            sources = [source for source in preset.get("sources", []) if source in available]
            label = preset.get("label") or preset_id
            item_label = "{} [COLOR yellow]{} sources[/COLOR]".format(label, len(sources))
            self._add_dir(item_label, "apply_custom_preset", self.search_icon, preset_id=preset_id)
        self._add_dir("[COLOR red]Delete Custom Preset[/COLOR]", "delete_custom_preset", self.search_icon)
        end_directory_with_view(self.addon_handle, self.addon)

    def apply_custom_preset(self, preset_id):
        available = set(self._available_sources())
        preset = self._custom_presets().get(preset_id)
        if not isinstance(preset, dict):
            return self.show_presets()
        chosen = [source for source in preset.get("sources", []) if source in available]
        if not chosen:
            xbmcgui.Dialog().notification("Global Search", "Preset has no available sources", xbmcgui.NOTIFICATION_WARNING, 3000)
            return self.show_custom_presets()
        state = self._load_state()
        state["profile"] = "custom"
        state["custom_label"] = preset.get("label") or "Custom"
        state["sources"] = chosen
        self._save_state(state)
        return self.show_menu()

    def delete_custom_preset(self):
        presets = self._custom_presets()
        if not presets:
            return self.show_presets()
        ordered = sorted(presets.items(), key=lambda item: item[1].get("label", "").lower())
        labels = [preset.get("label") or preset_id for preset_id, preset in ordered]
        idx = xbmcgui.Dialog().select("Delete Custom Preset", labels)
        if idx == -1:
            return self.show_custom_presets()
        preset_id, preset = ordered[idx]
        if not xbmcgui.Dialog().yesno("Delete Custom Preset", preset.get("label") or preset_id):
            return self.show_custom_presets()
        state = self._load_state()
        custom_presets = state.get("custom_presets")
        if isinstance(custom_presets, dict):
            custom_presets.pop(preset_id, None)
        self._save_state(state)
        return self.show_custom_presets()

    def choose_sources(self):
        available = self._available_sources()
        if not available:
            xbmcgui.Dialog().notification("Global Search", "No sources available", xbmcgui.NOTIFICATION_WARNING, 3000)
            return self.show_menu()

        selected_order = self._selected_sources()
        selected = set(selected_order)
        ordered = selected_order + [name for name in available if name not in selected]
        labels = []
        for name in ordered:
            marker = "[x] " if name in selected else "[ ] "
            labels.append("{}{}".format(marker, self._source_label(name)))
        preselect = [idx for idx, name in enumerate(ordered) if name in selected]
        dialog = xbmcgui.Dialog()
        if hasattr(dialog, "multiselect"):
            indexes = dialog.multiselect("Global Search Sources", labels, preselect=preselect)
        else:
            single = dialog.select("Global Search Source", labels, preselect=preselect[0] if preselect else 0)
            indexes = [] if single == -1 else [single]
        if indexes is None or indexes == -1:
            return self.show_menu()
        chosen = [ordered[idx] for idx in indexes if 0 <= idx < len(ordered)]
        if not chosen:
            xbmcgui.Dialog().notification("Global Search", "No sources selected", xbmcgui.NOTIFICATION_WARNING, 3000)
            return self.show_menu()
        state = self._load_state()
        state["sources"] = chosen
        state["profile"] = "custom"
        state.pop("custom_label", None)
        self._save_state(state)
        return self.show_menu()

    def select_all_sources(self):
        available = self._available_sources()
        if not available:
            xbmcgui.Dialog().notification("Global Search", "No sources available", xbmcgui.NOTIFICATION_WARNING, 3000)
            return self.show_menu()
        state = self._load_state()
        state["sources"] = available
        state["profile"] = "custom"
        state.pop("custom_label", None)
        self._save_state(state)
        xbmcgui.Dialog().notification(
            "Global Search",
            "{} sources selected".format(len(available)),
            xbmcgui.NOTIFICATION_INFO,
            3000,
        )
        return self.show_menu()

    def show_sources(self):
        for name in self._selected_sources():
            item = xbmcgui.ListItem(self._source_label(name))
            icon = self._source_icon(name)
            item.setArt({"thumb": icon, "icon": icon, "fanart": self.fanart})
            xbmcplugin.addDirectoryItem(self.addon_handle, "", item, False)
        end_directory_with_view(self.addon_handle, self.addon)

    def new_search(self, search_mode="selected"):
        keyboard = xbmc.Keyboard("", "[COLOR yellow]{}[/COLOR]".format(self._search_mode_label(search_mode)))
        keyboard.doModal()
        if not keyboard.isConfirmed():
            return self.show_menu()
        query = keyboard.getText().strip()
        if not query:
            return self.show_menu()
        self._remember_query(query)
        self._open_results(query, refresh=True, search_mode=search_mode)

    def _open_results(self, query, refresh=False, page=1, search_mode="selected"):
        if refresh:
            self._mark_refresh_once(query)
        target = "{}?mode=21&website=global_search&query={}&page={}&search_mode={}".format(
            sys_argv0(), urllib.parse.quote_plus(query), int(page), urllib.parse.quote_plus(search_mode)
        )
        xbmcplugin.endOfDirectory(self.addon_handle, succeeded=True, updateListing=False, cacheToDisc=False)
        xbmc.sleep(100)
        xbmc.executebuiltin("Container.Update({},replace)".format(target))

    def _capture_site_search(self, site, query):
        captured = []
        original_add = xbmcplugin.addDirectoryItem
        original_end = xbmcplugin.endOfDirectory

        def capture_add(handle, url, listitem, isFolder=False, totalItems=0):
            captured.append((url, listitem, isFolder))
            return True

        def capture_end(handle, succeeded=True, updateListing=False, cacheToDisc=True):
            return None

        xbmcplugin.addDirectoryItem = capture_add
        xbmcplugin.endOfDirectory = capture_end
        try:
            site.search(query)
        finally:
            xbmcplugin.addDirectoryItem = original_add
            xbmcplugin.endOfDirectory = original_end
        return captured

    def _apply_profile_overrides(self, profile):
        overrides = PROFILE_OVERRIDES.get(profile, {})
        previous = {}
        for setting_id, value in overrides.items():
            try:
                previous[setting_id] = self.addon.getSetting(setting_id)
                self.addon.setSetting(setting_id, value)
            except Exception:
                pass
        return previous

    def _restore_profile_overrides(self, previous):
        for setting_id, value in previous.items():
            try:
                self.addon.setSetting(setting_id, value)
            except Exception:
                pass

    def _clone_video_item(self, source_name, url, source_item):
        source_label = self._source_label(source_name)
        original_label = source_item.getLabel() if source_item else ""
        label = "[COLOR yellow][{}][/COLOR] {}".format(source_label, original_label or "Video")
        item = xbmcgui.ListItem(label)
        if source_item:
            item.setArt({
                "thumb": source_item.getArt("thumb"),
                "icon": source_item.getArt("icon") or source_item.getArt("thumb"),
                "fanart": source_item.getArt("fanart") or self.fanart,
            })
            item.setProperty("IsPlayable", source_item.getProperty("IsPlayable") or "true")
        else:
            item.setArt({"thumb": self._source_icon(source_name), "icon": self._source_icon(source_name), "fanart": self.fanart})
            item.setProperty("IsPlayable", "true")
        return item

    def _result_from_item(self, source_name, url, source_item, is_folder=False):
        art = {}
        if source_item:
            art = {
                "thumb": source_item.getArt("thumb"),
                "icon": source_item.getArt("icon") or source_item.getArt("thumb"),
                "fanart": source_item.getArt("fanart") or self.fanart,
            }
        return {
            "source": source_name,
            "url": url,
            "label": source_item.getLabel() if source_item else "Video",
            "art": art,
            "is_folder": bool(is_folder),
        }

    def _is_video_result(self, url, source_item, is_folder):
        if is_folder:
            return False
        if not url:
            return False
        if "mode=4" in url:
            return True
        try:
            return bool(source_item and source_item.getProperty("IsPlayable") == "true")
        except Exception:
            return False

    def _add_cached_result(self, result):
        source = result.get("source", "")
        label = "[COLOR yellow][{}][/COLOR] {}".format(self._source_label(source), result.get("label") or "Video")
        item = xbmcgui.ListItem(label)
        art = result.get("art") if isinstance(result.get("art"), dict) else {}
        item.setArt({
            "thumb": art.get("thumb") or self._source_icon(source),
            "icon": art.get("icon") or art.get("thumb") or self._source_icon(source),
            "fanart": art.get("fanart") or self.fanart,
        })
        is_folder = bool(result.get("is_folder"))
        if not is_folder:
            item.setProperty("IsPlayable", "true")
        xbmcplugin.addDirectoryItem(self.addon_handle, result.get("url", ""), item, is_folder)

    def _add_refresh_item(self, query, page=1, search_mode="selected"):
        url = "{}?mode=20&website=global_search&action=refresh_search&query={}&page={}&search_mode={}".format(
            sys_argv0(), urllib.parse.quote_plus(query), int(page), urllib.parse.quote_plus(search_mode)
        )
        item = xbmcgui.ListItem("[COLOR cyan]Refresh {}[/COLOR]".format(self._search_mode_label(search_mode)))
        item.setArt({"thumb": self.search_icon, "icon": self.search_icon, "fanart": self.fanart})
        xbmcplugin.addDirectoryItem(self.addon_handle, url, item, True)

    def _add_page_item(self, query, page, label, search_mode="selected"):
        url = "{}?mode=21&website=global_search&query={}&page={}&search_mode={}".format(
            sys_argv0(), urllib.parse.quote_plus(query), int(page), urllib.parse.quote_plus(search_mode)
        )
        item = xbmcgui.ListItem(label)
        item.setArt({"thumb": self.search_icon, "icon": self.search_icon, "fanart": self.fanart})
        xbmcplugin.addDirectoryItem(self.addon_handle, url, item, True)

    def _render_results_page(self, query, results, page=1, search_mode="selected"):
        try:
            page = max(1, int(page))
        except Exception:
            page = 1
        total = len(results)
        pages = max(1, int((total + RESULTS_PER_PAGE - 1) / RESULTS_PER_PAGE))
        if page > pages:
            page = pages
        start = (page - 1) * RESULTS_PER_PAGE
        end = start + RESULTS_PER_PAGE

        self._add_refresh_item(query, page, search_mode=search_mode)
        if page > 1:
            self._add_page_item(query, page - 1, "[COLOR cyan]Previous Page[/COLOR] ({}/{})".format(page - 1, pages), search_mode=search_mode)
        for result in results[start:end]:
            self._add_cached_result(result)
        if end < total:
            self._add_page_item(query, page + 1, "[COLOR cyan]Next Page[/COLOR] ({}/{})".format(page + 1, pages), search_mode=search_mode)
        end_directory_with_view(self.addon_handle, self.addon)

    def show_cached_results(self, query, page=1, search_mode="selected"):
        results = self._cached_results(query, search_mode=search_mode)
        if results is None:
            return False
        self._render_results_page(query, results, page, search_mode=search_mode)
        return True

    def run(self, query, refresh=False, page=1, search_mode="selected"):
        query = (query or "").strip()
        if not query:
            return self.show_menu()
        self._remember_query(query)
        refresh = bool(refresh) or self._consume_refresh_once(query)
        if not refresh and self.show_cached_results(query, page, search_mode=search_mode):
            return
        sources = self._sources_for_search(query, search_mode)
        profile = self._selected_profile()
        max_results_per_site = 12
        self.logger("Global search mode '{}' profile '{}' using sources: {}".format(search_mode, profile, ", ".join(sources)))
        progress = xbmcgui.DialogProgress()
        progress.create(self._search_mode_label(search_mode), "Searching {} sources".format(len(sources)))
        added = 0
        failed = []
        cache_results = []
        started = time.time()
        try:
            for index, source in enumerate(sources):
                if progress.iscanceled():
                    break
                percent = int((index / float(max(1, len(sources)))) * 100)
                progress.update(percent, "Searching {}".format(self._source_label(source)))
                previous_settings = self._apply_profile_overrides(profile)
                try:
                    site = self.loader(source) if self.loader else None
                    if not site:
                        failed.append(source)
                        continue
                    captured = self._capture_site_search(site, query)
                except Exception as exc:
                    self.logger("{} failed: {}".format(source, exc), xbmc.LOGWARNING)
                    failed.append(source)
                    continue
                finally:
                    self._restore_profile_overrides(previous_settings)
                site_added = 0
                non_video_skipped = 0
                for url, listitem, is_folder in captured:
                    if not self._is_video_result(url, listitem, is_folder):
                        non_video_skipped += 1
                        continue
                    cache_results.append(self._result_from_item(source, url, listitem, is_folder=False))
                    added += 1
                    site_added += 1
                    if site_added >= max_results_per_site:
                        break
                self.logger("Global search source '{}' captured {} video items ({} non-video entries skipped)".format(
                    source, site_added, non_video_skipped
                ))
        finally:
            progress.close()
        if added == 0:
            xbmcgui.Dialog().notification("Global Search", "No results found", xbmcgui.NOTIFICATION_INFO, 3000)
        if failed:
            self.logger("Skipped/failed sources: {}".format(", ".join(failed)), xbmc.LOGWARNING)
        self._save_results(query, cache_results, search_mode=search_mode, sources=sources)
        self.logger("Global search '{}' ({}) returned {} results in {:.1f}s".format(query, search_mode, added, time.time() - started))
        self._render_results_page(query, cache_results, page, search_mode=search_mode)


def sys_argv0():
    import sys
    return sys.argv[0]
