#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import os
import urllib.parse
import xbmc
import xbmcaddon
import xbmcgui
import xbmcplugin
import xbmcvfs
import traceback
from importlib import import_module

ADDON = xbmcaddon.Addon()
ADDON_ID = ADDON.getAddonInfo('id')
ADDON_PATH = ADDON.getAddonInfo('path')
ADDON_HANDLE = int(sys.argv[1])
RESOURCES_DIR = os.path.join(ADDON_PATH, 'resources')
WEBSITES_DIR = os.path.join(RESOURCES_DIR, 'websites')
LOGOS_DIR = os.path.join(RESOURCES_DIR, 'logos')
FANART_PATH = os.path.join(LOGOS_DIR, 'fanart.jpg')
DEFAULT_ICON_PATH = os.path.join(LOGOS_DIR, 'icon.png')

def log(msg, level=xbmc.LOGINFO):
    xbmc.log(f"[{ADDON_ID}] {msg}", level)

def notify_user(msg):
    xbmcgui.Dialog().notification('AdultHideout Error', str(msg), xbmcgui.NOTIFICATION_ERROR, 3000)

def get_setting_id_from_name(name):
    return f"show_{name.lower().replace('-', '').replace('_', '')}"

def build_main_menu_fast():
    if not os.path.exists(WEBSITES_DIR):
        log(f"ERROR: Websites folder not found at: {WEBSITES_DIR}", xbmc.LOGERROR)
        notify_user(f"Missing folder: {WEBSITES_DIR}")
        xbmcplugin.endOfDirectory(ADDON_HANDLE)
        return

    log(f"Scanning for websites in: {WEBSITES_DIR}")

    try:
        viewtype = int(ADDON.getSetting('viewtype') or '0')
    except ValueError:
        viewtype = 0
    
    found_any = False
    
    for filename in sorted(os.listdir(WEBSITES_DIR)):
        if not filename.endswith('.py') or filename == '__init__.py':
            continue

        module_raw_name = filename[:-3]
        
        setting_id = get_setting_id_from_name(module_raw_name)
        if ADDON.getSetting(setting_id) == 'false':
            continue

        label = module_raw_name.replace('_', ' ').replace('-', ' ').title()
        
        icon_path = os.path.join(LOGOS_DIR, f"{module_raw_name}.png")
        if not xbmcvfs.exists(icon_path):
            icon_path = os.path.join(LOGOS_DIR, f"{module_raw_name.replace('_', '-')}.png")
            if not xbmcvfs.exists(icon_path):
                icon_path = DEFAULT_ICON_PATH

        context_menu = [
            ('Sort by...', f'RunPlugin({sys.argv[0]}?mode=7&action=select_sort&website={module_raw_name})'),
            ('Change Content...', f'RunPlugin({sys.argv[0]}?mode=7&action=select_content_type&website={module_raw_name})')
        ]

        url_params = f"?mode=2&website={module_raw_name}&url=BOOTSTRAP"
        url = f"{sys.argv[0]}{url_params}"
        
        li = xbmcgui.ListItem(label=label)
        li.setArt({'icon': icon_path, 'thumb': icon_path, 'fanart': FANART_PATH})
        li.addContextMenuItems(context_menu)
        
        xbmcplugin.addDirectoryItem(handle=ADDON_HANDLE, url=url, listitem=li, isFolder=True)
        found_any = True

    if not found_any:
        log("No website files found (.py)!", xbmc.LOGWARNING)

    xbmcplugin.setContent(ADDON_HANDLE, 'videos')
    
    view_modes = [50, 51, 500, 501, 502]
    if viewtype < len(view_modes):
        xbmc.executebuiltin(f'Container.SetViewMode({view_modes[viewtype]})')
    
    xbmcplugin.endOfDirectory(ADDON_HANDLE)

def load_single_website(website_name):
    if ADDON_PATH not in sys.path:
        sys.path.insert(0, ADDON_PATH)
        
    from resources.lib.base_website import BaseWebsite

    try:
        module = import_module(f'resources.websites.{website_name}')
        for attr in dir(module):
            cls = getattr(module, attr)
            if isinstance(cls, type) and issubclass(cls, BaseWebsite) and cls is not BaseWebsite:
                return cls(ADDON_HANDLE)
    except ImportError:
        log(f"ImportError for {website_name}, trying fallback search.", xbmc.LOGWARNING)

    target_clean = website_name.replace('-', '').replace('_', '').lower()
    
    if os.path.exists(WEBSITES_DIR):
        for filename in os.listdir(WEBSITES_DIR):
            if filename.endswith('.py') and filename != '__init__.py':
                fname_clean = filename[:-3].replace('-', '').replace('_', '').lower()
                if fname_clean == target_clean:
                    try:
                        module = import_module(f'resources.websites.{filename[:-3]}')
                        for attr in dir(module):
                            cls = getattr(module, attr)
                            if isinstance(cls, type) and issubclass(cls, BaseWebsite) and cls is not BaseWebsite:
                                return cls(ADDON_HANDLE)
                    except Exception as e:
                        log(f"Error loading fallback module {filename}: {e}", xbmc.LOGERROR)
    
    return None

def handle_routing():
    params = {}
    try:
        if len(sys.argv) > 2 and sys.argv[2]:
            params = dict(urllib.parse.parse_qsl(sys.argv[2][1:]))
    except Exception:
        pass

    mode = params.get('mode')
    website_name = params.get('website')
    
    log(f"Routing: mode={mode}, website={website_name}")

    if mode is None:
        build_main_menu_fast()
        return

    target_website = None
    if website_name:
        target_website = load_single_website(website_name)
    
    if not target_website:
        log(f"Could not load website module for: {website_name}", xbmc.LOGERROR)
        notify_user(f"Module not found: {website_name}")
        xbmcplugin.endOfDirectory(ADDON_HANDLE)
        return

    url = params.get('url')
    action = params.get('action')

    if url == 'BOOTSTRAP':
        if hasattr(target_website, 'get_start_url_and_label'):
             url, _ = target_website.get_start_url_and_label()
        else:
             url = target_website.base_url

    if mode == '2':
        target_website.process_content(url)
        
    elif mode == '4':
        target_website.play_video(url)
        
    elif mode == '5':
        target_website.show_search_menu()
        
    elif mode == '6':
        target_website.handle_search_entry(url, mode, target_website.name, action)
        
    elif mode == '7':
        original_url = params.get('original_url')
        filter_type = params.get('filter_type')
        
        if action and hasattr(target_website, action):
            try:
                if filter_type:
                    getattr(target_website, action)(filter_type, original_url)
                else:
                    getattr(target_website, action)(original_url)
            except TypeError:
                getattr(target_website, action)()
        else:
            notify_user("Action not supported or implemented")
            
    elif mode == '8':
        if hasattr(target_website, 'process_categories'):
            target_website.process_categories(url)
        else:
            xbmcplugin.endOfDirectory(ADDON_HANDLE)
            
    elif mode == '9':
        if hasattr(target_website, 'process_actresses_list'):
            target_website.process_actresses_list(url)
        else:
            xbmcplugin.endOfDirectory(ADDON_HANDLE)
            
    else:
        xbmcplugin.endOfDirectory(ADDON_HANDLE)

if __name__ == '__main__':
    try:
        handle_routing()
    except Exception as e:
        log(f"CRITICAL ERROR: {e}\n{traceback.format_exc()}", xbmc.LOGERROR)
        notify_user(f"Critical Error: {str(e)}")
        xbmcplugin.endOfDirectory(ADDON_HANDLE)