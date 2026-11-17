# -*- coding: utf-8 -*-
"""Run KVAT's own site test headless, exactly as the diagnostics addon would.

Usage:
    python tools/headless/kvat_run.py swingerpornfun hqporner [--json] [--force] [--mode smart]

--force removes the site from KNOWN_EXTERNAL_ISSUES for this run, so the real
listing/playback checks execute instead of the short-circuited IGNORED result.
"""

import argparse
import json
import os
import socket
import sys
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
ADDON = os.path.join(REPO, "plugin.video.adulthideout")
KVAT = os.path.join(REPO, "script.adulthideout.kvat")
STUBS = os.path.join(HERE, "kodi_stubs")
CORE_URL = "http://127.0.0.1:8191"

socket.setdefaulttimeout(60.0)


def _bootstrap():
    sys.path.insert(0, STUBS)
    sys.path.insert(0, ADDON)  # "resources" must resolve to the plugin's package
    import xbmcaddon

    xbmcaddon.addon_path = ADDON
    xbmcaddon.PATHS.update({
        "plugin.video.adulthideout": ADDON,
        "script.adulthideout.kvat": KVAT,
    })
    import xbmc  # noqa: F401
    import xbmcgui  # noqa: F401
    import xbmcplugin  # noqa: F401
    import xbmcvfs  # noqa: F401

    import importlib.util

    core_py = os.path.join(KVAT, "resources", "lib", "core.py")
    spec = importlib.util.spec_from_file_location("kvat_core", core_py)
    module = importlib.util.module_from_spec(spec)
    sys.modules["kvat_core"] = module
    spec.loader.exec_module(module)
    return module


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("sites", nargs="+")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--force", action="store_true", help="ignore KNOWN_EXTERNAL_ISSUES")
    parser.add_argument("--mode", default="smart")
    parser.add_argument("--core", default=CORE_URL)
    args = parser.parse_args(argv)

    module = _bootstrap()
    module.CORE_API_URL = args.core
    results = []
    for site in args.sites:
        if args.force:
            module.KNOWN_EXTERNAL_ISSUES.pop(site, None)
        try:
            result = module.run_site_test(site, mode=args.mode)
        except Exception:
            result = {"site": site, "status": "ERROR", "error": traceback.format_exc(limit=4)}
        results.append(result)

    if args.json:
        print(json.dumps(results, indent=2, ensure_ascii=False, default=str))
    else:
        for result in results:
            print("=" * 78)
            print("%-18s %-9s %5ss  %s" % (
                result.get("site"), result.get("status"),
                result.get("elapsed_seconds", ""), (result.get("error") or "")[:110]))
            for name, check in (result.get("checks") or {}).items():
                print("   %-12s %-8s %s" % (name, check.get("status"), str(check.get("detail"))[:110]))
            stream = result.get("stream_probe") or {}
            if stream:
                print("   stream: %s %s" % (stream.get("status"), str(stream.get("url") or stream.get("error"))[:110]))
    failed = [r for r in results if r.get("status") != "PASS"]
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
