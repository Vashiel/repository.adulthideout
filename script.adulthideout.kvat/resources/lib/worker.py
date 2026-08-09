import os
import sys

import xbmc


ADDON_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ADDON_ROOT not in sys.path:
    sys.path.insert(0, ADDON_ROOT)

from resources.lib.core import now_iso, read_json, run_site_test, sanitize_text, write_json


def main(args):
    if len(args) < 2:
        return
    job_path, result_path = args[0], args[1]
    job = read_json(job_path, {}) or {}
    sites = [str(site) for site in (job.get("sites") or []) if str(site)]
    if not sites:
        site = str(job.get("site") or "")
        sites = [site] if site else []
    mode = str(job.get("mode") or "quick")
    if not sites:
        write_json(result_path, {
            "state": "complete",
            "current_site": "",
            "error": "worker received no website id",
            "results": [],
        })
        return

    monitor = xbmc.Monitor()
    results = []
    for index, site in enumerate(sites):
        if monitor.abortRequested():
            break
        write_json(result_path, {
            "state": "running",
            "mode": mode,
            "current_index": index,
            "current_site": site,
            "results": results,
            "updated_at": now_iso(),
        })
        try:
            result = run_site_test(site, mode=mode)
        except Exception as exc:
            result = {
                "site": site,
                "label": site,
                "status": "FAILED",
                "mode": mode,
                "error": sanitize_text(exc),
            }
        results.append(result)

    write_json(result_path, {
        "state": "complete",
        "mode": mode,
        "current_index": len(results),
        "current_site": "",
        "results": results,
        "updated_at": now_iso(),
    })


if __name__ == "__main__":
    main(sys.argv[1:])
