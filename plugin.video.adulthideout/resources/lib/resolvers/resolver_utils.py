import gzip
import io
import re
import time
import urllib.request
import urllib.parse
import xbmc
import xbmcgui
import xbmcaddon
import sys
import os
import logging

sys.path.append(
    os.path.join(
        xbmcaddon.Addon().getAddonInfo("path"),
        "resources", "lib", "vendor", "cloudscraper"
    )
)
try:
    import cloudscraper
    _HAS_CF = True
except Exception:
    _HAS_CF = False

_ADDON = xbmcaddon.Addon()
_ADDON_ID = _ADDON.getAddonInfo("id")
_SHOW_NOTIFICATION = True
logger = logging.getLogger(__name__)

def http_get(url, headers=None, retries=2, sleep=0.4, timeout=15):
    headers = headers or {}
    headers.setdefault("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64)")
    headers.setdefault("Accept-Encoding", "gzip, deflate")

    last_exc = None

    if _HAS_CF:
        try:
            scraper = cloudscraper.create_scraper(
                browser={"browser": "chrome", "platform": "windows", "mobile": False}
            )
            xbmc.log("[AdultHideout][resolver_utils] cloudscraper GET: {}".format(url), xbmc.LOGINFO)
            response = scraper.get(url, headers=headers, timeout=timeout)
            if response.status_code == 200:
                try:
                    return response.text
                except UnicodeDecodeError:
                    xbmc.log("[resolver_utils] Cloudscraper text decoding failed for {}".format(url), xbmc.LOGWARNING)
                    try:
                        return response.content.decode("latin-1", errors="replace")
                    except Exception as decode_err:
                        xbmc.log(f"[resolver_utils] Cloudscraper fallback decoding failed: {decode_err}", xbmc.LOGERROR)
                        return ""
            else:
                xbmc.log("[AdultHideout][resolver_utils] cloudscraper GET failed with status {}: {}".format(response.status_code, url), xbmc.LOGWARNING)

        except Exception as e:
            xbmc.log("[AdultHideout][resolver_utils] cloudscraper GET failed: {}".format(e), xbmc.LOGWARNING)

    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = resp.read()
                if resp.info().get("Content-Encoding") == "gzip":
                    buf = io.BytesIO(data)
                    with gzip.GzipFile(fileobj=buf) as f:
                        data = f.read()
                try:
                    return data.decode("utf-8")
                except UnicodeDecodeError:
                    xbmc.log("[resolver_utils] UTF-8 decoding failed, trying latin-1", xbmc.LOGDEBUG)
                    return data.decode("latin-1", errors="replace")
        except Exception as e:
            last_exc = e
            xbmc.log("[AdultHideout][resolver_utils] urllib attempt {} failed: {}".format(attempt+1, e), xbmc.LOGWARNING)
            if attempt < retries:
                time.sleep(sleep)

    xbmc.log("[AdultHideout][resolver_utils] HTTP GET failed: {}".format(last_exc), xbmc.LOGERROR)
    return ""


def unpack_js(p, a, c, k):
    if not p:
        return ""
    import re
    if not isinstance(k, list):
        if isinstance(k, str):
            k = k.split('|')
        else:
            xbmc.log("[AdultHideout][resolver_utils] unpack_js: k is neither string nor list.", xbmc.LOGERROR)
            return p

    def _repl(match):
        word = match.group(0)
        try:
            if not 2 <= a <= 36:
                return word
            val = int(word, a)
            if 0 <= val < len(k) and k[val]:
                return k[val]
        except (TypeError, ValueError):
            pass
        return word

    try:
        return re.sub(r'\b\w+\b', _repl, p)
    except Exception as e:
        xbmc.log("[AdultHideout][resolver_utils] unpack_js failed during substitution: {}".format(e), xbmc.LOGERROR)
        return p


def notify(message, icon=xbmcgui.NOTIFICATION_INFO, time_ms=3000):
    xbmc.log("[AdultHideout][resolver_utils] {}".format(message), xbmc.LOGINFO)
    if _SHOW_NOTIFICATION:
        xbmcgui.Dialog().notification("Resolver", message, icon, time_ms)


def resolve_generic(embed_url, referer, headers):
    headers = dict(headers or {})
    headers["Referer"] = referer or embed_url

    html = http_get(embed_url, headers=headers)
    if not html:
        notify("Generic resolver: No data received from {}".format(embed_url), xbmcgui.NOTIFICATION_WARNING)
        return "", headers

    patterns = [
        r'<source[^>]+src=["\']([^"\']+\.(?:m3u8|mp4)[^"\']*)["\']',
        r'file\s*[:=]\s*["\']([^"\']+\.(?:m3u8|mp4)[^"\']*)["\']',
        r'player\.src\s*\(\s*["\']([^"\']+\.(?:m3u8|mp4)[^"\']*)["\']',
        r'(https?://[^\s"\']+\.(?:m3u8|mp4)[^"\']*)',
        r'window\.open\s*\(\s*["\'](https?://[^\s"\']+\.(?:m3u8|mp4)[^"\']*)["\']',
    ]

    for pattern in patterns:
        m = re.search(pattern, html, re.IGNORECASE)
        if m:
            stream_url = m.group(1).strip()
            if stream_url.startswith('http') and (stream_url.endswith('.m3u8') or stream_url.endswith('.mp4')):
                notify("Generic resolver success: {}".format(stream_url.split('/')[-1]))
                return stream_url, headers
            else:
                xbmc.log("[AdultHideout][resolver_utils] Generic match skipped (invalid format/start)", xbmc.LOGDEBUG)

    notify("Generic resolver: No stream found for {}".format(embed_url), xbmcgui.NOTIFICATION_WARNING)
    return "", headers

def get_ua():
    return (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/126.0.0.0 Safari/537.36"
    )

