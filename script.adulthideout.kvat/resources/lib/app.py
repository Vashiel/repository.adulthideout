import os
import re
import sys
import time
import urllib.parse
import uuid

import xbmc
import xbmcaddon
import xbmcgui
import xbmcvfs

from resources.lib.core import (
    ADDON,
    ADDON_ID,
    JOBS_PATH,
    REPORTS_PATH,
    TARGET_ADDON_ID,
    build_report,
    cleanup_old_reports,
    ensure_directories,
    list_websites,
    now_iso,
    read_json,
    report_summary,
    sanitize_text,
    website_label,
    write_json,
)


ADDON_PATH = xbmcvfs.translatePath(ADDON.getAddonInfo("path"))
WORKER_PATH = os.path.join(ADDON_PATH, "resources", "lib", "worker.py")
MONITOR = xbmc.Monitor()


def text(label_id, fallback):
    return ADDON.getLocalizedString(label_id) or fallback


def parse_arguments(arguments):
    params = {}
    for argument in arguments:
        value = str(argument or "").lstrip("?")
        if "&" not in value and value.count("=") > 1:
            value = "&".join(value.split())
        params.update(dict(urllib.parse.parse_qsl(value)))
        if "=" in value and "&" not in value:
            key, item = value.split("=", 1)
            params[key] = item
    return params


def timeout_for_mode(mode):
    if mode == "full":
        return 95
    if mode in ("detail", "playback"):
        return 55
    return 25


def stop_worker():
    xbmc.executebuiltin('StopScript("{}")'.format(WORKER_PATH))
    MONITOR.waitForAbort(0.5)


def stop_active_test():
    try:
        xbmc.executebuiltin("PlayerControl(Stop)")
    except Exception:
        pass
    try:
        target_path = xbmcvfs.translatePath(
            xbmcaddon.Addon(TARGET_ADDON_ID).getAddonInfo("path")
        )
        xbmc.executebuiltin(
            'StopScript("{}")'.format(os.path.join(target_path, "default.py"))
        )
    except Exception:
        pass
    stop_worker()
    MONITOR.waitForAbort(1.0)


def cleanup_worker_files(*paths):
    for path in paths:
        try:
            if os.path.exists(path):
                os.remove(path)
        except OSError:
            pass


def cleanup_stale_worker_files(max_age_seconds=600):
    ensure_directories()
    cutoff = time.time() - max_age_seconds
    for name in os.listdir(JOBS_PATH):
        if not name.startswith(("job-", "result-")):
            continue
        path = os.path.join(JOBS_PATH, name)
        try:
            if os.path.isfile(path) and os.path.getmtime(path) < cutoff:
                os.remove(path)
        except OSError:
            pass


def timeout_result(site, mode):
    return {
        "site": site,
        "label": website_label(site),
        "status": "TIMEOUT",
        "error": "website test exceeded {} seconds".format(timeout_for_mode(mode)),
        "mode": mode,
    }


def run_worker_batch(sites, mode, progress_callback=None, cancelled_callback=None):
    ensure_directories()
    pending = list(sites or [])
    completed = []
    cancelled = False
    while pending and not cancelled and not MONITOR.abortRequested():
        token = uuid.uuid4().hex
        job_path = os.path.join(JOBS_PATH, "job-{}.json".format(token))
        result_path = os.path.join(JOBS_PATH, "result-{}.json".format(token))
        write_json(job_path, {"sites": pending, "mode": mode})
        command = 'RunScript("{}","{}","{}")'.format(WORKER_PATH, job_path, result_path)
        xbmc.executebuiltin(command)

        segment_results = []
        current_site = pending[0]
        deadline = time.time() + timeout_for_mode(mode)
        segment_complete = False
        try:
            while not MONITOR.abortRequested():
                state = read_json(result_path, None) if os.path.exists(result_path) else None
                if isinstance(state, dict):
                    snapshot = state.get("results")
                    if isinstance(snapshot, list):
                        segment_results = snapshot
                    reported_site = str(state.get("current_site") or "")
                    if reported_site and reported_site != current_site:
                        current_site = reported_site
                        deadline = time.time() + timeout_for_mode(mode)
                    if progress_callback:
                        progress_callback(len(completed) + len(segment_results), current_site)
                    if state.get("state") == "complete":
                        completed.extend(segment_results)
                        pending = []
                        segment_complete = True
                        break

                if cancelled_callback and cancelled_callback():
                    cancelled = True
                    stop_active_test()
                    completed.extend(segment_results)
                    break
                if time.time() >= deadline:
                    stop_active_test()
                    completed.extend(segment_results)
                    hung_index = len(segment_results)
                    hung_site = pending[hung_index] if hung_index < len(pending) else current_site
                    completed.append(timeout_result(hung_site, mode))
                    pending = pending[hung_index + 1:]
                    break
                MONITOR.waitForAbort(0.2)
        finally:
            cleanup_worker_files(job_path, job_path + ".tmp", result_path, result_path + ".tmp")

        if segment_complete:
            break
    return completed, cancelled or MONITOR.abortRequested()


def report_filename():
    stamp = time.strftime("%Y%m%d-%H%M%S")
    suffix = uuid.uuid4().hex[:6]
    return os.path.join(REPORTS_PATH, "adult-hideout-diagnostics-{}-{}.json".format(stamp, suffix))


def save_report(mode, results, started_at, cancelled=False):
    report = build_report(mode, results, started_at, cancelled=cancelled)
    path = report_filename()
    write_json(path, report)
    cleanup_old_reports()
    return path, report


def summary_message(summary):
    return (
        "{}: {}\n{}: {}\n{}: {}\n{}: {}\n{}: {}\n{}: {}"
        .format(
            text(30020, "Total"), summary.get("total", 0),
            text(30021, "Passed"), summary.get("PASS", 0),
            text(30022, "Warnings"), summary.get("WARNING", 0),
            text(30023, "Failed"), summary.get("FAILED", 0),
            text(30024, "Timeouts"), summary.get("TIMEOUT", 0),
            text(30041, "Known external outages"), summary.get("IGNORED", 0),
        )
    )


def show_report(report, path=""):
    summary = report.get("summary") or report_summary(report.get("sites") or [])
    lines = [summary_message(summary), ""]
    problem_sites = [
        item for item in report.get("sites") or []
        if item.get("status") not in ("PASS", "IGNORED")
    ]
    if problem_sites:
        lines.append(text(30025, "Problems"))
        for item in problem_sites:
            detail = item.get("error")
            if not detail:
                detail = "; ".join((item.get("listing") or {}).get("messages") or [])
            lines.append("{}  {}  {}".format(
                item.get("status", "FAILED"),
                item.get("label") or item.get("site"),
                sanitize_text(detail),
            ).rstrip())
    ignored_sites = [
        item for item in report.get("sites") or []
        if item.get("status") == "IGNORED"
    ]
    if ignored_sites:
        lines.extend(["", text(30041, "Known external outages")])
        for item in ignored_sites:
            lines.append("{}  {}".format(
                item.get("label") or item.get("site"),
                item.get("external_issue") or "",
            ).rstrip())
    if path:
        lines.extend(["", text(30026, "Report"), path])
    xbmcgui.Dialog().textviewer(text(30000, "AdultHideout Diagnostics"), "\n".join(lines))


def run_sites(sites, mode, show_result=True):
    if mode == "smart":
        return run_smart_scan(sites, show_result=show_result)
    if not sites:
        xbmcgui.Dialog().notification(
            text(30000, "AdultHideout Diagnostics"),
            text(30027, "No websites selected"),
            xbmcgui.NOTIFICATION_WARNING,
            3000,
        )
        return
    if xbmc.Player().isPlaying():
        xbmcgui.Dialog().ok(
            text(30000, "AdultHideout Diagnostics"),
            text(30028, "Stop current playback before starting diagnostics."),
        )
        return

    started_at = now_iso()
    progress = xbmcgui.DialogProgress()
    progress.create(text(30000, "AdultHideout Diagnostics"), text(30029, "Preparing tests..."))
    results = []
    cancelled = False
    try:
        total = len(sites)
        labels = {site["id"]: site["label"] for site in sites}

        def update_progress(done, current_site):
            progress.update(
                int((done * 100) / max(total, 1)),
                "{} ({}/{})".format(
                    labels.get(current_site, website_label(current_site)),
                    min(done + 1, total),
                    total,
                ),
            )

        results, cancelled = run_worker_batch(
            [site["id"] for site in sites],
            mode,
            progress_callback=update_progress,
            cancelled_callback=progress.iscanceled,
        )
        progress.update(100, text(30030, "Writing report..."))
    finally:
        progress.close()

    path, report = save_report(mode, results, started_at, cancelled=cancelled)
    if show_result:
        show_report(report, path)


def run_smart_scan(sites, show_result=True):
    if not sites:
        return
    if xbmc.Player().isPlaying():
        xbmcgui.Dialog().ok(
            text(30000, "AdultHideout Diagnostics"),
            text(30028, "Stop current playback before starting diagnostics."),
        )
        return

    started_at = now_iso()
    progress = xbmcgui.DialogProgress()
    progress.create(text(30000, "AdultHideout Diagnostics"), text(30042, "Fast screening..."))
    results = []
    cancelled = False
    try:
        total = len(sites)
        labels = {site["id"]: site["label"] for site in sites}

        def update_screening(done, current_site):
            progress.update(
                int((done * 70) / max(total, 1)),
                "{} ({}/{})".format(
                    labels.get(current_site, website_label(current_site)),
                    min(done + 1, total),
                    total,
                ),
            )

        results, cancelled = run_worker_batch(
            [site["id"] for site in sites],
            "quick",
            progress_callback=update_screening,
            cancelled_callback=progress.iscanceled,
        )

        candidates = []
        for item in results:
            listing = item.get("listing") or {}
            needs_detail = (
                item.get("status") in ("FAILED", "TIMEOUT")
                or int(listing.get("videos") or 0) == 0
                or bool(listing.get("folder_errors"))
            )
            if needs_detail:
                candidates.append(item)
        by_site = {item.get("site"): index for index, item in enumerate(results)}
        candidate_total = len(candidates)
        candidate_ids = [item.get("site") for item in candidates if item.get("site")]

        def update_detail(done, current_site):
            progress.update(
                70 + int((done * 29) / max(candidate_total, 1)),
                "{}: {} ({}/{})".format(
                    text(30043, "Detailed check"),
                    labels.get(current_site, website_label(current_site)),
                    min(done + 1, candidate_total),
                    candidate_total,
                ),
            )

        detailed_results, detail_cancelled = ([], False)
        if candidate_ids and not cancelled:
            detailed_results, detail_cancelled = run_worker_batch(
                candidate_ids,
                "detail",
                progress_callback=update_detail,
                cancelled_callback=progress.iscanceled,
            )
        cancelled = cancelled or detail_cancelled
        for detailed in detailed_results:
            site_id = detailed.get("site")
            if site_id not in by_site:
                continue
            screening = results[by_site[site_id]]
            detailed["screening"] = {
                "status": screening.get("status"),
                "elapsed_seconds": screening.get("elapsed_seconds"),
                "messages": (screening.get("listing") or {}).get("messages") or [],
            }
            results[by_site[site_id]] = detailed
        progress.update(100, text(30030, "Writing report..."))
    finally:
        progress.close()

    path, report = save_report("smart", results, started_at, cancelled=cancelled)
    if show_result:
        show_report(report, path)


def latest_report_path():
    ensure_directories()
    reports = sorted(
        (os.path.join(REPORTS_PATH, name) for name in os.listdir(REPORTS_PATH) if name.endswith(".json")),
        key=lambda path: os.path.getmtime(path),
        reverse=True,
    )
    return reports[0] if reports else ""


def show_previous_reports():
    ensure_directories()
    reports = sorted(
        (os.path.join(REPORTS_PATH, name) for name in os.listdir(REPORTS_PATH) if name.endswith(".json")),
        key=lambda path: os.path.getmtime(path),
        reverse=True,
    )
    if not reports:
        xbmcgui.Dialog().notification(
            text(30000, "AdultHideout Diagnostics"),
            text(30031, "No reports available"),
            xbmcgui.NOTIFICATION_INFO,
            2500,
        )
        return
    selected = xbmcgui.Dialog().select(
        text(30005, "Previous reports"),
        [os.path.basename(path) for path in reports],
    )
    if selected >= 0:
        report = read_json(reports[selected], {}) or {}
        show_report(report, reports[selected])


def export_latest_report():
    source = latest_report_path()
    if not source:
        xbmcgui.Dialog().notification(
            text(30000, "AdultHideout Diagnostics"),
            text(30031, "No reports available"),
            xbmcgui.NOTIFICATION_INFO,
            2500,
        )
        return
    destination = xbmcgui.Dialog().browseSingle(
        0,
        text(30032, "Choose export folder"),
        "files",
        "",
        False,
        True,
        "special://home/",
    )
    if not destination:
        return
    if "://" in destination:
        target = destination.rstrip("/\\") + "/" + os.path.basename(source)
    else:
        target = os.path.join(xbmcvfs.translatePath(destination), os.path.basename(source))
    if xbmcvfs.copy(source, target):
        xbmcgui.Dialog().ok(
            text(30000, "AdultHideout Diagnostics"),
            "{}\n{}".format(text(30033, "Report exported"), target),
        )
    else:
        xbmcgui.Dialog().ok(
            text(30000, "AdultHideout Diagnostics"),
            text(30034, "The report could not be exported."),
        )


def retest_failed():
    path = latest_report_path()
    report = read_json(path, {}) if path else {}
    failed_ids = {
        item.get("site") for item in report.get("sites") or []
        if item.get("status") in ("WARNING", "FAILED", "TIMEOUT") and item.get("site")
    }
    if not failed_ids:
        xbmcgui.Dialog().notification(
            text(30000, "AdultHideout Diagnostics"),
            text(30035, "The latest report has no failed websites."),
            xbmcgui.NOTIFICATION_INFO,
            3000,
        )
        return
    sites = [site for site in list_websites() if site["id"] in failed_ids]
    mode = str((report.get("run") or {}).get("mode") or "smart")
    if mode == "quick":
        mode = "detail"
    run_sites(sites, mode)


def select_websites():
    sites = list_websites()
    selected = xbmcgui.Dialog().multiselect(
        text(30003, "Select websites"),
        [site["label"] for site in sites],
    )
    if not selected:
        return
    test_mode = xbmcgui.Dialog().select(
        text(30036, "Test mode"),
        [
            text(30001, "Smart check"),
            text(30007, "Quick listing check"),
            text(30002, "Full playback check"),
        ],
    )
    if test_mode < 0:
        return
    modes = ("smart", "quick", "full")
    run_sites([sites[index] for index in selected], modes[test_mode])


def confirm_all(mode, count):
    if mode == "smart":
        message = text(
            30044,
            "Runs a fast screen first, then inspects useful folders only for suspicious websites.",
        )
    elif mode == "full":
        message = text(
            30037,
            "This test visibly plays and seeks one video per website and may take several hours.",
        )
    else:
        message = text(
            30038,
            "This test checks every website listing and first thumbnail and may take some time.",
        )
    return xbmcgui.Dialog().yesno(
        text(30000, "AdultHideout Diagnostics"),
        "{}\n\n{}: {}".format(message, text(30020, "Total"), count),
    )


def show_main_menu():
    options = [
        text(30001, "Smart check all websites"),
        text(30007, "Quick listing check all websites"),
        text(30003, "Select websites"),
        text(30004, "Retest failed"),
        text(30005, "Previous reports"),
        text(30006, "Export latest report"),
    ]
    selected = xbmcgui.Dialog().select(text(30000, "AdultHideout Diagnostics"), options)
    if selected == 0:
        sites = list_websites()
        if confirm_all("smart", len(sites)):
            run_sites(sites, "smart")
    elif selected == 1:
        sites = list_websites()
        if confirm_all("quick", len(sites)):
            run_sites(sites, "quick")
    elif selected == 2:
        select_websites()
    elif selected == 3:
        retest_failed()
    elif selected == 4:
        show_previous_reports()
    elif selected == 5:
        export_latest_report()


def main(arguments=None):
    ensure_directories()
    cleanup_stale_worker_files()
    try:
        xbmcaddon.Addon(TARGET_ADDON_ID)
    except Exception:
        xbmcgui.Dialog().ok(
            text(30000, "AdultHideout Diagnostics"),
            text(30039, "AdultHideout is not installed."),
        )
        return
    params = parse_arguments(arguments or sys.argv[1:])
    if params.get("all") == "1":
        run_sites(
            list_websites(),
            params.get("mode", "smart"),
            show_result=params.get("quiet") != "1",
        )
        return
    requested_sites = [
        item.strip()
        for item in re.split(r"[;,]", params.get("sites", ""))
        if item.strip()
    ]
    if requested_sites:
        available = {item["id"]: item for item in list_websites()}
        selected = [available[site] for site in requested_sites if site in available]
        run_sites(
            selected,
            params.get("mode", "smart"),
            show_result=params.get("quiet") != "1",
        )
        return
    site = params.get("site")
    if site:
        available = {item["id"]: item for item in list_websites()}
        if site not in available:
            xbmcgui.Dialog().ok(
                text(30000, "AdultHideout Diagnostics"),
                "{}: {}".format(text(30040, "Unknown website"), site),
            )
            return
        run_sites(
            [available[site]],
            params.get("mode", "quick"),
            show_result=params.get("quiet") != "1",
        )
        return
    show_main_menu()
