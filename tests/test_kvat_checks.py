"""Run: python tests/test_kvat_checks.py"""
import importlib.util, os, sys, tempfile, types

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
PROFILE = tempfile.mkdtemp()
for name in ("xbmc", "xbmcgui", "xbmcplugin", "xbmcaddon", "xbmcvfs"):
    stub = types.ModuleType(name)
    stub.__getattr__ = lambda attr: (lambda *a, **k: "")
    sys.modules[name] = stub
sys.modules["xbmc"].LOGINFO = sys.modules["xbmc"].LOGWARNING = 0
sys.modules["xbmcvfs"].translatePath = lambda path: path
sys.modules["xbmcvfs"].exists = lambda path: True
addon_path = os.path.join(ROOT, "plugin.video.adulthideout")
sys.modules["xbmcaddon"].Addon = lambda *a: type("A", (), {"getAddonInfo": lambda s, k: addon_path if k == "path" else PROFILE})()

spec = importlib.util.spec_from_file_location("kvat_core", os.path.join(ROOT, "script.adulthideout.kvat", "resources", "lib", "core.py"))
core = importlib.util.module_from_spec(spec)
spec.loader.exec_module(core)

# English by default: a language subdomain, path or page language warns.
assert core.check_language("https://www.eporner.com", {"final_url": "https://www.eporner.com/", "html_lang": "en"})["status"] == "PASS"
assert core.check_language("https://xhamster.com", {"final_url": "https://de.xhamster.com/"})["status"] == "WARNING"
assert core.check_language("https://www.analdin.com", {}, ["https://www.analdin.com/de/kategorien/"])["status"] == "WARNING"
assert core.check_language("https://x.com", {"html_lang": "ja"})["status"] == "WARNING"
print("language ok")

# Buttons: what the module offers in its source must show up in its start listing.
offered = core.offered_buttons("eporner")
assert {"Search", "Categories"} <= offered, offered
shown = [("Search", "5", ""), ("Next Page >>>>", "2", "u")]
check = core.check_buttons(shown, offered, video_count=30)
assert check["status"] == "WARNING" and "Categories" in check["detail"], check
assert core.check_buttons(shown + [("Categories", "8", "c")], {"Categories"}, 30)["status"] == "PASS"
print("buttons ok")

# Thumbnails: placeholders, one image for all, and the 5th video's image.
real = ["https://cdn.x/{}.jpg".format(i) for i in range(10)]
assert core.check_thumbnails(real, {"status": "loaded"})["status"] == "PASS"
assert core.check_thumbnails(["https://x/blank.gif"] * 10, {"status": "loaded"})["status"] == "WARNING"
assert core.check_thumbnails(["https://cdn.x/same.jpg"] * 8 + real[:2], {"status": "loaded"})["status"] == "WARNING"
fifth_bad = real[:4] + ["/addon/resources/logos/x.png"] + real[5:]
assert "#5" in core.check_thumbnails(fifth_bad, {"status": "loaded"})["detail"]
proxied = "http://127.0.0.1:8191/thumb?u=https%3A%2F%2Fcdn.x%2Fa.jpg&r=x"
assert core._thumb_source(proxied) == "https://cdn.x/a.jpg"
assert core.check_thumbnails(real, {"status": "failed", "error": "403"})["status"] == "WARNING"
print("thumbnails ok")

# Only reachable, videos and playback fail a site; core is information only.
mk = core.make_check
status, problems = core.summarize_checks({"reachable": mk("PASS", ""), "english": mk("WARNING", "de"), "core": mk("WARNING", "x")})
assert status == "WARNING" and len(problems) == 1
assert core.summarize_checks({"playback": mk("FAILED", "x")})[0] == "FAILED"
assert core.check_core({"core": 1, "fallback": 0}, {"core": 4, "fallback": 0}, "core profile")["status"] == "PASS"
assert core.check_core({"core": 1, "fallback": 0}, {"core": 1, "fallback": 2}, "python")["status"] == "WARNING"
assert core.search_engine("anyporn") == "core profile"
print("summary ok")

# Parallel sites: each thread gets only its own listing; threads without hooks reach the original.
import threading, xbmcplugin
calls = []
xbmcplugin.addDirectoryItem = lambda *a, **k: calls.append("plugin")
core._install_routing()
seen = {"a": [], "b": []}
barrier = threading.Barrier(2)
def lister(name):
    with core.thread_hooks(addDirectoryItem=lambda *a, **k: seen[name].append(a[0])):
        barrier.wait()
        for i in range(50):
            xbmcplugin.addDirectoryItem(name)
threads = [threading.Thread(target=lister, args=(n,)) for n in "ab"]
[t.start() for t in threads]; [t.join() for t in threads]
xbmcplugin.addDirectoryItem("x")
assert seen == {"a": ["a"] * 50, "b": ["b"] * 50} and calls == ["plugin"], (seen, calls)
print("parallel hooks ok")

# Tactile loads the diagnostics anew per run; a second copy must still reach the routing.
spec2 = importlib.util.spec_from_file_location("kvat_core2", spec.origin)
core2 = importlib.util.module_from_spec(spec2); spec2.loader.exec_module(core2)
got = []
with core2.thread_hooks(addDirectoryItem=lambda *a, **k: got.append(a[0])):
    xbmcplugin.addDirectoryItem("second run")
assert got == ["second run"], got
print("reload ok")

# Tactile caches thumbnails as local files: an existing file is a real image, the logo is not.
cached = os.path.join(PROFILE, "thumb.jpg"); open(cached, "wb").write(b"\xff\xd8\xff")
assert not core.is_placeholder_thumb(cached)
assert core.is_placeholder_thumb(os.path.join(PROFILE, "missing.jpg"))
assert core.is_placeholder_thumb(os.path.join(addon_path, "resources", "logos", "x.png"))
print("local thumbs ok")
