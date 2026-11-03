# -*- coding: utf-8 -*-
"""Proxy for protected thumbnail and stream requests offloaded to service.adulthideout.core,
with native Kodi pipe fallback for platforms without core daemon (e.g. Android)
and runtime bridging for embedded webview / standalone player runtimes."""

import os
import platform
import re
import time
import urllib.parse
import urllib.request
import xbmc
import xbmcgui

PORT_PROPERTY = "AdultHideout.ThumbProxyPort"
DEFAULT_CORE_PORT = "8191"

DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0.0.0 Safari/537.36"
)

# Retained for backward-compatibility with callers inspecting these attributes
ALLOWED_HOSTS = frozenset()
ALLOWED_PATH_PREFIXES = ()
UNRESTRICTED_PATH_HOSTS = frozenset()

_IS_ANDROID = "android" in platform.system().lower() or os.path.exists("/system/build.prop")
_CORE_HEALTH_CACHE = [0.0, False]


def _log(message, level=xbmc.LOGINFO):
    xbmc.log("[AdultHideout][ThumbProxy] {}".format(message), level)


def _valid_image_url(url):
    if not url or not isinstance(url, str):
        return False
    return url.startswith("http://") or url.startswith("https://")


def ensure_embedded_image_proxy():
    """If running inside an embedded webview or standalone player runtime,
    ensure the host API server can proxy remote piped images with Referer/User-Agent."""
    try:
        import sys
        server_mod = sys.modules.get("api.server")
        if server_mod:
            handler_cls = None
            for key, val in server_mod.__dict__.items():
                if isinstance(val, type) and hasattr(val, "handle_serve_image"):
                    handler_cls = val
                    break

            if handler_cls and not getattr(handler_cls, "_remote_thumb_patched", False):
                _orig_handle = handler_cls.handle_serve_image

                def _patched_handle_serve_image(self, img_path: str):
                    if not img_path:
                        self.send_response(404)
                        self.end_headers()
                        return
                    for _ in range(4):
                        if not (img_path.startswith("/api/image?path=") or img_path.startswith("api/image?path=")):
                            break
                        img_path = urllib.parse.unquote(img_path.split("path=", 1)[1])
                    if img_path.startswith("http://") or img_path.startswith("https://"):
                        req_url = img_path
                        req_headers = {
                            "User-Agent": DEFAULT_UA
                        }
                        if "|" in img_path:
                            req_url, query_str = img_path.split("|", 1)
                            parsed_params = urllib.parse.parse_qs(query_str, keep_blank_values=True)
                            for k, v in parsed_params.items():
                                req_headers[k] = v[0] if len(v) == 1 else ",".join(v)
                        cache_file = None
                        meta_file = None
                        try:
                            import hashlib
                            import tempfile
                            cache_dir = os.path.join(tempfile.gettempdir(), "ah_thumb_cache")
                            os.makedirs(cache_dir, exist_ok=True)
                            cache_key = hashlib.md5(img_path.encode("utf-8")).hexdigest()
                            cache_file = os.path.join(cache_dir, cache_key + ".bin")
                            meta_file = os.path.join(cache_dir, cache_key + ".meta")
                            if os.path.isfile(cache_file) and os.path.getsize(cache_file) > 0:
                                cached_ctype = "image/jpeg"
                                if os.path.isfile(meta_file):
                                    try:
                                        with open(meta_file, "r", encoding="utf-8") as mf:
                                            cached_ctype = mf.read().strip() or "image/jpeg"
                                    except Exception:
                                        pass
                                with open(cache_file, "rb") as cf:
                                    cached_data = cf.read()
                                self.send_response(200)
                                self.send_header("Content-Type", cached_ctype)
                                self.send_header("Content-Length", str(len(cached_data)))
                                self.send_header("Cache-Control", "public, max-age=604800")
                                self.send_header("Access-Control-Allow-Origin", "*")
                                self.send_header("X-Content-Type-Options", "nosniff")
                                self.end_headers()
                                self.wfile.write(cached_data)
                                return
                        except Exception:
                            pass
                        try:
                            req = urllib.request.Request(req_url, headers=req_headers)
                            with urllib.request.urlopen(req, timeout=12) as resp:
                                data = resp.read()
                                content_type = resp.headers.get("Content-Type", "image/jpeg")
                                if ";" in content_type:
                                    content_type = content_type.split(";")[0].strip()
                                if cache_file and len(data) > 0:
                                    try:
                                        with open(cache_file, "wb") as cf:
                                            cf.write(data)
                                        if meta_file:
                                            with open(meta_file, "w", encoding="utf-8") as mf:
                                                mf.write(content_type)
                                    except Exception:
                                        pass
                                self.send_response(200)
                                self.send_header("Content-Type", content_type)
                                self.send_header("Content-Length", str(len(data)))
                                self.send_header("Cache-Control", "public, max-age=604800")
                                self.send_header("Access-Control-Allow-Origin", "*")
                                self.send_header("X-Content-Type-Options", "nosniff")
                                self.end_headers()
                                self.wfile.write(data)
                                return
                        except Exception as exc:
                            self.send_response(404)
                            self.end_headers()
                            return
                    return _orig_handle(self, img_path)

                handler_cls.handle_serve_image = _patched_handle_serve_image
                handler_cls._remote_thumb_patched = True
                _log("Embedded player runtime hooked: remote thumbnail proxy active")
    except Exception as exc:
        _log("Runtime image proxy notice: {}".format(exc), xbmc.LOGDEBUG)


# Apply patch immediately if embedded player runtime is active
ensure_embedded_image_proxy()


def is_core_healthy():
    """Check if service.adulthideout.core is running and responding on 127.0.0.1:8191."""
    now = time.time()
    if now - _CORE_HEALTH_CACHE[0] < 15.0:
        return _CORE_HEALTH_CACHE[1]

    healthy = False
    try:
        req = urllib.request.Request("http://127.0.0.1:{}/health".format(DEFAULT_CORE_PORT))
        with urllib.request.urlopen(req, timeout=0.2) as resp:
            healthy = (resp.status == 200)
    except Exception:
        healthy = False

    _CORE_HEALTH_CACHE[0] = now
    _CORE_HEALTH_CACHE[1] = healthy
    return healthy


_CORE_START_ATTEMPTED = False


def ensure_core_running(interactive=False):
    """If service.adulthideout.core is installed, ensure its platform binary is present
    (showing an install prompt when interactive=True and missing) and bootstrap the engine."""
    global _CORE_START_ATTEMPTED
    if is_core_healthy():
        return True
    if _CORE_START_ATTEMPTED and not interactive:
        return False
    if not interactive:
        _CORE_START_ATTEMPTED = True

    try:
        addon_path = None
        try:
            import xbmcaddon
            addon_path = xbmcaddon.Addon().getAddonInfo("path")
        except Exception:
            pass

        if not addon_path:
            addon_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

        addons_dir = os.path.dirname(addon_path)
        core_dir = os.path.join(addons_dir, "service.adulthideout.core")
        service_py = os.path.join(core_dir, "service.py")
        if os.path.isfile(service_py):
            import importlib.util
            import threading
            spec = importlib.util.spec_from_file_location("adulthideout_core_service", service_py)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)

            has_binary = True
            if hasattr(mod, "is_binary_installed"):
                has_binary = bool(mod.is_binary_installed(core_dir))

            if not has_binary:
                if interactive and hasattr(mod, "prompt_and_install_core"):
                    declined = False
                    try:
                        declined = xbmcgui.Window(10000).getProperty("AdultHideoutCore.PromptDeclined") == "1"
                    except Exception:
                        declined = False
                    if not declined:
                        _CORE_HEALTH_CACHE[0] = 0.0
                        if mod.prompt_and_install_core(core_dir):
                            _CORE_HEALTH_CACHE[0] = 0.0
                            return is_core_healthy()
                return False

            if hasattr(mod, "start_engine"):
                _log("Found installed Core binary, bootstrapping engine...")
                try:
                    xbmcgui.Window(10000).setProperty("AdultHideoutCore.TriggerStart", str(time.time()))
                except Exception:
                    pass
                t = threading.Thread(target=mod.start_engine, args=(core_dir,), daemon=True)
                t.start()
                for _ in range(15):
                    time.sleep(0.1)
                    _CORE_HEALTH_CACHE[0] = 0.0
                    if is_core_healthy():
                        _log("service.adulthideout.core bootstrapped successfully on port 8191")
                        return True
    except Exception as exc:
        _log("Bootstrap core notice: {}".format(exc), xbmc.LOGDEBUG)

    return False


class ThumbProxy:
    """Lightweight connector. The actual high-performance multi-threaded proxying
    is handled natively by the Rust core engine (service.adulthideout.core)."""

    def __init__(self):
        pass

    def start(self):
        ensure_embedded_image_proxy()
        if not is_core_healthy():
            ensure_core_running()
        if is_core_healthy():
            window = xbmcgui.Window(10000)
            window.setProperty(PORT_PROPERTY, DEFAULT_CORE_PORT)
            _log("ThumbProxy delegated to service.adulthideout.core on 127.0.0.1:{}".format(DEFAULT_CORE_PORT))
        return True

    def stop(self):
        xbmcgui.Window(10000).clearProperty(PORT_PROPERTY)


def build_thumb_url(image_url, referer=None):
    """Return a local Rust-core proxy URL for protected thumbnails if core is running,
    otherwise fallback to Kodi's native pipe syntax with Referer and User-Agent."""
    if not _valid_image_url(image_url):
        return image_url

    # Strip existing localhost proxy wrapping if passed recursively
    if image_url.startswith("http://127.0.0.1:8191/thumb?"):
        parsed = urllib.parse.urlparse(image_url)
        params = urllib.parse.parse_qs(parsed.query)
        image_url = params.get("u", [image_url])[0]
        if not referer:
            referer = params.get("r", [None])[0]

    # If Rust Core is healthy and running, use local proxy
    if is_core_healthy():
        port = DEFAULT_CORE_PORT
        data = {"u": image_url}
        if referer:
            data["r"] = referer
        return "http://127.0.0.1:{}/thumb?{}".format(port, urllib.parse.urlencode(data))

    # Core is not running (e.g. on Android or embedded runtimes).
    # Use Kodi's native CCurlFile pipe syntax so Kodi or embedded runtimes send proper headers:
    if "|" not in image_url:
        params = {}
        if referer:
            params["Referer"] = referer
        params["User-Agent"] = DEFAULT_UA
        return "{}|{}".format(image_url, urllib.parse.urlencode(params))

    return image_url


def build_proxy_stream_url(stream_url, referer=None):
    """Return a local Rust-core proxy URL for video stream playback."""
    if not stream_url or not isinstance(stream_url, str):
        return stream_url
    port = DEFAULT_CORE_PORT
    data = {"url": stream_url}
    if referer:
        data["r"] = referer
    return "http://127.0.0.1:{}/proxy?{}".format(port, urllib.parse.urlencode(data))


def build_stream_url(stream_url, referer=None):
    """Return a local Rust-core HLS/m3u8 stream proxy URL."""
    if not stream_url or not isinstance(stream_url, str):
        return stream_url
    port = DEFAULT_CORE_PORT
    data = {"url": stream_url}
    if referer:
        data["r"] = referer
    return "http://127.0.0.1:{}/stream/playlist.m3u8?{}".format(port, urllib.parse.urlencode(data))


def build_loadvid_url(filename):
    if not re.match(r"^adulthideout_loadvid_[0-9a-f]{16}\.m3u8$", filename or ""):
        return ""
    port = DEFAULT_CORE_PORT
    return "http://127.0.0.1:{}/proxy?url={}".format(port, filename)
