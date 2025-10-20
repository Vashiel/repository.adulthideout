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
from importlib import import_module
from resources.lib.base_website import BaseWebsite

addon_handle = int(sys.argv[1])
addon = xbmcaddon.Addon()

def load_websites(addon_handle):
    websites = []
    websites_dir = os.path.join(addon.getAddonInfo('path'), 'resources', 'websites')
    if not os.path.exists(websites_dir):
        xbmc.log(f"Websites directory not found: {websites_dir}", xbmc.LOGERROR)
        return websites

    for filename in sorted(os.listdir(websites_dir)):
        if filename.endswith('.py') and filename != '__init__.py':
            module_name = filename[:-3]
            try:
                module = import_module(f'resources.websites.{module_name}')
                for attr in dir(module):
                    cls = getattr(module, attr)
                    if isinstance(cls, type) and issubclass(cls, BaseWebsite) and cls is not BaseWebsite:
                        websites.append(cls(addon_handle))
                        break
            except Exception as e:
                xbmc.log(f"Failed to load module {module_name}: {e}", xbmc.LOGERROR)
    return websites

def main():
    websites = load_websites(addon_handle)
    for website in websites:
        setting_id = f"show_{website.name.lower().replace('-', '')}"
        try:
            is_visible = addon.getSettingBool(setting_id)
        except:
            is_visible = True

        if is_visible:
            start_url, label = website.get_start_url_and_label()
            
            context_menu = []
            
            if hasattr(website, 'select_sort'):
                context_menu.append(
                    ('Sort by...', f'RunPlugin({sys.argv[0]}?mode=7&action=select_sort&website={website.name})')
                )
            if hasattr(website, 'select_content_type'):
                context_menu.append(
                    ('Change Content...', f'RunPlugin({sys.argv[0]}?mode=7&action=select_content_type&website={website.name})')
                )

            icon_path = os.path.join(addon.getAddonInfo('path'), 'resources', 'logos', f'{website.name}.png')
            if not xbmcvfs.exists(icon_path):
                icon_path = website.icon

            website.add_dir(
                label, start_url, 2, icon_path, website.fanart,
                context_menu=context_menu if context_menu else None
            )

    xbmcplugin.setContent(addon_handle, 'videos')
    viewtype = int(addon.getSetting('viewtype') or '0')
    view_modes = [50, 51, 500, 501, 502]
    xbmc.executebuiltin(f'Container.SetViewMode({view_modes[viewtype]})')
    xbmcplugin.endOfDirectory(addon_handle)

def find_website_by_name(name, websites):
    for site in websites:
        if name == site.name:
            return site
    return None

def handle_routing():
    params = {}
    try:
        paramstring = sys.argv[2][1:]
        if paramstring:
            params = dict(urllib.parse.parse_qsl(paramstring))
    except IndexError:
        pass

    mode = params.get('mode')
    website_name = params.get('website')
    
    if mode is None:
        main()
        return

    websites = load_websites(addon_handle)
    target_website = find_website_by_name(website_name, websites)
    if not target_website:
        xbmc.log(f"Could not find a responsible website for: {params}", xbmc.LOGERROR)
        xbmcplugin.endOfDirectory(addon_handle)
        return

    url = params.get('url')
    action = params.get('action')

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
        if action and hasattr(target_website, action):
            getattr(target_website, action)(original_url)
            
    elif mode == '8':
        if hasattr(target_website, 'process_categories'):
            target_website.process_categories(url)
        else:
            xbmc.log(f"Website {target_website.name} has no function for mode 8", xbmc.LOGWARNING)
            xbmcplugin.endOfDirectory(addon_handle)

    elif mode == '9':
        if hasattr(target_website, 'process_actresses_list'):
            target_website.process_actresses_list(url)
        else:
            xbmc.log(f"Website {target_website.name} has no function for mode 9", xbmc.LOGWARNING)
            xbmcplugin.endOfDirectory(addon_handle)
    else:
        xbmcgui.Dialog().notification("Error", f"Invalid mode: {mode}", xbmcgui.NOTIFICATION_ERROR)
        xbmcplugin.endOfDirectory(addon_handle)

if __name__ == '__main__':
    handle_routing()