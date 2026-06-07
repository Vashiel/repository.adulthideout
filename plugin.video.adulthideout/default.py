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
import inspect
from importlib import import_module
from resources.lib.view_utils import end_directory_with_view

ADDON = xbmcaddon.Addon()
ADDON_ID = ADDON.getAddonInfo('id')
ADDON_PATH = ADDON.getAddonInfo('path')
ADDON_HANDLE = int(sys.argv[1])
RESOURCES_DIR = os.path.join(ADDON_PATH, 'resources')
WEBSITES_DIR = os.path.join(RESOURCES_DIR, 'websites')
LOGOS_DIR = os.path.join(RESOURCES_DIR, 'logos')
FANART_PATH = os.path.join(LOGOS_DIR, 'fanart.jpg')
DEFAULT_ICON_PATH = os.path.join(LOGOS_DIR, 'icon.png')
VIEW_SERVICE_PATH = os.path.join(ADDON_PATH, 'resources', 'lib', 'view_service.py')
VIEW_SERVICE_VERSION = "9"

def log(msg, level=xbmc.LOGINFO):
    xbmc.log(f"[{ADDON_ID}] {msg}", level)

def notify_user(msg):
    xbmcgui.Dialog().notification('AdultHideout Error', str(msg), xbmcgui.NOTIFICATION_ERROR, 3000)

def ensure_view_service():
    try:
        window = xbmcgui.Window(10000)
        service_running = window.getProperty("AdultHideout.ViewServiceRunning") == "true"
        service_version = window.getProperty("AdultHideout.ViewServiceVersion")
        if (not service_running or service_version != VIEW_SERVICE_VERSION) and xbmcvfs.exists(VIEW_SERVICE_PATH):
            if service_running and service_version != VIEW_SERVICE_VERSION:
                for script_id in (VIEW_SERVICE_PATH, ADDON_ID):
                    xbmc.executebuiltin("StopScript({})".format(script_id))
                xbmc.sleep(500)
            xbmc.executebuiltin("RunScript({})".format(VIEW_SERVICE_PATH))
    except Exception as exc:
        log("Could not start view service: {}".format(exc), xbmc.LOGWARNING)

def get_setting_id_from_name(name):
    return f"show_{name.lower().replace('-', '').replace('_', '')}"

def build_main_menu_fast():
    if not os.path.exists(WEBSITES_DIR):
        log(f"ERROR: Websites folder not found at: {WEBSITES_DIR}", xbmc.LOGERROR)
        notify_user(f"Missing folder: {WEBSITES_DIR}")
        xbmcplugin.endOfDirectory(ADDON_HANDLE)
        return

    log(f"Scanning for websites in: {WEBSITES_DIR}")

    found_any = False

    global_search_item = xbmcgui.ListItem(label="[COLOR yellow]Global Search[/COLOR]")
    global_search_icon = os.path.join(LOGOS_DIR, "search.png")
    if not xbmcvfs.exists(global_search_icon):
        global_search_icon = DEFAULT_ICON_PATH
    global_search_item.setArt({"icon": global_search_icon, "thumb": global_search_icon, "fanart": FANART_PATH})
    xbmcplugin.addDirectoryItem(
        handle=ADDON_HANDLE,
        url=f"{sys.argv[0]}?mode=20&website=global_search",
        listitem=global_search_item,
        isFolder=True,
    )
    
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
        if module_raw_name == 'chaturbate':
            context_menu.append(
                ('Filter...', f'RunPlugin({sys.argv[0]}?mode=7&action=select_filter&website={module_raw_name})')
            )

        url_params = f"?mode=2&website={module_raw_name}&url=BOOTSTRAP"
        url = f"{sys.argv[0]}{url_params}"
        
        li = xbmcgui.ListItem(label=label)
        li.setArt({'icon': icon_path, 'thumb': icon_path, 'fanart': FANART_PATH})
        li.addContextMenuItems(context_menu)
        
        xbmcplugin.addDirectoryItem(handle=ADDON_HANDLE, url=url, listitem=li, isFolder=True)
        found_any = True

    if not found_any:
        log("No website files found (.py)!", xbmc.LOGWARNING)

    end_directory_with_view(ADDON_HANDLE, ADDON)

def load_single_website(website_name):
    if ADDON_PATH not in sys.path:
        sys.path.insert(0, ADDON_PATH)
        
    from resources.lib.base_website import BaseWebsite

    try:
        module = import_module(f'resources.websites.{website_name}')
        for attr in dir(module):
            cls = getattr(module, attr)
            if isinstance(cls, type) and issubclass(cls, BaseWebsite) and cls is not BaseWebsite and cls.__module__ == module.__name__:
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
                            if isinstance(cls, type) and issubclass(cls, BaseWebsite) and cls is not BaseWebsite and cls.__module__ == module.__name__:
                                return cls(ADDON_HANDLE)
                    except Exception as e:
                        log(f"Error loading fallback module {filename}: {e}", xbmc.LOGERROR)
    
    return None

def handle_routing():
    ensure_view_service()
    params = {}
    try:
        if len(sys.argv) > 2 and sys.argv[2]:
            params = dict(urllib.parse.parse_qsl(sys.argv[2][1:]))
    except Exception:
        pass

    mode = params.get('mode')
    website_name = params.get('website')
    
    log(f"Routing: mode={mode}, website={website_name}")

    try:
        from resources.lib.official_source import verify_and_warn
        verify_and_warn(ADDON, show_dialog=(mode is None))
    except Exception as exc:
        log(f"Official source check failed unexpectedly: {exc}", xbmc.LOGWARNING)

    if mode is None:
        build_main_menu_fast()
        return

    if website_name == 'global_search' or mode in ('20', '21'):
        from resources.lib.global_search import GlobalSearch
        global_search = GlobalSearch(ADDON_HANDLE, addon=ADDON, loader=load_single_website, logger=log)
        action = params.get('action')
        if action == 'new_search':
            global_search.new_search()
        elif action == 'show_presets':
            global_search.show_presets()
        elif action == 'apply_preset':
            global_search.apply_preset(params.get('profile'))
        elif action == 'choose_sources':
            global_search.choose_sources()
        elif action == 'show_sources':
            global_search.show_sources()
        elif action == 'clear_history':
            global_search.clear_history()
        elif action == 'edit_search':
            global_search.edit_search(params.get('query', ''))
        elif mode == '21':
            try:
                page = int(params.get('page', '1') or '1')
            except Exception:
                page = 1
            global_search.run(params.get('query', ''), refresh=params.get('refresh') == '1', page=page)
        else:
            global_search.show_menu()
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
    original_url = params.get('url')

    websites_with_internal_bootstrap = ['drtuber', 'cumlouder', 'pornhat']
    
    if url == 'BOOTSTRAP' and mode == '2' and website_name not in websites_with_internal_bootstrap:
        if hasattr(target_website, 'get_start_url_and_label'):
             url, _ = target_website.get_start_url_and_label()
        else:
             url = target_website.base_url

    if mode == '2':
        page = int(params.get('page', '1'))
        
        # Safe call: check if process_content supports 'page' argument
        sig = inspect.signature(target_website.process_content)
        if 'page' in sig.parameters:
            target_website.process_content(url, page=page)
        else:
            target_website.process_content(url)
        
    elif mode == '4':
        target_website.play_video(url)
        
    elif mode == '5':
        target_website.show_search_menu()
        
    elif mode == '6':
        target_website.handle_search_entry(url, mode, target_website.name, action)
        
    elif mode == '7':
        original_url = params.get('original_url') or params.get('url')
        filter_type = params.get('filter_type')
        
        if action and hasattr(target_website, action):
            try:
                if action in ('download_with_ffmpeg', 'record_with_ffmpeg'):
                    getattr(target_website, action)(original_url, params.get('name'))
                elif filter_type:
                    getattr(target_website, action)(filter_type, original_url)
                else:
                    getattr(target_website, action)(original_url)
            except TypeError:
                getattr(target_website, action)()
        else:
            notify_user("Action not supported or implemented")
        xbmcplugin.endOfDirectory(ADDON_HANDLE, succeeded=True, updateListing=False, cacheToDisc=False)
            
    elif mode == '8':
        if hasattr(target_website, 'process_categories'):
            target_website.process_categories(url)
        else:
            xbmcplugin.endOfDirectory(ADDON_HANDLE)
            
    elif mode == '9':
        if hasattr(target_website, 'process_pornstars'):
            target_website.process_pornstars(url)
        elif hasattr(target_website, 'process_actresses_list'):
            target_website.process_actresses_list(url)
        else:
            xbmcplugin.endOfDirectory(ADDON_HANDLE)
            
    elif mode == '10':
        if hasattr(target_website, 'process_channels'):
            target_website.process_channels(url)
        else:
            xbmcplugin.endOfDirectory(ADDON_HANDLE)
            
    elif mode == '11':
        if hasattr(target_website, 'process_collections'):
            target_website.process_collections(url)
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
