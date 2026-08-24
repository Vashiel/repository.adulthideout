import json
import os
import platform
import re
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone

import xbmc
import xbmcaddon
import xbmcvfs


ADDON_ID = "script.adulthideout.kvat"
TARGET_ADDON_ID = "plugin.video.adulthideout"
REPORT_SCHEMA_VERSION = 2

# External outages are reported separately and never sent into the repair loop.
KNOWN_EXTERNAL_ISSUES = {
    "swingerpornfun": "The website currently serves a managed Cloudflare challenge to Kodi.",
    "vintagepornfun": "The website currently serves a managed Cloudflare challenge to Kodi.",
}

ADDON = xbmcaddon.Addon(ADDON_ID)
PROFILE_PATH = xbmcvfs.translatePath(ADDON.getAddonInfo("profile"))
REPORTS_PATH = os.path.join(PROFILE_PATH, "reports")
JOBS_PATH = os.path.join(PROFILE_PATH, "jobs")

COLOR_TAG_RE = re.compile(r"\[/?COLOR(?:\s+[^\]]+)?\]", re.IGNORECASE)
STYLE_TAG_RE = re.compile(r"\[/?(?:B|I|LIGHT|UPPERCASE|LOWERCASE)\]", re.IGNORECASE)
URL_RE = re.compile(r"https?://([^/\s|]+)(?:[^\s]*)?", re.IGNORECASE)
SECRET_RE = re.compile(
    r"(?i)\b(authorization|cookie|token|signature|sig|key|password)\s*[:=]\s*([^&,;\s]+)"
)


def now_iso():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def ensure_directories():
    for path in (PROFILE_PATH, REPORTS_PATH, JOBS_PATH):
        if not xbmcvfs.exists(path):
            xbmcvfs.mkdirs(path)


def log(message, level=xbmc.LOGINFO):
    xbmc.log("[AdultHideout Diagnostics] {}".format(message), level)


def clean_label(value):
    value = COLOR_TAG_RE.sub("", str(value or ""))
    return STYLE_TAG_RE.sub("", value).strip()


def website_label(site):
    overrides = {
        "giantessporn": "Giantess Porn",
        "tickleporn": "Tickle Porn",
        "85po": "85po",
        "whereismyporn": "MoneyPornVideo",
    }
    return overrides.get(site, site.replace("_", " ").replace("-", " ").title())


def get_target_addon():
    return xbmcaddon.Addon(TARGET_ADDON_ID)


def stop_target_plugin():
    try:
        addon_path = xbmcvfs.translatePath(get_target_addon().getAddonInfo("path"))
        xbmc.executebuiltin(
            'StopScript("{}")'.format(os.path.join(addon_path, "default.py"))
        )
    except Exception:
        pass


def list_websites():
    target = get_target_addon()
    addon_path = xbmcvfs.translatePath(target.getAddonInfo("path"))
    websites_path = os.path.join(addon_path, "resources", "websites")
    directories, files = xbmcvfs.listdir(websites_path)
    del directories
    sites = sorted(
        filename[:-3]
        for filename in files
        if filename.endswith(".py") and filename != "__init__.py"
    )
    return [{"id": site, "label": website_label(site)} for site in sites]


def website_url(site):
    query = urllib.parse.urlencode({
        "mode": "2",
        "website": site,
        "url": "BOOTSTRAP",
    })
    return "plugin://{}/?{}".format(TARGET_ADDON_ID, query)


def execute_jsonrpc(method, params=None):
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": method,
        "params": params or {},
    }
    response = json.loads(xbmc.executeJSONRPC(json.dumps(payload)))
    if "error" in response:
        error = response.get("error") or {}
        raise RuntimeError("JSON-RPC {}: {}".format(
            error.get("code", "error"),
            error.get("message", "unknown error"),
        ))
    return response.get("result") or {}


def get_directory(url):
    params = {
        "directory": url,
        "media": "video",
        "properties": ["title", "thumbnail", "fanart", "duration"],
    }
    result = execute_jsonrpc("Files.GetDirectory", params)
    files = result.get("files") or []
    if not files:
        time.sleep(0.5)
        result = execute_jsonrpc("Files.GetDirectory", params)
        files = result.get("files") or []
    return files


def is_video_item(item):
    path = str(item.get("file") or "")
    if item.get("filetype") == "directory":
        return False
    if path.startswith("plugin://"):
        query = urllib.parse.urlsplit(path).query
        mode = dict(urllib.parse.parse_qsl(query)).get("mode")
        return mode == "4"
    if item.get("filetype") == "file":
        return True
    lowered = path.lower().split("|", 1)[0]
    return lowered.endswith((".mp4", ".m3u8", ".mpd", ".mkv", ".webm"))


def is_folder_item(item):
    return item.get("filetype") == "directory"


def useful_child_folders(items):
    skipped_modes = {"5", "6", "20", "21", "30", "31", "32", "40"}
    skipped_labels = ("search", "next", "reload", "download", "vault")
    candidates = []
    for item in items:
        if not is_folder_item(item):
            continue
        label = clean_label(item.get("label")).lower()
        if any(word in label for word in skipped_labels):
            continue
        path = str(item.get("file") or "")
        mode = dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(path).query)).get("mode")
        if mode in skipped_modes:
            continue
        priority = 50
        if any(word in label for word in ("latest", "recent", "new", "videos", "home")):
            priority = 0
        elif any(word in label for word in ("popular", "viewed", "rated", "featured")):
            priority = 10
        elif any(word in label for word in ("category", "tag", "model", "pornstar")):
            priority = 40
        candidates.append((priority, label, item))
    candidates.sort(key=lambda entry: (entry[0], entry[1]))
    return [entry[2] for entry in candidates]


def thumbnail_from_item(item):
    return str(item.get("thumbnail") or item.get("fanart") or "")


def unwrap_image_url(url):
    value = str(url or "")
    if value.startswith("image://"):
        value = value[len("image://"):]
        if value.endswith("/"):
            value = value[:-1]
        value = urllib.parse.unquote(value)
    return value


def probe_thumbnail(url):
    if not url:
        return {"status": "missing"}
    source = unwrap_image_url(url)
    request_source, separator, encoded_headers = source.partition("|")
    supplied_headers = dict(urllib.parse.parse_qsl(encoded_headers)) if separator else {}
    handle = None
    try:
        handle = xbmcvfs.File(source)
        data = handle.readBytes(128)
        if not data and request_source.startswith(("http://", "https://")):
            parsed = urllib.parse.urlsplit(request_source)
            headers = {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/134.0.0.0 Safari/537.36"
                ),
                "Referer": "{}://{}/".format(parsed.scheme, parsed.netloc),
                "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
                "Accept-Encoding": "identity",
            }
            headers.update(supplied_headers)
            request = urllib.request.Request(request_source, headers=headers)
            with urllib.request.urlopen(request, timeout=10) as response:
                data = response.read(128)
        if not data:
            return {"status": "failed", "error": "empty response"}
        if isinstance(data, str):
            data = data.encode("latin-1", "ignore")
        prefix = bytes(data[:32]).lstrip().lower()
        if prefix.startswith((b"<html", b"<!doctype", b"<script")):
            return {"status": "failed", "error": "HTML returned instead of image data"}
        return {"status": "loaded", "bytes_checked": len(data)}
    except Exception as exc:
        return {"status": "failed", "error": sanitize_text(exc)}
    finally:
        if handle is not None:
            try:
                handle.close()
            except Exception:
                pass


def inspect_listing(site, verify_thumbnail=True, deep=False):
    started = time.time()
    root_items = get_directory(website_url(site))
    inspected_items = list(root_items)
    videos = [item for item in inspected_items if is_video_item(item)]
    followed_folders = 0
    folder_errors = []

    if not videos and deep:
        queue = [(folder, 1) for folder in useful_child_folders(root_items)]
        visited = set()
        while queue and followed_folders < 8 and not videos:
            folder, depth = queue.pop(0)
            folder_url = str(folder.get("file") or "")
            if not folder_url or folder_url in visited:
                continue
            visited.add(folder_url)
            followed_folders += 1
            try:
                child_items = get_directory(folder_url)
            except Exception as exc:
                log("{} child listing failed: {}".format(site, sanitize_text(exc)), xbmc.LOGWARNING)
                folder_errors.append(sanitize_text(exc))
                continue
            inspected_items.extend(child_items)
            videos.extend(item for item in child_items if is_video_item(item))
            if not videos and depth < 2:
                queue.extend((child, depth + 1) for child in useful_child_folders(child_items))

    folders = [item for item in root_items if is_folder_item(item)]
    thumbnail = {"status": "missing"}
    if videos:
        for attempt, video in enumerate(videos[:3], start=1):
            thumbnail_url = thumbnail_from_item(video)
            if not thumbnail_url:
                continue
            thumbnail = (
                probe_thumbnail(thumbnail_url)
                if verify_thumbnail
                else {"status": "present"}
            )
            thumbnail["attempts"] = attempt
            if thumbnail.get("status") not in ("missing", "failed"):
                break

    status = "PASS"
    messages = []
    if not root_items:
        status = "FAILED"
        messages.append("website returned no directory items")
    elif not videos:
        status = "FAILED" if deep else "WARNING"
        messages.append(
            "no playable video found after inspecting useful folders"
            if deep else "no playable video found in the inspected listing"
        )
    if videos and thumbnail.get("status") in ("missing", "failed"):
        if status == "PASS":
            status = "WARNING"
        messages.append("video thumbnail could not be loaded")

    return {
        "status": status,
        "elapsed_seconds": round(time.time() - started, 2),
        "items": len(root_items),
        "folders": len(folders),
        "videos": len(videos),
        "followed_folders": followed_folders,
        "folder_errors": folder_errors[:3],
        "thumbnail": thumbnail,
        "messages": messages,
        "playback_urls": [str(item.get("file") or "") for item in videos[:3]],
    }


def wait(monitor, seconds):
    return monitor.waitForAbort(seconds)


def inspect_playback(url, start_timeout=15, seek_enabled=True):
    result = {
        "status": "FAILED",
        "started": False,
        "seek_tested": False,
        "seek_succeeded": False,
        "messages": [],
    }
    if not url:
        result["messages"].append("no playable item was available")
        return result

    player = xbmc.Player()
    monitor = xbmc.Monitor()
    if player.isPlaying():
        try:
            xbmc.executebuiltin("PlayerControl(Stop)")
            wait(monitor, 1.0)
        except Exception:
            pass
        if player.isPlaying():
            result["messages"].append("previous diagnostic playback could not be stopped")
            result["status"] = "WARNING"
            return result

    started_at = time.time()
    playback_requested = False
    try:
        playback_requested = True
        execute_jsonrpc("Player.Open", {"item": {"file": url}})
        while time.time() - started_at < start_timeout:
            if monitor.abortRequested():
                result["messages"].append("Kodi is shutting down")
                return result
            if player.isPlayingVideo():
                result["started"] = True
                break
            wait(monitor, 0.25)

        result["startup_seconds"] = round(time.time() - started_at, 2)
        if not result["started"]:
            result["messages"].append("video did not start before the timeout")
            return result

        total = 0
        before = 0
        duration_deadline = time.time() + 6.0
        while time.time() < duration_deadline and player.isPlayingVideo():
            try:
                total = float(player.getTotalTime() or 0)
                before = float(player.getTime() or 0)
            except Exception:
                total = 0
                before = 0
            if total > 0:
                break
            wait(monitor, 0.5)
        result["duration_seconds"] = round(total, 2)
        result["status"] = "PASS" if total > 0 else "WARNING"
        if seek_enabled and total <= 0:
            result["messages"].append("video started but duration and seeking were unavailable")

        if seek_enabled and total >= 30:
            result["seek_tested"] = True
            target = min(total * 0.5, total - 10)
            player.seekTime(target)
            wait(monitor, 3.0)
            try:
                after = float(player.getTime() or 0)
            except Exception:
                after = 0
            result["seek_succeeded"] = player.isPlayingVideo() and after > before + 3
            if not result["seek_succeeded"]:
                result["status"] = "WARNING"
                result["messages"].append("video started but the seek check did not advance")
        return result
    except Exception as exc:
        result["messages"].append(sanitize_text(exc))
        return result
    finally:
        if playback_requested:
            try:
                xbmc.executebuiltin("PlayerControl(Stop)")
                for _ in range(10):
                    if not player.isPlaying():
                        break
                    wait(monitor, 0.25)
            except Exception:
                pass
            stop_target_plugin()
            wait(monitor, 0.5)


def inspect_playback_candidates(urls, max_attempts=3, seek_enabled=True):
    attempts = []
    for index, url in enumerate(list(urls or [])[:max_attempts]):
        attempt = inspect_playback(url, seek_enabled=seek_enabled)
        attempt["attempt"] = index + 1
        attempts.append(attempt)
        if attempt.get("status") == "PASS":
            return {
                "status": "PASS" if index == 0 else "WARNING",
                "working_attempt": index + 1,
                "attempts": attempts,
                "messages": [] if index == 0 else [
                    "playback required fallback to video attempt {}".format(index + 1)
                ],
            }
    if any(attempt.get("started") for attempt in attempts):
        return {
            "status": "WARNING",
            "working_attempt": None,
            "attempts": attempts,
            "messages": ["video playback started, but seeking could not be verified"],
        }
    return {
        "status": "FAILED",
        "working_attempt": None,
        "attempts": attempts,
        "messages": [
            "none of the tested videos started and sought successfully"
            if seek_enabled else "none of the tested videos started successfully"
        ],
    }


def run_site_test(site, mode="quick"):
    started = time.time()
    result = {
        "site": site,
        "label": website_label(site),
        "status": "FAILED",
        "started_at": now_iso(),
        "mode": mode,
    }
    if site in KNOWN_EXTERNAL_ISSUES:
        result["status"] = "IGNORED"
        result["external_issue"] = KNOWN_EXTERNAL_ISSUES[site]
        result["elapsed_seconds"] = round(time.time() - started, 2)
        result["finished_at"] = now_iso()
        return result

    try:
        detailed = mode in ("full", "detail", "playback")
        listing = inspect_listing(site, verify_thumbnail=True, deep=detailed)
        playback_urls = listing.pop("playback_urls", [])
        result["listing"] = listing
        result["status"] = listing.get("status", "FAILED")
        if mode in ("full", "playback"):
            playback = inspect_playback_candidates(
                playback_urls,
                seek_enabled=mode == "full",
            )
            result["playback"] = playback
            if playback.get("status") == "FAILED":
                result["status"] = "FAILED"
            elif playback.get("status") == "WARNING":
                result["status"] = "WARNING"
            elif playback.get("status") == "PASS":
                thumbnail = listing.get("thumbnail") or {}
                if thumbnail.get("status") == "missing":
                    result["status"] = "WARNING"
                else:
                    # A remote thumbnail probe can fail even when Kodi's skin loader
                    # succeeds. Keep the evidence, but do not call a playable site broken.
                    result["status"] = "PASS"
                    if thumbnail.get("status") == "failed":
                        result["advisories"] = ["thumbnail could not be verified automatically"]
    except Exception as exc:
        result["error"] = sanitize_text(exc)
        result["status"] = "FAILED"
    result["elapsed_seconds"] = round(time.time() - started, 2)
    result["finished_at"] = now_iso()
    return result


def sanitize_text(value):
    text = str(value or "")
    try:
        home = os.path.expanduser("~")
        if home:
            text = text.replace(home, "<home>")
    except Exception:
        pass
    text = URL_RE.sub(
        lambda match: "https://{}/<redacted>".format(match.group(1).rsplit("@", 1)[-1]),
        text,
    )
    text = SECRET_RE.sub(lambda match: "{}=<redacted>".format(match.group(1)), text)
    return text[:1000]


def environment_info():
    target = get_target_addon()
    if xbmc.getCondVisibility("System.Platform.Android"):
        platform_name = "Android"
    elif xbmc.getCondVisibility("System.Platform.Windows"):
        platform_name = "Windows"
    elif xbmc.getCondVisibility("System.Platform.OSX"):
        platform_name = "macOS"
    elif xbmc.getCondVisibility("System.Platform.Linux"):
        platform_name = "Linux"
    else:
        platform_name = "Unknown"
    return {
        "platform": platform_name,
        "architecture": platform.machine() or "unknown",
        "kodi_version": xbmc.getInfoLabel("System.BuildVersion"),
        "python_version": platform.python_version(),
        "skin": xbmc.getSkinDir(),
        "adult_hideout_version": target.getAddonInfo("version"),
        "diagnostics_version": ADDON.getAddonInfo("version"),
    }


def read_json(path, default=None):
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except Exception:
        return default


def write_json(path, payload):
    ensure_directories()
    temporary = path + ".tmp"
    with open(temporary, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True, ensure_ascii=True)
    os.replace(temporary, path)


def report_summary(results):
    counts = {"PASS": 0, "WARNING": 0, "FAILED": 0, "TIMEOUT": 0, "IGNORED": 0}
    for result in results:
        status = result.get("status", "FAILED")
        counts[status] = counts.get(status, 0) + 1
    counts["total"] = len(results)
    return counts


def cleanup_old_reports(keep=10):
    ensure_directories()
    reports = sorted(
        (os.path.join(REPORTS_PATH, name) for name in os.listdir(REPORTS_PATH) if name.endswith(".json")),
        key=lambda path: os.path.getmtime(path),
        reverse=True,
    )
    for path in reports[keep:]:
        try:
            os.remove(path)
        except OSError:
            pass


def build_report(mode, results, started_at, cancelled=False):
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "run": {
            "mode": mode,
            "started_at": started_at,
            "finished_at": now_iso(),
            "cancelled": bool(cancelled),
        },
        "environment": environment_info(),
        "summary": report_summary(results),
        "sites": results,
        "privacy": {
            "video_titles_included": False,
            "stream_urls_included": False,
            "credentials_included": False,
        },
    }
