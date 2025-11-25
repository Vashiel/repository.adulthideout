#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging
import sys
import os
import json
import urllib.parse
import xbmc
import xbmcaddon
import xbmcgui
import xbmcplugin
import xbmcvfs
import html

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
        self.icons = {
            'default': self.icon,
            'search': os.path.join(self.addon.getAddonInfo('path'), 'resources', 'logos', 'search.png'),
            'categories': os.path.join(self.addon.getAddonInfo('path'), 'resources', 'logos', 'categories.png'),
            'pornstars': os.path.join(self.addon.getAddonInfo('path'), 'resources', 'logos', 'pornstars.png'),
            'settings': os.path.join(self.addon.getAddonInfo('path'), 'resources', 'logos', 'settings.png'),
            'groups': os.path.join(self.addon.getAddonInfo('path'), 'resources', 'logos', 'icon.png'),
            'galleries': os.path.join(self.addon.getAddonInfo('path'), 'resources', 'logos', 'icon.png'),            
        }
        for key, path in self.icons.items():
            if not xbmcvfs.exists(path):
                self.logger.warning(f"Icon not found: {path}")

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
        
        if original_url:
            parsed_original = urllib.parse.urlparse(original_url)
            parsed_new = urllib.parse.urlparse(new_url)
            
            original_path = parsed_original.path.strip('/')
            if 'cat/' in original_path or 'search/' in original_path:
                 pass

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
        
        liz = xbmcgui.ListItem(name)
        liz.setArt({'thumb': icon, 'icon': icon, 'fanart': fanart})
        
        # --- NEUER, SICHERER BLOCK ---
        if info_labels:
            liz.setInfo('video', info_labels)
        # --- ENDE ---

        if context_menu: 
            liz.addContextMenuItems(context_menu)
            
        xbmcplugin.addDirectoryItem(handle=self.addon_handle, url=u, listitem=liz, isFolder=True)

    def add_link(self, name, url, mode, icon, fanart, context_menu=None, info_labels=None):
        u = f"{sys.argv[0]}?url={urllib.parse.quote_plus(url)}&mode={mode}&name={urllib.parse.quote_plus(name)}&website={self.name}"
        liz = xbmcgui.ListItem(name)
        liz.setArt({'thumb': icon, 'icon': icon, 'fanart': fanart})
        liz.getVideoInfoTag().setTitle(name)
        liz.setProperty('IsPlayable', 'true')
        
        # Auto-add context menu for sorting if not provided
        if context_menu is None:
            context_menu = []
        
        # Add sort menu if available
        if hasattr(self, 'select_sort'):
            # Get current URL from sys.argv
            current_url = sys.argv[0] + sys.argv[2] if len(sys.argv) > 2 else ""
            context_menu.append(
                ('Sort by...', f'RunPlugin({sys.argv[0]}?mode=7&action=select_sort&website={self.name}&original_url={urllib.parse.quote_plus(current_url)})')
            )
        
        if context_menu: 
            liz.addContextMenuItems(context_menu)
        
        xbmcplugin.addDirectoryItem(handle=self.addon_handle, url=u, listitem=liz, isFolder=False)

    def notify_error(self, message):
        xbmcgui.Dialog().notification("Error", f"{self.name}: {message}", xbmcgui.NOTIFICATION_ERROR, 5000)

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

    def process_content(self, url):
        raise NotImplementedError

    def play_video(self, url):
        raise NotImplementedError

    def end_directory(self, content_type="videos"):
        xbmcplugin.setContent(self.addon_handle, content_type)
        viewtype = int(self.addon.getSetting('viewtype') or '0')
        view_modes = [50, 51, 500, 501, 502]
        xbmc.executebuiltin(f'Container.SetViewMode({view_modes[viewtype]})')
        xbmcplugin.endOfDirectory(self.addon_handle)