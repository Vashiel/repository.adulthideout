import re
import logging
import cloudscraper
import json
import base64
import random
from urllib.parse import urljoin, urlparse

logger = logging.getLogger(__name__)

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; rv:128.0) Gecko/20100101 Firefox/128.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3 Safari/605.1.15",
]

def _get_random_ua():
    return random.choice(USER_AGENTS)

def _voe_decode(ct, luts):
    try:
        lut_items = eval(luts)
        lut = [''.join([('\\' + x) if x in '.*+?^${}()|[]\\' else x for x in i]) for i in lut_items]
    except:
        logger.warning("[voesx_resolver] Fallback during LUT parsing.")
        try:
            lut = [''.join([('\\' + x) if x in '.*+?^${}()|[]\\' else x for x in i]) for i in luts[2:-2].split("','")]
        except:
            logger.error("[voesx_resolver] Could not parse LUT: %s", luts)
            return {}

    txt = ''
    for i in ct:
        x = ord(i)
        if 64 < x < 91:
            x = (x - 52) % 26 + 65
        elif 96 < x < 123:
            x = (x - 84) % 26 + 97
        txt += chr(x)

    for i in lut:
        try:
            txt = re.sub(i, '', txt)
        except Exception as e:
            logger.error("[voesx_resolver] Error during re.sub with LUT part '%s': %s", i, e)

    try:
        missing_padding = len(txt) % 4
        if missing_padding:
            txt += '=' * (4 - missing_padding)
        ct = base64.b64decode(txt).decode('utf-8')
    except Exception as e:
        logger.error("[voesx_resolver] _voe_decode: First b64decode step failed: %s", e)
        return {}

    txt = ''.join([chr(ord(i) - 3) for i in ct])

    try:
        missing_padding = len(txt) % 4
        if missing_padding:
            txt_reversed = txt[::-1]
            txt_reversed += '=' * (4 - missing_padding)
        else:
            txt_reversed = txt[::-1]

        txt_decoded = base64.b64decode(txt_reversed).decode('utf-8')
    except Exception as e:
        logger.error("[voesx_resolver] _voe_decode: Second b64decode step failed: %s", e)
        return {}

    try:
        return json.loads(txt_decoded)
    except Exception as e:
        logger.error("[voesx_resolver] JSON parsing of decoded string failed: %s", e)
        logger.error("Decoded string (start): %s", txt_decoded[:200])
        return {}

def resolve(url, referer=None, headers=None):
    logger.info("[AdultHideout][resolver:voesx] Input: %s", url)

    scraper = cloudscraper.create_scraper(browser={"browser": "chrome", "platform": "windows", "mobile": False})

    base_headers = {
        "User-Agent": _get_random_ua(),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9,de;q=0.8",
        "Referer": referer or url,
    }
    if headers:
        base_headers.update(headers)

    try:
        web_url = url
        html = scraper.get(web_url, headers=base_headers).text

        redirect_url = web_url
        if 'const currentUrl' in html:
            r = re.search(r'''window\.location\.href\s*=\s*'([^']+)''', html)
            if r:
                redirect_url = r.group(1)
                logger.info("[voesx_resolver] JS redirect found, following to: %s", redirect_url)
                html = scraper.get(redirect_url, headers=base_headers).text

        r = re.search(r"['\"]hls['\"]\s*:\s*['\"]([^'\"]+)['\"]", html)
        if r:
            stream_url = r.group(1)
            logger.info("[voesx_resolver] HLS URL found directly in HTML: %s", stream_url)
            play_headers = {"User-Agent": base_headers["User-Agent"], "Referer": web_url}
            return stream_url, play_headers

        r_decode = re.search(r'sources\s*=\s*(\{.*?\})\s*;', html, re.DOTALL)
        if r_decode:
            logger.info("[voesx_resolver] 'sources' object found in HTML.")
            try:
                sources_data = json.loads(r_decode.group(1))
                if 'hls' in sources_data:
                    stream_url = sources_data['hls']
                    logger.info("[voesx_resolver] HLS URL extracted from 'sources' object: %s", stream_url)
                    play_headers = {"User-Agent": base_headers["User-Agent"], "Referer": web_url}
                    return stream_url, play_headers
            except Exception as e:
                logger.warning("[voesx_resolver] Error parsing 'sources' object: %s", e)

        logger.info("[voesx_resolver] Trying older decoding method...")
        r_old = re.search(r'json">\["([^"]+)"]</script>\s*<script\s*src="([^"]+)', html)
        if r_old:
            logger.info("[voesx_resolver] Old JSON/script pattern found.")
            json_data = r_old.group(1)
            script_url_path = r_old.group(2)
            script_url = urljoin(redirect_url, script_url_path)

            script_headers = base_headers.copy()
            script_headers["Referer"] = redirect_url
            html2 = scraper.get(script_url, headers=script_headers).text

            repl_match = re.search(r"(\[(?:'\\?\W{1,2}'[,\]]){1,15})", html2)
            if repl_match:
                logger.info("[voesx_resolver] Decryption LUT found.")
                luts = repl_match.group(1)

                decoded_data = _voe_decode(json_data, luts)

                sources = []
                if 'hls' in decoded_data and decoded_data['hls']:
                    sources.append((10000, decoded_data['hls']))

                for key in ['file', 'source', 'direct_access_url']:
                    if key in decoded_data and decoded_data[key]:
                        try:
                            label_match = re.search(r'(\d{3,4})p', decoded_data[key])
                            label_num = int(label_match.group(1)) if label_match else 0
                            sources.append((label_num, decoded_data[key]))
                        except:
                            sources.append((0, decoded_data[key]))

                if sources:
                    sources.sort(key=lambda x: x[0], reverse=True)
                    stream_url = sources[0][1]
                    play_headers = {"User-Agent": base_headers["User-Agent"], "Referer": web_url}
                    logger.info("[voesx_resolver] Stream URL (decoded) found: %s", stream_url)
                    return stream_url, play_headers
            else:
                logger.warning("[voesx_resolver] Could not find decryption LUT in script: %s", script_url)

        mp4_match = re.search(r'''['"]mp4['"]\s*:\s*['"](?P<url>[^"']+)['"]''', html)
        if mp4_match:
            stream_url = mp4_match.group("url")
            play_headers = {"User-Agent": base_headers["User-Agent"], "Referer": web_url}
            logger.info("[voesx_resolver] Stream URL (Fallback MP4) found: %s", stream_url)
            return stream_url, play_headers

        logger.error("[voesx_resolver] Could not find any stream URL.")
        raise Exception('Voe.sx: No video found')

    except Exception as e:
        logger.error("[voesx_resolver] Critical error: %s", e, exc_info=True)
        raise Exception("Voe.sx error: {}".format(e))

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    test_url = "https://voe.sx/e/di5hqowbbive"
    try:
        result, hdrs = resolve(test_url, referer="https://www.freeomovie.to/cougar-sightings-6/")
        print("Final URL:", result)
        print("Headers:", hdrs)
    except Exception as e:
        print("Error:", e)