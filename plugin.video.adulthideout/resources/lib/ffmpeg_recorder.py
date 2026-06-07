# -*- coding: utf-8 -*-

import os
import re
import shutil
import subprocess
import sys
import urllib.parse

import xbmc
import xbmcgui
import xbmcvfs


def _localized(addon, string_id, fallback):
    try:
        value = addon.getLocalizedString(string_id)
        return value or fallback
    except Exception:
        return fallback


def is_enabled(addon):
    try:
        return addon.getSetting("enable_ffmpeg_recorder") == "true"
    except Exception:
        return False


def add_record_context(website, context_menu, video_url, title):
    if not is_enabled(website.addon):
        return context_menu

    items = list(context_menu or [])
    command = (
        "RunPlugin({base}?mode=7&action=download_with_ffmpeg&website={website}"
        "&original_url={url}&name={title})"
    ).format(
        base=sys.argv[0],
        website=urllib.parse.quote_plus(website.name),
        url=urllib.parse.quote_plus(video_url or ""),
        title=urllib.parse.quote_plus(title or ""),
    )
    label = _localized(website.addon, 30633, "Video herunterladen")
    items.append((label, command))
    return items


def record_with_ffmpeg(website, page_url, title=None):
    addon = website.addon
    if not is_enabled(addon):
        _notify(addon, 30634, "FFmpeg recorder is disabled.", error=True)
        return False

    ffmpeg = _resolve_ffmpeg_path(addon)
    if not ffmpeg:
        _notify(addon, 30635, "FFmpeg executable was not found.", error=True)
        return False

    resolver = getattr(website, "resolve_recording_stream", None)
    if not resolver:
        _notify(addon, 30637, "Could not resolve a direct stream for recording.", error=True)
        return False

    result = resolver(page_url)
    stream_url, headers, extension = _normalize_result(result)
    if not stream_url:
        _notify(addon, 30637, "Could not resolve a direct stream for recording.", error=True)
        return False

    download_dir = _resolve_download_dir(addon)
    if not download_dir:
        _notify(addon, 30638, "Recording download folder could not be created.", error=True)
        return False

    filename = _safe_filename(title or _title_from_url(page_url) or website.name)
    extension = extension or _extension_from_url(stream_url)
    output_path = _unique_path(os.path.join(download_dir, filename + "." + extension))
    log_path = output_path + ".log"
    command = _build_command(ffmpeg, stream_url, headers, output_path)

    try:
        log_file = open(log_path, "ab")
        startupinfo = None
        creationflags = 0
        if os.name == "nt":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        subprocess.Popen(
            command,
            stdin=subprocess.DEVNULL,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            startupinfo=startupinfo,
            creationflags=creationflags,
        )
        log_file.close()
    except Exception as exc:
        try:
            log_file.close()
        except Exception:
            pass
        xbmc.log("[AdultHideout] FFmpeg recorder failed: {}".format(exc), xbmc.LOGERROR)
        xbmcgui.Dialog().notification("AdultHideout", str(exc), xbmcgui.NOTIFICATION_ERROR, 6000)
        return False

    message = _localized(addon, 30636, "Recording started: {}").format(os.path.basename(output_path))
    xbmcgui.Dialog().notification("AdultHideout", message, xbmcgui.NOTIFICATION_INFO, 5000)
    xbmc.log("[AdultHideout] FFmpeg recorder started: {}".format(output_path), xbmc.LOGINFO)
    return True


def _normalize_result(result):
    if isinstance(result, dict):
        return result.get("url"), result.get("headers") or {}, result.get("extension")
    if isinstance(result, (list, tuple)):
        url = result[0] if len(result) > 0 else None
        headers = result[1] if len(result) > 1 else {}
        extension = result[2] if len(result) > 2 else None
        return url, headers or {}, extension
    if isinstance(result, str):
        return result, {}, None
    return None, {}, None


def _build_command(ffmpeg, stream_url, headers, output_path):
    command = [ffmpeg, "-hide_banner", "-y", "-loglevel", "warning"]
    headers = dict(headers or {})
    if headers.get("User-Agent"):
        command.extend(["-user_agent", headers["User-Agent"]])
    if headers.get("Referer"):
        command.extend(["-referer", headers["Referer"]])
    header_lines = []
    for key in ("Cookie", "Origin", "Accept", "Accept-Language"):
        value = headers.get(key)
        if value:
            header_lines.append("{}: {}".format(key, value))
    if header_lines:
        command.extend(["-headers", "\r\n".join(header_lines) + "\r\n"])
    command.extend(["-i", stream_url, "-c", "copy", output_path])
    return command


def _resolve_ffmpeg_path(addon):
    configured = (addon.getSetting("ffmpeg_path") or "").strip().strip('"')
    if configured:
        translated = xbmcvfs.translatePath(configured)
        if os.path.isfile(translated):
            return translated
    for candidate in ("ffmpeg", "ffmpeg.exe"):
        found = shutil.which(candidate)
        if found:
            return found
    return ""


def _resolve_download_dir(addon):
    configured = (addon.getSetting("ffmpeg_download_folder") or "").strip()
    if configured:
        target = xbmcvfs.translatePath(configured)
    else:
        target = os.path.join(xbmcvfs.translatePath(addon.getAddonInfo("profile")), "recordings")
    try:
        if not xbmcvfs.exists(target):
            xbmcvfs.mkdirs(target)
        if not xbmcvfs.exists(target):
            os.makedirs(target, exist_ok=True)
        return target if xbmcvfs.exists(target) or os.path.isdir(target) else ""
    except Exception:
        return ""


def _safe_filename(value):
    value = re.sub(r"\[[^\]]+\]", " ", value or "")
    value = re.sub(r"[\\/:*?\"<>|]+", " ", value)
    value = re.sub(r"\s+", " ", value).strip(" .")
    return (value or "recording")[:120]


def _title_from_url(url):
    path = urllib.parse.urlparse(url or "").path.rstrip("/")
    slug = urllib.parse.unquote(path.split("/")[-1] if path else "")
    return slug.replace("-", " ").replace("_", " ").strip()


def _extension_from_url(url):
    path = urllib.parse.urlparse(url or "").path.lower()
    if ".m3u8" in path:
        return "mp4"
    match = re.search(r"\.([a-z0-9]{2,5})(?:$|[?#])", path)
    if match and match.group(1) in ("mp4", "mkv", "webm", "mov"):
        return match.group(1)
    return "mp4"


def _unique_path(path):
    if not os.path.exists(path):
        return path
    root, ext = os.path.splitext(path)
    idx = 2
    while True:
        candidate = "{} ({}){}".format(root, idx, ext)
        if not os.path.exists(candidate):
            return candidate
        idx += 1


def _notify(addon, string_id, fallback, error=False):
    message = _localized(addon, string_id, fallback)
    icon = xbmcgui.NOTIFICATION_ERROR if error else xbmcgui.NOTIFICATION_INFO
    xbmcgui.Dialog().notification("AdultHideout", message, icon, 5000)
