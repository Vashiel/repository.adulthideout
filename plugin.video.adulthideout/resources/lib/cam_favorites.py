# -*- coding: utf-8 -*-
import json
import os
import sys
import time
import urllib.parse

import xbmc
import xbmcaddon
import xbmcgui
import xbmcplugin
import xbmcvfs


ADDON = xbmcaddon.Addon("plugin.video.adulthideout")
FILENAME = "cam_favorites.json"
PREFIX = "CAM_FAVORITES:"


def _text(string_id, fallback):
    return ADDON.getLocalizedString(string_id) or fallback


def _path():
    profile = xbmcvfs.translatePath(ADDON.getAddonInfo("profile"))
    os.makedirs(profile, exist_ok=True)
    return os.path.join(profile, FILENAME)


def _load():
    try:
        with open(_path(), "r", encoding="utf-8") as handle:
            data = json.load(handle)
        if isinstance(data, dict) and isinstance(data.get("favorites"), dict):
            return data
    except (OSError, ValueError, TypeError):
        pass
    return {"version": 1, "favorites": {}}


def _save(data):
    target = _path()
    temporary = target + ".tmp"
    with open(temporary, "w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
    os.replace(temporary, target)


def _key(site, username):
    return "{}:{}".format((site or "").lower(), (username or "").lower())


def is_favorite(site, username):
    return _key(site, username) in _load()["favorites"]


def context_menu(site, username, label, url, thumb):
    exists = is_favorite(site, username)
    action = "remove" if exists else "add"
    text = _text(30954, "Remove from Cam Favorites") if exists else _text(30953, "Add to Cam Favorites")
    command = (
        "RunPlugin({}?mode=90&action={}&site={}&username={}&label={}&url={}&thumb={})".format(
            sys.argv[0], action,
            urllib.parse.quote_plus(site or ""),
            urllib.parse.quote_plus(username or ""),
            urllib.parse.quote_plus(label or username or ""),
            urllib.parse.quote_plus(url or ""),
            urllib.parse.quote_plus(thumb or ""),
        )
    )
    return [(text, command)]


def add(site, username, label="", url="", thumb=""):
    if not site or not username:
        return
    data = _load()
    key = _key(site, username)
    previous = data["favorites"].get(key, {})
    now = int(time.time())
    data["favorites"][key] = {
        "site": site.lower(),
        "username": username,
        "label": label or username,
        "url": url,
        "thumb": thumb,
        "added_at": previous.get("added_at") or now,
        "last_seen": previous.get("last_seen") or 0,
        "last_online": previous.get("last_online") or now,
        "online": True,
    }
    _save(data)
    xbmcgui.Dialog().notification("AdultHideout", _text(30955, "Added to Cam Favorites"), xbmcgui.NOTIFICATION_INFO, 2500)


def remove(site, username):
    data = _load()
    if data["favorites"].pop(_key(site, username), None) is not None:
        _save(data)
    xbmcgui.Dialog().notification("AdultHideout", _text(30956, "Removed from Cam Favorites"), xbmcgui.NOTIFICATION_INFO, 2500)


def touch(site, username):
    data = _load()
    entry = data["favorites"].get(_key(site, username))
    if entry:
        entry["last_seen"] = int(time.time())
        _save(data)


def _add_group(site, label, group, icon, fanart):
    item = xbmcgui.ListItem(label)
    item.setArt({"thumb": icon, "icon": icon, "poster": icon, "fanart": fanart})
    url = "{}?mode=2&website={}&url={}".format(
        sys.argv[0], urllib.parse.quote_plus(site), urllib.parse.quote_plus(PREFIX + group)
    )
    xbmcplugin.addDirectoryItem(int(sys.argv[1]), url, item, isFolder=True)


def _offline_item(site_object, entry):
    label = "[COLOR grey]{}[/COLOR]".format(entry.get("label") or entry.get("username"))
    item = xbmcgui.ListItem(label)
    thumb = entry.get("thumb") or site_object.icon
    item.setArt({"thumb": thumb, "icon": thumb, "poster": thumb, "fanart": site_object.fanart})
    item.setInfo("video", {"title": entry.get("username") or label, "plot": _text(30961, "Currently offline")})
    item.addContextMenuItems(context_menu(site_object.name, entry.get("username"), entry.get("label"), entry.get("url"), thumb))
    xbmcplugin.addDirectoryItem(site_object.addon_handle, "", item, isFolder=False)


def show(site_object, group="root"):
    if group == "root":
        _add_group(site_object.name, _text(30958, "Online"), "online", site_object.icon, site_object.fanart)
        _add_group(site_object.name, _text(30959, "Offline"), "offline", site_object.icon, site_object.fanart)
        _add_group(site_object.name, _text(30960, "Recently Seen"), "recent", site_object.icon, site_object.fanart)
        _add_group(site_object.name, _text(30933, "All"), "all", site_object.icon, site_object.fanart)
        site_object.end_directory("videos")
        return

    data = _load()
    entries = [entry for entry in data["favorites"].values() if entry.get("site") == site_object.name]
    live = site_object.get_cam_favorite_status(entries) if entries else {}
    now = int(time.time())
    for entry in entries:
        model = live.get((entry.get("username") or "").lower())
        entry["online"] = bool(model)
        if model:
            entry["last_online"] = now
            entry["label"] = model.get("username") or entry.get("label")
    _save(data)

    if group == "online":
        entries = [entry for entry in entries if entry.get("online")]
    elif group == "offline":
        entries = [entry for entry in entries if not entry.get("online")]
    elif group == "recent":
        entries = [entry for entry in entries if int(entry.get("last_seen") or 0) > 0]
        entries.sort(key=lambda entry: int(entry.get("last_seen") or 0), reverse=True)
    else:
        entries.sort(key=lambda entry: (not entry.get("online"), (entry.get("label") or "").lower()))

    for entry in entries:
        model = live.get((entry.get("username") or "").lower())
        if model:
            site_object.add_cam_favorite_model(model)
        else:
            _offline_item(site_object, entry)
    if not entries:
        xbmcgui.Dialog().notification("AdultHideout", _text(30962, "No Cam Favorites in this group"), xbmcgui.NOTIFICATION_INFO, 2500)
    site_object.end_directory("videos")


def handle(params):
    action = params.get("action")
    if action == "add":
        add(params.get("site"), params.get("username"), params.get("label"), params.get("url"), params.get("thumb"))
    elif action == "remove":
        remove(params.get("site"), params.get("username"))
    xbmc.executebuiltin("Container.Refresh")
