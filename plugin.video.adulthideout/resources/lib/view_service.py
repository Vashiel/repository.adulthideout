# -*- coding: utf-8 -*-

import os
import sys
import time

import xbmc
import xbmcaddon
import xbmcgui


ADDON_ID = "plugin.video.adulthideout"
ADDON = xbmcaddon.Addon(ADDON_ID)
ADDON_PATH = ADDON.getAddonInfo("path")
if ADDON_PATH and ADDON_PATH not in sys.path:
    sys.path.insert(0, ADDON_PATH)

from resources.lib.view_utils import apply_view_mode


RUNNING_PROPERTY = "AdultHideout.ViewServiceRunning"
VERSION_PROPERTY = "AdultHideout.ViewServiceVersion"
SERVICE_VERSION = "9"
PENDING_SECONDS = 60


def _log(message, level=xbmc.LOGINFO):
    xbmc.log("[AdultHideout][ViewService] {}".format(message), level)


def _addon_container_active():
    path = xbmc.getInfoLabel("Container.FolderPath") or ""
    return path.startswith("plugin://{}/".format(ADDON_ID)) or path == "plugin://{}".format(ADDON_ID)


def _settings_visible():
    return (
        xbmc.getCondVisibility("Window.IsActive(addonsettings)")
        or xbmc.getCondVisibility("Window.IsVisible(addonsettings)")
    )


def _current_addon():
    return xbmcaddon.Addon(ADDON_ID)


def _current_viewtype():
    return _current_addon().getSetting("viewtype")


class ViewSettingsMonitor(xbmc.Monitor):
    def __init__(self):
        super(ViewSettingsMonitor, self).__init__()
        self.last_viewtype = _current_viewtype()
        self.pending_until = 0
        self.waiting_for_settings_close = False

    def _mark_pending_if_changed(self):
        current = _current_viewtype()
        if current != self.last_viewtype:
            self.last_viewtype = current
            self.pending_until = time.time() + PENDING_SECONDS
            self.waiting_for_settings_close = True
            _log("viewtype changed to {}; waiting for addon container".format(current))

    def apply_settings_change(self):
        apply_view_mode(
            _current_addon(),
            reason="settings_changed",
            persist=True,
            schedule=True,
            log_success=True,
        )
        xbmc.executebuiltin("Container.Refresh")
        _log("refreshed addon container after settings change")

    def onSettingsChanged(self):
        self._mark_pending_if_changed()


def run():
    window = xbmcgui.Window(10000)
    if (
        window.getProperty(RUNNING_PROPERTY) == "true"
        and window.getProperty(VERSION_PROPERTY) == SERVICE_VERSION
    ):
        _log("already running; exiting duplicate")
        return

    window.setProperty(RUNNING_PROPERTY, "true")
    window.setProperty(VERSION_PROPERTY, SERVICE_VERSION)
    monitor = ViewSettingsMonitor()
    _log("started")
    try:
        while not monitor.abortRequested():
            monitor._mark_pending_if_changed()

            addon_container_active = _addon_container_active()
            settings_visible = _settings_visible()
            if monitor.pending_until:
                if settings_visible:
                    monitor.pending_until = time.time() + PENDING_SECONDS
                elif addon_container_active:
                    monitor.apply_settings_change()
                    monitor.pending_until = 0
                    monitor.waiting_for_settings_close = False
                elif time.time() > monitor.pending_until:
                    _log("timed out waiting for addon container after settings change", xbmc.LOGWARNING)
                    monitor.pending_until = 0
                    monitor.waiting_for_settings_close = False

            if monitor.waitForAbort(0.5):
                break
    finally:
        window.clearProperty(RUNNING_PROPERTY)
        window.clearProperty(VERSION_PROPERTY)
        _log("stopped")


if __name__ == "__main__":
    run()
