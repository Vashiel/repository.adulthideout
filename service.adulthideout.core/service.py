import ctypes
import os
import platform
import shutil
import stat
import subprocess
import time
import urllib.request

try:
    import xbmc
    import xbmcaddon
    import xbmcgui
    import xbmcvfs
except ImportError:
    xbmc = None
    xbmcaddon = None
    xbmcgui = None
    xbmcvfs = None

DEFAULT_BIND = "127.0.0.1:8191"
HEALTH_URL = f"http://{DEFAULT_BIND}/health"
CORE_VERSION = "1.0.0"
RAW_BASE_URLS = (
    "https://raw.githubusercontent.com/Vashiel/repository.adulthideout/master/core-binaries",
    "https://github.com/Vashiel/repository.adulthideout/raw/master/core-binaries",
    "https://github.com/Vashiel/PhantomFlare/releases/latest/download",
)
_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def _log(msg: str, level=None):
    if xbmc is not None:
        xbmc.log(f"[AdultHideoutCore] {msg}", level if level is not None else xbmc.LOGINFO)


def _tr(string_id: int, fallback: str, *args) -> str:
    text = fallback
    if xbmcaddon is not None:
        for addon_id in ("plugin.video.adulthideout", "service.adulthideout.core"):
            try:
                loc = xbmcaddon.Addon(addon_id).getLocalizedString(string_id)
                if loc:
                    text = loc
                    break
            except Exception:
                pass
    if args:
        try:
            return text.format(*args)
        except Exception:
            try:
                return fallback.format(*args)
            except Exception:
                return text
    return text


def detect_platform_arch():
    sys_name = platform.system().lower()
    machine = platform.machine().lower()
    is_64bit = ctypes.sizeof(ctypes.c_void_p) == 8

    if "android" in sys_name or os.path.exists("/system/build.prop"):
        arch = "android-arm64-v8a" if is_64bit else "android-armeabi-v7a"
        return arch, "libadulthideout_core.so", "adulthideout-core", ["libadulthideout_core.so"]
    if sys_name == "windows":
        arch = "windows-x86_64" if is_64bit else "windows-x86"
        req = ["adulthideout_core.dll", "adulthideout-core.exe", "libwinpthread-1.dll"] if is_64bit else ["adulthideout_core.dll", "adulthideout-core.exe"]
        return arch, "adulthideout_core.dll", "adulthideout-core.exe", req
    if sys_name == "linux":
        arch = "linux-aarch64" if ("arm" in machine or "aarch64" in machine) else "linux-x86_64"
        return arch, "libadulthideout_core.so", "adulthideout-core", ["libadulthideout_core.so"]
    if sys_name == "darwin":
        arch = "darwin-arm64" if "arm" in machine else "darwin-x86_64"
        return arch, "libadulthideout_core.dylib", "adulthideout-core", ["libadulthideout_core.dylib"]

    return None, None, None, []


def get_data_dir(addon_dir: str) -> str:
    if xbmcvfs is not None:
        try:
            p = xbmcvfs.translatePath("special://userdata/addon_data/service.adulthideout.core")
            if p:
                return os.path.normpath(p.rstrip("/\\"))
        except Exception:
            pass
    if addon_dir:
        norm = os.path.normpath(addon_dir.rstrip("/\\"))
        addons_parent = os.path.dirname(norm)
        kodi_root = os.path.dirname(addons_parent)
        candidate = os.path.join(kodi_root, "userdata", "addon_data", "service.adulthideout.core")
        if os.path.isdir(os.path.join(kodi_root, "userdata")):
            return candidate
    return addon_dir.rstrip("/\\") if addon_dir else ""


def resolve_paths(addon_dir: str):
    if addon_dir:
        addon_dir = addon_dir.rstrip("/\\")
    arch, lib_name, bin_name, _ = detect_platform_arch()
    if not arch:
        return None, None

    data_dir = get_data_dir(addon_dir)
    search_roots = []
    if data_dir:
        search_roots.append(data_dir)
    if addon_dir and addon_dir not in search_roots:
        search_roots.append(addon_dir)

    for root in search_roots:
        lib_candidate = os.path.join(root, "bin", arch, lib_name) if lib_name else None
        bin_candidate = os.path.join(root, "bin", arch, bin_name) if bin_name else None
        if (lib_candidate and os.path.isfile(lib_candidate) and os.path.getsize(lib_candidate) > 100000) or (
            bin_candidate and os.path.isfile(bin_candidate) and os.path.getsize(bin_candidate) > 100000
        ):
            return lib_candidate, bin_candidate

    primary_root = data_dir or addon_dir
    lib_path = os.path.join(primary_root, "bin", arch, lib_name) if lib_name else None
    bin_path = os.path.join(primary_root, "bin", arch, bin_name) if bin_name else None
    return lib_path, bin_path


def is_binary_installed(addon_dir: str) -> bool:
    if addon_dir:
        addon_dir = addon_dir.rstrip("/\\")
    arch, _, _, required_files = detect_platform_arch()
    if not arch or not required_files:
        return False
    data_dir = get_data_dir(addon_dir)
    for root in (data_dir, addon_dir):
        if not root:
            continue
        target_dir = os.path.join(root, "bin", arch)
        if all(
            os.path.isfile(os.path.join(target_dir, fname))
            and os.path.getsize(os.path.join(target_dir, fname)) > 10000
            for fname in required_files
        ):
            return True
    return False


def download_platform_binaries(addon_dir: str, show_progress: bool = True) -> bool:
    if addon_dir:
        addon_dir = addon_dir.rstrip("/\\")
    arch, _, _, required_files = detect_platform_arch()
    if not arch or not required_files:
        _log("Unsupported platform architecture for Core binary download", xbmc.LOGWARNING if xbmc else None)
        return False

    data_dir = get_data_dir(addon_dir)
    target_dir = os.path.join(data_dir, "bin", arch)
    os.makedirs(target_dir, exist_ok=True)

    if xbmcgui is not None:
        try:
            xbmcgui.Window(10000).setProperty("AdultHideoutCore.Downloading", "1")
        except Exception:
            pass

    progress = None
    if show_progress and xbmcgui is not None:
        try:
            progress = xbmcgui.DialogProgress()
            progress.create(
                "AdultHideout Core",
                _tr(31015, "Initializing Core engine for {}... ({} KB)", arch, 0),
            )
        except Exception:
            progress = None

    try:
        total_files = len(required_files)
        for idx, filename in enumerate(required_files):
            dest_path = os.path.join(target_dir, filename)
            tmp_path = dest_path + ".tmp"
            downloaded = False
            last_err = None

            for base_url in RAW_BASE_URLS:
                if base_url.endswith("/download"):
                    url = f"{base_url}/{arch}-{filename}"
                else:
                    url = f"{base_url}/{arch}/{filename}"
                try:
                    req = urllib.request.Request(
                        url,
                        headers={"User-Agent": "AdultHideoutCore/1.0 (+https://github.com/Vashiel/repository.adulthideout)"},
                    )
                    with _OPENER.open(req, timeout=20.0) as resp:
                        if resp.status != 200:
                            continue
                        total_bytes = int(resp.headers.get("Content-Length") or 0)
                        read_bytes = 0
                        with open(tmp_path, "wb") as out_f:
                            while True:
                                if progress is not None and progress.iscanceled():
                                    raise RuntimeError("Cancelled by user")
                                chunk = resp.read(65536)
                                if not chunk:
                                    break
                                out_f.write(chunk)
                                read_bytes += len(chunk)
                                if progress is not None:
                                    file_pct = int((read_bytes * 100) / total_bytes) if total_bytes > 0 else 50
                                    overall_pct = int(((idx * 100) + file_pct) / total_files)
                                    progress.update(
                                        min(99, max(1, overall_pct)),
                                        _tr(31015, "Downloading {} for {}... ({} KB)", filename, arch, read_bytes // 1024),
                                    )
                    if os.path.isfile(tmp_path) and os.path.getsize(tmp_path) > 10000:
                        if os.path.exists(dest_path):
                            try:
                                os.remove(dest_path)
                            except OSError:
                                pass
                        os.replace(tmp_path, dest_path)
                        if platform.system().lower() != "windows":
                            try:
                                os.chmod(dest_path, 0o755)
                            except OSError:
                                pass
                        downloaded = True
                        _log(f"Downloaded {filename} ({read_bytes} bytes) from {url}")
                        break
                except Exception as exc:
                    last_err = exc
                    try:
                        if os.path.exists(tmp_path):
                            os.remove(tmp_path)
                    except OSError:
                        pass

            if not downloaded:
                _log(f"Failed to download {filename} for {arch}: {last_err}", xbmc.LOGERROR if xbmc else None)
                return False

        try:
            with open(os.path.join(target_dir, "version.txt"), "w", encoding="utf-8") as vf:
                vf.write(CORE_VERSION)
        except Exception:
            pass

        if progress is not None:
            progress.update(100, _tr(31016, "Starting AdultHideout Core engine..."))
        return True
    finally:
        if xbmcgui is not None:
            try:
                xbmcgui.Window(10000).setProperty("AdultHideoutCore.Downloading", "0")
            except Exception:
                pass
        if progress is not None:
            try:
                progress.close()
            except Exception:
                pass


def prompt_and_install_core(addon_dir: str) -> bool:
    if addon_dir:
        addon_dir = addon_dir.rstrip("/\\")
    if is_healthy():
        return True
    if is_binary_installed(addon_dir):
        start_engine(addon_dir)
        for _ in range(15):
            if is_healthy():
                return True
            time.sleep(0.1)
        return is_healthy()

    arch, _, _, _ = detect_platform_arch()
    if not arch:
        return False

    # Wait if another thread or service is actively downloading
    if xbmcgui is not None:
        try:
            if xbmcgui.Window(10000).getProperty("AdultHideoutCore.Downloading") == "1":
                for _ in range(40):
                    time.sleep(0.5)
                    if is_healthy():
                        return True
                    if xbmcgui.Window(10000).getProperty("AdultHideoutCore.Downloading") != "1":
                        break
        except Exception:
            pass

    if is_healthy():
        return True

    ok = download_platform_binaries(addon_dir, show_progress=True)
    if not ok:
        return False

    try:
        if xbmcgui is not None:
            xbmcgui.Window(10000).setProperty("AdultHideoutCore.TriggerStart", str(time.time()))
    except Exception:
        pass

    for _ in range(20):
        if is_healthy():
            break
        time.sleep(0.15)

    if not is_healthy():
        start_engine(addon_dir)

    for _ in range(15):
        if is_healthy():
            break
        time.sleep(0.1)

    return is_healthy()


def is_healthy() -> bool:
    try:
        req = urllib.request.Request(HEALTH_URL)
        with _OPENER.open(req, timeout=2.0) as resp:
            return resp.status == 200
    except Exception:
        return False


def start_engine(addon_dir: str):
    lib_path, bin_path = resolve_paths(addon_dir)
    loaded_lib = None
    proc = None
    sys_name = platform.system().lower()
    is_android = "android" in sys_name or os.path.exists("/system/build.prop")

    # 1. Try In-Process native library (cdylib via ctypes: works everywhere, including Android)
    if lib_path and os.path.exists(lib_path):
        actual_lib_path = lib_path

        if is_android:
            # Android linker namespace blocks dlopen from external storage (/storage or /sdcard).
            # Copy to internal app storage under /data (especially code_cache) where classloader-namespace has permitted paths.
            pkg_name = None
            try:
                with open("/proc/self/cmdline", "rb") as cf:
                    pkg_name = cf.read().split(b"\x00")[0].decode("utf-8", "ignore").strip()
            except Exception:
                pass

            target_dirs = []
            if pkg_name:
                for base in ("/data/user/0", "/data/data"):
                    target_dirs.extend([
                        os.path.join(base, pkg_name, "code_cache"),
                        os.path.join(base, pkg_name, "cache"),
                        os.path.join(base, pkg_name, "files"),
                    ])

            target_dirs.extend([
                "/data/user/0/org.xbmc.kodi/code_cache",
                "/data/data/org.xbmc.kodi/code_cache",
                "/data/user/0/org.xbmc.kodi/cache",
                "/data/data/org.xbmc.kodi/cache",
                "/data/user/0/org.xbmc.kodi/files",
                "/data/data/org.xbmc.kodi/files",
            ])

            if xbmcvfs:
                try:
                    temp_dir = xbmcvfs.translatePath("special://temp")
                    if temp_dir and temp_dir not in target_dirs:
                        target_dirs.append(temp_dir)
                except Exception:
                    pass

            for tdir in target_dirs:
                try:
                    if os.path.isdir(tdir):
                        candidate = os.path.join(tdir, "libadulthideout_core.so")
                        shutil.copy2(lib_path, candidate)
                        try:
                            os.chmod(candidate, 0o755)
                        except Exception:
                            pass
                        actual_lib_path = candidate
                        _log(f"Copied library to internal path: {actual_lib_path}")
                        break
                except Exception as ce:
                    _log(f"Failed to copy to {tdir}: {ce}", xbmc.LOGWARNING if xbmc else None)

        if sys_name == "windows" and hasattr(os, "add_dll_directory"):
            try:
                os.add_dll_directory(os.path.dirname(actual_lib_path))
            except Exception:
                pass

        try:
            _log(f"Loading in-process engine from {actual_lib_path}")
            loaded_lib = ctypes.CDLL(actual_lib_path)
            loaded_lib.start_core_service.argtypes = [ctypes.c_uint16]
            loaded_lib.start_core_service.restype = ctypes.c_int32
            loaded_lib.stop_core_service.restype = ctypes.c_int32

            res = loaded_lib.start_core_service(8191)
            _log(f"In-process engine started (result={res})")

            for _ in range(15):
                if is_healthy():
                    break
                time.sleep(0.1)
        except Exception as e:
            _log(f"In-process ctypes load failed: {e}", xbmc.LOGWARNING if xbmc else None)
            loaded_lib = None

    # 2. Fallback to subprocess if in-process library was not available (non-Android only)
    if not is_healthy() and bin_path and os.path.exists(bin_path):
        if is_android:
            _log("Standalone binary execution is disabled on Android; using in-process engine.")
            return loaded_lib, proc
        _log(f"Falling back to standalone process: {bin_path}")
        if sys_name != "windows":
            try:
                st = os.stat(bin_path)
                os.chmod(bin_path, st.st_mode | stat.S_IEXEC)
            except OSError:
                pass

        env = os.environ.copy()
        env["PHANTOMFLARE_BIND"] = DEFAULT_BIND

        extra_kwargs = {}
        if sys_name == "windows":
            extra_kwargs["creationflags"] = 0x08000000  # CREATE_NO_WINDOW

        try:
            proc = subprocess.Popen(
                [bin_path],
                cwd=os.path.dirname(bin_path) or addon_dir,
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                **extra_kwargs,
            )
            _log(f"Started engine process (PID {proc.pid})")
        except Exception as e:
            _log(f"Failed to spawn process: {e}", xbmc.LOGERROR if xbmc else None)

    return loaded_lib, proc


def run_kodi_service() -> None:
    if xbmcaddon is None or xbmc is None:
        return

    sys_name = platform.system().lower()
    is_android = "android" in sys_name or os.path.exists("/system/build.prop")
    if is_android:
        _log("Android environment detected: Ready for in-process ARM core engine.")

    addon = xbmcaddon.Addon()
    addon_dir = xbmcvfs.translatePath(addon.getAddonInfo("path")).rstrip("/\\")

    loaded_lib = None
    proc = None

    if is_healthy():
        _log(f"Existing engine daemon already responsive on http://{DEFAULT_BIND}/v1")
    elif is_binary_installed(addon_dir):
        loaded_lib, proc = start_engine(addon_dir)
    else:
        _log("Core binary not yet installed for this system; downloading platform binary automatically in background...")
        try:
            if download_platform_binaries(addon_dir, show_progress=False):
                loaded_lib, proc = start_engine(addon_dir)
        except Exception as exc:
            _log(f"Auto-download on startup notice: {exc}", xbmc.LOGWARNING if xbmc else None)

    failed_checks = 0
    last_trigger = ""
    monitor = xbmc.Monitor()
    while not monitor.abortRequested():
        # Poll faster (1.0s) while binary is not yet running so post-install activation is instant without restart
        wait_interval = 10.0 if (loaded_lib is not None or proc is not None or is_healthy()) else 1.0
        if monitor.waitForAbort(wait_interval):
            break

        if loaded_lib is None and proc is None and not is_healthy():
            trigger = ""
            if xbmcgui is not None:
                try:
                    trigger = xbmcgui.Window(10000).getProperty("AdultHideoutCore.TriggerStart") or ""
                except Exception:
                    trigger = ""
            if (trigger and trigger != last_trigger) or is_binary_installed(addon_dir):
                last_trigger = trigger
                if is_binary_installed(addon_dir):
                    _log("Detected newly installed Core binary; starting engine immediately...")
                    loaded_lib, proc = start_engine(addon_dir)
            elif not is_binary_installed(addon_dir) and (xbmcgui is None or xbmcgui.Window(10000).getProperty("AdultHideoutCore.Downloading") != "1"):
                try:
                    if download_platform_binaries(addon_dir, show_progress=False):
                        loaded_lib, proc = start_engine(addon_dir)
                except Exception:
                    pass
            continue

        healthy = False
        if loaded_lib is not None and hasattr(loaded_lib, "is_core_service_running"):
            try:
                healthy = bool(loaded_lib.is_core_service_running())
            except Exception:
                healthy = False
        if not healthy:
            healthy = is_healthy()

        if healthy:
            failed_checks = 0
        else:
            failed_checks += 1
            if failed_checks >= 3:
                _log("Daemon unresponsive after 3 checks, restarting...", xbmc.LOGWARNING)
                failed_checks = 0
                if loaded_lib is not None:
                    try:
                        loaded_lib.stop_core_service()
                    except Exception:
                        pass
                    time.sleep(0.5)
                    try:
                        loaded_lib.start_core_service(8191)
                    except Exception:
                        pass
                elif proc is not None:
                    if proc.poll() is None:
                        try:
                            proc.terminate()
                            proc.wait(timeout=1.0)
                        except Exception:
                            pass
                    time.sleep(0.5)
                    try:
                        _, bin_path = resolve_paths(addon_dir)
                        env = os.environ.copy()
                        env["PHANTOMFLARE_BIND"] = DEFAULT_BIND
                        extra_kwargs = {}
                        if platform.system().lower() == "windows":
                            extra_kwargs["creationflags"] = 0x08000000
                        proc = subprocess.Popen(
                            [bin_path],
                            cwd=os.path.dirname(bin_path) or addon_dir,
                            env=env,
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                            **extra_kwargs,
                        )
                    except Exception:
                        pass
                elif is_binary_installed(addon_dir):
                    loaded_lib, proc = start_engine(addon_dir)

    # Clean shutdown
    if loaded_lib is not None:
        try:
            loaded_lib.stop_core_service()
        except Exception:
            pass
    if proc is not None and proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=2.0)
        except Exception:
            proc.kill()

    _log("Service stopped cleanly.")


if __name__ == "__main__":
    run_kodi_service()
