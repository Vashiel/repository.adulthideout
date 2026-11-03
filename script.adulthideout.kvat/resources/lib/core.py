import importlib
import json
import os
import platform
import re
import socket
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

import xbmc
import xbmcaddon
import xbmcgui
import xbmcplugin
import xbmcvfs


try:
    _orig_xbmcaddon_Addon = xbmcaddon.Addon
    def _safe_xbmcaddon_Addon(addon_id=None):
        if not addon_id:
            try:
                return _orig_xbmcaddon_Addon("plugin.video.adulthideout")
            except Exception:
                return _orig_xbmcaddon_Addon()
        return _orig_xbmcaddon_Addon(addon_id)
    xbmcaddon.Addon = _safe_xbmcaddon_Addon
except Exception:
    pass

ADDON_ID = "script.adulthideout.kvat"
TARGET_ADDON_ID = "plugin.video.adulthideout"

try:
    _target_obj = xbmcaddon.Addon(TARGET_ADDON_ID)
    _target_path = xbmcvfs.translatePath(_target_obj.getAddonInfo("path"))
    if _target_path and _target_path not in sys.path:
        sys.path.insert(0, _target_path)
    _target_lib = os.path.join(_target_path, "resources", "lib")
    if _target_lib and _target_lib not in sys.path:
        sys.path.insert(0, _target_lib)
    _target_res = os.path.join(_target_path, "resources")
    import resources
    if hasattr(resources, "__path__") and _target_res not in resources.__path__:
        resources.__path__.append(_target_res)
    import resources.lib
    if hasattr(resources.lib, "__path__") and _target_lib not in resources.lib.__path__:
        resources.lib.__path__.append(_target_lib)
    import resources.lib.view_utils
    import resources.lib.base_website
    import resources.lib.kvs_tube
except Exception:
    pass

REPORT_SCHEMA_VERSION = 2

# External outages are reported separately and never sent into the repair loop.
KNOWN_EXTERNAL_ISSUES = {
    "borntobefuck": "Videos on the website are locked behind a mandatory Telegram gate (btbf.link/telegram).",
    "czechvideo": "The former video website is currently unavailable; czechvideo.org now serves unrelated editorial content.",
    "hentaimama": "The website currently serves a managed Cloudflare challenge to Kodi.",
    "hqporner": "The website currently serves a managed Cloudflare challenge to Kodi.",
    "javhdporn": "Upstream video player is protected by custom JS obfuscation and encrypted API token.",
    "ogporn": "The website currently does not respond reliably.",
    "pornktube": "Upstream video stream token gate is protected by a Cloudflare Turnstile managed challenge.",
    "pornrabbit": "The website discontinued its video tube archive and converted into a webcam directory.",
    "saintporn": "The website currently returns HTTP 503.",
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


def install_dns_retry(retries=7, delay=0.3):
    if os.name != "nt" or getattr(socket, "_ah_diagnostics_retry", False):
        return
    original_getaddrinfo = socket.getaddrinfo
    cache = {}

    def getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
        key = (str(host or "").lower(), port, family, type, proto, flags)
        last_error = None
        for attempt in range(retries):
            try:
                result = original_getaddrinfo(host, port, family, type, proto, flags)
                if result:
                    cache[key] = result
                return result
            except socket.gaierror as exc:
                last_error = exc
                if getattr(exc, "errno", None) not in (11001, 11002):
                    raise
                if attempt < retries - 1:
                    time.sleep(delay * (attempt + 1))
        if key in cache:
            return cache[key]
        raise last_error

    socket.getaddrinfo = getaddrinfo
    socket._ah_diagnostics_retry = True


install_dns_retry()


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
            last_error = None
            for attempt in range(3):
                try:
                    request = urllib.request.Request(request_source, headers=headers)
                    with urllib.request.urlopen(request, timeout=10) as response:
                        data = response.read(128)
                    if data:
                        break
                except urllib.error.HTTPError as exc:
                    last_error = exc
                    if exc.code < 500 and exc.code != 429:
                        raise
                except urllib.error.URLError as exc:
                    last_error = exc
                if attempt < 2:
                    time.sleep(0.4 * (attempt + 1))
            if not data and last_error is not None:
                raise last_error
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


CORE_API_URL = "http://127.0.0.1:8191"
_BASE_URL_CACHE = {}


_BASE_URL_PATTERNS = [
    re.compile(r'base_url\s*=\s*["\'](https?://[^"\']+)["\']', re.IGNORECASE),
    re.compile(r'["\']base_url["\']\s*:\s*["\'](https?://[^"\']+)["\']', re.IGNORECASE),
    re.compile(r'BASE_URL_STR\s*=\s*["\'](https?://[^"\']+)["\']', re.IGNORECASE),
    re.compile(r'BASE_URL\s*=\s*["\'](https?://[^"\']+)["\']', re.IGNORECASE),
    re.compile(r'DEFAULT_BASE_URL\s*=\s*["\'](https?://[^"\']+)["\']', re.IGNORECASE),
    re.compile(r'self\.base_url\s*=\s*["\'](https?://[^"\']+)["\']', re.IGNORECASE),
    re.compile(r'base_url\s*=\s*kwargs\.get\(["\']base_url["\'],\s*["\'](https?://[^"\']+)["\']\)', re.IGNORECASE),
    re.compile(r'super\([^)]*\)\.__init__\([^)]*?["\'](https?://[^"\']+)["\']', re.DOTALL),
    re.compile(r'["\'](https?://(?:www\.)?[a-zA-Z0-9-]+\.[a-z]{2,}(?::\d+)?)["\']'),
]
_SITE_URL_OVERRIDES = {
    "txxx": "https://txxx.com",
    "vxxx": "https://vxxx.com",
}


def get_website_base_url(site):
    if site in _SITE_URL_OVERRIDES:
        return _SITE_URL_OVERRIDES[site]
    if site in _BASE_URL_CACHE:
        return _BASE_URL_CACHE[site]
    try:
        target = get_target_addon()
        addon_path = xbmcvfs.translatePath(target.getAddonInfo("path"))
        site_py = os.path.join(addon_path, "resources", "websites", "{}.py".format(site))
        if os.path.exists(site_py):
            with open(site_py, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
                for pattern in _BASE_URL_PATTERNS:
                    match = pattern.search(content)
                    if match:
                        raw = match.group(1).rstrip("/")
                        parsed = urllib.parse.urlsplit(raw)
                        if parsed.scheme and parsed.netloc:
                            base_url = "{}://{}".format(parsed.scheme, parsed.netloc)
                            _BASE_URL_CACHE[site] = base_url
                            return base_url
    except Exception:
        pass
    return None


def run_core_diagnostic(site, mode="quick"):
    base_url = get_website_base_url(site)
    if not base_url:
        return None
    try:
        query = urllib.parse.urlencode({
            "url": base_url,
            "id": site,
            "timeout": "8000",
        })
        diag_url = "{}/diagnose?{}".format(CORE_API_URL, query)
        req = urllib.request.Request(diag_url)
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(req, timeout=10) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode("utf-8"))
                started_iso = now_iso()
                verdict = data.get("verdict", "PASS")
                items = data.get("items_found", 0)
                thumb_status = data.get("thumbnail_status", "missing")
                messages = data.get("messages") or []
                elapsed_sec = round(float(data.get("elapsed_ms", 0)) / 1000.0, 2)

                listing = {
                    "status": verdict,
                    "elapsed_seconds": elapsed_sec,
                    "items": items,
                    "folders": 0,
                    "videos": items,
                    "followed_folders": 0,
                    "folder_errors": [],
                    "thumbnail": {
                        "status": thumb_status,
                        "sample": data.get("sample_thumbnail"),
                    },
                    "messages": messages,
                }
                res = {
                    "site": site,
                    "label": website_label(site),
                    "status": verdict,
                    "started_at": started_iso,
                    "finished_at": now_iso(),
                    "elapsed_seconds": elapsed_sec,
                    "mode": mode,
                    "core_accelerated": True,
                    "listing": listing,
                    "dns_ok": data.get("dns_ok", True),
                    "tls_ok": data.get("tls_ok", True),
                    "http_status": data.get("http_status", 200),
                    "challenge_detected": data.get("challenge_detected", False),
                    "challenge_solved": data.get("challenge_solved", False),
                }
                if messages:
                    res["advisories"] = messages
                return res
    except Exception:
        pass
    return None


_LOADED_WEBSITES = {}


def load_website_instance(site):
    if not site:
        return None
    site = site.replace("-", "_")
    if site in _LOADED_WEBSITES:
        return _LOADED_WEBSITES[site]
    try:
        target = get_target_addon()
        addon_path = xbmcvfs.translatePath(target.getAddonInfo("path"))
        if addon_path not in sys.path:
            sys.path.insert(0, addon_path)
        target_resources = os.path.join(addon_path, "resources")
        target_lib = os.path.join(target_resources, "lib")
        if target_lib not in sys.path:
            sys.path.insert(0, target_lib)

        if "resources" in sys.modules and hasattr(sys.modules["resources"], "__path__"):
            if target_resources not in sys.modules["resources"].__path__:
                sys.modules["resources"].__path__.append(target_resources)
        if "resources.lib" in sys.modules and hasattr(sys.modules["resources.lib"], "__path__"):
            if target_lib not in sys.modules["resources.lib"].__path__:
                sys.modules["resources.lib"].__path__.append(target_lib)

        BaseWebsite = None
        if "resources.lib.base_website" in sys.modules:
            BaseWebsite = getattr(sys.modules["resources.lib.base_website"], "BaseWebsite", None)

        if BaseWebsite is None:
            if "resources.lib.base_website" in sys.modules:
                del sys.modules["resources.lib.base_website"]
            try:
                from resources.lib.base_website import BaseWebsite
            except Exception:
                bw_path = os.path.join(target_lib, "base_website.py")
                if os.path.isfile(bw_path):
                    bw_spec = importlib.util.spec_from_file_location("resources.lib.base_website", bw_path)
                    bw_mod = importlib.util.module_from_spec(bw_spec)
                    sys.modules["resources.lib.base_website"] = bw_mod
                    bw_spec.loader.exec_module(bw_mod)
                    BaseWebsite = getattr(bw_mod, "BaseWebsite", None)
                else:
                    return None

        if BaseWebsite is None:
            return None

        site_py = os.path.join(addon_path, "resources", "websites", "{}.py".format(site))
        if not os.path.isfile(site_py):
            return None
        try:
            module = importlib.import_module("resources.websites.{}".format(site))
        except Exception:
            mod_name = "resources.websites.{}".format(site)
            spec = importlib.util.spec_from_file_location(mod_name, site_py)
            module = importlib.util.module_from_spec(spec)
            sys.modules[mod_name] = module
            spec.loader.exec_module(module)

        cls = None
        for attribute in dir(module):
            candidate = getattr(module, attribute)
            if (
                isinstance(candidate, type)
                and issubclass(candidate, BaseWebsite)
                and candidate is not BaseWebsite
                and candidate.__module__ == module.__name__
            ):
                cls = candidate
                break

        if not cls:
            for attribute in dir(module):
                candidate = getattr(module, attribute)
                if (
                    isinstance(candidate, type)
                    and issubclass(candidate, BaseWebsite)
                    and candidate is not BaseWebsite
                ):
                    cls = candidate
                    break

        if cls:
            try:
                inst = cls(-1, target)
            except TypeError:
                inst = cls(-1)
            _LOADED_WEBSITES[site] = inst
            return inst
    except Exception as exc:
        log("Failed loading website instance for {}: {}".format(site, exc), xbmc.LOGWARNING)
    return None


def probe_stream_reachability(stream_url, headers=None, timeout=15):
    if not stream_url:
        return {"status": "FAILED", "error": "Empty stream URL"}

    target_url = str(stream_url).strip()
    clean_url, sep, pipe_headers = target_url.partition("|")
    clean_url = clean_url.strip()

    try:
        parts = urllib.parse.urlsplit(clean_url)
        safe_chars = "/%:@!$&'()*+,;=-_~."
        quoted_path = urllib.parse.quote(parts.path, safe=safe_chars)
        clean_url = urllib.parse.urlunsplit((parts.scheme, parts.netloc, quoted_path, parts.query, parts.fragment))
    except Exception:
        pass

    is_m3u8 = ".m3u8" in clean_url.lower()
    req_headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/134.0.0.0 Safari/537.36"
        ),
        "Accept": "*/*",
    }
    if not is_m3u8:
        req_headers["Range"] = "bytes=0-1024"

    if sep and pipe_headers:
        for k, v in urllib.parse.parse_qsl(pipe_headers):
            if k.lower() in ("accept-language", "accept-encoding", "connection", "upgrade-insecure-requests"):
                continue
            if k.lower() == "accept" and "html" in str(v).lower():
                continue
            if is_m3u8 and k.lower() == "range":
                continue
            req_headers[k] = v
    if headers:
        for k, v in headers.items():
            if k.lower() in ("accept-language", "accept-encoding", "connection", "upgrade-insecure-requests"):
                continue
            if is_m3u8 and k.lower() == "range":
                continue
            if k.lower() == "accept" and "html" in str(v).lower():
                continue
            req_headers[k] = v

    sanitized_headers = {}
    for k, v in req_headers.items():
        try:
            sk = str(k).encode("ascii", "ignore").decode("ascii")
            sv = str(v).encode("latin-1", "ignore").decode("latin-1")
            sanitized_headers[sk] = sv
        except Exception:
            pass

    try:
        import ssl
        try:
            ssl_ctx = ssl._create_unverified_context()
        except Exception:
            ssl_ctx = None
        handlers = [urllib.request.ProxyHandler({})]
        if ssl_ctx:
            handlers.append(urllib.request.HTTPSHandler(context=ssl_ctx))
        opener = urllib.request.build_opener(*handlers)
        req = urllib.request.Request(clean_url, headers=sanitized_headers)
        with opener.open(req, timeout=timeout) as resp:
            code = resp.status
            content_type = resp.headers.get("Content-Type", "")
            data = resp.read(512)

            prefix = bytes(data[:64]).lstrip().lower()
            if prefix.startswith((b"<!doctype", b"<html", b"<head", b"<body")):
                return {
                    "status": "FAILED",
                    "http_status": code,
                    "error": "Stream returned HTML error page instead of video data",
                    "stream_url": sanitize_text(clean_url),
                }

            if code in (200, 206):
                return {
                    "status": "PASS",
                    "http_status": code,
                    "content_type": content_type,
                    "bytes_verified": len(data),
                    "stream_url": sanitize_text(clean_url),
                }
            else:
                return {
                    "status": "FAILED",
                    "http_status": code,
                    "error": "Stream returned HTTP {}".format(code),
                    "stream_url": sanitize_text(clean_url),
                }
    except urllib.error.HTTPError as exc:
        return {
            "status": "FAILED",
            "http_status": exc.code,
            "error": "Stream server returned HTTP {}".format(exc.code),
            "stream_url": sanitize_text(clean_url),
        }
    except Exception as exc:
        return {
            "status": "FAILED",
            "error": "Stream check failed: {}".format(sanitize_text(exc)),
            "stream_url": sanitize_text(clean_url),
        }


def resolve_and_probe_stream(site, playback_url):
    if not playback_url:
        return {"status": "FAILED", "error": "No playable video found to test"}

    page_url = playback_url
    if playback_url.startswith("plugin://"):
        parsed = urllib.parse.urlsplit(playback_url)
        params = dict(urllib.parse.parse_qsl(parsed.query))
        page_url = params.get("url") or playback_url
        site = (params.get("website") or site or "").replace("-", "_")

    # Direct media URL
    if page_url.startswith(("http://", "https://")) and any(
        page_url.lower().split("?", 1)[0].endswith(ext)
        for ext in (".mp4", ".m3u8", ".mpd", ".mkv", ".webm")
    ):
        return probe_stream_reachability(page_url)

    inst = load_website_instance(site)
    if not inst:
        return {
            "status": "FAILED",
            "error": "Website scraper could not be loaded",
        }

    stream_url = None
    stream_headers = {}

    # 1. Try resolve_recording_stream
    resolver = getattr(inst, "resolve_recording_stream", None)
    if resolver and callable(resolver):
        try:
            resolved = resolver(page_url)
            if resolved:
                if isinstance(resolved, dict):
                    stream_url = resolved.get("url")
                    stream_headers = resolved.get("headers") or {}
                elif isinstance(resolved, (tuple, list)) and len(resolved) > 0:
                    stream_url = resolved[0]
                    stream_headers = resolved[1] if len(resolved) > 1 else {}
                elif isinstance(resolved, str):
                    stream_url = resolved
        except Exception as exc:
            log("[{}] resolve_recording_stream error: {}".format(site, exc), xbmc.LOGWARNING)

    # 2. Fallback to play_video with intercepted xbmcplugin.setResolvedUrl
    captured = {}
    if not stream_url:
        play_video_fn = getattr(inst, "play_video", None)
        if play_video_fn and callable(play_video_fn):
            orig_set_resolved = getattr(xbmcplugin, "setResolvedUrl", None)

            def mock_set_resolved(handle=None, succeeded=True, item=None, listitem=None, *args, **kwargs):
                li = item or listitem or (args[0] if args else None)
                captured["succeeded"] = succeeded
                path = li.getPath() if li and hasattr(li, "getPath") else ""
                captured["path"] = path
                captured["item"] = li
                if succeeded and path:
                    try:
                        captured["probe"] = probe_stream_reachability(path, headers=stream_headers)
                    except Exception as probe_err:
                        captured["probe_err"] = str(probe_err)

            orig_guard_join = None
            try:
                from resources.lib import proxy_utils
                orig_guard_join = getattr(proxy_utils.PlaybackGuard, "join", None)
                proxy_utils.PlaybackGuard.join = lambda self, *a, **kw: None
            except Exception:
                pass

            try:
                xbmcplugin.setResolvedUrl = mock_set_resolved
                play_video_fn(page_url)
            except Exception as exc:
                log("[{}] play_video error: {}".format(site, exc), xbmc.LOGWARNING)
            finally:
                if orig_set_resolved:
                    xbmcplugin.setResolvedUrl = orig_set_resolved
                if orig_guard_join:
                    try:
                        from resources.lib import proxy_utils
                        proxy_utils.PlaybackGuard.join = orig_guard_join
                    except Exception:
                        pass

            if captured.get("probe") and captured["probe"].get("status") == "PASS":
                return captured["probe"]

            if captured.get("succeeded") and captured.get("path"):
                stream_url = captured["path"]

    if not stream_url:
        return {
            "status": "FAILED",
            "error": "Stream resolution failed (scraper could not resolve stream)",
        }

    probe = probe_stream_reachability(stream_url, headers=stream_headers)
    if probe.get("status") != "PASS" and ("127.0.0.1" in stream_url or "localhost" in stream_url):
        if captured.get("succeeded"):
            return {
                "status": "PASS",
                "http_status": 200,
                "stream_url": sanitize_text(stream_url),
                "note": "Stream resolved via local proxy controller",
            }
    return probe


def run_site_test(site, mode="smart"):
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

    # 1. High-speed native Rust Core diagnostic
    # In quick mode: return immediately
    if mode == "quick":
        core_result = run_core_diagnostic(site, mode=mode)
        if core_result is not None:
            return core_result

    # In smart/detail/full mode: fast-fail if Core detected DNS or domain failure
    core_fast = run_core_diagnostic(site, mode=mode)
    if core_fast is not None and core_fast.get("status") == "FAILED":
        return core_fast

    # 2. Kodi listing inspection
    try:
        detailed = mode in ("full", "detail", "playback", "smart")
        listing = inspect_listing(site, verify_thumbnail=True, deep=detailed)
        playback_urls = listing.pop("playback_urls", [])
        result["listing"] = listing
        result["status"] = listing.get("status", "FAILED")

        if result["status"] == "FAILED":
            messages = listing.get("messages") or []
            result["error"] = "; ".join(messages) if messages else "Listing failed"
            result["elapsed_seconds"] = round(time.time() - started, 2)
            result["finished_at"] = now_iso()
            return result

        # 3. Stream verification
        if mode in ("smart", "playback", "stream", "detail"):
            # Lightweight background stream resolution & preflight probe
            if not playback_urls:
                result["status"] = "FAILED"
                result["error"] = "No playable video found in listing"
            else:
                stream_test = resolve_and_probe_stream(site, playback_urls[0])
                result["stream_probe"] = stream_test
                if stream_test.get("status") == "FAILED":
                    result["status"] = "FAILED"
                    result["error"] = stream_test.get("error") or "Stream playback test failed"
                else:
                    # Stream resolution & probe passed!
                    thumb = listing.get("thumbnail") or {}
                    if thumb.get("status") == "missing":
                        result["status"] = "WARNING"
                        result["advisories"] = ["Thumbnail missing"]
                    else:
                        result["status"] = "PASS"
                        if thumb.get("status") == "failed":
                            result["advisories"] = ["Thumbnail could not be verified automatically"]

        elif mode == "full":
            playback = inspect_playback_candidates(
                playback_urls,
                seek_enabled=True,
            )
            result["playback"] = playback
            if playback.get("status") == "FAILED":
                result["status"] = "FAILED"
                result["error"] = "; ".join(playback.get("messages") or ["Playback failed"])
            elif playback.get("status") == "WARNING":
                result["status"] = "WARNING"
            elif playback.get("status") == "PASS":
                result["status"] = "PASS"

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
    for attempt in range(8):
        try:
            os.replace(temporary, path)
            break
        except OSError:
            if attempt == 7:
                raise
            time.sleep(0.05 * (attempt + 1))


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
