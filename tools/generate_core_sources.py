#!/usr/bin/env python3
"""Regenerates the list of sources the Rust Core searches directly.

Each website module is loaded with Kodi and third-party modules stubbed, so the
list holds the search URL the site really uses. Sites whose search does not work
as a plain HTML page get an entry in OVERRIDES (JSON API, POST form, cookies,
moved domain, link rewrite). Sites in PYTHON_ONLY stay with their Python module
in the global search. No network access is needed.

Run from the repository root after adding or changing website modules:
    python tools/generate_core_sources.py
"""
import importlib
import importlib.abc
import importlib.machinery
import json
import os
import sys
import tempfile
from unittest.mock import MagicMock

ADDON = os.path.abspath("plugin.video.adulthideout")
WEBSITES = os.path.join(ADDON, "resources", "websites")

# The Core cannot get usable results here; the Python module keeps searching them.
PYTHON_ONLY = {
    "pornhub",      # serves the Core a block page
    "hypnotube",    # results only after a session-bound POST redirect
    "stripchat",    # live cams, play payload built by the module
    "akih",         # search returns series; the module expands them to episodes
    "inporn",       # JSON API search with the module's minimum-duration filter
    "leakgallery",  # search results are Angular transfer-state media records
    "mixporn",      # Core reports success but extracts no cards on the current site
    "showcamrips",  # model search and per-recording artwork decoded by the module
    # These modules filter their results (blocked terms, ratings, orientation).
    # The Core cannot apply those filters, so they must keep searching in Python.
    "iwara",
    "hentaimama",
    "hentaisea",
    "xvideos",
}

_TXXX_API = "{base}api/videos2.php?params={params}/relevance/60/search..1.all..&s={{}}"

OVERRIDES = {
    # Shared "videos" JSON API (txxx network). Without api_page_url the module gets its JSON play payload.
    "txxx": {"base_url": "https://txxx.com/", "search_url": _TXXX_API.format(base="https://txxx.com/", params="259200/str")},
    "vjav": {"base_url": "https://vjav.com/", "search_url": _TXXX_API.format(base="https://vjav.com/", params="259200/str")},
    "hdzog": {"base_url": "https://hdzog.com/", "search_url": _TXXX_API.format(base="https://hdzog.com/", params="259200/str")},
    "voyeurhit": {"base_url": "https://voyeurhit.com/", "search_url": _TXXX_API.format(base="https://voyeurhit.com/", params="259200/str")},
    "shemalez": {"base_url": "https://shemalez.com/", "search_url": _TXXX_API.format(base="https://shemalez.com/", params="259200/she")},
    "tubepornclassic": {"base_url": "https://tubepornclassic.com/", "api_page_url": "https://tubepornclassic.com/videos/{id}/",
                        "search_url": _TXXX_API.format(base="https://tubepornclassic.com/", params="86400/str")},
    "hclips": {"base_url": "https://hclips.com/", "api_page_url": "https://hclips.com/videos/{id}/{dir}/",
               "search_url": _TXXX_API.format(base="https://hclips.com/", params="86400/str")},
    "abxxx": {"base_url": "https://abxxx.com/", "api_page_url": "https://abxxx.com/video/{id}/{dir}/",
              "search_url": _TXXX_API.format(base="https://abxxx.com/", params="259200/str")},
    "vxxx": {"base_url": "https://vxxx.com/", "api_page_url": "https://vxxx.com/video/{id}/{dir}/",
             "search_url": _TXXX_API.format(base="https://vxxx.com/", params="259200/str")},
    "upornia": {"base_url": "https://upornia.com/", "api_page_url": "PLAY_VIDEO:{id}",
                "search_url": "https://upornia.com/api/videos.php?params=86400/str/relevance/60/search..1.all..&s={}"},
    # Other JSON APIs and feeds.
    "latestpornvideo": {"search_url": "https://latestpornvideo.com/wp-json/wp/v2/posts?search={}&per_page=60"},
    "hentaiocean": {"base_url": "https://hentaiocean.com/", "search_url": "https://hentaiocean.com/rss.xml?q={}"},
    "archivebate": {"base_url": "https://archivebate.com/", "search_url": "https://archivebate.com/api/v1/search?query={}&page=1"},
    # Internal search routes and moved domains.
    "8kporner": {"base_url": "https://8kporner.com/", "search_url": "https://8kporner.com/?link1=search&keyword={}"},
    "ebalka26": {"base_url": "https://1ebalka.ru.actor/", "search_url": "https://1ebalka.ru.actor/search/{}/"},
    # Search by POST form.
    # The POST form redirects; the result page itself is a plain GET URL.
    "heavy_r": {"base_url": "https://www.heavy-r.com/", "search_url": "https://www.heavy-r.com/search/{}.html"},
    "pornhoarder": {"base_url": "https://pornhoarder.tv/", "search_url": "https://pornhoarder.tv/ajax_search.php",
                    "post_data": "search={}&sort=0&date=0&author=0&page=1" + "".join(
                        "&servers%5B%5D=" + server for server in ("47", "21", "40", "45", "12", "25", "41", "44", "42", "43", "48", "29"))},
    # Modules that search through their own code instead of a search_url.
    "boundhub": {"base_url": "https://www.boundhub.com/", "search_url": "https://www.boundhub.com/search/{}/"},
    "porndoe": {"base_url": "https://porndoe.com/", "search_url": "https://porndoe.com/search?q={}"},
    "rapelust": {"base_url": "https://rapelust.com/", "search_url": "https://rapelust.com/?s={}"},
    "tokyomotion": {"base_url": "https://www.tokyomotion.net/", "search_url": "https://www.tokyomotion.net/search?search_query={}&search_type=videos"},
    "xfreehd": {"base_url": "https://www.xfreehd.com/", "search_url": "https://www.xfreehd.com/search?search_query={}&search_type=videos"},
    "tube8": {"base_url": "https://www.tube8.com/", "search_url": "https://www.tube8.com/searches.html?q={}"},
    "sexu": {"base_url": "https://sexu.com/", "search_url": "https://sexu.com/search", "post_data": "query={}"},
    # The module searches tag pages, not the search page.
    "myporntape": {"base_url": "https://myporntape.com/", "search_url": "https://myporntape.com/tags/{}/"},
    # Series pages link to their first episode.
    "watchhentai": {"link_replace": [["/series/", "/videos/"], ["-id-01/", "-episode-1-id-01/"]]},
}


class StubMissingModules(importlib.abc.MetaPathFinder, importlib.abc.Loader):
    """Answers imports of anything not installed here (xbmc, requests, ...)."""

    def find_spec(self, name, path=None, target=None):
        if name.split(".")[0] == "resources":
            return None
        # Stub only what is really missing; a stubbed optional dependency of an
        # installed package (e.g. simplejson for requests) breaks that package.
        for finder in sys.meta_path:
            if finder is self or not hasattr(finder, "find_spec"):
                continue
            try:
                if finder.find_spec(name, path, target) is not None:
                    return None
            except Exception:
                continue
        return importlib.machinery.ModuleSpec(name, self, is_package=True)

    def create_module(self, spec):
        stub = MagicMock(name=spec.name)
        stub.__path__ = []
        stub.__spec__ = spec
        stub.__name__ = spec.name
        return stub

    def exec_module(self, module):
        pass


def read_site(name, base_class):
    module = importlib.import_module("resources.websites." + name)
    for attr in dir(module):
        cls = getattr(module, attr)
        if (isinstance(cls, type) and issubclass(cls, base_class) and cls is not base_class
                and cls.__module__ == module.__name__):
            site = cls(1)
            return getattr(site, "search_url", None), getattr(site, "base_url", None)
    return None, None


def main():
    sys.path.insert(0, ADDON)
    # Import installed packages before stubbing: they probe optional dependencies
    # (e.g. requests -> simplejson), and a stub for those breaks them.
    for package in ("requests", "urllib3", "bs4", "cloudscraper", "certifi", "chardet", "charset_normalizer", "idna"):
        try:
            importlib.import_module(package)
        except Exception:
            pass
    sys.meta_path.append(StubMissingModules())
    # Modules create cache folders from Kodi paths while loading. Point those stubs at a
    # throwaway folder, or they create folders named after the mock in the working directory.
    scratch = tempfile.mkdtemp(prefix="core_sources_")
    xbmcvfs = importlib.import_module("xbmcvfs")
    xbmcvfs.translatePath = lambda path: scratch
    importlib.import_module("xbmcaddon").Addon.return_value.getAddonInfo.return_value = scratch
    sys.argv = ["plugin://plugin.video.adulthideout/", "1", ""]
    from resources.lib.base_website import BaseWebsite

    sources, skipped = [], {}
    for filename in sorted(os.listdir(WEBSITES)):
        if not filename.endswith(".py") or filename == "__init__.py":
            continue
        name = filename[:-3]
        if name in PYTHON_ONLY:
            skipped[name] = "Python only"
            continue
        entry = {"id": name}
        try:
            search_url, base_url = read_site(name, BaseWebsite)
            if isinstance(search_url, str) and search_url.startswith("http"):
                entry["search_url"] = search_url.replace("%s", "{}")
            if isinstance(base_url, str):
                entry["base_url"] = base_url
        except Exception as exc:
            if name not in OVERRIDES:
                skipped[name] = "load error: {}".format(exc)
                continue
        entry.update(OVERRIDES.get(name, {}))
        if "{}" not in entry.get("search_url", "") + entry.get("post_data", ""):
            skipped[name] = "no usable search_url: {!r}".format(entry.get("search_url"))[:90]
            continue
        sources.append(entry)

    target = os.path.join(ADDON, "resources", "core_search_sources.json")
    with open(target, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(sources, handle, indent=0, sort_keys=True)
        handle.write("\n")
    print("{} sources written, {} skipped".format(len(sources), len(skipped)))
    for name, reason in sorted(skipped.items()):
        print("  {}: {}".format(name, reason))


if __name__ == "__main__":
    main()
