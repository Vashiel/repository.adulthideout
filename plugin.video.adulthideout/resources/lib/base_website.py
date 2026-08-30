#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging
import sys
import os
import gzip
import json
import re
import urllib.parse
import xbmc
import xbmcaddon
import xbmcgui
import xbmcplugin
import xbmcvfs
import html
from resources.lib.view_utils import end_directory_with_view

_ICON_PATH_CACHE = {}
_NON_PERFORMER_KEYWORDS = {
    "categories", "search", "top rated", "trending", "channels", "models", "pornstars",
    "tags", "filter", "sort by", "next page", "prev page", "all", "latest", "most viewed",
    "popular", "hd", "4k", "full movies", "smart streams", "vault", "history", "downloads",
    "collections", "settings", "home", "back", "next page >>", "<< prev page", "play all",
}
_PERFORMERS_CACHE = None

def _get_performer_metadata(name):
    global _PERFORMERS_CACHE
    if not name:
        return None
    clean_name = re.sub(r'\[.*?\]', '', name).strip().lower()
    if (
        not clean_name
        or len(clean_name) < 3
        or len(clean_name) > 40
        or clean_name in _NON_PERFORMER_KEYWORDS
        or clean_name.startswith(("sort", "next", "prev", "page", ">>", "<<", "play all"))
    ):
        return None

    if _PERFORMERS_CACHE is None:
        _PERFORMERS_CACHE = {}
        try:
            addon_path = xbmcaddon.Addon("plugin.video.adulthideout").getAddonInfo("path")
            p_file = os.path.join(addon_path, "resources", "data", "star_index.json.gz")
            if os.path.exists(p_file):
                with gzip.open(p_file, "rt", encoding="utf-8") as f:
                    payload = json.load(f)
                    rows = payload.get("performers", []) + payload.get("website_metadata", [])
                    for p in rows:
                        n = p.get("name", "").strip().lower()
                        if n:
                            _PERFORMERS_CACHE[n] = p
        except Exception:
            pass

    return _PERFORMERS_CACHE.get(clean_name)

class KodiLogHandler(logging.Handler):
    def emit(self, record):
        levels = {
            logging.CRITICAL: xbmc.LOGFATAL,
            logging.ERROR: xbmc.LOGERROR,
            logging.WARNING: xbmc.LOGWARNING,
            logging.INFO: xbmc.LOGINFO,
            logging.DEBUG: xbmc.LOGDEBUG,
            logging.NOTSET: xbmc.LOGNONE,
        }
        xbmc.log(self.format(record), levels.get(record.levelno, xbmc.LOGINFO))

class BaseWebsite:
    supports_uploader_lookup = False
    uploader_lookup_patterns = ()
    def __init__(self, name, base_url, search_url, addon_handle, addon=None):
        self.name = name
        self.base_url = base_url
        self.search_url = search_url
        self.addon_handle = addon_handle
        self.addon = addon or xbmcaddon.Addon()
        self.logger = logging.getLogger(f"plugin.video.adulthideout.{name}")
        self.logger.setLevel(logging.INFO)
        if not self.logger.handlers:
            handler = KodiLogHandler()
            handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s: %(message)s'))
            self.logger.addHandler(handler)
        self.fanart = os.path.join(self.addon.getAddonInfo('path'), 'resources', 'logos', 'fanart.jpg')
        self.icon = os.path.join(self.addon.getAddonInfo('path'), 'resources', 'logos', 'icon.png')
        addon_path = self.addon.getAddonInfo('path')
        cached_icons = _ICON_PATH_CACHE.get(addon_path)
        if cached_icons is None:
            logo_path = os.path.join(addon_path, 'resources', 'logos')
            cached_icons = {
                'default': self.icon,
                'search': os.path.join(logo_path, 'search.png'),
                'categories': os.path.join(logo_path, 'categories.png'),
                'pornstars': os.path.join(logo_path, 'pornstars.png'),
                'settings': os.path.join(logo_path, 'settings.png'),
                'groups': self.icon,
                'galleries': self.icon,
            }
            for key, path in cached_icons.items():
                if not xbmcvfs.exists(path):
                    self.logger.warning(f"Icon not found: {path}")
            _ICON_PATH_CACHE[addon_path] = cached_icons
        self.icons = dict(cached_icons)

    def is_primary_listing_url(self, url):
        """Return whether *url* belongs to the site's main video listing.

        Pagination must not hide the standard navigation, while search,
        category and performer URLs must remain clean video-only listings.
        """
        def normalized(value):
            parsed = urllib.parse.urlparse(urllib.parse.urljoin(self.base_url, value or self.base_url))
            path = re.sub(r"/(?:page/)?\d+/?$", "/", parsed.path or "/", flags=re.IGNORECASE)
            path = "/" + path.strip("/") if path.strip("/") else "/"
            query = tuple(sorted(
                (key, item)
                for key, item in urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
                if key.lower() not in ("from", "from_videos", "page")
            ))
            return parsed.netloc.lower(), path.lower(), query

        candidates = [self.base_url]
        candidates.extend(getattr(self, "sort_paths", {}).values())
        current = normalized(url)
        return current in {normalized(candidate) for candidate in candidates}

    def get_start_url_and_label(self):
        label = f"{self.name.capitalize()}"
        url = self.base_url
        sort_label_suffix = "Videos" 

        if hasattr(self, 'sort_options') and self.sort_options and hasattr(self, 'sort_paths'):
            setting_id = f"{self.name}_sort_by"
            saved_sort_setting = self.addon.getSetting(setting_id)
            
            sort_option = self.sort_options[0] 
            
            try:
                sort_idx = int(saved_sort_setting)
            except ValueError:
                try:
                    sort_idx = self.sort_options.index(saved_sort_setting)
                except ValueError:
                    sort_idx = 0

            if 0 <= sort_idx < len(self.sort_options):
                sort_option = self.sort_options[sort_idx]
            
            sort_path = self.sort_paths.get(sort_option)
            if sort_path:
                url = urllib.parse.urljoin(self.base_url, sort_path)
            
            sort_label_suffix = sort_option
        
        final_label = f"{label} [COLOR yellow]{sort_label_suffix}[/COLOR]"
        return url, final_label

    def select_sort(self, original_url=None):
        if not hasattr(self, 'sort_options') or not self.sort_options:
            self.notify_info("This site does not support sorting.")
            return

        try:
            current_setting_idx = int(self.addon.getSetting(f"{self.name}_sort_by"))
            if not (0 <= current_setting_idx < len(self.sort_options)):
                current_setting_idx = 0
        except (ValueError, TypeError):
            current_setting_str = self.addon.getSetting(f"{self.name}_sort_by")
            try:
                current_setting_idx = self.sort_options.index(current_setting_str)
            except (ValueError, IndexError):
                current_setting_idx = 0

        dialog = xbmcgui.Dialog()
        idx = dialog.select("Sort by...", self.sort_options, preselect=current_setting_idx)

        if idx == -1: return

        self.addon.setSetting(f"{self.name}_sort_by", str(idx))
        
        new_url, _ = self.get_start_url_and_label()

        xbmc.executebuiltin(f"Container.Update({sys.argv[0]}?mode=2&url={urllib.parse.quote_plus(new_url)}&website={self.name},replace)")

    def get_queries_path(self):
        addon_profile = xbmcvfs.translatePath(self.addon.getAddonInfo('profile'))
        if not xbmcvfs.exists(addon_profile):
            xbmcvfs.mkdirs(addon_profile)
        return os.path.join(addon_profile, 'queries.json')

    def save_query(self, query):
        file_path = self.get_queries_path()
        all_queries = self.get_all_queries()
        if query in all_queries:
            all_queries.remove(query)
        all_queries.insert(0, query)
        with open(file_path, 'w') as f:
            json.dump(all_queries, f)

    def get_all_queries(self):
        file_path = self.get_queries_path()
        try:
            with open(file_path, 'r') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return []

    def get_last_query(self):
        queries = self.get_all_queries()
        return queries[0] if queries else ""

    def edit_query(self, query_to_edit=None):
        queries = self.get_all_queries()
        if not queries: return self.notify_info("No search history to edit.")

        original_query = query_to_edit
        if not original_query:
            query_idx = xbmcgui.Dialog().select("Select query to edit", queries)
            if query_idx == -1: return
            original_query = queries[query_idx]
        
        keyb = xbmc.Keyboard(original_query, "[COLOR yellow]Edit search text[/COLOR]")
        keyb.doModal()
        if keyb.isConfirmed():
            new_query = keyb.getText()
            if new_query and new_query != original_query:
                try: index = queries.index(original_query); queries[index] = new_query
                except ValueError: queries.append(new_query)
                with open(self.get_queries_path(), 'w') as f: json.dump(queries, f)
                self.notify_info("Search query updated."); xbmc.executebuiltin('Container.Refresh')

    def clear_search_history(self):
        if xbmcgui.Dialog().yesno("Confirm", "Are you sure you want to clear the search history?"):
            with open(self.get_queries_path(), 'w') as f: json.dump([], f)
            self.notify_info("Search history cleared."); xbmc.executebuiltin('Container.Refresh')

    def add_dir(self, name, url, mode, icon=None, fanart=None, context_menu=None, name_param=None, info_labels=None, **kwargs):
        icon = icon or self.icons.get('default', self.icon)
        fanart = fanart or self.fanart
        u = f"{sys.argv[0]}?url={urllib.parse.quote_plus(str(url))}&mode={mode}&name={urllib.parse.quote_plus(name_param or name)}&website={self.name}"
        if kwargs:
            for key, value in kwargs.items(): u += f"&{key}={urllib.parse.quote_plus(str(value))}"

        # Automatic central performer metadata enrichment across ALL websites
        star_meta = _get_performer_metadata(name_param or name)
        if star_meta:
            if not info_labels:
                info_labels = {}
            if "plot" not in info_labels:
                try:
                    from resources.lib.performer_index import PerformerIndex
                    info_labels["plot"] = PerformerIndex.format_static_plot(star_meta)
                except Exception:
                    pass
            if "genre" not in info_labels and star_meta.get("tags"):
                info_labels["genre"] = ", ".join(star_meta.get("tags", []))
            if "country" not in info_labels and star_meta.get("country"):
                info_labels["country"] = star_meta.get("country")
            if "year" not in info_labels and star_meta.get("birth_year"):
                try:
                    info_labels["year"] = int(star_meta.get("birth_year"))
                except Exception:
                    pass
            if star_meta.get("thumb") and (not icon or icon == self.icons.get('default', self.icon)):
                icon = star_meta.get("thumb")

        liz = xbmcgui.ListItem(name)
        liz.setArt({'thumb': icon, 'icon': icon, 'fanart': fanart, 'poster': icon})

        if info_labels:
            liz.setInfo('video', info_labels)

        context_menu = list(context_menu or [])
        try:
            from resources.lib.personal_library import build_save_command
            context_menu.append((
                self.addon.getLocalizedString(30706) or 'Save to Vault',
                build_save_command(sys.argv[0], u, name_param or name, self.name, icon, fanart, 'folder')
            ))
        except Exception as exc:
            self.logger.warning("Vault directory context failed: %s", exc)
        if context_menu:
            liz.addContextMenuItems(context_menu)

        xbmcplugin.addDirectoryItem(handle=self.addon_handle, url=u, listitem=liz, isFolder=True)

    def video_art(self, icon, fanart=None):
        effective_fanart = icon if self.addon.getSetting('use_video_thumbs_as_fanart') == 'true' else (fanart or self.fanart)
        return {'thumb': icon, 'icon': icon, 'poster': icon, 'fanart': effective_fanart}

    def add_link(self, name, url, mode, icon, fanart, context_menu=None, info_labels=None, uploader_name=None, uploader_url=None):
        u = f"{sys.argv[0]}?url={urllib.parse.quote_plus(url)}&mode={mode}&name={urllib.parse.quote_plus(name)}&website={self.name}&thumbnail={urllib.parse.quote_plus(icon or '')}&fanart={urllib.parse.quote_plus(fanart or '')}"
        liz = xbmcgui.ListItem(name)
        art = self.video_art(icon, fanart)
        effective_fanart = art['fanart']
        liz.setArt(art)
        liz.getVideoInfoTag().setTitle(name)
        liz.setProperty('IsPlayable', 'true')
        
        if info_labels:
            liz.setInfo('video', info_labels)
        
        # Auto-add context menu for sorting if not provided
        if context_menu is None:
            context_menu = []
        else:
            context_menu = list(context_menu)
        
        # Add sort menu if available
        if hasattr(self, 'select_sort') and hasattr(self, 'sort_options') and self.sort_options:
            # Check if sort is already present
            sort_action = 'action=select_sort'
            is_present = False
            for label, command in context_menu:
                 if sort_action in command:
                     is_present = True
                     break
            
            if not is_present:
                # Get current URL from sys.argv
                current_url = sys.argv[0] + sys.argv[2] if len(sys.argv) > 2 else ""
                context_menu.append(
                    ('Sort by...', f'RunPlugin({sys.argv[0]}?mode=7&action=select_sort&website={self.name}&original_url={urllib.parse.quote_plus(current_url)})')
                )

        if mode == 4 and getattr(self.__class__, 'resolve_recording_stream', None) is not getattr(BaseWebsite, 'resolve_recording_stream', None) and getattr(self.__class__, 'resolve_recording_stream', None) is not None:
            try:
                from resources.lib.download_manager import add_download_context
                context_menu = add_download_context(self, context_menu, url, name, icon)
            except Exception as exc:
                self.logger.warning("Download context failed: %s", exc)

        if mode == 4:
            try:
                from resources.lib.personal_library import build_save_command
                context_menu.append((
                    self.addon.getLocalizedString(30706) or 'Save to Vault',
                    build_save_command(sys.argv[0], u, name, self.name, icon, effective_fanart, 'video')
                ))
            except Exception as exc:
                self.logger.warning("Vault video context failed: %s", exc)

        if mode == 4 and (uploader_url or self.supports_uploader_lookup):
            target = uploader_url or url
            label = self.addon.getLocalizedString(30942) or "More from this uploader"
            if uploader_name:
                label = "{}: {}".format(label, uploader_name)
            context_menu.append((
                label,
                "RunPlugin({}?mode=7&action=more_from_uploader&website={}&original_url={})".format(
                    sys.argv[0],
                    urllib.parse.quote_plus(self.name),
                    urllib.parse.quote_plus(target),
                ),
            ))

        if context_menu:
            liz.addContextMenuItems(context_menu)

        xbmcplugin.addDirectoryItem(handle=self.addon_handle, url=u, listitem=liz, isFolder=False)

    def _load_uploader_page(self, url):
        for method_name in ("make_request", "_get_html", "_get"):
            method = getattr(self, method_name, None)
            if not callable(method):
                continue
            try:
                content = method(url)
                if isinstance(content, bytes):
                    content = content.decode("utf-8", "ignore")
                if content:
                    return content
            except Exception as exc:
                self.logger.debug("Uploader lookup via %s failed: %s", method_name, exc)
        return ""

    def more_from_uploader(self, original_url=None):
        if not original_url:
            return self.notify_info("No uploader information available")

        self.logger.info("Uploader lookup source: %s", original_url)

        path = urllib.parse.urlparse(original_url).path.lower()
        profile_markers = (
            "/profiles/", "/profile/", "/channels/", "/channel/",
            "/members/", "/member/", "/users/", "/user/", "/author/",
            "/uploader/",
        )
        if any(marker in path for marker in profile_markers):
            return self._open_uploader_listing(original_url)

        content = self._load_uploader_page(original_url)
        if not content:
            return self.notify_error("Could not load uploader information")

        patterns = self.uploader_lookup_patterns or (
            (r'href=["\']([^"\']*/profiles/[^"\']+)["\'][^>]*>(.*?)</a>', 1, 2),
            (r'href=["\']([^"\']*/channels/[^"\']+)["\'][^>]*>(.*?)</a>', 1, 2),
            (r'href=["\']([^"\']*/[^"\']*/channel/[^"\']+/)["\'][^>]*>(.*?)</a>', 1, 2),
            (r'href=["\']([^"\']*/members/[^"\']+)["\'][^>]*>(.*?)</a>', 1, 2),
            (r'href=["\']([^"\']*/(?:users?|profile|author|uploader)/[^"\']+)["\'][^>]*>(.*?)</a>', 1, 2),
        )
        candidates = []
        seen = set()
        for pattern, url_group, label_group in patterns:
            for match in re.finditer(pattern, content, re.IGNORECASE | re.DOTALL):
                href = match.group(url_group)
                raw_label = match.group(label_group)
                href = href.replace("\\/", "/")
                target = urllib.parse.urljoin(self.base_url, html.unescape(href))
                if target in seen:
                    continue
                label = re.sub(r"<[^>]+>", " ", raw_label)
                label = re.sub(r"\s+", " ", html.unescape(label)).strip()
                if not label:
                    label = urllib.parse.unquote(target.rstrip("/").split("/")[-1])
                seen.add(target)
                candidates.append((label, target))

        if not candidates:
            return self.notify_info("No uploader information available")

        # The first site-specific match belongs to the current video's main
        # uploader. Later matches commonly come from recommendation cards.
        return self._open_uploader_listing(candidates[0][1])

    def _open_uploader_listing(self, target_url):
        self.logger.info("Opening uploader profile: %s", target_url)
        plugin_url = (
            "{}?mode=2&website={}&url={}".format(
                sys.argv[0],
                urllib.parse.quote_plus(self.name),
                urllib.parse.quote_plus(target_url),
            )
        )
        xbmc.executebuiltin("Container.Update({})".format(plugin_url))

    def notify_error(self, message):
        self.logger.warning(f"notify_error: {message}")
        active_channel = xbmcgui.Window(10000).getProperty("AdultHideout.SmartChannel")
        if active_channel:
            # During 24/7 Smart Streams, auto-skip broken/unavailable streams silently
            xbmc.log(f"[AdultHideout] Smart Stream active - skipping failed video ({self.name}: {message}) silently to next", xbmc.LOGINFO)
            xbmc.executebuiltin("PlayerControl(Next)")
            return
        xbmcgui.Dialog().notification("Error", f"{self.name}: {message}", xbmcgui.NOTIFICATION_ERROR, 3000)

    def notify_info(self, message):
        xbmcgui.Dialog().notification("Info", message, xbmcgui.NOTIFICATION_INFO, 3000)

    def get_search_query(self):
        keyboard = xbmc.Keyboard(self.get_last_query(), f'[COLOR yellow]Enter search text for {self.name}[/COLOR]')
        keyboard.doModal()
        if keyboard.isConfirmed():
            query = keyboard.getText()
            if query: self.save_query(query); return query
        return None

    def search(self, query):
        if not query: return
        search_url = self.search_url.format(urllib.parse.quote_plus(query))
        self.process_content(search_url)

    def show_search_menu(self):
        self.add_dir('[COLOR blue]New Search[/COLOR]', '', 6, self.icons['search'], action='new_search')
        self.add_dir('[COLOR blue]Edit Search History[/COLOR]', '', 6, self.icons['settings'], action='edit_history')
        queries = self.get_all_queries()
        if queries: self.add_dir('[COLOR red]Clear Search History[/COLOR]', '', 6, self.icons['settings'], action='clear_history')
        for query in queries:
            context_menu = [('Edit', f'RunPlugin({sys.argv[0]}?mode=6&website={self.name}&action=edit_search_item&url={urllib.parse.quote_plus(query)})')]
            self.add_dir(f'[COLOR yellow]{html.unescape(query)}[/COLOR]', query, 6, self.icons['search'], context_menu=context_menu, action='history_search')
        self.end_directory()

    def handle_search_entry(self, url, mode, name, action=None):
        if action == 'new_search':
            query = self.get_search_query()
            if query: self.search(query)
        elif action == 'history_search': self.search(url)
        elif action == 'edit_history': self.edit_query()
        elif action == 'edit_search_item': self.edit_query(query_to_edit=url)
        elif action == 'clear_history': self.clear_search_history()

    def download_with_ffmpeg(self, original_url=None, title=None):
        from resources.lib.download_manager import enqueue_download
        enqueue_download(self, original_url, title=title)

    def record_with_ffmpeg(self, original_url=None, title=None):
        self.download_with_ffmpeg(original_url, title=title)

    def convert_duration(self, duration_str):
        """Converts duration string (MM:SS or HH:MM:SS) to total seconds for Kodi."""
        if not duration_str:
            return 0
        try:
            parts = duration_str.split(':')
            if len(parts) == 2:  # MM:SS
                return int(parts[0]) * 60 + int(parts[1])
            elif len(parts) == 3:  # HH:MM:SS
                return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
        except (ValueError, IndexError):
            pass
        return 0

    def play_video(self, url):
        raise NotImplementedError

    def resolve_recording_stream(self, url):
        return None

    def end_directory(self, content_type="videos"):
        end_directory_with_view(self.addon_handle, self.addon, content_type=content_type)
