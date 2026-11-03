# -*- coding: utf-8 -*-
# DoodStream / DsvPlay / MyVidPlay / Playmogo resolver
# Reverse-engineered from current DoodStream JS (Feb 2026)
#
# Flow:
#   1. Fetch embed page → get /pass_md5/{hash}/{token} path
#   2. GET /pass_md5/... → returns base stream URL
#   3. Append makePlay(): 10 random chars + ?token={token}&expiry={timestamp}
#   4. Final URL = base_url + random_string + ?token=...&expiry=...

import random
import re
import string
import time
from urllib.parse import urlparse
import xbmc

# Use the addon's vendored cloudscraper
try:
    import cloudscraper
    _HAS_CF = True
except ImportError:
    try:
        import os, sys
        vendor_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "lib", "vendor"
        )
        if vendor_path not in sys.path:
            sys.path.insert(0, vendor_path)
        import cloudscraper
        _HAS_CF = True
    except ImportError:
        _HAS_CF = False

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; rv:128.0) Gecko/20100101 Firefox/128.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3 Safari/605.1.15",
]

# All known DoodStream mirror domains
KNOWN_DOMAINS = [
    "doodstream", "dsvplay", "myvidplay", "dood.to", "dood.pm",
    "dood.watch", "dood.so", "dood.wf", "dood.re", "dood.cx",
    "dood.la", "dood.ws", "dood.sh", "dood.yt", "ds2play",
    "doods.pro", "d0o0d", "d0000d", "do0od", "d000d",
    "playmogo"
]


def _make_play(token):
    """Replicate DoodStream's makePlay() JavaScript function."""
    chars = string.ascii_letters + string.digits
    random_str = "".join(random.choice(chars) for _ in range(10))
    expiry = int(time.time() * 1000)
    return f"{random_str}?token={token}&expiry={expiry}"


def _is_challenge_page(html):
    if not html:
        return False
    if "/pass_md5/" in html:
        return False
    lower = html.lower()
    return any(marker in lower for marker in (
        "just a moment",
        "attention required",
        "security check",
        "captcha-player",
        "cf-turnstile-wrapper",
        "verify you are human",
        "checking your browser",
    ))


def _extract_pass_md5(html):
    if not html:
        return None
    call_match = re.search(r'''(?:\.get|fetch)\s*\(\s*['"](/pass_md5/[^'"]+)['"]''', html)
    if call_match:
        return call_match.group(1)
    lit_match = re.search(r'''['"](/pass_md5/[^'"]+)['"]''', html)
    if lit_match:
        return lit_match.group(1)
    return None


def resolve(url, referer=None, headers=None):
    xbmc.log(f"[AdultHideout][doodstream] Resolving: {url}", xbmc.LOGINFO)

    ua = random.choice(USER_AGENTS)
    scraper = None
    if _HAS_CF:
        try:
            scraper = cloudscraper.create_scraper(
                browser={"browser": "chrome", "platform": "windows", "mobile": False}
            )
        except Exception:
            scraper = None

    base_headers = {
        "User-Agent": ua,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9,de;q=0.8",
        "Referer": referer or url,
    }
    if headers:
        base_headers.update(headers)

    # Step 1: Fetch the embed page
    html = ""
    final_url = url
    if scraper is not None:
        try:
            response = scraper.get(url, headers=base_headers, allow_redirects=True)
            if response.status_code == 200 and not _is_challenge_page(response.text):
                html = response.text
                final_url = response.url
            else:
                xbmc.log(
                    f"[AdultHideout][doodstream] Scraper returned HTTP {response.status_code}, falling back to Core engine...",
                    xbmc.LOGINFO,
                )
        except Exception as e:
            xbmc.log(f"[AdultHideout][doodstream] Scraper request failed: {e}", xbmc.LOGINFO)

    pass_md5_path = _extract_pass_md5(html)
    if not pass_md5_path:
        try:
            from resources.lib.resilient_http import fetch_text
            core_html = fetch_text(url, headers=base_headers, scraper=scraper)
            if core_html and not _is_challenge_page(core_html):
                html = core_html
                pass_md5_path = _extract_pass_md5(html)
        except Exception as exc:
            xbmc.log(f"[AdultHideout][doodstream] Core fetch failed: {exc}", xbmc.LOGWARNING)

    if not pass_md5_path:
        if _is_challenge_page(html):
            xbmc.log(
                "[AdultHideout][doodstream] Cloudflare/Turnstile challenge could not be bypassed",
                xbmc.LOGWARNING,
            )
        else:
            xbmc.log("[AdultHideout][doodstream] No /pass_md5/ pattern found in HTML", xbmc.LOGERROR)
        return None, {}

    xbmc.log(f"[AdultHideout][doodstream] Found pass_md5 path: {pass_md5_path}", xbmc.LOGINFO)
    host = urlparse(final_url).netloc
    if not host or host in ("d000d.com", "dood.stream", "dood.to"):
        host = "playmogo.com"

    # Extract token from the pass_md5 path (last path segment)
    token = pass_md5_path.split("/")[-1]

    # Also try to extract token from makePlay function as fallback
    token_match = re.search(r"""token[=:]\s*['"]?([a-z0-9]+)['"]?""", html)
    if token_match:
        make_play_match = re.search(
            r"""makePlay\s*\(.*?token\s*[=+]\s*['"]([a-z0-9]+)['"]""",
            html, re.DOTALL
        )
        if make_play_match:
            token = make_play_match.group(1)
            xbmc.log(f"[AdultHideout][doodstream] Token from makePlay: {token}", xbmc.LOGINFO)

    # Step 3: Fetch the pass_md5 URL to get the base stream URL
    pass_md5_url = f"https://{host}{pass_md5_path}"
    pass_headers = base_headers.copy()
    pass_headers["Referer"] = final_url
    pass_headers["X-Requested-With"] = "XMLHttpRequest"

    base_stream_url = ""
    for attempt in range(3):
        try:
            if scraper is not None:
                data_response = scraper.get(pass_md5_url, headers=pass_headers)
                if data_response.status_code == 200:
                    base_stream_url = data_response.text.strip()
            if not base_stream_url or base_stream_url.startswith("<!DOCTYPE") or "<html" in base_stream_url:
                from resources.lib.resilient_http import fetch_text
                base_stream_url = (fetch_text(pass_md5_url, headers=pass_headers, scraper=scraper) or "").strip()
            if base_stream_url and base_stream_url != "RELOAD":
                break
            time.sleep(1.0)
        except Exception as e:
            try:
                from resources.lib.resilient_http import fetch_text
                base_stream_url = (fetch_text(pass_md5_url, headers=pass_headers, scraper=scraper) or "").strip()
                if base_stream_url and base_stream_url != "RELOAD":
                    break
            except Exception:
                pass

    if not base_stream_url or not base_stream_url.startswith("http"):
        if base_stream_url == "RELOAD":
            xbmc.log("[AdultHideout][doodstream] Server returned RELOAD - try again later", xbmc.LOGWARNING)
        else:
            xbmc.log(f"[AdultHideout][doodstream] Invalid base URL: {base_stream_url[:100]}", xbmc.LOGERROR)
        return None, {}

    # Step 4: Build final URL with makePlay()
    final_stream_url = base_stream_url + _make_play(token)

    play_headers = {
        "User-Agent": ua,
        "Referer": f"https://{host}/",
    }

    xbmc.log("[AdultHideout][doodstream] Final stream URL resolved", xbmc.LOGINFO)
    return final_stream_url, play_headers
