# -*- coding: utf-8 -*-

import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.parse
import urllib.request
import uuid

import xbmc
import xbmcaddon
import xbmcgui
import xbmcplugin
import xbmcvfs


VIDEO_EXTENSIONS = ("mp4", "mkv", "webm", "mov", "ts")
VFS_PREFIXES = ("smb://", "nfs://")
JOB_STATES = ("queued", "running", "transferring", "submitted", "complete", "failed", "cancelled")
ADDON_ID = "plugin.video.adulthideout"


def _addon():
    # The background worker is launched through RunScript, where Kodi cannot
    # infer an add-on id. Always bind settings and profile paths explicitly.
    return xbmcaddon.Addon(ADDON_ID)


def _profile_path(*parts):
    root = xbmcvfs.translatePath(_addon().getAddonInfo("profile"))
    return os.path.join(root, *parts)


def _jobs_dir():
    path = _profile_path("downloads", "jobs")
    os.makedirs(path, exist_ok=True)
    return path


def _staging_dir():
    path = _profile_path("downloads", "staging")
    os.makedirs(path, exist_ok=True)
    return path


def _job_path(job_id):
    return os.path.join(_jobs_dir(), "{}.json".format(job_id))


def _cancel_path(job_id):
    return os.path.join(_jobs_dir(), "{}.cancel".format(job_id))


def is_cancel_requested(job_id):
    return os.path.exists(_cancel_path(job_id))


def load_job(job_id):
    try:
        with open(_job_path(job_id), "r", encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, ValueError, TypeError):
        return None


def save_job(job):
    job["updated"] = int(time.time())
    path = _job_path(job["id"])
    temp_path = path + ".tmp"
    with open(temp_path, "w", encoding="utf-8") as handle:
        json.dump(job, handle, ensure_ascii=False, indent=2, sort_keys=True)
    os.replace(temp_path, path)


def update_job(job_id, **changes):
    job = load_job(job_id)
    if not job:
        return None
    job.update(changes)
    save_job(job)
    return job


def update_job_for_run(job_id, run_token, **changes):
    job = load_job(job_id)
    if not job or job.get("run_token") != run_token or job.get("status") == "cancelled" or is_cancel_requested(job_id):
        return None
    job.update(changes)
    save_job(job)
    return job


def list_jobs():
    jobs = []
    try:
        names = os.listdir(_jobs_dir())
    except OSError:
        return jobs
    for name in names:
        if not name.endswith(".json"):
            continue
        job = load_job(name[:-5])
        if job:
            jobs.append(job)
    return sorted(jobs, key=lambda item: item.get("created", 0), reverse=True)


def add_download_context(website, context_menu, page_url, title, thumbnail=""):
    items = list(context_menu or [])
    params = {
        "mode": "30",
        "action": "enqueue",
        "website": website.name,
        "original_url": page_url or "",
        "name": title or "",
        "thumbnail": thumbnail or "",
    }
    command = "RunPlugin({}?{})".format(sys.argv[0], urllib.parse.urlencode(params))
    label = website.addon.getLocalizedString(30633) or "Download video"
    items.append((label, command))
    return items


def _notify(message, error=False):
    icon = xbmcgui.NOTIFICATION_ERROR if error else xbmcgui.NOTIFICATION_INFO
    xbmcgui.Dialog().notification("AdultHideout", str(message), icon, 5000)


def _setting(name, fallback=""):
    try:
        value = _addon().getSetting(name)
        return value if value != "" else fallback
    except Exception:
        return fallback


def _is_vfs(path):
    return (path or "").lower().startswith(VFS_PREFIXES)


def _join_path(folder, name):
    if _is_vfs(folder):
        return folder.rstrip("/\\") + "/" + name
    return os.path.join(xbmcvfs.translatePath(folder), name)


def _safe_filename(value):
    value = re.sub(r"\[[^\]]+\]", " ", value or "")
    value = re.sub(r"[\\/:*?\"<>|]+", " ", value)
    value = re.sub(r"\s+", " ", value).strip(" .")
    return (value or "video")[:120]


def _extension(stream_url, explicit=""):
    explicit = (explicit or "").lower().lstrip(".")
    if explicit in VIDEO_EXTENSIONS:
        return explicit
    path = urllib.parse.urlparse(stream_url or "").path.lower()
    if ".m3u8" in path:
        return "mp4"
    match = re.search(r"\.([a-z0-9]{2,5})$", path)
    if match and match.group(1) in VIDEO_EXTENSIONS:
        return match.group(1)
    return "mp4"


def _looks_hls(url):
    return ".m3u8" in (url or "").lower()


def _unique_destination(folder, filename):
    candidate = _join_path(folder, filename)
    if not xbmcvfs.exists(candidate):
        return candidate
    root, ext = os.path.splitext(filename)
    index = 2
    while True:
        candidate = _join_path(folder, "{} ({}){}".format(root, index, ext))
        if not xbmcvfs.exists(candidate):
            return candidate
        index += 1


def _write_probe(folder):
    probe = _join_path(folder, ".adulthideout-write-test-{}.tmp".format(uuid.uuid4().hex[:8]))
    try:
        if _is_vfs(folder):
            if not xbmcvfs.exists(folder):
                xbmcvfs.mkdirs(folder)
            handle = xbmcvfs.File(probe, "w")
            written = handle.write("AdultHideout")
            handle.close()
            ok = bool(written) and xbmcvfs.exists(probe)
            xbmcvfs.delete(probe)
            return ok
        path = xbmcvfs.translatePath(folder)
        os.makedirs(path, exist_ok=True)
        with open(probe, "wb") as handle:
            handle.write(b"AdultHideout")
        os.remove(probe)
        return True
    except Exception as exc:
        xbmc.log("[AdultHideout][downloads] destination probe failed: {}".format(exc), xbmc.LOGWARNING)
        try:
            xbmcvfs.delete(probe)
        except Exception:
            pass
        return False


def ensure_download_folder(interactive=True):
    addon = _addon()
    folder = (addon.getSetting("download_folder") or addon.getSetting("ffmpeg_download_folder") or "").strip()
    if folder and _write_probe(folder):
        if not addon.getSetting("download_folder"):
            addon.setSetting("download_folder", folder)
        return folder
    if not interactive:
        return ""
    heading = addon.getLocalizedString(30648) or "Choose a download folder"
    message = addon.getLocalizedString(30647) or "Choose where AdultHideout should save downloaded videos. Local, SMB and NFS folders are supported."
    if not xbmcgui.Dialog().yesno("AdultHideout", message):
        return ""
    try:
        folder = xbmcgui.Dialog().browseSingle(3, heading, "files", "", False, False, "")
    except AttributeError:
        folder = xbmcgui.Dialog().browse(3, heading, "files")
    folder = (folder or "").strip()
    if not folder:
        return ""
    if not _write_probe(folder):
        _notify(addon.getLocalizedString(30649) or "The selected folder is not writable.", error=True)
        return ""
    addon.setSetting("download_folder", folder)
    return folder


def normalize_resolved(result):
    if isinstance(result, dict):
        return result.get("url"), result.get("headers") or {}, result.get("extension") or ""
    if isinstance(result, (tuple, list)):
        return (
            result[0] if len(result) > 0 else None,
            result[1] if len(result) > 1 else {},
            result[2] if len(result) > 2 else "",
        )
    if isinstance(result, str):
        return result, {}, ""
    return None, {}, ""


def _backend_for(stream_url):
    values = ("auto", "internal", "ffmpeg", "aria2", "jdownloader")
    try:
        index = int(_setting("download_backend", "0"))
    except ValueError:
        index = 0
    requested = values[index] if 0 <= index < len(values) else "auto"
    if requested == "auto":
        return "ffmpeg" if _looks_hls(stream_url) else "internal"
    return requested


def _resolve_ffmpeg():
    configured = _setting("ffmpeg_path").strip().strip('"')
    if configured:
        configured = xbmcvfs.translatePath(configured)
        if os.path.isfile(configured):
            return configured
    for name in ("ffmpeg", "ffmpeg.exe"):
        found = shutil.which(name)
        if found:
            return found
    return ""


def enqueue_download(website, page_url, title="", thumbnail=""):
    folder = ensure_download_folder(interactive=True)
    if not folder:
        return False
    resolver = getattr(website, "resolve_recording_stream", None)
    if not resolver:
        _notify(_addon().getLocalizedString(30637) or "Could not resolve a downloadable stream.", error=True)
        return False
    try:
        stream_url, headers, explicit_extension = normalize_resolved(resolver(page_url))
    except Exception as exc:
        xbmc.log("[AdultHideout][downloads] resolve failed: {}".format(exc), xbmc.LOGERROR)
        stream_url = None
        headers = {}
        explicit_extension = ""
    if not stream_url:
        _notify(_addon().getLocalizedString(30637) or "Could not resolve a downloadable stream.", error=True)
        return False

    backend = _backend_for(stream_url)
    if backend == "internal" and _looks_hls(stream_url):
        _notify(_addon().getLocalizedString(30661) or "HLS downloads require FFmpeg.", error=True)
        return False
    if backend == "ffmpeg" and not _resolve_ffmpeg():
        _notify(_addon().getLocalizedString(30635) or "FFmpeg executable was not found.", error=True)
        return False

    extension = _extension(stream_url, explicit_extension)
    filename = _safe_filename(title or website.name) + "." + extension
    destination = _unique_destination(folder, filename)
    job = {
        "id": uuid.uuid4().hex,
        "created": int(time.time()),
        "updated": int(time.time()),
        "status": "queued",
        "backend": backend,
        "title": title or _safe_filename(filename),
        "website": website.name,
        "page_url": page_url or "",
        "stream_url": stream_url,
        "headers": dict(headers or {}),
        "extension": extension,
        "thumbnail": thumbnail or "",
        "folder": folder,
        "destination": destination,
        "progress": 0,
        "downloaded": 0,
        "total": 0,
        "error": "",
        "run_token": uuid.uuid4().hex,
    }
    save_job(job)

    if backend == "aria2":
        return _submit_aria2(job)
    if backend == "jdownloader":
        return _submit_jdownloader(job)
    worker = os.path.join(_addon().getAddonInfo("path"), "resources", "lib", "download_worker.py")
    xbmc.executebuiltin('RunScript("{}","{}","{}")'.format(worker, job["id"], job["run_token"]))
    _notify((_addon().getLocalizedString(30651) or "Download queued: {}").format(job["title"]))
    return True


def _json_rpc(url, method, params):
    payload = json.dumps({"jsonrpc": "2.0", "id": str(int(time.time() * 1000)), "method": method, "params": params}).encode("utf-8")
    request = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=10) as response:
        data = json.loads(response.read().decode("utf-8", "replace"))
    if data.get("error"):
        raise RuntimeError(data["error"].get("message") or str(data["error"]))
    return data.get("result")


def _aria2_params(method_params):
    secret = _setting("aria2_secret").strip()
    return (["token:" + secret] if secret else []) + list(method_params)


def _submit_aria2(job):
    endpoint = _setting("aria2_rpc_url", "http://127.0.0.1:6800/jsonrpc").strip()
    options = {"out": os.path.basename(job["destination"])}
    remote_dir = _setting("aria2_directory").strip()
    if remote_dir:
        options["dir"] = remote_dir
    headers = ["{}: {}".format(key, value) for key, value in job.get("headers", {}).items() if value]
    if headers:
        options["header"] = headers
    try:
        gid = _json_rpc(endpoint, "aria2.addUri", _aria2_params([[job["stream_url"]], options]))
        update_job(job["id"], status="submitted", external_id=gid, progress=0)
        _notify((_addon().getLocalizedString(30662) or "Sent to aria2: {}").format(job["title"]))
        return True
    except Exception as exc:
        update_job(job["id"], status="failed", error=str(exc))
        _notify("aria2: {}".format(exc), error=True)
        return False


def _submit_jdownloader(job):
    if job.get("headers"):
        update_job(job["id"], status="failed", error="JDownloader Click'n'Load cannot preserve required stream headers")
        _notify(_addon().getLocalizedString(30664) or "This stream needs headers that JDownloader cannot receive through Click'n'Load.", error=True)
        return False
    endpoint = _setting("jdownloader_url", "http://127.0.0.1:9666").rstrip("/") + "/flash/add"
    data = urllib.parse.urlencode({"urls": job["stream_url"], "package": "AdultHideout", "source": job.get("page_url", "")}).encode("utf-8")
    try:
        request = urllib.request.Request(endpoint, data=data)
        with urllib.request.urlopen(request, timeout=10) as response:
            answer = response.read().decode("utf-8", "replace").strip().lower()
        if answer and "success" not in answer and "true" not in answer:
            raise RuntimeError(answer[:200])
        update_job(job["id"], status="submitted", external_id="clicknload")
        _notify((_addon().getLocalizedString(30663) or "Sent to JDownloader: {}").format(job["title"]))
        return True
    except Exception as exc:
        update_job(job["id"], status="failed", error=str(exc))
        _notify("JDownloader: {}".format(exc), error=True)
        return False


def refresh_external_job(job):
    if job.get("backend") != "aria2" or job.get("status") not in ("submitted", "running"):
        return job
    gid = job.get("external_id")
    if not gid:
        return job
    try:
        endpoint = _setting("aria2_rpc_url", "http://127.0.0.1:6800/jsonrpc").strip()
        status = _json_rpc(endpoint, "aria2.tellStatus", _aria2_params([gid, ["status", "totalLength", "completedLength", "errorMessage", "files"]]))
        total = int(status.get("totalLength") or 0)
        done = int(status.get("completedLength") or 0)
        state = status.get("status")
        mapped = {"active": "running", "waiting": "submitted", "paused": "submitted", "complete": "complete", "error": "failed", "removed": "cancelled"}.get(state, "submitted")
        changes = {"status": mapped, "total": total, "downloaded": done, "progress": int(done * 100 / total) if total else 0}
        if status.get("errorMessage"):
            changes["error"] = status["errorMessage"]
        files = status.get("files") or []
        if files and files[0].get("path"):
            changes["final_path"] = files[0]["path"]
        return update_job(job["id"], **changes) or job
    except Exception:
        return job


def cancel_job(job_id):
    job = load_job(job_id)
    if not job or job.get("status") in ("complete", "failed", "cancelled"):
        return
    try:
        with open(_cancel_path(job_id), "wb") as handle:
            handle.write(b"cancel")
    except OSError:
        pass
    if job.get("backend") == "aria2" and job.get("external_id"):
        try:
            endpoint = _setting("aria2_rpc_url", "http://127.0.0.1:6800/jsonrpc").strip()
            _json_rpc(endpoint, "aria2.remove", _aria2_params([job["external_id"]]))
        except Exception:
            pass
    update_job(job_id, status="cancelled", error="Cancelled by user")


def retry_job(job_id):
    job = load_job(job_id)
    if not job or job.get("status") not in ("failed", "cancelled"):
        return False
    try:
        os.remove(_cancel_path(job_id))
    except OSError:
        pass
    job.update({"status": "queued", "error": "", "progress": 0, "run_token": uuid.uuid4().hex})
    save_job(job)
    if job.get("backend") == "aria2":
        return _submit_aria2(job)
    if job.get("backend") == "jdownloader":
        return _submit_jdownloader(job)
    worker = os.path.join(_addon().getAddonInfo("path"), "resources", "lib", "download_worker.py")
    xbmc.executebuiltin('RunScript("{}","{}","{}")'.format(worker, job["id"], job["run_token"]))
    return True


def delete_job(job_id):
    job = load_job(job_id)
    if not job:
        return
    if job.get("status") in ("running", "transferring"):
        _notify(_addon().getLocalizedString(30665) or "Cancel the active download before removing it.", error=True)
        return
    try:
        os.remove(_job_path(job_id))
    except OSError:
        pass
    try:
        os.remove(_cancel_path(job_id))
    except OSError:
        pass
    for leftover in (staging_path(job), staging_path(job) + ".log"):
        try:
            if os.path.exists(leftover):
                os.remove(leftover)
        except OSError:
            pass


def _format_size(value):
    size = float(value or 0)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024.0 or unit == "TB":
            return "{:.1f} {}".format(size, unit)
        size /= 1024.0
    return "0 B"


def show_manager(handle, base_url):
    addon = _addon()
    refresh_url = "{}?mode=31&action=refresh".format(base_url)
    refresh_item = xbmcgui.ListItem(label="[COLOR yellow]{}[/COLOR]".format(addon.getLocalizedString(30654) or "Refresh"))
    xbmcplugin.addDirectoryItem(handle, refresh_url, refresh_item, True)
    for raw_job in list_jobs():
        job = refresh_external_job(raw_job)
        status = job.get("status", "queued")
        progress = int(job.get("progress") or 0)
        label = "[{}] {}".format(status.upper(), job.get("title") or "Download")
        if status in ("running", "transferring") and job.get("total"):
            label = "[{} {}%] {}".format(status.upper(), progress, job.get("title") or "Download")
        item = xbmcgui.ListItem(label=label)
        item.setArt({"thumb": job.get("thumbnail") or "", "icon": job.get("thumbnail") or ""})
        details = "{} / {}".format(_format_size(job.get("downloaded")), _format_size(job.get("total"))) if job.get("total") else _format_size(job.get("downloaded"))
        plot = "Backend: {}\nStatus: {}\n{}".format(job.get("backend"), status, details)
        if job.get("error"):
            plot += "\n" + job["error"]
        item.setInfo("video", {"title": job.get("title") or "Download", "plot": plot})
        menu = []
        if status not in ("complete", "failed", "cancelled"):
            menu.append((addon.getLocalizedString(30655) or "Cancel download", "RunPlugin({}?mode=31&action=cancel&job_id={})".format(base_url, job["id"])))
        else:
            if status in ("failed", "cancelled"):
                menu.append((addon.getLocalizedString(30667) or "Retry download", "RunPlugin({}?mode=31&action=retry&job_id={})".format(base_url, job["id"])))
            menu.append((addon.getLocalizedString(30656) or "Remove entry", "RunPlugin({}?mode=31&action=delete_job&job_id={})".format(base_url, job["id"])))
        item.addContextMenuItems(menu)
        playable = status == "complete" and bool(job.get("final_path")) and xbmcvfs.exists(job.get("final_path"))
        if playable:
            item.setProperty("IsPlayable", "true")
            xbmcplugin.addDirectoryItem(handle, job["final_path"], item, False)
        else:
            xbmcplugin.addDirectoryItem(handle, "", item, False)
    xbmcplugin.setContent(handle, "videos")
    xbmcplugin.endOfDirectory(handle, succeeded=True, cacheToDisc=False)


def handle_manager_action(handle, base_url, action, params):
    if action == "cancel":
        cancel_job(params.get("job_id", ""))
        xbmc.executebuiltin("Container.Refresh")
        xbmcplugin.endOfDirectory(handle, succeeded=True, updateListing=False, cacheToDisc=False)
        return
    if action == "delete_job":
        delete_job(params.get("job_id", ""))
        xbmc.executebuiltin("Container.Refresh")
        xbmcplugin.endOfDirectory(handle, succeeded=True, updateListing=False, cacheToDisc=False)
        return
    if action == "retry":
        retry_job(params.get("job_id", ""))
        xbmc.executebuiltin("Container.Refresh")
        xbmcplugin.endOfDirectory(handle, succeeded=True, updateListing=False, cacheToDisc=False)
        return
    show_manager(handle, base_url)


def ffmpeg_path():
    return _resolve_ffmpeg()


def staging_path(job):
    filename = "{}.part.{}".format(job["id"], job.get("extension") or "mp4")
    return os.path.join(_staging_dir(), filename)


def mark_cancelled(job_id, run_token):
    job = load_job(job_id)
    if not job or job.get("run_token") != run_token or not is_cancel_requested(job_id):
        return
    job.update({"status": "cancelled", "error": "Cancelled by user"})
    save_job(job)


def write_metadata(job, final_path):
    metadata = {
        "title": job.get("title") or "",
        "website": job.get("website") or "",
        "source": job.get("page_url") or "",
        "thumbnail": job.get("thumbnail") or "",
        "downloaded": int(time.time()),
    }
    target = final_path + ".ah.json"
    try:
        handle = xbmcvfs.File(target, "w")
        handle.write(json.dumps(metadata, ensure_ascii=False, indent=2))
        handle.close()
    except Exception as exc:
        xbmc.log("[AdultHideout][downloads] metadata write failed: {}".format(exc), xbmc.LOGWARNING)


def finalize_file(job, staging_file, run_token=""):
    destination = job["destination"]
    if run_token:
        update_job_for_run(job["id"], run_token, status="transferring", progress=100)
    else:
        update_job(job["id"], status="transferring", progress=100)
    if _is_vfs(destination):
        if not xbmcvfs.copy(staging_file, destination):
            raise RuntimeError("Could not copy completed download to {}".format(destination))
        try:
            os.remove(staging_file)
        except OSError:
            pass
    else:
        parent = os.path.dirname(destination)
        os.makedirs(parent, exist_ok=True)
        os.replace(staging_file, destination)
    write_metadata(job, destination)
    return destination


def build_ffmpeg_command(job, output_path):
    command = [ffmpeg_path(), "-hide_banner", "-y", "-loglevel", "warning"]
    headers = dict(job.get("headers") or {})
    if headers.get("User-Agent"):
        command.extend(["-user_agent", headers.pop("User-Agent")])
    if headers.get("Referer"):
        command.extend(["-referer", headers.pop("Referer")])
    header_lines = ["{}: {}".format(key, value) for key, value in headers.items() if value]
    if header_lines:
        command.extend(["-headers", "\r\n".join(header_lines) + "\r\n"])
    command.extend(["-i", job["stream_url"], "-c", "copy", output_path])
    return command


def hidden_process_options():
    startupinfo = None
    creationflags = 0
    if os.name == "nt":
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    return startupinfo, creationflags
