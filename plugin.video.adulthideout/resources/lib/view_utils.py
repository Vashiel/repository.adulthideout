# -*- coding: utf-8 -*-

import xbmc
import xbmcplugin
import xbmcvfs
import os
import sqlite3
import time


ADDON_ID = "plugin.video.adulthideout"
VIDEO_WINDOW_ID = 10025
VIEW_MODES = [
    50,  # List
    51,  # Poster
    55,  # Wide List
    500,  # Wall
    502,  # Fanart
]
VIEW_DB_MODES = [
    65586,  # List: 1 << 16 | 50
    65587,  # Poster: 1 << 16 | 51
    65591,  # Wide List: 1 << 16 | 55
    131572,  # Wall: 2 << 16 | 500
    131574,  # Fanart: 2 << 16 | 502
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


def get_db_view_mode(addon, default_index=2):
    index, _ = get_view_selection(addon, default_index=default_index)
    return VIEW_DB_MODES[index]


def get_content_type_for_view(addon, content_type="videos"):
    _, view_mode = get_view_selection(addon)
    if content_type == "videos" and view_mode in (50, 51):
        return "movies"
    return content_type


def _profile_path(path):
    try:
        return xbmcvfs.translatePath(path)
    except AttributeError:
        return xbmc.translatePath(path)


def _view_db_path():
    return os.path.join(_profile_path("special://profile/Database"), "ViewModes6.db")


def persist_view_mode(addon, log_success=True):
    db_view_mode = get_db_view_mode(addon)
    db_path = _view_db_path()
    if not os.path.exists(db_path):
        return False

    skin = xbmc.getSkinDir() or "skin.estuary"
    root_path = "plugin://{}/".format(ADDON_ID)
    like_path = "plugin://{}%".format(ADDON_ID)
    last_error = None

    for _ in range(4):
        try:
            con = sqlite3.connect(db_path, timeout=1.0)
            try:
                cur = con.cursor()
                cur.execute(
                    "update view set viewMode=? where window=? and skin=? and path like ?",
                    (db_view_mode, VIDEO_WINDOW_ID, skin, like_path),
                )
                cur.execute(
                    "update view set viewMode=? where window=? and skin=? and path=?",
                    (db_view_mode, VIDEO_WINDOW_ID, skin, root_path),
                )
                cur.execute(
                    "select count(*) from view where window=? and skin=? and path=?",
                    (VIDEO_WINDOW_ID, skin, root_path),
                )
                if cur.fetchone()[0] == 0:
                    cur.execute(
                        (
                            "insert into view "
                            "(window,path,viewMode,sortMethod,sortOrder,sortAttributes,skin) "
                            "values (?,?,?,?,?,?,?)"
                        ),
                        (VIDEO_WINDOW_ID, root_path, db_view_mode, 0, 1, 0, skin),
                    )
                con.commit()
                changes = con.total_changes
            finally:
                con.close()
            if log_success:
                xbmc.log(
                    "[AdultHideout][View] persisted ViewModes6.db viewMode={} changes={}".format(
                        db_view_mode, changes
                    ),
                    xbmc.LOGINFO,
                )
            return True
        except Exception as exc:
            last_error = exc
            time.sleep(0.2)

    xbmc.log(
        "[AdultHideout][View] could not persist ViewModes6.db: {}".format(last_error),
        xbmc.LOGWARNING,
    )
    return False


def _schedule_view_mode(view_mode):
    for suffix, delay in (("A", "00:01"), ("B", "00:02")):
        name = "AdultHideoutViewMode{}".format(suffix)
        xbmc.executebuiltin("CancelAlarm({},true)".format(name))
        xbmc.executebuiltin(
            "AlarmClock({},Container.SetViewMode({}),{},silent)".format(name, view_mode, delay)
        )


def apply_view_mode(
    addon,
    reason="runtime",
    content_type="",
    persist=True,
    schedule=True,
    log_success=True,
):
    view_index, view_mode = get_view_selection(addon)
    if persist:
        persist_view_mode(addon, log_success=log_success)
    if log_success:
        xbmc.log(
            "[AdultHideout][View] applying viewtype={} as SetViewMode({}) reason={} content={}".format(
                view_index, view_mode, reason, content_type
            ),
            xbmc.LOGINFO,
        )
    xbmc.executebuiltin("Container.SetViewMode({})".format(view_mode))
    if schedule:
        _schedule_view_mode(view_mode)
    return view_mode


def end_directory_with_view(addon_handle, addon, content_type="videos"):
    content_type = get_content_type_for_view(addon, content_type=content_type)
    xbmcplugin.setContent(addon_handle, content_type)
    xbmcplugin.endOfDirectory(addon_handle)
    apply_view_mode(
        addon,
        reason="directory_end",
        content_type=content_type,
        persist=True,
        schedule=True,
        log_success=False,
    )
