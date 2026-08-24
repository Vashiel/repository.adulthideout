# -*- coding: utf-8 -*-

import os
import sys
import time
import threading

# Ensure addon root directory and lib directory are in sys.path
_curr_file = os.path.abspath(__file__)
_lib_dir = os.path.dirname(_curr_file)
_res_dir = os.path.dirname(_lib_dir)
_addon_root = os.path.dirname(_res_dir)

for _p in (_addon_root, _lib_dir, os.path.join(_lib_dir, "vendor")):
    if _p and _p not in sys.path:
        sys.path.insert(0, _p)

import xbmc
import xbmcaddon
import xbmcgui

ADDON_ID = "plugin.video.adulthideout"
ADDON = xbmcaddon.Addon(ADDON_ID)

try:
    from resources.lib.view_utils import apply_view_mode
    from resources.lib.thumb_proxy import ThumbProxy
except ImportError:
    try:
        from view_utils import apply_view_mode
        from thumb_proxy import ThumbProxy
    except Exception as exc:
        xbmc.log(f"[AdultHideout][ViewService] Warning importing modules: {exc}", xbmc.LOGWARNING)
        apply_view_mode = lambda *args, **kwargs: None
        ThumbProxy = None


RUNNING_PROPERTY = "AdultHideout.ViewServiceRunning"
VERSION_PROPERTY = "AdultHideout.ViewServiceVersion"
SERVICE_VERSION = "35"
PENDING_SECONDS = 60
STALL_TIMEOUT_SECONDS = 6.0

_SEEN_CHANNEL_URLS = set()
_CHANNEL_PAGES = {}
_IS_REFILLING = False
_STOPPED_SINCE = None


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


def _refill_smart_playlist(channel, playlist):
    global _SEEN_CHANNEL_URLS, _CHANNEL_PAGES, _IS_REFILLING
    if _IS_REFILLING:
        return 0
    _IS_REFILLING = True
    try:
        try:
            from resources.lib.smart_playlists import SmartPlaylists, is_query_relevance_match
        except ImportError:
            from smart_playlists import SmartPlaylists, is_query_relevance_match
        spl = SmartPlaylists(addon_handle=-1, plugin_url=f"plugin://{ADDON_ID}/", addon=ADDON)

        current_page = _CHANNEL_PAGES.get(channel, 1) + 1
        _CHANNEL_PAGES[channel] = current_page

        fresh_videos = spl._get_channel_videos(channel, force_refresh=True, page=current_page)
        if not fresh_videos and current_page > 2:
            _CHANNEL_PAGES[channel] = 1
            fresh_videos = spl._get_channel_videos(channel, force_refresh=True, page=1)

        if channel.startswith("custom_"):
            stream = spl._get_temp_stream(channel) or {}
            required_queries = stream.get("stars") or [stream.get("query", "")]
            required_queries = [query for query in required_queries if query]
            if required_queries:
                fresh_videos = [
                    item for item in fresh_videos
                    if any(
                        is_query_relevance_match(query, item.get("title", ""))[0]
                        for query in required_queries
                    )
                ]

        if not fresh_videos:
            return 0

        # Filter out already played URLs
        new_items = [it for it in fresh_videos if it.get("target_url") and it.get("target_url") not in _SEEN_CHANNEL_URLS]

        if len(new_items) < 5:
            _SEEN_CHANNEL_URLS.clear()
            # Even after resetting the seen-set, never re-queue a video that is
            # still sitting in the live Kodi playlist - that reintroduces the
            # exact item that just failed/stalled right behind itself, which
            # causes the same broken stream to be retried against a proxy that
            # was already torn down.
            try:
                queued_urls = {playlist[i].getfilename() for i in range(len(playlist))}
            except Exception:
                queued_urls = set()
            new_items = [it for it in fresh_videos if it.get("target_url") not in queued_urls]

        added_count = 0
        for item in new_items:
            target_url = item.get("target_url", "")
            if not target_url:
                continue
            _SEEN_CHANNEL_URLS.add(target_url)

            label = item.get("title", "Video")
            source = item.get("website", "")
            display_label = f"[COLOR yellow][{source}][/COLOR] {label}" if (source and not label.startswith("[")) else label
            li = xbmcgui.ListItem(label=display_label, path=target_url)
            thumb = item.get("thumbnail") or spl.icon
            li.setArt({"thumb": thumb, "icon": thumb, "fanart": spl.fanart})
            li.setProperty("IsPlayable", "true")
            li.setInfo("video", {"title": display_label, "mediatype": "video"})
            playlist.add(target_url, li)
            added_count += 1
            if added_count >= 20:
                break

        if added_count > 0:
            _log("24/7 Smart Stream: Pushed {} fresh videos from Page {} (Queue size: {})".format(
                added_count, current_page, len(playlist)
            ))
        return added_count
    except Exception as exc:
        _log("Error auto-refilling smart playlist: {}".format(exc), xbmc.LOGWARNING)
        return 0
    finally:
        _IS_REFILLING = False


class SmartPlayerMonitor(xbmc.Player):
    def __init__(self):
        super(SmartPlayerMonitor, self).__init__()
        self.is_paused = False
        self.last_playback_time = -999
        self.stuck_since = None
        self.grace_until = 0
        self.av_started = False
        self.recover_at = None
        self.skip_requested = False

    def onAVStarted(self):
        global _STOPPED_SINCE
        _STOPPED_SINCE = None
        self.av_started = True
        self.recover_at = None
        self.skip_requested = False
        self.last_playback_time = -999
        self.stuck_since = None
        self.grace_until = time.time() + 6.0
        if xbmcgui.Window(10000).getProperty("AdultHideout.SmartChannel"):
            xbmc.executebuiltin("ActivateWindow(fullscreenvideo)")
        self._check_and_refill()

    def onPlayBackStarted(self):
        global _STOPPED_SINCE
        _STOPPED_SINCE = None
        self.av_started = False
        self.last_playback_time = -999
        self.stuck_since = None
        self.grace_until = time.time() + 6.0
        self._check_and_refill()

    def onPlayBackSeek(self, time_offset, seek_offset):
        self.last_playback_time = -999
        self.stuck_since = None
        self.grace_until = time.time() + 5.0

    def _check_and_refill(self):
        try:
            active_channel = xbmcgui.Window(10000).getProperty("AdultHideout.SmartChannel")
            if not active_channel:
                return
            playlist = xbmc.PlayList(xbmc.PLAYLIST_VIDEO)
            size = len(playlist)
            pos = playlist.getposition()
            remaining_ahead = size - pos if pos >= 0 else size
            if remaining_ahead < 15 or size < 20:
                threading.Thread(target=_refill_smart_playlist, args=(active_channel, playlist)).start()
        except Exception:
            pass

    def onPlayBackPaused(self):
        self.is_paused = True
        self.stuck_since = None

    def onPlayBackResumed(self):
        self.is_paused = False
        self.stuck_since = None
        self.grace_until = time.time() + 4.0

    def onPlayBackError(self):
        active_channel = xbmcgui.Window(10000).getProperty("AdultHideout.SmartChannel")
        if active_channel:
            _log("Playback error on smart channel - auto skipping to next video")
            self.stuck_since = None
            self.last_playback_time = -999
            self.grace_until = time.time() + 6.0
            self.skip_requested = True
            self.av_started = False
            self.recover_at = time.time() + 0.5

    def onPlayBackStopped(self):
        global _STOPPED_SINCE
        self.is_paused = False
        self.stuck_since = None
        self.last_playback_time = -999
        active_channel = xbmcgui.Window(10000).getProperty("AdultHideout.SmartChannel")
        if active_channel and (self.skip_requested or not self.av_started):
            self.recover_at = time.time() + 0.5
            _STOPPED_SINCE = None
            return

        # A stop after AV playback began is an explicit user stop.
        window = xbmcgui.Window(10000)
        window.clearProperty("AdultHideout.SmartChannel")
        window.clearProperty("AdultHideout.LastQueuedSize")
        self.av_started = False
        self.recover_at = None
        self.skip_requested = False
        _STOPPED_SINCE = None

    def onPlayBackEnded(self):
        global _STOPPED_SINCE
        self.is_paused = False
        self.stuck_since = None
        self.last_playback_time = -999
        self.av_started = False
        self.skip_requested = True
        self.recover_at = time.time() + 1.0
        _STOPPED_SINCE = None
        self._check_and_refill()


def run():
    global _SEEN_CHANNEL_URLS, _CHANNEL_PAGES, _STOPPED_SINCE
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
    player_monitor = SmartPlayerMonitor()
    thumb_proxy = ThumbProxy() if ThumbProxy else None

    try:
        if thumb_proxy:
            if not thumb_proxy.start():
                _log("thumbnail proxy unavailable", xbmc.LOGWARNING)
        _log("started version {}".format(SERVICE_VERSION))

        last_refill_check = 0
        last_stall_check = 0
        last_channel_name = ""

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

            now = time.time()
            active_channel = window.getProperty("AdultHideout.SmartChannel")

            if active_channel and player_monitor.isPlaying():
                _STOPPED_SINCE = None
                if active_channel != last_channel_name:
                    last_channel_name = active_channel
                    _SEEN_CHANNEL_URLS.clear()
                    _CHANNEL_PAGES[active_channel] = 1
                    player_monitor.grace_until = now + 6.0

                # 1. Precise Stall / Buffer Watchdog with startup buffer immunity
                if now - last_stall_check >= 1.0:
                    last_stall_check = now
                    try:
                        cur_time = round(player_monitor.getTime(), 1)
                    except Exception:
                        cur_time = -1

                    # Only evaluate stall after initial startup buffering grace period has ended
                    if not player_monitor.is_paused and now >= player_monitor.grace_until:
                        if cur_time > 0 and cur_time == player_monitor.last_playback_time:
                            if not player_monitor.stuck_since:
                                player_monitor.stuck_since = now
                            elif now - player_monitor.stuck_since >= STALL_TIMEOUT_SECONDS:
                                _log("Stream stall/freeze confirmed (>6s at {:.1f}s). Skipping silently to next video".format(cur_time))
                                player_monitor.stuck_since = None
                                player_monitor.last_playback_time = -999
                                player_monitor.grace_until = now + 7.0
                                player_monitor.skip_requested = True
                                player_monitor.av_started = False
                                player_monitor.recover_at = now + 0.5
                                xbmc.executebuiltin("PlayerControl(Next)")
                        else:
                            player_monitor.stuck_since = None
                            player_monitor.last_playback_time = cur_time
                    else:
                        player_monitor.stuck_since = None

                # 2. Infinite 24/7 Deep Buffer Refill (every 1.5s)
                if now - last_refill_check >= 1.5:
                    last_refill_check = now
                    try:
                        playlist = xbmc.PlayList(xbmc.PLAYLIST_VIDEO)
                        size = len(playlist)
                        pos = playlist.getposition()
                        remaining_ahead = size - pos if pos >= 0 else size
                        if remaining_ahead < 15 or size < 20:
                            threading.Thread(target=_refill_smart_playlist, args=(active_channel, playlist)).start()
                    except Exception:
                        pass
            elif not player_monitor.isPlaying() and active_channel:
                if player_monitor.recover_at and now >= player_monitor.recover_at:
                    _log("Smart channel idle after failed item - advancing to next video")
                    # Retry once more if Kodi ignores Next without emitting a callback.
                    player_monitor.recover_at = now + 5.0
                    player_monitor.grace_until = now + 7.0
                    player_monitor._check_and_refill()
                    xbmc.executebuiltin("PlayerControl(Next)")

            if monitor.waitForAbort(0.5):
                break
    finally:
        if thumb_proxy:
            thumb_proxy.stop()
        window.clearProperty(RUNNING_PROPERTY)
        window.clearProperty(VERSION_PROPERTY)
        _log("stopped")


if __name__ == "__main__":
    run()
