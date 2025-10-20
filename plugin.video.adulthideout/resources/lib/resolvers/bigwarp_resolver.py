# -*- coding: utf-8 -*-
import re
import logging
import cloudscraper
import random
from urllib.parse import urljoin, urlparse
import html

logger = logging.getLogger(__name__)

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; rv:128.0) Gecko/20100101 Firefox/128.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3 Safari/605.1.15",
]

def _get_random_ua():
    return random.choice(USER_AGENTS)

def resolve(url, referer=None, headers=None):
    logger.info("[AdultHideout][resolver:bigwarp] Input: %s", url)

    try:
        pattern = r'(?://|\.)((?:bigwarp|bgwp)\.(?:io|cc|art|pro))/(?:e/|embed-)?([0-9a-zA-Z=]+)'
        match = re.search(pattern, url)
        if not match:
            raise Exception("Bigwarp: Could not extract host/media_id from URL.")
        
        host, media_id = match.groups()
        host_with_scheme = "https://" + host
        
        web_url = url 
        ref = urljoin(host_with_scheme, '/') 
        dl_url = urljoin(host_with_scheme, '/dl')
        
        post_data = {
            'op': 'embed',
            'file_code': media_id,
            'auto': '0'
        }
        
        request_headers = {
            "User-Agent": _get_random_ua(),
            "Referer": ref,
            "Origin": host_with_scheme 
        }
        if headers:
             request_headers.update(headers)

        scraper = cloudscraper.create_scraper(browser={"browser": "chrome", "platform": "windows", "mobile": False})
        
        logger.info("[Bigwarp] Sending POST to %s", dl_url)
        response = scraper.post(dl_url, data=post_data, headers=request_headers)
        
        if response.status_code != 200:
             logger.error("[Bigwarp] POST request failed with status %d", response.status_code)
             raise Exception("Bigwarp: POST request failed with status {}.".format(response.status_code))
             
        html_content = response.text

        s = re.search(r'''sources:\s*\[{\s*file\s*:\s*['"]([^'"]+)''', html_content, re.IGNORECASE)
        if s:
            stream_url = s.group(1).strip()
            
            play_headers = {
                "User-Agent": request_headers["User-Agent"], 
                "Referer": web_url 
            }
            
            # Unescape potential HTML entities
            stream_url = html.unescape(stream_url)

            logger.info("[Bigwarp] Final stream URL: %s", stream_url)
            return stream_url, play_headers
        else:
            logger.warning("[Bigwarp] Could not find 'sources' pattern in POST response.")
            raise Exception("Bigwarp: Stream URL not found after POST.")

    except Exception as e:
         logger.error("[Bigwarp] Error: %s", e, exc_info=True)
         raise Exception("Bigwarp Error: {}".format(e))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    test_url = "https://bigwarp.io/embed-yw7yd0we2xdu.html" 
    try:
        result, hdrs = resolve(test_url, referer="https://www.freeomovie.to/cougar-sightings-6/")
        print("Final URL:", result)
        print("Headers:", hdrs)
    except Exception as e:
        print("Error:", e)