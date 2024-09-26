import re
import xbmc
from ..functions import add_dir, add_link, make_request, fanart, logos
import xbmcgui
import xbmcplugin
import xbmcaddon
import urllib.parse as urllib_parse
from urllib.parse import urlparse
import html
import sys
from urllib.parse import urljoin
import subprocess
import xbmcvfs
import urllib.request
import urllib.error
import six


addon = xbmcaddon.Addon(id='plugin.video.adulthideout')

def process_luxuretv_content(url, mode=None):
    if "search" not in url and "newest" not in url:
        url = url
    if url == 'https://en.luxuretv.com/channels/':
        process_luxuretv_categories(url)
    else:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
            'Accept': '*/*',
            'Accept-Language': 'de-DE,de;q=0.9',
            'Referer': 'https://en.luxuretv.com/',
            'sec-ch-ua': '"Not/A)Brand";v="8", "Chromium";v="126", "Google Chrome";v="126"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'document',
            'sec-fetch-mode': 'navigate',
            'sec-fetch-site': 'none',
            'sec-fetch-user': '?1',
            'upgrade-insecure-requests': '1',
            'cookie': '__cf_bm=PEXQ1NXrz3PvIYJAWe90EU8faIvjhVjWxSIWUgdSbCY-1721992795-1.0.1.1-tF1Y5Oq0NZUWujQ.yV.6G4VJ_SAHLjh_Nnalk3vIHw9wZfMHtg1mTt6_j0vigCVnWLtRXpjmGz8tZ1deQmo3ng'
        }
        content = make_request_with_headers(url, headers=headers)
        add_dir(f'Search luxuretv', 'luxuretv', 5, logos + 'luxuretv.png', fanart)
        add_dir("Categories", "https://en.luxuretv.com/channels/", 2, logos + 'luxuretube.png', fanart)
        match = re.compile('a href="([^"]*)" title="([^"]*)"><img class="img lazyload" data-src="([^"]*)"', re.DOTALL).findall(content)
        # Get the base URL part from the input URL
        parsed_url = urlparse(url)
        base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
        for url, name, thumb in match:
            full_url = urljoin(base_url, url)  # Properly format the URL
            add_link(name, full_url, 4, thumb, fanart)
        try:
            match = re.compile('<a href=\'(.+?)\'>Next').findall(content)
            next_page_url = urljoin(base_url, match[0])  # Properly format the URL
            add_dir('[COLOR blue]Next  Page  >>>>[/COLOR]', next_page_url, 2, logos + 'luxuretv.png', fanart)
        except:
            pass

def process_luxuretv_categories(url):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
        'Accept': '*/*',
        'Accept-Language': 'de-DE,de;q=0.9',
        'Referer': 'https://en.luxuretv.com/',
        'sec-ch-ua': '"Not/A)Brand";v="8", "Chromium";v="126", "Google Chrome";v="126"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Windows"',
        'sec-fetch-dest': 'document',
        'sec-fetch-mode': 'navigate',
        'sec-fetch-site': 'none',
        'sec-fetch-user': '?1',
        'upgrade-insecure-requests': '1',
        'cookie': '__cf_bm=PEXQ1NXrz3PvIYJAWe90EU8faIvjhVjWxSIWUgdSbCY-1721992795-1.0.1.1-tF1Y5Oq0NZUWujQ.yV.6G4VJ_SAHLjh_Nnalk3vIHw9wZfMHtg1mTt6_j0vigCVnWLtRXpjmGz8tZ1deQmo3ng'
    }
    content = make_request_with_headers(url, headers=headers)
    parsed_url = urlparse(url)
    base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
    categories = re.compile('<a href="([^"]*)">.+?src="([^"]*)" alt="([^"]*)"', re.DOTALL).findall(content)
    for video_url, thumb, name in categories:
        full_url = urljoin(base_url, video_url)  # Properly format the URL
        add_dir(name, full_url, 2, thumb, fanart)

def play_luxuretv_video(url):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36',
        'Accept': '*/*',
        'Accept-Language': 'de-DE,de;q=0.9',
        'Referer': 'https://en.luxuretv.com/',
        'sec-ch-ua': '"Not)A;Brand";v="99", "Google Chrome";v="127", "Chromium";v="127"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Windows"',
        'sec-fetch-dest': 'video',
        'sec-fetch-mode': 'no-cors',
        'sec-fetch-site': 'same-site',
        'Range': 'bytes=0-'
    }

    content = make_request_with_headers(url, headers=headers)
    media_url = re.compile('source src="(.+?)" type=').findall(content)[0]
    return media_url


def make_request_with_headers(url, headers, max_retry_attempts=3, retry_wait_time=5000):
    req = urllib.request.Request(url, headers=headers)

    retries = 0

    while retries < max_retry_attempts:
        try:
            response = urllib.request.urlopen(req, timeout=60)
            link = response.read().decode('utf-8') if six.PY3 else response.read()
            response.close()
            return link
        except urllib.error.URLError as e:
            xbmc.log('Fehler beim Öffnen der URL "%s".' % url, level=xbmc.LOGERROR)
            if hasattr(e, 'code'):
                xbmc.log('Fehlercode: %s.' % e.code, level=xbmc.LOGERROR)
            elif hasattr(e, 'reason'):
                xbmc.log('Fehler beim Verbindungsaufbau zum Server.', level=xbmc.LOGERROR)
                xbmc.log('Grund: %s' % e.reason, level=xbmc.LOGERROR)

            retries += 1
            xbmc.sleep(retry_wait_time)

    xbmc.log('Alle Wiederholungsversuche fehlgeschlagen.', level=xbmc.LOGERROR)
    return ""
