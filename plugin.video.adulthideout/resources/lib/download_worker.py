# -*- coding: utf-8 -*-

import os
import importlib.util
import subprocess
import sys
import time

import xbmc

LIB_DIR = os.path.abspath(os.path.dirname(__file__))
ADDON_ROOT = os.path.abspath(os.path.join(LIB_DIR, "..", ".."))

for path in (LIB_DIR, ADDON_ROOT):
    while path in sys.path:
        sys.path.remove(path)
    sys.path.insert(0, path)

# Load the manager under an AdultHideout-specific module name. Some third-party
# Kodi modules expose their own top-level resources.lib package and otherwise
# replace AdultHideout's manager inside a background RunScript process.
MANAGER_PATH = os.path.join(LIB_DIR, "download_manager.py")
MANAGER_MODULE = "adulthideout_download_manager"
spec = importlib.util.spec_from_file_location(MANAGER_MODULE, MANAGER_PATH)
download_manager = importlib.util.module_from_spec(spec)
sys.modules[MANAGER_MODULE] = download_manager
spec.loader.exec_module(download_manager)



class _BackgroundProgress:
    def __init__(self, job):
        self.dialog = None
        self.expires_at = None
        try:
            setting = download_manager._setting("download_progress_display", "0")
            durations = {"0": 10, "1": 60, "2": None}
            duration = durations.get(str(setting), 10)
            if duration:
                self.expires_at = time.time() + duration
            dialog_class = getattr(__import__("xbmcgui"), "DialogProgressBG", None)
            if dialog_class:
                self.dialog = dialog_class()
                self.dialog.create("AdultHideout", job.get("title") or download_manager._lang(30747, "Download"))
        except Exception as exc:
            xbmc.log("[AdultHideout][downloads] progress dialog unavailable: {}".format(exc), xbmc.LOGDEBUG)

    def update(self, job, percent=None):
        if not self.dialog:
            return
        if self.expires_at and time.time() >= self.expires_at:
            self.close()
            return
        try:
            if percent is None:
                percent = int(job.get("progress") or 0)
            downloaded = download_manager._format_size(job.get("downloaded"))
            total = download_manager._format_size(job.get("total")) if job.get("total") else "?"
            message = "{} / {}".format(downloaded, total)
            speed = job.get("speed")
            if speed:
                message += "  |  {}".format(download_manager._format_size(speed) + "/s")
            eta = job.get("eta")
            if eta:
                message += "  |  " + download_manager._lang(30752, "ETA {}", download_manager._format_duration(eta))
            self.dialog.update(max(0, min(100, int(percent))), job.get("title") or download_manager._lang(30747, "Download"), message)
        except Exception:
            pass

    def close(self):
        if self.dialog:
            try:
                self.dialog.close()
            except Exception:
                pass
            self.dialog = None


def _cancelled(job_id, run_token):
    current = download_manager.load_job(job_id)
    return (
        not current
        or current.get("run_token") != run_token
        or current.get("status") == "cancelled"
        or download_manager.is_cancel_requested(job_id)
        or xbmc.Monitor().abortRequested()
    )


def _run_internal(job, run_token, progress=None):
    try:
        import requests
    except ImportError:
        from resources.lib.vendor import requests

    path = download_manager.staging_path(job)
    existing = os.path.getsize(path) if os.path.exists(path) else 0
    headers = dict(job.get("headers") or {})
    if existing:
        headers["Range"] = "bytes={}-".format(existing)
    response = requests.get(job["stream_url"], headers=headers, stream=True, timeout=(20, 45), allow_redirects=True)
    if existing and response.status_code == 416:
        content_range = response.headers.get("Content-Range", "")
        response.close()
        try:
            remote_size = int(content_range.rsplit("/", 1)[-1])
        except (TypeError, ValueError):
            remote_size = 0
        if remote_size and existing == remote_size:
            changes = {"downloaded": existing, "total": remote_size, "progress": 100, "speed": 0, "eta": 0}
            download_manager.update_job_for_run(job["id"], run_token, **changes)
            if progress:
                progress.update(dict(job, **changes), 100)
            return path

        # The server rejected this resume offset. Keep the job usable by
        # requesting the complete file again instead of failing permanently.
        headers.pop("Range", None)
        existing = 0
        response = requests.get(job["stream_url"], headers=headers, stream=True, timeout=(20, 45), allow_redirects=True)
    response.raise_for_status()
    if existing and response.status_code != 206:
        existing = 0
    mode = "ab" if existing else "wb"
    total = int(response.headers.get("Content-Length") or 0) + existing
    done = existing
    last_update = 0
    started = time.time()
    with open(path, mode) as output:
        for chunk in response.iter_content(chunk_size=256 * 1024):
            if _cancelled(job["id"], run_token):
                response.close()
                return None
            if not chunk:
                continue
            output.write(chunk)
            done += len(chunk)
            now = time.time()
            if now - last_update >= 1:
                percent = int(done * 100 / total) if total else 0
                elapsed = max(0.1, now - started)
                speed = int(max(0, done - existing) / elapsed)
                eta = int(max(0, total - done) / speed) if speed and total else 0
                changes = {"downloaded": done, "total": total, "progress": percent, "speed": speed, "eta": eta}
                current = download_manager.update_job_for_run(job["id"], run_token, **changes)
                if current and progress:
                    progress.update(current, percent)
                last_update = now
    response.close()
    current = download_manager.update_job_for_run(job["id"], run_token, downloaded=done, total=total, progress=100, eta=0)
    if current and progress:
        progress.update(current, 100)
    return path


def _run_ffmpeg(job, run_token, progress=None):
    path = download_manager.staging_path(job)
    log_path = path + ".log"
    controller = None
    ffmpeg_job = job
    try:
        if job.get("hls_proxy"):
            import proxy_utils

            controller = proxy_utils.HlsProxyController(
                job["stream_url"],
                headers=job.get("headers") or {},
                preserve_query=job.get("preserve_query", False),
            )
            ffmpeg_job = dict(job)
            ffmpeg_job["stream_url"] = controller.start()
            ffmpeg_job["headers"] = {}

        command = download_manager.build_ffmpeg_command(ffmpeg_job, path)
        startupinfo, creationflags = download_manager.hidden_process_options()
        with open(log_path, "ab") as log_file:
            process = subprocess.Popen(
                command,
                stdin=subprocess.DEVNULL,
                stdout=log_file,
                stderr=subprocess.STDOUT,
                startupinfo=startupinfo,
                creationflags=creationflags,
            )
            last_update = 0
            while process.poll() is None:
                if _cancelled(job["id"], run_token):
                    process.terminate()
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                    return None
                now = time.time()
                if now - last_update >= 1 and os.path.exists(path):
                    current = download_manager.update_job_for_run(job["id"], run_token, downloaded=os.path.getsize(path))
                    if current and progress:
                        progress.update(current)
                    last_update = now
                xbmc.sleep(500)
            if process.returncode != 0:
                raise RuntimeError("FFmpeg exited with code {}. See {}".format(process.returncode, log_path))
        return path if os.path.isfile(path) and os.path.getsize(path) else None
    finally:
        if controller:
            controller.stop()


def run(job_id, run_token=""):
    job = download_manager.load_job(job_id)
    if job and not job.get("run_token") and not run_token:
        run_token = "legacy"
        job = download_manager.update_job(job_id, run_token=run_token) or job
    run_token = run_token or (job or {}).get("run_token", "")
    if not job or job.get("status") == "cancelled" or job.get("run_token") != run_token:
        return
    download_manager.update_job_for_run(job_id, run_token, status="running", error="")
    progress = _BackgroundProgress(job)
    try:
        if job.get("backend") == "ffmpeg":
            staging = _run_ffmpeg(job, run_token, progress)
        else:
            staging = _run_internal(job, run_token, progress)
        if not staging:
            if _cancelled(job_id, run_token):
                download_manager.mark_cancelled(job_id, run_token)
            else:
                download_manager.update_job_for_run(job_id, run_token, status="failed", error=download_manager._lang(30750, "Download produced no file"))
            return
        if _cancelled(job_id, run_token):
            return
        final_path = download_manager.finalize_file(job, staging, run_token=run_token)
        download_manager.update_job_for_run(job_id, run_token, status="complete", final_path=final_path, progress=100)
        progress.close()
        xbmcgui = __import__("xbmcgui")
        xbmcgui.Dialog().notification("AdultHideout", download_manager._lang(30748, "Download complete: {}", job.get("title") or "Video"), xbmcgui.NOTIFICATION_INFO, 5000)
    except Exception as exc:
        xbmc.log("[AdultHideout][downloads] worker failed: {}".format(exc), xbmc.LOGERROR)
        if not _cancelled(job_id, run_token):
            download_manager.update_job_for_run(job_id, run_token, status="failed", error=str(exc))
            xbmcgui = __import__("xbmcgui")
            xbmcgui.Dialog().notification("AdultHideout", download_manager._lang(30749, "Download failed: {}", str(exc)), xbmcgui.NOTIFICATION_ERROR, 5000)
    finally:
        progress.close()
        download_manager.start_next_download()


if __name__ == "__main__" and len(sys.argv) > 1:
    run(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "")
