# -*- coding: utf-8 -*-

import os
import subprocess
import sys
import time

import xbmc

# RunScript starts this file with resources/lib as its import root. Add the
# actual add-on root so package imports work consistently on every platform.
ADDON_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ADDON_ROOT not in sys.path:
    sys.path.insert(0, ADDON_ROOT)

from resources.lib import download_manager


def _cancelled(job_id, run_token):
    current = download_manager.load_job(job_id)
    return (
        not current
        or current.get("run_token") != run_token
        or current.get("status") == "cancelled"
        or download_manager.is_cancel_requested(job_id)
        or xbmc.Monitor().abortRequested()
    )


def _run_internal(job, run_token):
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
    response.raise_for_status()
    if existing and response.status_code != 206:
        existing = 0
    mode = "ab" if existing else "wb"
    total = int(response.headers.get("Content-Length") or 0) + existing
    done = existing
    last_update = 0
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
                progress = int(done * 100 / total) if total else 0
                download_manager.update_job_for_run(job["id"], run_token, downloaded=done, total=total, progress=progress)
                last_update = now
    response.close()
    download_manager.update_job_for_run(job["id"], run_token, downloaded=done, total=total, progress=100)
    return path


def _run_ffmpeg(job, run_token):
    path = download_manager.staging_path(job)
    command = download_manager.build_ffmpeg_command(job, path)
    log_path = path + ".log"
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
                download_manager.update_job_for_run(job["id"], run_token, downloaded=os.path.getsize(path))
                last_update = now
            xbmc.sleep(500)
        if process.returncode != 0:
            raise RuntimeError("FFmpeg exited with code {}. See {}".format(process.returncode, log_path))
    return path if os.path.isfile(path) and os.path.getsize(path) else None


def run(job_id, run_token=""):
    job = download_manager.load_job(job_id)
    if job and not job.get("run_token") and not run_token:
        run_token = "legacy"
        job = download_manager.update_job(job_id, run_token=run_token) or job
    run_token = run_token or (job or {}).get("run_token", "")
    if not job or job.get("status") == "cancelled" or job.get("run_token") != run_token:
        return
    download_manager.update_job_for_run(job_id, run_token, status="running", error="")
    try:
        if job.get("backend") == "ffmpeg":
            staging = _run_ffmpeg(job, run_token)
        else:
            staging = _run_internal(job, run_token)
        if not staging:
            if _cancelled(job_id, run_token):
                download_manager.mark_cancelled(job_id, run_token)
            else:
                download_manager.update_job_for_run(job_id, run_token, status="failed", error="Download produced no file")
            return
        if _cancelled(job_id, run_token):
            return
        final_path = download_manager.finalize_file(job, staging, run_token=run_token)
        download_manager.update_job_for_run(job_id, run_token, status="complete", final_path=final_path, progress=100)
        xbmcgui = __import__("xbmcgui")
        xbmcgui.Dialog().notification("AdultHideout", "Download complete: {}".format(job.get("title") or "Video"), xbmcgui.NOTIFICATION_INFO, 5000)
    except Exception as exc:
        xbmc.log("[AdultHideout][downloads] worker failed: {}".format(exc), xbmc.LOGERROR)
        if not _cancelled(job_id, run_token):
            download_manager.update_job_for_run(job_id, run_token, status="failed", error=str(exc))


if __name__ == "__main__" and len(sys.argv) > 1:
    run(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "")
