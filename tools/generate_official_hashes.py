#!/usr/bin/env python3
"""Regenerates plugin.video.adulthideout/resources/official_hashes.json for a release.

The add-on compares these SHA-256 sums with its installed files, which come from the
release ZIP. The ZIP is built from the working tree (see addons_xml_generator.py), so
the sums are computed from the working-tree files, not from git blobs: with
core.autocrlf the two differ in line endings.

Run from the repository root after all add-on changes and before addons_xml_generator.py:
    python tools/generate_official_hashes.py
"""
import datetime
import hashlib
import json
import os

ADDON_ID = "plugin.video.adulthideout"
ADDON = os.path.abspath(ADDON_ID)
TARGET = os.path.join(ADDON, "resources", "official_hashes.json")
SKIP_DIRS = {".git", "__pycache__"}


def main():
    hashes = {}
    for base, dirs, files in os.walk(ADDON):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS)
        for name in sorted(files):
            path = os.path.join(base, name)
            if name.endswith((".pyc", ".pyo")) or os.path.abspath(path) == TARGET:
                continue
            relative = os.path.relpath(path, ADDON).replace(os.sep, "/")
            with open(path, "rb") as handle:
                hashes[relative] = hashlib.sha256(handle.read()).hexdigest()
    manifest = {
        "addon_id": ADDON_ID,
        "generated_utc": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "hash_algorithm": "sha256",
        "hashes": dict(sorted(hashes.items())),
    }
    with open(TARGET, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(manifest, handle, indent=4)
        handle.write("\n")
    print("{} files hashed into {}".format(len(hashes), os.path.relpath(TARGET)))


if __name__ == "__main__":
    main()
