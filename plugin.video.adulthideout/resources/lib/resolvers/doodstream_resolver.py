# -*- coding: utf-8 -*-
import re
import time
import random
import logging
import cloudscraper
import string 
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; rv:128.0) Gecko/20100101 Firefox/128.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3 Safari/605.1.15",
]

def _get_random_ua():
    return random.choice(USER_AGENTS)

def _dood_decode(data):
    t = string.ascii_letters + string.digits
    return data + ''.join([random.choice(t) for _ in range(10)])

def resolve(url, referer=None, headers=None):

    logger.info("[AdultHideout][resolver:doodstream] Eingang: %s", url)

    scraper = cloudscraper.create_scraper(browser={"browser": "chrome", "platform": "windows", "mobile": False})

    base_headers = {
        "User-Agent": _get_random_ua(),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9,de;q=0.8",
        "Referer": referer or "https://doodstream.com/",
        "Origin": "https://doodstream.com",
    }
    if headers:
        base_headers.update(headers)

    try:
        response = scraper.get(url, headers=base_headers)
        
        if response.status_code != 200:
            parsed_url = urlparse(url)
            if parsed_url.netloc not in ['doodstream.com', 'dsvplay.com']:
                 media_id_match = re.search(r'/(?:e|d)/([0-9a-zA-Z]+)', url)
                 if media_id_match:
                     media_id = media_id_match.group(1)
                     host = 'dsvplay.com' 
                     url = f"https://{host}/e/{media_id}"
                     logger.info(f"[Doodstream] Versuche Fallback-Host: {url}")
                     response = scraper.get(url, headers=base_headers)

        if response.status_code != 200:
             raise Exception(f"HTTP {response.status_code} beim Abrufen der Seite {url}")

        html = response.text
        host = urlparse(response.url).netloc 

    except Exception as e:
        logger.error(f"[Doodstream] Fehler bei Schritt 1 (Seite abrufen): {e}")
        raise

    match = re.search(r'''dsplayer\.hotkeys[^']+'([^']+).+?function\s*makePlay.+?return[^?]+([^"]+)''', html, re.DOTALL)
    
    if not match:
        iframe_match = re.search(r'<iframe\s*src="([^"]+)', html)
        if iframe_match:
            iframe_url_path = iframe_match.group(1)
            if iframe_url_path.startswith('//'):
                iframe_url = f"https_:{iframe_url_path}"
            elif iframe_url_path.startswith('/'):
                 iframe_url = f"https://{host}{iframe_url_path}"
            else:
                 iframe_url = iframe_url_path

            logger.info(f"[Doodstream] Kein Match, folge Iframe: {iframe_url}")
            base_headers["Referer"] = url 
            
            try:
                response = scraper.get(iframe_url, headers=base_headers)
                html = response.text
                match = re.search(r'''dsplayer\.hotkeys[^']+'([^']+).+?function\s*makePlay.+?return[^?]+([^"]+)''', html, re.DOTALL)
            except Exception as e:
                logger.error(f"[Doodstream] Fehler beim Abrufen des Iframes: {e}")
                raise Exception("Fehler beim Laden des Doodstream-Iframes.")
        
    if not match:
        logger.error(f"[Doodstream] HTML-Inhalt (Anfang): {html[:1000]}")
        raise Exception("Kein 'dsplayer.hotkeys' Block gefunden. Resolver-Logik ist veraltet.")
    
    data_url_path = match.group(1)
    token = match.group(2)
    
    logger.info("[Doodstream] 'dsplayer.hotkeys' Block gefunden.")

    data_url_headers = base_headers.copy()
    data_url_headers["Referer"] = url 
    data_url = f"https://{host}{data_url_path}"
    
    try:
        data_response = scraper.get(data_url, headers=data_url_headers)
        if data_response.status_code != 200:
            raise Exception(f"HTTP {data_response.status_code} beim Abrufen der Data-URL")
        encoded_stream_part = data_response.text
    except Exception as e:
        logger.error(f"[Doodstream] Fehler bei Schritt 3 (Data-URL abrufen): {e}")
        raise

    decoded_stream_part = _dood_decode(encoded_stream_part)
    final_url = f"{decoded_stream_part}{token}{str(int(time.time() * 1000))}"
    
    play_headers = {
        "User-Agent": base_headers["User-Agent"],
        "Referer": url, 
    }

    logger.info("[AdultHideout][resolver:doodstream] Finale URL: %s", final_url)
    return final_url, play_headers


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    test_url = "https://doodstream.com/e/h4httnw7lajw"
    try:
        result, hdrs = resolve(test_url)
        print("Finale URL:", result)
        print("Headers:", hdrs)
    except Exception as e:
        print("Fehler:", e)