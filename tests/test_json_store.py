"""Run: python -I tests/test_json_store.py"""
import json, os, sys, tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "plugin.video.adulthideout"))
from resources.lib.json_store import write_json_atomic

folder = tempfile.mkdtemp()
path = os.path.join(folder, "favorites.json")
write_json_atomic(path, ["Ä", "b"], indent=2)
assert json.load(open(path, encoding="utf-8")) == ["Ä", "b"]

# A failure mid-write (here: a value JSON cannot hold) must keep the old file and leave no temp file.
try:
    write_json_atomic(path, ["new", object()])
    raise AssertionError("expected a TypeError")
except TypeError:
    pass
assert json.load(open(path, encoding="utf-8")) == ["Ä", "b"], "old data must survive"
assert os.listdir(folder) == ["favorites.json"], os.listdir(folder)
print("ok")
