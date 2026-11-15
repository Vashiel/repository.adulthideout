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
