import re
import xbmc
import xbmcgui
import xbmcplugin
import xbmcaddon
import xbmcvfs
import urllib.parse as urllib_parse
import json
import ssl
import time
from six.moves import urllib_request, http_cookiejar
import logging
import html
import sys

# Einbindung der Funktionen und Klasse aus utils.py und adultsite.py

USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36'
base_hdrs = {'User-Agent': USER_AGENT, 'Accept': '*/*', 'Accept-Language': 'de-DE,de;q=0.9'}
addon = xbmcaddon.Addon()
addon_path = xbmcvfs.translatePath(addon.getAddonInfo('path'))

# Funktionen aus utils.py
def get_html(url, referer='', headers=None, data=None, ignore_certificate_errors=False, retries=3):
    if headers is None:
        headers = base_hdrs

    req = urllib_request.Request(url, data=data, headers=headers)
    if referer:
        req.add_header('Referer', referer)

    for attempt in range(retries):
        try:
            if ignore_certificate_errors:
                ctx = ssl.create_default_context()
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE
                response = urllib_request.urlopen(req, timeout=30, context=ctx)
            else:
                response = urllib_request.urlopen(req, timeout=30)
            result = response.read()
            response.close()
            return result.decode('utf-8')
        except urllib_request.URLError as e:
            xbmc.log(f'Error opening URL "{url}". Attempt {attempt + 1}', level=xbmc.LOGERROR)
            if hasattr(e, 'code'):
                xbmc.log(f'Error code: {e.code}.', level=xbmc.LOGERROR)
            elif hasattr(e, 'reason'):
                xbmc.log(f'Reason: {e.reason}', level=xbmc.LOGERROR)
            if attempt < retries - 1:
                xbmc.sleep(5000)  # Warte 5 Sekunden vor erneutem Versuch
        except Exception as e:
            xbmc.log(f'Error: {e}', level=xbmc.LOGERROR)
            return None
    return None

def notify(header, msg, duration=5000, icon=''):
    xbmcgui.Dialog().notification(header, msg, icon, duration, False)

# Klasse AdultSite aus adultsite.py
class AdultSite:
    def __init__(self, name, title, url, image=None, about=None):
        self.name = name
        self.title = title
        self.url = url
        self.image = image
        self.about = about

    def add_dir(self, name, url, mode, iconimage, fanart, description=''):
        u = f"{sys.argv[0]}?url={urllib_parse.quote_plus(url)}&mode={mode}"
        liz = xbmcgui.ListItem(name)
        liz.setArt({'icon': iconimage, 'fanart': fanart})
        liz.setInfo(type="Video", infoLabels={"Title": name, "Plot": description})
        xbmcplugin.addDirectoryItem(handle=int(sys.argv[1]), url=u, listitem=liz, isFolder=True)

    def add_link(self, name, url, mode, iconimage, fanart, description=''):
        u = f"{sys.argv[0]}?url={urllib_parse.quote_plus(url)}&mode={mode}"
        liz = xbmcgui.ListItem(name)
        liz.setArt({'icon': iconimage, 'fanart': fanart})
        liz.setInfo(type="Video", infoLabels={"Title": name, "Plot": description})
        xbmcplugin.addDirectoryItem(handle=int(sys.argv[1]), url=u, listitem=liz, isFolder=False)

# Instanziiere die AdultSite-Klasse für uflash
site = AdultSite('uflash', '[COLOR hotpink]Uflash[/COLOR]', 'http://www.uflash.tv/', 'http://www.uflash.tv/templates/frontend/default/images/logo.png')

# Hauptfunktion für die Verarbeitung von uflash Inhalten
def process_uflash_content(url):
    try:
        content = get_html(url)
        if not content:
            raise Exception("Failed to retrieve content")
            
        match = re.compile('<a href="([^"]*)".+?<img src="([^"]*)" alt="([^"]*)"', re.DOTALL).findall(content)
        for url, thumb, name in match:
            name = html.unescape(name)
            site.add_link(name, f"http://www.uflash.tv{url}", 4, thumb, '')
    except Exception as e:
        logging.error(f"Failed to process Uflash content: {e}")
        notify("Error", "Failed to process Uflash content", xbmcgui.NOTIFICATION_ERROR)

# Funktion zum Abspielen von uflash Videos
def play_uflash_video(url):
    try:
        headers = {
            'User-Agent': 'iPad', 
            'Accept-Encoding': 'deflate', 
            'X-Requested-With': 'XMLHttpRequest', 
            'Accept': 'application/json, text/javascript, */*; q=0.01'
        }
        video_id = url.split('/')[4]
        data = {'vid': f'{video_id}'}
        video_info_url = "http://www.uflash.tv/ajax/getvideo"

        content = get_html(video_info_url, headers=headers, data=urllib_parse.urlencode(data).encode('utf-8'))
        if not content:
            raise Exception("Failed to retrieve video information")
            
        jdata = json.loads(content)
        videourl = jdata["video_src"]

        play_video(videourl, url)
    except Exception as e:
        logging.error(f"Failed to play Uflash video: {e}")
        notify("Error", "Failed to play Uflash video", xbmcgui.NOTIFICATION_ERROR)

# Funktion zum Abspielen von Videos
def play_video(video_url, referer):
    try:
        headers = {
            'User-Agent': USER_AGENT,
            'Accept': '*/*',
            'Accept-Language': 'de-DE,de;q=0.9',
            'Referer': referer,
            'Connection': 'keep-alive'
        }
        
        list_item = xbmcgui.ListItem(path=video_url)
        list_item.setProperty('IsPlayable', 'true')
        list_item.setMimeType('video/mp4')
        list_item.setContentLookup(False)
        list_item.setPath(f"{video_url}|{urllib_parse.urlencode(headers)}")
        
        xbmc.Player().play(video_url, list_item)
    except Exception as e:
        logging.error(f"Failed to play video: {e}")
        notify("Error", "Failed to play video", xbmcgui.NOTIFICATION_ERROR)
