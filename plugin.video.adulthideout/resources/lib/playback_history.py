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

ADDON_ID = "plugin.video.adulthideout"
MAX_ENTRIES = 100


def _profile_dir():
    path = xbmcvfs.translatePath("special://profile/addon_data/{}/".format(ADDON_ID))
    if not xbmcvfs.exists(path):
        xbmcvfs.mkdirs(path)
    return path


def _history_path():
    return os.path.join(_profile_dir(), "playback_history.json")


def load_history():
    try:
        with open(_history_path(), "r", encoding="utf-8") as handle:
            data = json.load(handle)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def save_history(items):
    path = _history_path()
    temp_path = path + ".tmp"
    with open(temp_path, "w", encoding="utf-8") as handle:
        json.dump(items[:MAX_ENTRIES], handle, ensure_ascii=False, separators=(",", ":"))
    os.replace(temp_path, path)


def update_entry(entry, position, duration):
    if not isinstance(entry, dict) or not entry.get("url"):
        return
    position = max(0.0, float(position or 0))
    duration = max(0.0, float(duration or 0))
    items = [item for item in load_history() if item.get("url") != entry["url"]]

    # Very short starts and completed videos do not belong in Continue Watching.
    if position < 10 or (duration > 0 and position >= duration * 0.9):
        save_history(items)
        return

    saved = dict(entry)
    saved.update({"position": round(position, 1), "duration": round(duration, 1), "updated": int(time.time())})
    items.insert(0, saved)
    save_history(items)


def remove(url):
    save_history([item for item in load_history() if item.get("url") != url])


def clear():
    save_history([])


def show(addon_handle, plugin_url, action=None, params=None):
    params = params or {}
    addon = xbmcaddon.Addon(ADDON_ID)
    if action == "remove":
        remove(params.get("target", ""))
        xbmc.executebuiltin("Container.Refresh")
        return
    if action == "clear":
        if xbmcgui.Dialog().yesno("Continue Watching", "Clear playback history?"):
            clear()
            xbmc.executebuiltin("Container.Refresh")
        return

    items = load_history()
    for entry in items:
        target = entry.get("url", "")
        if not target:
            continue
        title = entry.get("title") or "Video"
        position = float(entry.get("position") or 0)
        duration = float(entry.get("duration") or 0)
        progress = int(position * 100 / duration) if duration > 0 else 0
        label = "{} [COLOR grey]({}%)[/COLOR]".format(title, progress) if progress else title
        item = xbmcgui.ListItem(label=label, path=target)
        thumb = entry.get("thumbnail", "")
        item.setArt({"thumb": thumb, "icon": thumb, "poster": thumb, "fanart": entry.get("fanart", thumb)})
        item.setProperty("IsPlayable", "true")
        item.setProperty("StartOffset", str(int(position)))
        item.setInfo("video", {"title": title, "mediatype": "video"})
        try:
            item.getVideoInfoTag().setResumePoint(position, duration)
        except Exception:
            pass
        remove_url = "{}?mode=80&action=remove&target={}".format(plugin_url, urllib.parse.quote_plus(target))
        item.addContextMenuItems([("Remove from Continue Watching", "RunPlugin({})".format(remove_url))])
        xbmcplugin.addDirectoryItem(addon_handle, target, item, False)

    if items:
        clear_url = "{}?mode=80&action=clear".format(plugin_url)
        clear_item = xbmcgui.ListItem(label="[COLOR red]Clear playback history[/COLOR]")
        xbmcplugin.addDirectoryItem(addon_handle, clear_url, clear_item, False)
    xbmcplugin.setContent(addon_handle, "videos")
    xbmcplugin.endOfDirectory(addon_handle, cacheToDisc=False)
