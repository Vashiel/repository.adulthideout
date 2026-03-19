# -*- coding: utf-8 -*-
# DoodStream / DsvPlay / MyVidPlay resolver
# Reverse-engineered from current DoodStream JS (Feb 2026)
#
# Flow:
#   1. Fetch embed page → get /pass_md5/{hash}/{token} path
#   2. GET /pass_md5/... → returns base stream URL
#   3. Append makePlay(): 10 random chars + ?token={token}&expiry={timestamp}
#   4. Final URL = base_url + random_string + ?token=...&expiry=...

import re
import time
import random
import string
import xbmc
from urllib.parse import urlparse

# Use the addon's vendored cloudscraper
try:
    import cloudscraper
    _HAS_CF = True
except ImportError:
    try:
        import sys, os
        vendor_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'lib', 'vendor')
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
KNOWN_DOMAINS = ['doodstream', 'dsvplay', 'myvidplay', 'dood.to', 'dood.pm',
                 'dood.watch', 'dood.so', 'dood.wf', 'dood.re', 'dood.cx',
                 'dood.la', 'dood.ws', 'dood.sh', 'dood.yt', 'ds2play',
                 'doods.pro', 'd0o0d', 'd0000d', 'do0od', 'd000d']


def _make_play(token):
    """Replicate DoodStream's makePlay() JavaScript function."""
    chars = string.ascii_letters + string.digits
    random_str = ''.join(random.choice(chars) for _ in range(10))
    expiry = int(time.time() * 1000)
    return f"{random_str}?token={token}&expiry={expiry}"


def resolve(url, referer=None, headers=None):
    xbmc.log(f"[AdultHideout][doodstream] Resolving: {url}", xbmc.LOGINFO)

    if not _HAS_CF:
        xbmc.log("[AdultHideout][doodstream] cloudscraper not available", xbmc.LOGERROR)
        return None, {}

    ua = random.choice(USER_AGENTS)
    scraper = cloudscraper.create_scraper(
        browser={"browser": "chrome", "platform": "windows", "mobile": False}
    )

    base_headers = {
        "User-Agent": ua,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9,de;q=0.8",
        "Referer": referer or url,
    }
    if headers:
        base_headers.update(headers)

    # Step 1: Fetch the embed page
    try:
        response = scraper.get(url, headers=base_headers, allow_redirects=True)
        if response.status_code != 200:
            xbmc.log(f"[AdultHideout][doodstream] Page returned HTTP {response.status_code}", xbmc.LOGERROR)
            return None, {}
        html = response.text
        final_url = response.url
        host = urlparse(final_url).netloc
        xbmc.log(f"[AdultHideout][doodstream] Page loaded from {host}, len={len(html)}", xbmc.LOGINFO)
    except Exception as e:
        xbmc.log(f"[AdultHideout][doodstream] Failed to fetch page: {e}", xbmc.LOGERROR)
        return None, {}

    # Step 2: Extract /pass_md5/ path and token
    # Try multiple patterns for robustness
    pass_md5_path = None
    
    # 1. Look for common call patterns: $.get('/pass_md5/...') or fetch('/pass_md5/...')
    call_match = re.search(r'''(?:\.get|fetch)\s*\(\s*['"](/pass_md5/[^'"]+)['"]''', html)
    if call_match:
        pass_md5_path = call_match.group(1)
    
    # 2. Look for the string literal alone if not found in a call
    if not pass_md5_path:
        lit_match = re.search(r'''['"](/pass_md5/[^'"]+)['"]''', html)
        if lit_match:
            pass_md5_path = lit_match.group(1)

    if not pass_md5_path:
        xbmc.log("[AdultHideout][doodstream] No /pass_md5/ pattern found in HTML", xbmc.LOGERROR)
        xbmc.log(f"[AdultHideout][doodstream] HTML (first 2000 chars): {html[:2000]}", xbmc.LOGINFO)
        return None, {}

    xbmc.log(f"[AdultHideout][doodstream] Found pass_md5 path: {pass_md5_path}", xbmc.LOGINFO)

    # Extract token from the pass_md5 path (last path segment)
    token = pass_md5_path.split('/')[-1]

    # Also try to extract token from makePlay function as fallback
    token_match = re.search(r"""token[=:]\s*['"]?([a-z0-9]+)['"]?""", html)
    if token_match:
        extracted_token = token_match.group(1)
        # Prefer the token from makePlay if available (it's more reliable)
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

    try:
        data_response = scraper.get(pass_md5_url, headers=pass_headers)
        if data_response.status_code != 200:
            xbmc.log(f"[AdultHideout][doodstream] pass_md5 returned HTTP {data_response.status_code}", xbmc.LOGERROR)
            return None, {}
        base_stream_url = data_response.text.strip()
        xbmc.log(f"[AdultHideout][doodstream] Base stream URL: {base_stream_url[:80]}", xbmc.LOGINFO)
    except Exception as e:
        xbmc.log(f"[AdultHideout][doodstream] Failed to fetch pass_md5: {e}", xbmc.LOGERROR)
        return None, {}

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

    xbmc.log(f"[AdultHideout][doodstream] Final stream URL: {final_stream_url[:100]}", xbmc.LOGINFO)
    return final_stream_url, play_headers


if __name__ == "__main__":
    # For local testing
    import logging
    logging.basicConfig(level=logging.INFO)

    class FakeXBMC:
        LOGINFO = 1
        LOGERROR = 3
        LOGWARNING = 2
        @staticmethod
        def log(msg, level=1):
            print(msg)

    import sys
    sys.modules['xbmc'] = FakeXBMC()

    test_url = "https://dsvplay.com/e/m1t67rtf6d2c/"
    try:
        result, hdrs = resolve(test_url)
        print("\nFinal URL:", result)
        print("Headers:", hdrs)
    except Exception as e:
        print("Error:", e)