"""Run: python -I tests/test_playlist_guard.py"""
import os, sys, types
for name in ("xbmc", "xbmcgui", "xbmcplugin", "xbmcaddon", "xbmcvfs"):
    stub = types.ModuleType(name)
    stub.__getattr__ = lambda attr: (lambda *a, **k: "")
    sys.modules[name] = stub
sys.modules["xbmc"].Player = sys.modules["xbmc"].Monitor = object
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "plugin.video.adulthideout"))
from resources.lib import view_service as vs

class Item:
    def __init__(self, f): self.f = f
    def getfilename(self): return self.f
def playlist(*files):
    return [Item(f) for f in files]

sys.modules["xbmc"].PlayList = lambda kind: playlist("plugin://plugin.video.adulthideout/?mode=4", "plugin://plugin.video.adulthideout/?mode=4")
assert vs._addon_playlist()
sys.modules["xbmc"].PlayList = lambda kind: playlist("plugin://plugin.video.adulthideout/?mode=4")
assert not vs._addon_playlist(), "single video is no list"
sys.modules["xbmc"].PlayList = lambda kind: playlist("plugin://plugin.video.youtube/x", "plugin://plugin.video.youtube/y")
assert not vs._addon_playlist(), "other addons stay untouched"
print("ok")

# Stop while a video loads: a normal list stops, a Smart Stream skips to the next video.
class Window:
    props = {}
    def __init__(self, *_): pass
    def getProperty(self, key): return self.props.get(key, "")
    def setProperty(self, key, value): self.props[key] = value
    def clearProperty(self, key): self.props.pop(key, None)
vs.xbmcgui.Window = Window
sys.modules["xbmc"].PlayList = lambda kind: playlist("plugin://plugin.video.adulthideout/?mode=4", "plugin://plugin.video.adulthideout/?mode=4")
monitor = vs.SmartPlayerMonitor()
monitor.onPlayBackStopped()
assert monitor.recover_at is None, "normal list: stop while loading must stop"
Window.props["AdultHideout.SmartChannel"] = "asmr"
monitor = vs.SmartPlayerMonitor()
monitor.onPlayBackStopped()
assert monitor.recover_at is not None, "smart stream: stop while loading skips"
print("stop ok")

# While default.py resolves a video, the idle check must not press Next (that piled up resolves).
w = Window()
assert not vs._resolving(w, 1000.0), "nothing resolving"
w.setProperty("AdultHideout.ResolvingSince", "990")
assert vs._resolving(w, 1000.0), "resolve started 10 s ago"
assert not vs._resolving(w, 1100.0), "a resolve older than 60 s counts as hung"
w.setProperty("AdultHideout.ResolvingSince", "garbage")
assert not vs._resolving(w, 1000.0)
print("resolving ok")

# A Trans pool switches the modules to their trans sections while harvesting, then restores them.
from resources.lib import smart_playlists as sp
class Addon:
    def __init__(self): self.values = {"xnxx_content_type": "0"}
    def getSetting(self, key): return self.values.get(key, "")
    def setSetting(self, key, value): self.values[key] = value
spl = sp.SmartPlaylists.__new__(sp.SmartPlaylists)
spl.addon = Addon()
spl._get_temp_stream = lambda channel: {"pool": "trans", "query": "cumpilation"} if channel == "custom_x" else None
spl._load_custom_streams = lambda: []
seen = {}
spl._get_fast_seed_unfiltered = lambda channel: seen.setdefault(channel, spl.addon.getSetting("xnxx_content_type"))
spl._get_fast_seed("custom_x")
assert seen["custom_x"] == "2", "harvest runs with xnxx switched to trans"
assert spl.addon.getSetting("xnxx_content_type") == "0", "setting restored afterwards"
spl._get_fast_seed_unfiltered = lambda channel: seen.setdefault(channel, spl.addon.getSetting("xnxx_content_type"))
spl._get_fast_seed("4k")
assert seen["4k"] == "0", "pools without orientation leave settings alone"
print("orientation ok")
