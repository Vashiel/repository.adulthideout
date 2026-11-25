"""Run: python tests/test_core_service.py"""
import ctypes
import importlib.util
import io
import os
import shutil
import stat
import subprocess
import tempfile


REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
SERVICE_PATH = os.path.join(REPO_ROOT, "service.adulthideout.core", "service.py")

spec = importlib.util.spec_from_file_location("adulthideout_core_service_test", SERVICE_PATH)
svc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(svc)


def _norm(path):
    return path.replace("\\", "/")


def _rmtree_writable(root):
    if not os.path.exists(root):
        return
    for dirpath, _dirnames, filenames in os.walk(root, topdown=False):
        for fname in filenames:
            try:
                os.chmod(os.path.join(dirpath, fname), 0o700)
            except OSError:
                pass
        try:
            os.chmod(dirpath, 0o700)
        except OSError:
            pass
    shutil.rmtree(root)


def test_android_candidate_dirs():
    orig_open = open
    orig_getuid = getattr(os, "getuid", None)
    orig_xbmcvfs = svc.xbmcvfs

    class FakeVfs:
        def __init__(self, temp_path):
            self.temp_path = temp_path

        def translatePath(self, path):
            if path == "special://temp":
                return self.temp_path
            return path

    def fake_open_for(cmdline_bytes):
        def _open(path, *args, **kwargs):
            if path == "/proc/self/cmdline":
                return io.BytesIO(cmdline_bytes)
            return orig_open(path, *args, **kwargs)
        return _open

    import builtins
    real_open = builtins.open
    try:
        # 1. Deduplication when cmdline is org.xbmc.kodi\0 and external temp is filtered out
        builtins.open = fake_open_for(b"org.xbmc.kodi\x00--arg")
        os.getuid = lambda: 10050
        svc.xbmcvfs = FakeVfs("/storage/emulated/0/Android/data/org.xbmc.kodi/files/.kodi/temp")
        dirs = [_norm(d) for d in svc._android_candidate_dirs()]
        assert len(dirs) == len(set(dirs)), ("duplicate dirs found", dirs)
        assert dirs == [
            "/data/user/0/org.xbmc.kodi/code_cache",
            "/data/user/0/org.xbmc.kodi/cache",
            "/data/user/0/org.xbmc.kodi/files",
            "/data/data/org.xbmc.kodi/code_cache",
            "/data/data/org.xbmc.kodi/cache",
            "/data/data/org.xbmc.kodi/files",
        ], dirs

        # 2. Strips :process suffix and prepends multi-user dir for uid >= 100000, keeps internal temp
        builtins.open = fake_open_for(b"org.xbmc.kodi:bg\x00")
        os.getuid = lambda: 1010123
        svc.xbmcvfs = FakeVfs("/data/user/0/org.xbmc.kodi/temp/")
        dirs = [_norm(d) for d in svc._android_candidate_dirs()]
        assert len(dirs) == len(set(dirs)), dirs
        assert dirs[0] == "/data/user/10/org.xbmc.kodi/code_cache", dirs
        assert "/data/user/0/org.xbmc.kodi/code_cache" in dirs, dirs
        assert "/data/data/org.xbmc.kodi/files" in dirs, dirs
        assert dirs[-1] == "/data/user/0/org.xbmc.kodi/temp", dirs
        print("candidate_dirs ok")
    finally:
        builtins.open = real_open
        if orig_getuid is None:
            if hasattr(os, "getuid"):
                delattr(os, "getuid")
        else:
            os.getuid = orig_getuid
        svc.xbmcvfs = orig_xbmcvfs


def test_stage_android_library():
    tmp_root = tempfile.mkdtemp(prefix="ah_core_stage_")
    orig_copy2 = shutil.copy2
    orig_copyfile = shutil.copyfile
    orig_chmod = os.chmod
    try:
        src = os.path.join(tmp_root, "src_lib.so")
        dst_dir = os.path.join(tmp_root, "app_cache")
        os.makedirs(dst_dir, exist_ok=True)
        payload_v1 = b"ELF-TEST-PAYLOAD-V1-" * 100
        with open(src, "wb") as handle:
            handle.write(payload_v1)

        def fail_copy2(*_a, **_kw):
            raise AssertionError("shutil.copy2 must not be used")

        shutil.copy2 = fail_copy2

        # Initial copy stages raw bytes, clears write bits, and leaves no .tmp file
        staged = svc._stage_android_library(src, dst_dir)
        assert staged == os.path.join(dst_dir, "libadulthideout_core.so"), staged
        with open(staged, "rb") as handle:
            assert handle.read() == payload_v1
        assert (stat.S_IMODE(os.stat(staged).st_mode) & 0o222) == 0, oct(os.stat(staged).st_mode)
        assert not os.path.exists(staged + ".tmp")

        # Fast-path reuse when SHA-256 matches, while still restoring read-only bits
        os.chmod(staged, 0o644)
        shutil.copyfile = lambda *_a, **_kw: (_ for _ in ()).throw(AssertionError("copyfile should not run on hash match"))
        reused = svc._stage_android_library(src, dst_dir)
        assert reused == staged
        assert (stat.S_IMODE(os.stat(staged).st_mode) & 0o222) == 0
        shutil.copyfile = orig_copyfile

        # Updating an existing read-only library replaces it cleanly
        payload_v2 = b"ELF-TEST-PAYLOAD-V2-" * 110
        with open(src, "wb") as handle:
            handle.write(payload_v2)
        updated = svc._stage_android_library(src, dst_dir)
        assert updated == staged
        with open(staged, "rb") as handle:
            assert handle.read() == payload_v2
        assert (stat.S_IMODE(os.stat(staged).st_mode) & 0o222) == 0
        assert not os.path.exists(staged + ".tmp")

        # Non-fatal chmod PermissionError still completes staging
        dst_dir_no_chmod = os.path.join(tmp_root, "app_cache_no_chmod")
        os.makedirs(dst_dir_no_chmod, exist_ok=True)
        payload_v3 = b"ELF-TEST-PAYLOAD-V3-" * 120
        with open(src, "wb") as handle:
            handle.write(payload_v3)

        def deny_chmod(_path, _mode):
            raise PermissionError(13, "chmod denied")

        os.chmod = deny_chmod
        fallback_staged = svc._stage_android_library(src, dst_dir_no_chmod)
        os.chmod = orig_chmod
        with open(fallback_staged, "rb") as handle:
            assert handle.read() == payload_v3
        print("stage_android_library ok")
    finally:
        shutil.copy2 = orig_copy2
        shutil.copyfile = orig_copyfile
        os.chmod = orig_chmod
        _rmtree_writable(tmp_root)


def test_start_engine_android_fallback():
    tmp_root = tempfile.mkdtemp(prefix="ah_core_start_")
    orig_resolve = svc.resolve_paths
    orig_cand = svc._android_candidate_dirs
    orig_stage = svc._stage_android_library
    orig_is_healthy = svc.is_healthy
    orig_cdll = ctypes.CDLL
    orig_system = svc.platform.system
    orig_popen = subprocess.Popen
    orig_sleep = svc.time.sleep
    try:
        src = os.path.join(tmp_root, "bin", "libadulthideout_core.so")
        os.makedirs(os.path.dirname(src), exist_ok=True)
        with open(src, "wb") as handle:
            handle.write(b"ELF-ENGINE-TEST" * 50)

        d1 = os.path.join(tmp_root, "d1_stage_fail")
        d2 = os.path.join(tmp_root, "d2_dlopen_fail")
        d3 = os.path.join(tmp_root, "d3_ok")
        for d in (d1, d2, d3):
            os.makedirs(d, exist_ok=True)

        attempts = []

        class DummyFn:
            argtypes = []
            restype = None

            def __init__(self, handler=None):
                self.handler = handler

            def __call__(self, *args):
                return self.handler(*args) if self.handler else 1

        class DummyLib:
            def __init__(self):
                self.start_calls = []
                self.start_core_service = DummyFn(lambda port: (self.start_calls.append(port) or 1))
                self.stop_core_service = DummyFn(lambda: 1)

        dummy_lib = DummyLib()
        healthy = {"state": False}

        svc.platform.system = lambda: "Android"
        svc.resolve_paths = lambda _addon_dir: (src, None)
        svc._android_candidate_dirs = lambda: [d1, d2, d3]
        svc.is_healthy = lambda: healthy["state"]
        svc.time.sleep = lambda _s: None
        subprocess.Popen = lambda *_a, **_kw: (_ for _ in ()).throw(AssertionError("Android must not spawn Popen"))

        def fake_stage(lib_path, tdir):
            attempts.append(("stage", tdir))
            if tdir == d1:
                raise PermissionError(13, "stage denied")
            return orig_stage(lib_path, tdir)

        def fake_cdll(path):
            attempts.append(("cdll", os.path.dirname(path)))
            if os.path.dirname(path) == d2:
                raise OSError("dlopen failed for d2")
            healthy["state"] = True
            return dummy_lib

        svc._stage_android_library = fake_stage
        ctypes.CDLL = fake_cdll

        loaded_lib, proc = svc.start_engine(tmp_root)
        assert loaded_lib is dummy_lib, loaded_lib
        assert proc is None
        assert dummy_lib.start_calls == [8191]
        assert attempts == [
            ("stage", d1),
            ("stage", d2),
            ("cdll", d2),
            ("stage", d3),
            ("cdll", d3),
        ], attempts

        # When all candidate dirs fail dlopen, start_engine returns (None, None) without Popen
        healthy["state"] = False
        ctypes.CDLL = lambda _path: (_ for _ in ()).throw(OSError("dlopen blocked everywhere"))
        loaded_lib, proc = svc.start_engine(tmp_root)
        assert loaded_lib is None and proc is None
        print("start_engine_android ok")
    finally:
        svc.resolve_paths = orig_resolve
        svc._android_candidate_dirs = orig_cand
        svc._stage_android_library = orig_stage
        svc.is_healthy = orig_is_healthy
        ctypes.CDLL = orig_cdll
        svc.platform.system = orig_system
        subprocess.Popen = orig_popen
        svc.time.sleep = orig_sleep
        _rmtree_writable(tmp_root)


if __name__ == "__main__":
    test_android_candidate_dirs()
    test_stage_android_library()
    test_start_engine_android_fallback()
    print("ok")
