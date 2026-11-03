import importlib.util
import os
import sys

import xbmc


LIB_DIR = os.path.abspath(os.path.dirname(__file__))
CORE_PATH = os.path.join(LIB_DIR, "core.py")
CORE_MODULE = "adulthideout_kvat_core"
spec = importlib.util.spec_from_file_location(CORE_MODULE, CORE_PATH)
core = importlib.util.module_from_spec(spec)
sys.modules[CORE_MODULE] = core
spec.loader.exec_module(core)

now_iso = core.now_iso
read_json = core.read_json
run_site_test = core.run_site_test
sanitize_text = core.sanitize_text
write_json = core.write_json


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

    # Parallel Batch Acceleration via Rust Core (only for Express 'quick' mode)
    batch_done = False
    if len(sites) > 1 and mode == "quick":
        try:
            import json
            import urllib.request
            site_items = []
            for s in sites:
                u = core.get_website_base_url(s)
                if u:
                    site_items.append({"id": s, "url": u})
            if site_items:
                write_json(result_path, {
                    "state": "running",
                    "mode": mode,
                    "current_index": 0,
                    "current_site": "Batch checking {} sites via Rust Core...".format(len(site_items)),
                    "results": results,
                    "updated_at": now_iso(),
                })
                batch_payload = json.dumps({
                    "concurrency": 20,
                    "timeout_ms": 10000,
                    "sites": site_items,
                }).encode("utf-8")
                req = urllib.request.Request(
                    "http://127.0.0.1:8191/diagnose",
                    data=batch_payload,
                    headers={"Content-Type": "application/json"},
                )
                opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
                with opener.open(req, timeout=120) as resp:
                    if resp.status == 200:
                        batch_data = json.loads(resp.read().decode("utf-8"))
                        core_map = {r["id"]: r for r in (batch_data.get("results") or [])}
                        for index, site in enumerate(sites):
                            data = core_map.get(site)
                            if data:
                                elapsed_sec = round(float(data.get("elapsed_ms", 0)) / 1000.0, 2)
                                verdict = data.get("verdict", "PASS")
                                messages = data.get("messages") or []
                                error_msg = "; ".join(messages) if verdict in ("FAILED", "WARNING") and messages else None
                                res = {
                                    "site": site,
                                    "label": core.website_label(site),
                                    "status": verdict,
                                    "started_at": now_iso(),
                                    "finished_at": now_iso(),
                                    "elapsed_seconds": elapsed_sec,
                                    "mode": mode,
                                    "core_accelerated": True,
                                    "error": error_msg,
                                    "listing": {
                                        "status": verdict,
                                        "elapsed_seconds": elapsed_sec,
                                        "items": data.get("items_found", 0),
                                        "folders": 0,
                                        "videos": data.get("items_found", 0),
                                        "followed_folders": 0,
                                        "folder_errors": [],
                                        "thumbnail": {
                                            "status": data.get("thumbnail_status", "missing"),
                                            "sample": data.get("sample_thumbnail"),
                                        },
                                        "messages": messages,
                                    },
                                    "dns_ok": data.get("dns_ok", True),
                                    "tls_ok": data.get("tls_ok", True),
                                    "http_status": data.get("http_status", 200),
                                    "challenge_detected": data.get("challenge_detected", False),
                                    "challenge_solved": data.get("challenge_solved", False),
                                }
                                if data.get("messages"):
                                    res["advisories"] = data.get("messages")
                                results.append(res)
                            else:
                                results.append(run_site_test(site, mode=mode))
                            write_json(result_path, {
                                "state": "running",
                                "mode": mode,
                                "current_index": index + 1,
                                "current_site": site,
                                "results": results,
                                "updated_at": now_iso(),
                            })
                        batch_done = True
        except Exception as exc:
            core.log("Rust batch diagnostic skipped/failed: {}".format(exc), xbmc.LOGWARNING)
            batch_done = False

    if not batch_done:
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
