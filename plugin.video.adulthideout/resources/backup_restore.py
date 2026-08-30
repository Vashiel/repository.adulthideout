#!/usr/bin/env python
# -*- coding: utf-8 -*-

import datetime
import json
import os
import xml.etree.ElementTree as ET

import xbmcaddon
import xbmcgui
import xbmcvfs


ADDON = xbmcaddon.Addon("plugin.video.adulthideout")
FORMAT = "AdultHideout Complete Backup"
FORMAT_VERSION = 1
PROFILE_FILES = (
    "vault.json",
    "custom_collections.json",
    "queries.json",
    "custom_streams.json",
    "performer_matrix.json",
    "playback_history.json",
    "cam_favorites.json",
)
GLOBAL_SEARCH_KEYS = (
    "history",
    "last_query",
    "history_modes",
    "result_options",
    "profile",
    "sources",
    "custom_label",
    "custom_presets",
)
SENSITIVE_SETTING_PARTS = (
    "password", "passwd", "secret", "token", "credential", "cookie",
    "api_key", "apikey", "username", "user_name", "path", "folder",
    "directory", "_url", "url_",
)
NON_PORTABLE_SETTINGS = {
    "aria2_rpc_url",
    "aria2_secret",
    "aria2_directory",
    "jdownloader_url",
    "ffmpeg_path",
    "ffmpeg_download_folder",
    "download_folder",
    "offline_library_folder",
}


def _text(string_id, fallback):
    return ADDON.getLocalizedString(string_id) or fallback


def _profile_dir():
    path = xbmcvfs.translatePath(ADDON.getAddonInfo("profile"))
    if not os.path.isdir(path):
        os.makedirs(path, exist_ok=True)
    return path


def _read_json(path, default=None):
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, ValueError, TypeError):
        return default


def _atomic_json_write(path, value):
    temporary = path + ".restore.tmp"
    with open(temporary, "w", encoding="utf-8") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
    os.replace(temporary, path)


def _portable_setting_ids():
    settings_path = os.path.join(ADDON.getAddonInfo("path"), "resources", "settings.xml")
    try:
        root = ET.parse(settings_path).getroot()
    except (OSError, ET.ParseError):
        return []
    result = []
    for node in root.findall(".//setting"):
        setting_id = node.get("id") or ""
        lowered = setting_id.lower()
        if not setting_id or node.get("type") == "action":
            continue
        if setting_id in NON_PORTABLE_SETTINGS:
            continue
        if any(part in lowered for part in SENSITIVE_SETTING_PARTS):
            continue
        if any(part in lowered for part in ("migrated", "accepted", "disclaimer")):
            continue
        result.append(setting_id)
    return sorted(set(result))


def _build_backup():
    profile = _profile_dir()
    files = {}
    for filename in PROFILE_FILES:
        value = _read_json(os.path.join(profile, filename))
        if isinstance(value, (dict, list)):
            files[filename] = value

    global_state = _read_json(os.path.join(profile, "global_search.json"), {})
    global_search = {}
    if isinstance(global_state, dict):
        for key in GLOBAL_SEARCH_KEYS:
            if key in global_state:
                global_search[key] = global_state[key]

    settings = {setting_id: ADDON.getSetting(setting_id) for setting_id in _portable_setting_ids()}
    return {
        "format": FORMAT,
        "format_version": FORMAT_VERSION,
        "created_utc": datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
        "addon_version": ADDON.getAddonInfo("version"),
        "data": {
            "profile_files": files,
            "global_search": global_search,
            "settings": settings,
        },
    }


def _write_vfs(path, payload):
    handle = xbmcvfs.File(path, "w")
    try:
        written = handle.write(payload)
    finally:
        handle.close()
    return written is not False


def export_backup():
    dialog = xbmcgui.Dialog()
    try:
        folder = dialog.browseSingle(3, _text(30946, "Choose backup folder"), "files", "", False, False, "")
    except AttributeError:
        folder = dialog.browse(3, _text(30946, "Choose backup folder"), "files")
    if not folder:
        return
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    filename = "AdultHideout-Complete-Backup-{}.json".format(stamp)
    target = folder.rstrip("/\\") + "/" + filename
    payload = json.dumps(_build_backup(), ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if _write_vfs(target, payload):
        dialog.notification("AdultHideout", _text(30948, "Complete backup exported"), xbmcgui.NOTIFICATION_INFO, 4000)
    else:
        dialog.notification("AdultHideout", _text(30950, "Backup operation failed"), xbmcgui.NOTIFICATION_ERROR, 4000)


def _read_vfs(path):
    handle = xbmcvfs.File(path)
    try:
        return handle.read()
    finally:
        handle.close()


def restore_backup():
    dialog = xbmcgui.Dialog()
    try:
        source = dialog.browseSingle(1, _text(30947, "Choose backup file"), "files", ".json", False, False, "")
    except AttributeError:
        source = dialog.browse(1, _text(30947, "Choose backup file"), "files", ".json")
    if not source:
        return
    try:
        backup = json.loads(_read_vfs(source))
    except (ValueError, TypeError, OSError):
        backup = None
    if not isinstance(backup, dict) or backup.get("format") != FORMAT or backup.get("format_version") != FORMAT_VERSION:
        dialog.notification("AdultHideout", _text(30950, "Invalid backup file"), xbmcgui.NOTIFICATION_ERROR, 4000)
        return
    if not dialog.yesno("AdultHideout", _text(30951, "Replace the backed-up AdultHideout data and settings?")):
        return

    data = backup.get("data") or {}
    profile = _profile_dir()
    for filename, value in (data.get("profile_files") or {}).items():
        if filename in PROFILE_FILES and isinstance(value, (dict, list)):
            _atomic_json_write(os.path.join(profile, filename), value)

    imported_search = data.get("global_search") or {}
    if isinstance(imported_search, dict):
        state_path = os.path.join(profile, "global_search.json")
        state = _read_json(state_path, {})
        if not isinstance(state, dict):
            state = {}
        for key in GLOBAL_SEARCH_KEYS:
            if key in imported_search:
                state[key] = imported_search[key]
        state["result_cache"] = {}
        _atomic_json_write(state_path, state)

    allowed = set(_portable_setting_ids())
    for setting_id, value in (data.get("settings") or {}).items():
        if setting_id in allowed and isinstance(value, (str, int, float, bool)):
            ADDON.setSetting(setting_id, str(value).lower() if isinstance(value, bool) else str(value))

    dialog.notification("AdultHideout", _text(30949, "Complete backup restored"), xbmcgui.NOTIFICATION_INFO, 5000)
    dialog.ok("AdultHideout", _text(30952, "Reopen AdultHideout to apply all restored settings."))


def run():
    options = (
        _text(30944, "Export complete backup"),
        _text(30945, "Restore complete backup"),
    )
    choice = xbmcgui.Dialog().select(_text(30943, "Complete Backup / Restore"), list(options))
    if choice == 0:
        export_backup()
    elif choice == 1:
        restore_backup()


if __name__ == "__main__":
    run()
