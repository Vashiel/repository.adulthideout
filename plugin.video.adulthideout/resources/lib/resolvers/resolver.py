# -*- coding: utf-8 -*-
import time
import urllib.parse
import urllib.error
import urllib.request

import xbmc
import xbmcaddon

from resources.lib.resolvers import bigwarp_resolver
from resources.lib.resolvers import dirtyvideo_resolver
from resources.lib.resolvers import doodstream_resolver
from resources.lib.resolvers import eightyeightz_resolver
from resources.lib.resolvers import hglink_resolver
from resources.lib.resolvers import lulustream_resolver
from resources.lib.resolvers import mixdrop_resolver
from resources.lib.resolvers import mydaddy_resolver
from resources.lib.resolvers import resolver_utils
from resources.lib.resolvers import streamtape_resolver
from resources.lib.resolvers import turboplayers_resolver
from resources.lib.resolvers import vidhide_resolver
from resources.lib.resolvers import vidello_resolver
from resources.lib.resolvers import voesx_resolver
from resources.lib.resolvers import vtube_resolver
from resources.lib.resolvers import tubexplayer_resolver
from resources.lib.resolvers import watchstreamhd_resolver


RESOLVERS = [
    {
        "key": "hglink",
        "setting": "resolver_enable_hglink",
        "module": hglink_resolver,
        "hosts": ("hglink.to", "hanerix.com"),
    },
    {
        "key": "doodstream",
        "setting": "resolver_enable_doodstream",
        "module": doodstream_resolver,
        "hosts": (
            "dood", "dooood", "dsvplay", "myvidplay", "playmogo.com",
            "dood.stream", "dood.li", "doodstream.link", "doodstream.co",
        ),
    },
    {
        "key": "streamtape",
        "setting": "resolver_enable_streamtape",
        "module": streamtape_resolver,
        "hosts": ("streamtape", "stape"),
    },
    {
        "key": "turboplayers",
        "setting": "resolver_enable_turboplayers",
        "module": turboplayers_resolver,
        "hosts": ("turboplayers.xyz", "turboviplay.com"),
    },
    {
        "key": "vidhide",
        "setting": "resolver_enable_vidhide",
        "module": vidhide_resolver,
        "hosts": (
            "vidhide.com", "vidhidepre.com", "minochinos.com",
            "callistanise.com", "sunflowercreativeworks.cyou", "ryderjet.com",
        ),
    },
    {
        "key": "voe",
        "setting": "resolver_enable_voe",
        "module": voesx_resolver,
        "hosts": (
            "voe.sx", "voe-unblock", "voeunblock", "un-block-voe",
            "v-o-e-unblock", "audaciousdefaulthouse.com",
            "launchreliantcleaverriver.com", "fittingcentermondaysunday.com",
        ),
    },
    {
        "key": "mixdrop",
        "setting": "resolver_enable_mixdrop",
        "module": mixdrop_resolver,
        "hosts": ("mixdrop", "m1xdrop", "mxdrop", "miiixdrop"),
    },
    {
        "key": "mydaddy",
        "setting": "resolver_enable_mydaddy",
        "module": mydaddy_resolver,
        "hosts": ("mydaddy.cc", "mydaddy"),
    },
    {
        "key": "88z",
        "setting": "resolver_enable_88z",
        "module": eightyeightz_resolver,
        "hosts": ("88z.io",),
    },
    {
        "key": "lulustream",
        "setting": "resolver_enable_lulustream",
        "module": lulustream_resolver,
        "hosts": ("lulu", "lulustream", "luluvdo"),
    },
    {
        "key": "vtube",
        "setting": "resolver_enable_vtube",
        "module": vtube_resolver,
        "hosts": ("vtube.to", "vtplay.net", "vtbe.net", "vtbe.to", "vtube.network"),
    },
    {
        "key": "vidello",
        "setting": "resolver_enable_vidello",
        "module": vidello_resolver,
        "hosts": ("vidello.net",),
    },
    {
        "key": "dirtyvideo",
        "setting": "resolver_enable_dirtyvideo",
        "module": dirtyvideo_resolver,
        "hosts": (
            "dirtyvideo.fun", "dirtyvideo", "netu.ac", "netu.tv", "netu.to",
            "waaw.ac", "waaw.tv", "waaw.to", "hqq.ac", "hqq.tv", "hqq.to",
        ),
    },
    {
        "key": "bigwarp",
        "setting": None,
        "module": bigwarp_resolver,
        "hosts": ("bigwarp", "bgwp"),
    },
    {
        "key": "tubexplayer",
        "setting": "resolver_enable_tubexplayer",
        "module": tubexplayer_resolver,
        "hosts": ("tubexplayer.com", "tubexplayer"),
    },
    {
        "key": "watchstreamhd",
        "setting": "resolver_enable_watchstreamhd",
        "module": watchstreamhd_resolver,
        "hosts": ("watchstreamhd.com", "watchstreamhd", "video-mart.com", "videostreamingworld.com"),
    },
]

PREFERRED_KEYS = [
    None,
    "hglink",
    "doodstream",
    "streamtape",
    "turboplayers",
    "vidhide",
    "voe",
    "mixdrop",
    "lulustream",
    "vtube",
    "vidello",
    "dirtyvideo",
    "mydaddy",
    "88z",
    "tubexplayer",
    "watchstreamhd",
]


def _addon():
    try:
        return xbmcaddon.Addon()
    except Exception:
        return None


def _setting_bool(addon, setting_id, default=True):
    if not setting_id or not addon:
        return default
    try:
        value = addon.getSetting(setting_id)
        if value == "":
            return default
        return value.lower() == "true"
    except Exception:
        return default


def _preferred_key(addon=None):
    addon = addon or _addon()
    try:
        index = int(addon.getSetting("resolver_preferred") or "0") if addon else 0
    except Exception:
        index = 0
    if 0 <= index < len(PREFERRED_KEYS):
        return PREFERRED_KEYS[index]
    return None


def _hostname(url):
    try:
        return urllib.parse.urlparse(url).netloc.lower()
    except Exception:
        xbmc.log("[AdultHideout][resolver] Failed to parse hostname from URL: {}".format(url), xbmc.LOGWARNING)
        return ""


def _host_matches(hostname, url, host_key):
    host_key = host_key.lower()
    lowered_url = url.lower()
    return (
        host_key == hostname
        or hostname.endswith("." + host_key)
        or host_key in hostname
        or host_key in lowered_url
    )


def resolver_entry_for_url(url):
    hostname = _hostname(url)
    for entry in RESOLVERS:
        for host_key in entry["hosts"]:
            if _host_matches(hostname, url, host_key):
                return entry
    return None


def resolver_key_for_url(url):
    entry = resolver_entry_for_url(url)
    return entry["key"] if entry else ""


def is_resolver_enabled(url, addon=None):
    entry = resolver_entry_for_url(url)
    if not entry:
        return True
    return _setting_bool(addon or _addon(), entry.get("setting"), True)


def resolver_sort_key_for_url(url, addon=None):
    addon = addon or _addon()
    entry = resolver_entry_for_url(url)
    if not entry:
        return 1000
    if not _setting_bool(addon, entry.get("setting"), True):
        return 2000
    preferred = _preferred_key(addon)
    if preferred and entry["key"] == preferred:
        return -1
    return 100


def sort_urls_by_resolver_preference(urls, addon=None):
    addon = addon or _addon()
    return sorted(urls, key=lambda item: resolver_sort_key_for_url(item, addon))


def resolver_preflight_enabled(addon=None):
    return _setting_bool(addon or _addon(), "resolver_preflight", True)


def probe_resolved_stream(url, headers=None, timeout=7):
    if not url:
        return False

    direct_url = url
    request_headers = {}
    if "|" in direct_url:
        direct_url, header_string = direct_url.split("|", 1)
        request_headers.update(dict(urllib.parse.parse_qsl(header_string)))

    if direct_url.startswith("http://127.0.0.1") or direct_url.startswith("http://localhost"):
        return True

    if not direct_url.startswith(("http://", "https://")):
        return False

    request_headers.setdefault("User-Agent", resolver_utils.get_ua())
    request_headers.setdefault("Accept", "*/*")
    request_headers.setdefault("Accept-Encoding", "identity")
    request_headers.setdefault("Connection", "close")
    if headers:
        for key, value in headers.items():
            if value:
                request_headers[key] = value

    start = time.time()
    try:
        req = urllib.request.Request(direct_url, headers=request_headers)
        with urllib.request.urlopen(req, timeout=timeout) as response:
            status = response.getcode() or 200
            content_type = response.headers.get("Content-Type", "").lower()
            chunk = response.read(65536)

        elapsed = time.time() - start
        if status >= 400:
            xbmc.log(
                "[AdultHideout][resolver] Stream preflight failed HTTP {} for {}".format(status, direct_url),
                xbmc.LOGWARNING,
            )
            return False
        if not chunk:
            xbmc.log(
                "[AdultHideout][resolver] Stream preflight failed with empty response for {}".format(direct_url),
                xbmc.LOGWARNING,
            )
            return False

        is_hls = ".m3u8" in direct_url.lower() or "mpegurl" in content_type
        if is_hls and b"#EXTM3U" not in chunk and b"#EXT-X-" not in chunk:
            xbmc.log(
                "[AdultHideout][resolver] Stream preflight rejected non-HLS playlist for {}".format(direct_url),
                xbmc.LOGWARNING,
            )
            return False

        xbmc.log(
            "[AdultHideout][resolver] Stream preflight OK in {:.2f}s for {}".format(elapsed, direct_url),
            xbmc.LOGINFO,
        )
        return True
    except urllib.error.HTTPError as exc:
        xbmc.log(
            "[AdultHideout][resolver] Stream preflight HTTPError {} for {}".format(exc.code, direct_url),
            xbmc.LOGWARNING,
        )
    except Exception as exc:
        xbmc.log(
            "[AdultHideout][resolver] Stream preflight failed for {}: {}".format(direct_url, exc),
            xbmc.LOGWARNING,
        )
    return False


def resolve(url, referer="", headers=None):
    xbmc.log("[AdultHideout][resolver] Input: {}".format(url), xbmc.LOGINFO)

    entry = resolver_entry_for_url(url)
    if entry:
        if not _setting_bool(_addon(), entry.get("setting"), True):
            xbmc.log(
                "[AdultHideout][resolver] Resolver {} disabled in settings for {}".format(entry["key"], url),
                xbmc.LOGINFO,
            )
            return "", {}

        selected_module = entry["module"]
        try:
            xbmc.log(
                "[AdultHideout][resolver] Executing custom resolver {} ({}) for {}".format(
                    selected_module.__name__, entry["key"], url
                ),
                xbmc.LOGINFO,
            )
            return selected_module.resolve(url, referer, headers)
        except Exception as e:
            import traceback
            xbmc.log(
                "[AdultHideout][resolver] Error in custom resolver {}: {}\n{}".format(
                    selected_module.__name__, e, traceback.format_exc()
                ),
                xbmc.LOGERROR,
            )
            return "", {}

    xbmc.log(
        "[AdultHideout][resolver] No custom resolver found for {}. Passing URL to Kodi/ResolveURL.".format(url),
        xbmc.LOGINFO,
    )
    final_headers = headers or {}
    final_headers.setdefault("User-Agent", resolver_utils.get_ua())
    if referer:
        final_headers["Referer"] = referer

    header_string = urllib.parse.urlencode(final_headers)
    return url + "|" + header_string, {}
