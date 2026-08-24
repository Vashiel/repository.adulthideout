# -*- coding: utf-8 -*-

import xbmc
import xbmcplugin
import xbmcvfs
import os
import time

ADDON_ID = "plugin.video.adulthideout"
VIDEO_WINDOW_ID = 10025
VIEW_MODES = [
    50,   # List
    51,   # Poster
    55,   # Wide List
    500,  # Wall
    502,  # Fanart
]


def get_view_selection(addon, default_index=2):
    try:
        index = int(addon.getSetting("viewtype") or default_index)
    except (TypeError, ValueError):
        index = default_index
    if index < 0 or index >= len(VIEW_MODES):
        index = default_index
    return index, VIEW_MODES[index]


def get_view_mode(addon, default_index=2):
    return get_view_selection(addon, default_index=default_index)[1]


def get_content_type_for_view(addon, content_type="videos"):
    return content_type


def apply_view_mode(
    addon,
    reason="runtime",
    content_type="",
    persist=False,
    schedule=False,
    log_success=False,
):
    try:
        _, view_mode = get_view_selection(addon)
        if xbmc:
            xbmc.executebuiltin(f"Container.SetViewMode({view_mode})")
        return view_mode
    except Exception:
        return 55


def end_directory_with_view(addon_handle, addon, content_type="videos"):
    try:
        if xbmcplugin:
            xbmcplugin.setContent(addon_handle, content_type)
            xbmcplugin.endOfDirectory(addon_handle)
    except Exception:
        if xbmcplugin:
            xbmcplugin.endOfDirectory(addon_handle)

    try:
        if content_type == "videos" and xbmc:
            _, view_mode = get_view_selection(addon)
            if view_mode:
                xbmc.executebuiltin(f"Container.SetViewMode({view_mode})")
    except Exception:
        pass
