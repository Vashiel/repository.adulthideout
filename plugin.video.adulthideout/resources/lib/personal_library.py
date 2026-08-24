#!/usr/bin/env python
# -*- coding: utf-8 -*-

import hashlib
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

from resources.lib.view_utils import end_directory_with_view


SCHEMA_VERSION = 1
ITEMS_PER_PAGE = 50
DEFAULT_COLLECTION_ID = "watch_later"


def _addon():
    return xbmcaddon.Addon()


def _text(message_id, fallback, *args):
    value = _addon().getLocalizedString(message_id) or fallback
    return value.format(*args) if args else value


def _profile_path():
    path = xbmcvfs.translatePath(_addon().getAddonInfo("profile"))
    if not os.path.isdir(path):
        if not xbmcvfs.mkdirs(path):
            os.makedirs(path, exist_ok=True)
    return path


def _library_path():
    return os.path.join(_profile_path(), "vault.json")


def _empty_library():
    return {
        "version": SCHEMA_VERSION,
        "collections": [
            {
                "id": DEFAULT_COLLECTION_ID,
                "name": "Watch Later",
                "created_at": int(time.time()),
                "system": True,
            }
        ],
        "items": [],
    }


def _normalise(data):
    if not isinstance(data, dict):
        data = _empty_library()
    collections = data.get("collections")
    items = data.get("items")
    if not isinstance(collections, list):
        collections = []
    if not any(item.get("id") == DEFAULT_COLLECTION_ID for item in collections if isinstance(item, dict)):
        collections.insert(0, _empty_library()["collections"][0])
    data["version"] = SCHEMA_VERSION
    data["collections"] = [item for item in collections if isinstance(item, dict) and item.get("id")]
    data["items"] = [item for item in items if isinstance(item, dict) and item.get("id")] if isinstance(items, list) else []
    return data


def load_library():
    try:
        with open(_library_path(), "r", encoding="utf-8") as handle:
            return _normalise(json.load(handle))
    except (OSError, ValueError, TypeError):
        return _empty_library()


def save_library(data):
    data = _normalise(data)
    path = _library_path()
    temp_path = path + ".tmp"
    with open(temp_path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
    os.replace(temp_path, path)


def _item_id(target_url):
    return hashlib.sha256((target_url or "").encode("utf-8")).hexdigest()[:24]


def _collection_id(name):
    seed = "{}:{}".format(name, time.time())
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16]


def build_save_command(plugin_url, target_url, title, website="", thumbnail="", fanart="", kind="video"):
    params = {
        "mode": "40",
        "action": "save_item",
        "target_url": target_url or "",
        "title": title or "",
        "source": website or "",
        "thumbnail": thumbnail or "",
        "fanart": fanart or "",
        "kind": kind or "video",
    }
    return "RunPlugin({}?{})".format(plugin_url, urllib.parse.urlencode(params))


class PersonalLibrary:
    def __init__(self, addon_handle, plugin_url):
        self.addon_handle = addon_handle
        self.plugin_url = plugin_url
        self.addon = _addon()
        addon_path = self.addon.getAddonInfo("path")
        self.icon = os.path.join(addon_path, "resources", "logos", "vault.png")
        if not os.path.exists(self.icon):
            self.icon = os.path.join(addon_path, "resources", "logos", "icon.png")
        self.search_icon = os.path.join(addon_path, "resources", "logos", "search.png")
        self.fanart = os.path.join(addon_path, "resources", "logos", "fanart.jpg")

    def _url(self, action, **kwargs):
        params = {"mode": "40", "action": action}
        params.update({key: str(value) for key, value in kwargs.items() if value is not None})
        return "{}?{}".format(self.plugin_url, urllib.parse.urlencode(params))

    def _add_dir(self, label, action, icon=None, context=None, **kwargs):
        item = xbmcgui.ListItem(label=label)
        art = icon or self.icon
        item.setArt({"thumb": art, "icon": art, "fanart": self.fanart})
        if context:
            item.addContextMenuItems(context)
        xbmcplugin.addDirectoryItem(self.addon_handle, self._url(action, **kwargs), item, True)

    def _finish(self, content_type="videos"):
        end_directory_with_view(self.addon_handle, self.addon, content_type=content_type)

    def show_root(self):
        data = load_library()
        total = len(data["items"])
        self._add_dir("[COLOR cyan]{}[/COLOR]".format(_text(30701, "New Collection")), "new_collection")
        if total:
            self._add_dir("[COLOR yellow]{}[/COLOR] ({})".format(_text(30702, "All Items"), total), "show_collection", collection_id="all")
            self._add_dir(_text(30703, "Search Vault"), "search", icon=self.search_icon)
        for collection in data["collections"]:
            collection_id = collection["id"]
            count = sum(collection_id in item.get("collections", []) for item in data["items"])
            collection_name = (_text(30705, "Watch Later") if collection.get("system")
                               else collection.get("name", _text(30728, "Collection")))
            context = []
            if not collection.get("system"):
                context = [
                    (_text(30707, "Rename Collection"), "RunPlugin({})".format(self._url("rename_collection", collection_id=collection_id))),
                    (_text(30708, "Delete Collection"), "RunPlugin({})".format(self._url("delete_collection", collection_id=collection_id))),
                ]
            self._add_dir("{} [COLOR grey]{}[/COLOR]".format(collection_name, count), "show_collection", context=context, collection_id=collection_id)
        self._add_dir("[COLOR grey]{}[/COLOR]".format(_text(30704, "Backup / Restore")), "backup_menu")
        self._finish("files")

    def _choose_collection(self, data, allow_new=True):
        collections = data["collections"]
        labels = [(_text(30705, "Watch Later") if item.get("system")
                  else item.get("name", _text(30728, "Collection"))) for item in collections]
        if allow_new:
            labels.append("[{}]".format(_text(30701, "New Collection")))
        index = xbmcgui.Dialog().select(_text(30716, "Save to Collection"), labels)
        if index < 0:
            return None
        if allow_new and index == len(collections):
            return self._create_collection(data)
        return collections[index]["id"]

    def _create_collection(self, data, name=None):
        if not name:
            keyboard = xbmc.Keyboard("", _text(30715, "Collection name"))
            keyboard.doModal()
            if not keyboard.isConfirmed():
                return None
            name = keyboard.getText().strip()
        if not name:
            return None
        existing = next((item for item in data["collections"] if item.get("name", "").lower() == name.lower()), None)
        if existing:
            return existing["id"]
        collection_id = _collection_id(name)
        data["collections"].append({"id": collection_id, "name": name, "created_at": int(time.time())})
        return collection_id

    def new_collection(self):
        data = load_library()
        collection_id = self._create_collection(data)
        if collection_id:
            save_library(data)
            xbmcgui.Dialog().notification(_text(30700, "Vault"), _text(30717, "Collection created"), xbmcgui.NOTIFICATION_INFO, 2500)
        self.show_root()

    def save_item(self, params):
        if not params.get("target_url", "").strip():
            xbmcgui.Dialog().notification(_text(30700, "Vault"), _text(30726, "Item cannot be saved"), xbmcgui.NOTIFICATION_ERROR, 3000)
            return
        data = load_library()
        collection_id = self._choose_collection(data)
        if not collection_id:
            return
        saved = self._save_items(data, [params], collection_id)
        if saved:
            save_library(data)
            xbmcgui.Dialog().notification(_text(30700, "Vault"), _text(30718, "Saved: {}", params.get("title", "").strip() or _text(30729, "Saved item")), xbmcgui.NOTIFICATION_INFO, 2500)

    def _save_items(self, data, items, collection_id):
        saved = 0
        for params in items:
            target_url = str(params.get("target_url", "")).strip()
            if not target_url:
                continue
            title = str(params.get("title", "")).strip() or _text(30729, "Saved item")
            item_id = _item_id(target_url)
            item = next((entry for entry in data["items"] if entry["id"] == item_id), None)
            if item is None:
                item = {
                    "id": item_id,
                    "title": title,
                    "target_url": target_url,
                    "source": params.get("source", ""),
                    "thumbnail": params.get("thumbnail", ""),
                    "fanart": params.get("fanart", ""),
                    "kind": params.get("kind", "video"),
                    "collections": [],
                    "created_at": int(time.time()),
                }
                data["items"].append(item)
            else:
                for key, value in (
                    ("title", title),
                    ("source", params.get("source", "")),
                    ("thumbnail", params.get("thumbnail", "")),
                    ("fanart", params.get("fanart", "")),
                ):
                    if value:
                        item[key] = value
            if collection_id not in item["collections"]:
                item["collections"].append(collection_id)
                saved += 1
        return saved

    def save_items(self, items):
        data = load_library()
        collection_id = self._choose_collection(data)
        if not collection_id:
            return 0
        saved = self._save_items(data, items, collection_id)
        if saved:
            save_library(data)
            xbmcgui.Dialog().notification(_text(30700, "Vault"), _text(30730, "Saved {} items", saved), xbmcgui.NOTIFICATION_INFO, 3000)
        return saved

    def _collection_items(self, data, collection_id):
        if collection_id == "all":
            return list(data["items"])
        return [item for item in data["items"] if collection_id in item.get("collections", [])]

    def show_collection(self, collection_id, page=1, query=""):
        data = load_library()
        items = self._collection_items(data, collection_id)
        if query:
            needle = query.lower()
            items = [item for item in items if needle in item.get("title", "").lower() or needle in item.get("source", "").lower()]
        items.sort(key=lambda item: item.get("created_at", 0), reverse=True)
        try:
            page = max(1, int(page or 1))
        except (TypeError, ValueError):
            page = 1
        total_pages = max(1, (len(items) + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE)
        page = min(page, total_pages)
        start = (page - 1) * ITEMS_PER_PAGE
        if page > 1:
            self._add_dir("[COLOR cyan]{}[/COLOR] ({}/{})".format(_text(30711, "Previous Page"), page - 1, total_pages), "show_collection", collection_id=collection_id, page=page - 1, query=query)
        for entry in items[start:start + ITEMS_PER_PAGE]:
            self._add_saved_item(entry, collection_id)
        if page < total_pages:
            self._add_dir("[COLOR cyan]{}[/COLOR] ({}/{})".format(_text(30712, "Next Page"), page + 1, total_pages), "show_collection", collection_id=collection_id, page=page + 1, query=query)
        self._finish("videos")

    def _add_saved_item(self, entry, collection_id):
        source = entry.get("source", "")
        label = entry.get("title", _text(30729, "Saved item"))
        if source:
            label = "[COLOR yellow][{}][/COLOR] {}".format(source, label)
        item = xbmcgui.ListItem(label=label)
        thumb = entry.get("thumbnail") or self.icon
        item.setArt({"thumb": thumb, "icon": thumb, "fanart": entry.get("fanart") or self.fanart})
        is_folder = entry.get("kind") != "video"
        if not is_folder:
            item.setProperty("IsPlayable", "true")
        context = [
            (_text(30709, "Add to Another Collection"), "RunPlugin({})".format(self._url("move_item", item_id=entry["id"]))),
            (_text(30710, "Remove from Collection"), "RunPlugin({})".format(self._url("remove_item", item_id=entry["id"], collection_id=collection_id))),
            (_text(30731, "Delete from Vault"), "RunPlugin({})".format(self._url("remove_item", item_id=entry["id"], collection_id="all"))),
        ]
        item.addContextMenuItems(context)
        xbmcplugin.addDirectoryItem(self.addon_handle, entry.get("target_url", ""), item, is_folder)

    def search(self):
        keyboard = xbmc.Keyboard("", _text(30703, "Search Vault"))
        keyboard.doModal()
        if keyboard.isConfirmed() and keyboard.getText().strip():
            self.show_collection("all", query=keyboard.getText().strip())
        else:
            self.show_root()

    def move_item(self, item_id):
        data = load_library()
        item = next((entry for entry in data["items"] if entry["id"] == item_id), None)
        if not item:
            return
        collection_id = self._choose_collection(data)
        if collection_id and collection_id not in item.get("collections", []):
            item.setdefault("collections", []).append(collection_id)
            save_library(data)
        xbmc.executebuiltin("Container.Refresh")

    def remove_item(self, item_id, collection_id):
        data = load_library()
        item = next((entry for entry in data["items"] if entry["id"] == item_id), None)
        if not item:
            return
        if collection_id == "all":
            if not xbmcgui.Dialog().yesno(_text(30700, "Vault"), _text(30724, "Remove this item from all collections?")):
                return
            data["items"] = [entry for entry in data["items"] if entry["id"] != item_id]
        else:
            item["collections"] = [value for value in item.get("collections", []) if value != collection_id]
            if not item["collections"]:
                data["items"] = [entry for entry in data["items"] if entry["id"] != item_id]
        save_library(data)
        xbmc.executebuiltin("Container.Refresh")

    def rename_collection(self, collection_id):
        data = load_library()
        collection = next((item for item in data["collections"] if item["id"] == collection_id and not item.get("system")), None)
        if not collection:
            return
        keyboard = xbmc.Keyboard(collection.get("name", ""), _text(30707, "Rename Collection"))
        keyboard.doModal()
        if keyboard.isConfirmed() and keyboard.getText().strip():
            collection["name"] = keyboard.getText().strip()
            save_library(data)
        xbmc.executebuiltin("Container.Refresh")

    def delete_collection(self, collection_id):
        xbmc.log(f"[AdultHideout][Vault] delete_collection called for collection_id='{collection_id}'", xbmc.LOGINFO)
        data = load_library()
        collection = next((item for item in data["collections"] if item["id"] == collection_id and not item.get("system")), None)
        if not collection:
            xbmc.log(f"[AdultHideout][Vault] Collection '{collection_id}' not found or is system collection", xbmc.LOGWARNING)
            return
        if not xbmcgui.Dialog().yesno(_text(30700, "Vault"), _text(30727, "Delete collection '{}' ?", collection.get("name", ""))):
            xbmc.log(f"[AdultHideout][Vault] User cancelled deletion of collection '{collection.get('name')}'", xbmc.LOGINFO)
            return
        data["collections"] = [item for item in data["collections"] if item["id"] != collection_id]
        for item in data["items"]:
            item["collections"] = [value for value in item.get("collections", []) if value != collection_id]
        data["items"] = [item for item in data["items"] if item.get("collections")]
        save_library(data)
        xbmc.log(f"[AdultHideout][Vault] Successfully deleted collection '{collection.get('name')}' and updated vault.json", xbmc.LOGINFO)
        if xbmcgui:
            xbmcgui.Dialog().notification(_text(30700, "Vault"), f"Collection '{collection.get('name')}' deleted", xbmcgui.NOTIFICATION_INFO, 2000)
        xbmc.executebuiltin("Container.Refresh")

    def show_backup_menu(self):
        self._add_dir(_text(30713, "Export Vault Backup"), "export_backup")
        self._add_dir(_text(30714, "Restore Vault Backup"), "restore_backup")
        self._finish("files")

    def export_backup(self):
        dialog = xbmcgui.Dialog()
        try:
            folder = dialog.browseSingle(3, _text(30719, "Choose backup folder"), "files", "", False, False, "")
        except AttributeError:
            folder = dialog.browse(3, _text(30719, "Choose backup folder"), "files")
        if not folder:
            return self.show_backup_menu()
        target = folder.rstrip("/\\") + "/AdultHideout-Vault-Backup.json"
        payload = json.dumps(load_library(), ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        handle = xbmcvfs.File(target, "w")
        handle.write(payload)
        handle.close()
        xbmcgui.Dialog().notification(_text(30700, "Vault"), _text(30721, "Backup exported"), xbmcgui.NOTIFICATION_INFO, 3000)
        self.show_backup_menu()

    def restore_backup(self):
        dialog = xbmcgui.Dialog()
        try:
            source = dialog.browseSingle(1, _text(30720, "Choose Vault backup"), "files", ".json", False, False, "")
        except AttributeError:
            source = dialog.browse(1, _text(30720, "Choose Vault backup"), "files", ".json")
        if not source:
            return self.show_backup_menu()
        handle = xbmcvfs.File(source)
        payload = handle.read()
        handle.close()
        try:
            restored = _normalise(json.loads(payload))
        except (ValueError, TypeError):
            xbmcgui.Dialog().notification(_text(30700, "Vault"), _text(30723, "Invalid backup file"), xbmcgui.NOTIFICATION_ERROR, 3000)
            return self.show_backup_menu()
        if xbmcgui.Dialog().yesno(_text(30700, "Vault"), _text(30725, "Replace the current Vault with this backup?")):
            save_library(restored)
            xbmcgui.Dialog().notification(_text(30700, "Vault"), _text(30722, "Backup restored"), xbmcgui.NOTIFICATION_INFO, 3000)
            xbmc.executebuiltin("Container.Refresh")
            return
        self.show_backup_menu()

    def handle(self, action, params):
        if action in (None, "", "root"):
            return self.show_root()
        if action == "new_collection":
            return self.new_collection()
        if action == "save_item":
            return self.save_item(params)
        if action == "show_collection":
            return self.show_collection(params.get("collection_id", DEFAULT_COLLECTION_ID), params.get("page", 1), params.get("query", ""))
        if action == "search":
            return self.search()
        if action == "move_item":
            return self.move_item(params.get("item_id", ""))
        if action == "remove_item":
            return self.remove_item(params.get("item_id", ""), params.get("collection_id", "all"))
        if action == "rename_collection":
            return self.rename_collection(params.get("collection_id", ""))
        if action == "delete_collection":
            return self.delete_collection(params.get("collection_id", ""))
        if action == "backup_menu":
            return self.show_backup_menu()
        if action == "export_backup":
            return self.export_backup()
        if action == "restore_backup":
            return self.restore_backup()
        return self.show_root()
