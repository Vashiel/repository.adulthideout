# -*- coding: utf-8 -*-
"""Stub of the xbmcaddon module: an in-memory settings store per addon id."""

import json
import os
import tempfile

ADDON_ID = "plugin.video.adulthideout"
_ADDON_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "plugin.video.adulthideout"))
# Never inside the checkout: modules write page caches and clearances into their profile.
_PROFILE_PATH = os.path.join(tempfile.gettempdir(), "adulthideout-headless-profile")
_STORE = {}
_CALLS = []

# id -> addon directory, for harnesses that run more than one addon in one process.
PATHS = {}


def set_addon_path(path):
    global _ADDON_PATH
    _ADDON_PATH = path


def set_settings(values):
    _STORE.clear()
    _STORE.update({str(k): str(v) for k, v in (values or {}).items()})


def load_settings(path):
    if path and os.path.exists(path):
        with open(path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
        set_settings(payload.get("settings") if isinstance(payload, dict) and "settings" in payload else payload)
        return True
    return False


def settings_snapshot():
    return dict(_STORE)


def calls():
    return list(_CALLS)


class Addon(object):
    def __init__(self, id=None, *args, **kwargs):
        self.id = id or ADDON_ID
        self._settings = _STORE

    def getAddonInfo(self, key):
        addon_path = PATHS.get(self.id) or _ADDON_PATH
        profile_path = PATHS.get("__profile__") or _PROFILE_PATH
        return {
            "id": self.id,
            "name": self.id,
            "version": "0.0.0",
            "path": addon_path,
            "profile": profile_path,
            "icon": os.path.join(addon_path, "icon.png"),
            "fanart": os.path.join(addon_path, "fanart.jpg"),
            "author": "headless",
        }.get(key, "")

    def getSetting(self, key):
        return self._settings.get(key, "")

    def getSettingString(self, key):
        return self._settings.get(key, "")

    def getSettingBool(self, key):
        return str(self._settings.get(key, "")).lower() in ("true", "1", "yes")

    def getSettingInt(self, key):
        try:
            return int(self._settings.get(key, 0))
        except (TypeError, ValueError):
            return 0

    def getSettingNumber(self, key):
        try:
            return float(self._settings.get(key, 0))
        except (TypeError, ValueError):
            return 0.0

    def setSetting(self, key, value):
        self._settings[str(key)] = str(value)
        _CALLS.append((self.id, str(key), str(value)))

    def setSettingString(self, key, value):
        self.setSetting(key, value)

    def setSettingBool(self, key, value):
        self.setSetting(key, "true" if value else "false")

    def setSettingInt(self, key, value):
        self.setSetting(key, value)

    def getLocalizedString(self, string_id):
        return str(string_id)

    def openSettings(self):
        return None

    def getAddonInfoPath(self):
        return _ADDON_PATH


def __getattr__(name):
    def _noop(*args, **kwargs):
        return ""
    return _noop
