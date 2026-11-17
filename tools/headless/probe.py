# -*- coding: utf-8 -*-
"""Drive one of the addon's site modules outside of Kodi.

Usage:
    python tools/headless/probe.py <site> list [url] [--core] [--json] [--settings k=v,...]
    python tools/headless/probe.py <site> play <url> [--core] [--json]
    python tools/headless/probe.py <site> search <query> [--core] [--json]
    python tools/headless/probe.py <site> fetch <url> [--core] [--json] [--raw]
    python tools/headless/probe.py <site> info

The stub modules in kodi_stubs/ stand in for xbmc*, so the module imports and runs
exactly as it does in Kodi. Every http request still goes through requests; with
--core it is routed through the local Rust core (127.0.0.1:8191) first.
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
STUBS = os.path.join(HERE, "kodi_stubs")

socket.setdefaulttimeout(30.0)


def _bootstrap(settings=None, use_core=False, addon_path=None):
    sys.path.insert(0, STUBS)
    sys.path.insert(0, ADDON)
    import xbmc
    import xbmcaddon
    import xbmcgui  # noqa: F401
    import xbmcplugin
    import xbmcvfs  # noqa: F401

    xbmcaddon.set_addon_path(addon_path or ADDON)
    if settings:
        xbmcaddon.set_settings(settings)
    if use_core:
        from resources.lib import core_transport
        core_transport.install()
    return xbmc, xbmcaddon, xbmcplugin


def _site_module(name):
    import importlib
    for candidate in ("resources.websites." + name, name):
        try:
            return importlib.import_module(candidate)
        except ModuleNotFoundError as exc:
            if exc.name not in (candidate, "resources", "resources.websites"):
                raise
    raise SystemExit("site module not found: " + name)


def _site_class(module):
    import inspect
    from resources.lib.base_website import BaseWebsite

    found = []
    for _, obj in vars(module).items():
        if inspect.isclass(obj) and obj.__module__ == module.__name__ and issubclass(obj, BaseWebsite):
            found.append(obj)
    if not found:
        raise SystemExit("no BaseWebsite subclass in " + module.__name__)
    return found[0]


def _build(args):
    xbmcaddon = sys.modules["xbmcaddon"]
    settings = {}
    for pair in (args.settings or "").split(","):
        if "=" in pair:
            key, value = pair.split("=", 1)
            settings[key.strip()] = value.strip()
    _bootstrap(settings=settings, use_core=args.core)
    module = _site_module(args.site)
    cls = _site_class(module)
    addon = xbmcaddon.Addon("plugin.video.adulthideout")
    try:
        return cls(1, addon), module
    except TypeError:
        return cls(1), module


def _item_summary(entry):
    item = entry.get("item") or {}
    info = item.get("info") or {}
    art = item.get("art") or {}
    props = item.get("properties") or {}
    routed = entry.get("url", "") or ""
    page_url = routed
    if "url=" in routed:
        import urllib.parse
        query = urllib.parse.parse_qs(urllib.parse.urlsplit(routed).query)
        page_url = (query.get("url") or [routed])[0]
    return {
        "label": item.get("label", ""),
        "url": page_url,
        "routed": routed,
        "folder": entry.get("is_folder"),
        "thumb": art.get("thumb") or art.get("poster") or "",
        "fanart": art.get("fanart", ""),
        "plot": (info.get("plot") or "")[:160],
        "duration": info.get("duration"),
        "props": {k: v for k, v in props.items() if k in ("IsPlayable", "mimetype", "type")},
    }


def _process_content(website, url, page):
    """Mirror default.py: pass page only where the module takes it."""
    import inspect
    method = website.process_content
    params = inspect.signature(method).parameters
    if "page" in params or any(p.kind is inspect.Parameter.VAR_KEYWORD for p in params.values()):
        return method(url, page=page)
    return method(url)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("site")
    parser.add_argument("action", choices=("list", "play", "playfirst", "search", "fetch", "info"))
    parser.add_argument("arg", nargs="?")
    parser.add_argument("--core", action="store_true", help="route page fetches through 127.0.0.1:8191")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--raw", action="store_true", help="with fetch: print the body head")
    parser.add_argument("--settings", default="")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--index", type=int, default=0, help="with playfirst: which listed video to play")
    args = parser.parse_args(argv)

    xbmc, xbmcaddon, xbmcplugin = _bootstrap(
        settings={k: v for k, v in (p.split("=", 1) for p in (args.settings or "").split(",") if "=" in p)},
        use_core=args.core,
    )

    result = {"site": args.site, "action": args.action, "ok": False}
    try:
        website, module = _build(args)
        result["class"] = type(website).__name__
        result["base_url"] = getattr(website, "base_url", "")
        target = args.arg

        if args.action == "info":
            result["ok"] = True
            result["attrs"] = {
                key: getattr(website, key)
                for key in ("label", "base_url", "search_url", "sort_options", "sort_paths", "categories_path")
                if hasattr(website, key)
            }

        elif args.action == "list":
            xbmcplugin.reset()
            url = target or getattr(website, "base_url", "")
            _process_content(website, url, 1)
            entries = [_item_summary(e) for e in xbmcplugin.DIRECTORY]
            items = [e for e in entries if e["url"] not in ("", None) and not e["folder"] or not e["url"]]
            result.update({
                "ok": True,
                "url": url,
                "count": len(entries),
                "videos": [e for e in entries if not e["folder"] and e["url"]],
                "folders": [e["label"] for e in entries if e["folder"]],
                "items": entries[: args.limit] if args.limit else entries,
            })

        elif args.action == "search":
            xbmcplugin.reset()
            website.search(target or "")
            entries = [_item_summary(e) for e in xbmcplugin.DIRECTORY]
            result.update({
                "ok": True,
                "count": len(entries),
                "videos": [e for e in entries if not e["folder"] and e["url"]],
                "items": entries[: args.limit] if args.limit else entries,
            })

        elif args.action == "play":
            xbmcplugin.reset()
            website.play_video(target)
            resolved = xbmcplugin.RESOLVED
            result.update({
                "ok": bool(resolved) and bool(resolved[-1].get("succeeded")),
                "resolved": resolved,
            })

        elif args.action == "playfirst":
            xbmcplugin.reset()
            _process_content(website, target or getattr(website, "base_url", ""), 1)
            videos = [e for e in xbmcplugin.DIRECTORY if not e.get("is_folder") and e.get("url")]
            if not videos:
                result["error"] = "listing returned no videos"
            else:
                index = min(args.index, len(videos) - 1)
                chosen = _item_summary(videos[index])
                target = chosen["url"]
                xbmcplugin.reset()
                website.play_video(target)
                resolved = xbmcplugin.RESOLVED
                result.update({
                    "ok": bool(resolved) and bool(resolved[-1].get("succeeded")),
                    "page_url": target,
                    "label": chosen["label"],
                    "resolved": resolved,
                })

        elif args.action == "fetch":
            import time
            started = time.time()
            response = None
            fetcher = getattr(website, "_get", None)
            if fetcher is not None:
                try:
                    body = fetcher(target)
                    result["mode"] = "_get"
                    result["body_len"] = len(body or "")
                    result["title"] = _title(body or "")
                    result["head"] = (body or "")[:400] if args.raw else _title(body or "")
                    result["ok"] = bool(body)
                except Exception as exc:
                    result["error"] = "%s: %s" % (type(exc).__name__, exc)
            if "body_len" not in result:
                import requests
                reply = requests.get(target, timeout=30)
                result.update({
                    "mode": "requests",
                    "ok": reply.status_code == 200,
                    "status": reply.status_code,
                    "content_type": reply.headers.get("content-type", ""),
                    "body_len": len(reply.content),
                    "title": _title(reply.text),
                    "head": reply.text[:400] if args.raw else "",
                })
            result["elapsed"] = round(time.time() - started, 2)
            result["core"] = _core_stats()

    except SystemExit:
        raise
    except Exception:
        result["error"] = traceback.format_exc(limit=6)

    if args.core and "core" not in result:
        result["core"] = _core_stats()

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
    else:
        _print_human(result)
    return 0 if result.get("ok") else 1


def _core_stats():
    try:
        from resources.lib import core_transport
        return {"stats": core_transport.stats(), "thread": core_transport.thread_stats()}
    except Exception:
        return ""


def _title(body):
    import re
    match = re.search(r"<title[^>]*>(.*?)</title>", body or "", re.I | re.S)
    return re.sub(r"\s+", " ", match.group(1)).strip()[:200] if match else ""


def _print_human(result):
    print("site=%(site)s action=%(action)s ok=%(ok)s" % result)
    for key in ("class", "base_url", "url", "count", "status", "content_type", "body_len", "title", "elapsed", "error", "core"):
        if result.get(key) not in (None, "", {}):
            value = result[key]
            print("%-13s %s" % (key + ":", value if not isinstance(value, str) else value[:600]))
    for item in (result.get("videos") or [])[:20]:
        print("  video: %-60s %s" % (item["label"][:60], item["url"][:110]))
    for folder in (result.get("folders") or [])[:20]:
        print("  folder: %s" % folder)
    for entry in (result.get("resolved") or [])[:3]:
        print("  resolved: %s" % json.dumps(entry, ensure_ascii=False)[:800])


if __name__ == "__main__":
    sys.exit(main())
