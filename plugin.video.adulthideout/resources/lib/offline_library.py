# -*- coding: utf-8 -*-

import json
import os
import urllib.parse

import xbmc
import xbmcaddon
import xbmcgui
import xbmcplugin
import xbmcvfs


ADDON_ID = "plugin.video.adulthideout"


VIDEO_EXTENSIONS = (".mp4", ".mkv", ".webm", ".mov", ".ts", ".m4v")


def _addon():
    return xbmcaddon.Addon(ADDON_ID)


def _root_folder():
    addon = _addon()
    return (addon.getSetting("offline_library_folder") or addon.getSetting("download_folder") or "").strip()


def _join(folder, name):
    if "://" in folder:
        return folder.rstrip("/\\") + "/" + name
    return os.path.join(xbmcvfs.translatePath(folder), name)


def _read_metadata(video_path):
    sidecar = video_path + ".ah.json"
    if not xbmcvfs.exists(sidecar):
        return {}
    try:
        handle = xbmcvfs.File(sidecar)
        raw = handle.read()
        handle.close()
        return json.loads(raw) if raw else {}
    except Exception:
        return {}


def show(handle, base_url, path=""):
    folder = path or _root_folder()
    if not folder:
        item = xbmcgui.ListItem(label="[COLOR yellow]Configure an offline folder in AdultHideout settings[/COLOR]")
        xbmcplugin.addDirectoryItem(handle, "", item, False)
        xbmcplugin.endOfDirectory(handle, succeeded=True, cacheToDisc=False)
        return
    try:
        directories, files = xbmcvfs.listdir(folder)
    except Exception as exc:
        xbmc.log("[AdultHideout][offline] list failed: {}".format(exc), xbmc.LOGERROR)
        directories, files = [], []
    for name in sorted(directories, key=str.lower):
        child = _join(folder, name)
        item = xbmcgui.ListItem(label=name)
        url = "{}?mode=32&path={}".format(base_url, urllib.parse.quote_plus(child))
        xbmcplugin.addDirectoryItem(handle, url, item, True)
    for name in sorted(files, key=str.lower):
        if not name.lower().endswith(VIDEO_EXTENSIONS):
            continue
        video_path = _join(folder, name)
        metadata = _read_metadata(video_path)
        title = metadata.get("title") or os.path.splitext(name)[0]
        item = xbmcgui.ListItem(label=title, path=video_path)
        item.setProperty("IsPlayable", "true")
        item.setInfo("video", {"title": title, "plot": metadata.get("source") or video_path})
        thumbnail = metadata.get("thumbnail") or ""
        if thumbnail:
            item.setArt({"thumb": thumbnail, "icon": thumbnail})
        delete_url = "{}?mode=31&action=delete_offline&path={}".format(base_url, urllib.parse.quote_plus(video_path))
        item.addContextMenuItems([(_addon().getLocalizedString(30660) or "Delete offline file", "RunPlugin({})".format(delete_url))])
        xbmcplugin.addDirectoryItem(handle, video_path, item, False)
    xbmcplugin.setContent(handle, "videos")
    xbmcplugin.endOfDirectory(handle, succeeded=True, cacheToDisc=False)


def delete(path):
    if not path or not xbmcvfs.exists(path):
        return
    title = os.path.basename(path)
    if not xbmcgui.Dialog().yesno("AdultHideout", "Delete '{}' permanently?".format(title)):
        return
    if xbmcvfs.delete(path):
        sidecar = path + ".ah.json"
        if xbmcvfs.exists(sidecar):
            xbmcvfs.delete(sidecar)
        xbmc.executebuiltin("Container.Refresh")
