"""Run: python -I tests/test_matching.py"""
import os, sys, types
for name in ("xbmc", "xbmcgui", "xbmcplugin", "xbmcaddon", "xbmcvfs"):
    stub = types.ModuleType(name)
    stub.__getattr__ = lambda attr: (lambda *a, **k: "")
    sys.modules[name] = stub
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "plugin.video.adulthideout"))
from resources.lib.global_search import GlobalSearch

gs = GlobalSearch.__new__(GlobalSearch)
gs._state_cache = {}  # no saved search state, so no length or quality filter
assert gs._matches_all_query_words("Hospital ASMR Roleplay", "asmr hospital")
assert not gs._matches_all_query_words("ASMR Nurse", "asmr hospital")
assert gs._matches_query_strictly("Soft ASMR", "asmr")
assert not gs._matches_query_strictly("asmrtist", "asmr")
print("ok")

# Display filter must keep word-order matches, or saved results show as 0.
gs._result_options = lambda q, m: {}
gs._sources_for_search = lambda q, m: []
shown = gs._display_results("asmr hospital", [{"source": "eroasmr", "label": "Nurse discharging you from the hospital ASMR"}])
assert len(shown) == 1, shown
print("display ok")

# Sites the Core cannot fetch go to Python first; Core-deadline sites last.
import io, json, urllib.request
fake = {"results": [], "failed_sources": ["slowsite", "missav"],
        "failed_reasons": {"slowsite": "deadline during fetch (started 9000ms)", "missav": "solver failed: http 403"}}
urllib.request.urlopen = lambda *a, **k: type("R", (), {"__enter__": lambda s: io.BytesIO(json.dumps(fake).encode()), "__exit__": lambda s, *e: None})()
gs._load_core_targets = lambda sources: [{"id": i} for i in ("slowsite", "missav", "fastsite")]
gs.logger = lambda *a, **k: None
progress = type("P", (), {"update": lambda *a: None, "iscanceled": lambda s: False})()
_, remaining, _ = gs._run_core_search("asmr hospital", ["slowsite", "missav", "fastsite", "pythononly"], progress, 25, gs._matches_all_query_words)
assert remaining == ["missav", "pythononly", "slowsite"], remaining
print("core order ok")

# Down or rate-limited sites are not retried in Python; Cloudflare and unfinished ones are.
from resources.lib.global_search import _HOPELESS_CORE_REASON as H
for why in ("network: timed out", "http 404", "http 429", "http 502"):
    assert H.match(why), why
for why in ("http 403, solver skipped (failed before)", "http 503, solver skipped", "solver failed: http 403",
            "deadline during queued, never started", "http 4031"):
    assert not H.match(why), why
fake["failed_sources"].append("deadsite"); fake["failed_reasons"]["deadsite"] = "http 404 (started 10ms)"
gs._load_core_targets = lambda sources: [{"id": i} for i in ("slowsite", "missav", "fastsite", "deadsite")]
_, remaining, _ = gs._run_core_search("q", ["slowsite", "missav", "fastsite", "deadsite"], progress, 25, gs._matches_all_query_words)
assert remaining == ["missav", "slowsite"], remaining
print("hopeless ok")

# A worker of a finished search fails its next HTTP call instead of running on.
try:
    import requests
except ImportError:
    requests = None
if requests:
    import threading
    from resources.lib import global_search as gsm
    gsm._install_request_cancel_hook()
    gsm._THREAD_LOCAL.cancel = threading.Event(); gsm._THREAD_LOCAL.cancel.set()
    try:
        requests.Session().get("http://127.0.0.1:9/")
        raise AssertionError("cancelled worker made a request")
    except gsm.SearchAbandoned:
        pass
    gsm._THREAD_LOCAL.cancel = None
    print("cancel ok")

# Trust the sites: a result without the query words stays in a normal search (missav matches tags),
# but film searches keep their title check. The Core gets "query", so it does not filter either.
tag_hit = [{"source": "missav", "label": "Night shift nurse whispers naughty nurse talk"}]
assert len(gs._display_results("asmr hospital", tag_hit, search_mode="selected")) == 1
assert gs._display_results("asmr hospital", tag_hit, search_mode="full_movies") == []
sent = {}
def capture(*a, **k):
    sent.update(json.loads(a[0].data))
    return type("R", (), {"__enter__": lambda s: io.BytesIO(json.dumps({"results": [], "failed_sources": []}).encode()), "__exit__": lambda s, *e: None})()
urllib.request.urlopen = capture
gs._run_core_search("asmr hospital", ["missav"], progress, 25, gs._matcher_for("asmr hospital", "selected"))
assert sent.get("query") == "asmr hospital" and "queries" not in sent and sent["strict_match"] is False, sent
print("trust ok")

# Relevance before source order: the title with both words leads even from a late source.
gs._sources_for_search = lambda q, m: ["3movs", "missav", "zzsite"]
mixed = [{"source": "3movs", "label": "Banged in the hospital"}, {"source": "zzsite", "label": "Hospital ASMR roleplay"}]
assert gs._display_results("asmr hospital", mixed, search_mode="selected")[0]["source"] == "zzsite"
print("sort ok")

# Length and quality chosen before the search: results that miss them are dropped while collecting.
from resources.lib.global_search import passes_search_filters as ok
assert ok({}, "anything", "")
assert ok({"length": "20"}, "Long one", "25:10") and not ok({"length": "20"}, "Short one", "12:00")
assert ok({"length": "20"}, "Long one [COLOR lime](31:02)[/COLOR]", ""), "length from the label"
assert not ok({"length": "10"}, "No length at all", ""), "unknown length fails an active length filter"
assert ok({"length": "movie"}, "x", "1:32:00") and not ok({"length": "movie"}, "x", "45:00")
assert ok({"quality": "hd"}, "Nurse 1080p", "") and ok({"quality": "hd"}, "Clip in 4K", "")
assert not ok({"quality": "hd"}, "Plain title", "") and not ok({"quality": "4k"}, "Clip 1080p", "")
print("filters ok")

# Sites with their own length/quality filter: settings set while searching, searched via their module.
from resources.lib.global_search import native_filter_settings, native_filter_dimensions
f = {"length": "20", "quality": "hd"}
s = native_filter_settings(f)
assert s["xnxx_duration"] == "4" and s["spankbang_quality"] == "1" and s["xhamster_resolution"] == "720p+"
assert native_filter_dimensions(f, "xnxx") == {"length", "quality"}
assert native_filter_dimensions(f, "xhamster") == {"quality"}, "xhamster has no 20+ setting"
assert native_filter_dimensions(f, "missav") == set() and native_filter_settings({}) == {}
assert ok(f, "Plain title", "", {"length", "quality"}), "native filters: unknown length and no HD word are fine"
assert not ok(f, "Plain title", "5:00", {"length", "quality"}), "a known short length still fails"
gs._state_cache = {"search_filters": f}
gs.websites_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "plugin.video.adulthideout", "resources", "websites")
assert "xnxx" not in {e["id"] for e in GlobalSearch._load_core_targets(gs, ["xnxx", "eroasmr"])}
gs._state_cache = {}
print("native filters ok")

# Results are stored per search in their own file, not in the state file read on every action.
import tempfile
gs.profile_path = tempfile.mkdtemp()
gs._state_cache = {"result_cache": {"old": "26 MB"}}
gs._selected_profile = lambda: "balanced"; gs._selected_sources = lambda: ["a"]
gs._filter_results = lambda r: r
gs._save_results("milf", [{"source": "a", "url": "u1", "label": "x"}], search_mode="selected")
assert gs._cached_results("milf", search_mode="selected")[0]["url"] == "u1"
assert gs._cached_results("other", search_mode="selected") is None
gs._save_state(gs._state_cache)
assert "result_cache" not in json.load(open(os.path.join(gs.profile_path, "global_search.json")))
print("result files ok")

# Quality levels: 720p+, 1080p+, 4K only. xnxx has no 4K level, so it is checked by title there.
assert ok({"quality": "fhd"}, "Clip 1080p", "") and ok({"quality": "fhd"}, "Clip 4K", "")
assert not ok({"quality": "fhd"}, "Clip 720p", "") and not ok({"quality": "fhd"}, "Clip HD", "")
assert native_filter_settings({"quality": "fhd"})["xnxx_quality"] == "2"
assert native_filter_dimensions({"quality": "4k"}, "xnxx") == set()
assert native_filter_dimensions({"quality": "4k"}, "eporner") == {"quality"}
print("quality levels ok")
