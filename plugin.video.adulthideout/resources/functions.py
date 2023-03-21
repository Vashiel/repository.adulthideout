import os
import re
import json
import six
import urllib
import sys
from kodi_six import xbmc, xbmcvfs, xbmcaddon, xbmcplugin, xbmcgui
from six.moves import urllib_request, urllib_parse, http_cookiejar
from resources.functions import *


addon = xbmcaddon.Addon(id='plugin.video.adulthideout')
home = addon.getAddonInfo('path')
if home[-1] == ';':
    home = home[0:-1]
cacheDir = os.path.join(home, 'cache')
cookiePath = os.path.join(home, 'cookies.lwp')
fanart = os.path.join(home, 'resources/logos/fanart.jpg')
icon = os.path.join(home, 'resources/logos/icon.png')
logos = os.path.join(home, 'resources/logos\\')  # subfolder for logos
homemenu = os.path.join(home, 'resources', 'playlists')
urlopen = urllib_request.urlopen
cookiejar = http_cookiejar.LWPCookieJar()
cookie_handler = urllib_request.HTTPCookieProcessor(cookiejar)
urllib_request.build_opener(cookie_handler)


# Setzen der Log-Level Konstanten
# INFO wird für Python 3 verwendet und NOTICE für Python 2
LOG_LEVEL = xbmc.LOGINFO if six.PY3 else xbmc.LOGNOTICE

# Setzen der Standard-Opener und Cookie-Jar
COOKIE_JAR = http_cookiejar.LWPCookieJar()
COOKIE_HANDLER = urllib_request.HTTPCookieProcessor(COOKIE_JAR)
urllib_request.install_opener(urllib_request.build_opener(COOKIE_HANDLER))

# Maximale Anzahl von Versuchen, um eine fehlgeschlagene Anfrage zu wiederholen
MAX_RETRY_ATTEMPTS = int(addon.getSetting('max_retry_attempts'))


def add_dir(name, url, mode, iconimage, fanart):
    u = sys.argv[0] + '?url=' + urllib_parse.quote_plus(url) + '&mode=' + str(mode) +\
        '&name=' + urllib_parse.quote_plus(name) + '&iconimage=' + str(iconimage)
    xbmc.log("Adding directory: Name: {}, URL: {}, Mode: {}, Icon: {}, Fanart: {}".format(name, url, mode, iconimage, fanart), level=xbmc.LOGINFO)
    ok = True
    liz = xbmcgui.ListItem(name)
    liz.setArt({ 'thumb': iconimage, 'icon': icon, 'fanart': fanart})
    ok = xbmcplugin.addDirectoryItem(handle=int(sys.argv[1]), url=u,
                                    listitem=liz, isFolder=True)
    return ok

def add_link(name, url, mode, iconimage, fanart):
    quoted_url = urllib_parse.quote(url)
    u = sys.argv[0] + '?url=' + quoted_url + '&mode=' + str(mode) \
        + '&name=' + str(name) + "&iconimage=" + str(iconimage)
    xbmc.log("Adding link to directory: Name: {}, URL: {}, Mode: {}, Icon: {}, Fanart: {}".format(name, url, mode, iconimage, fanart), level=xbmc.LOGINFO)
    ok = True
    liz = xbmcgui.ListItem(name)
    liz.setArt({'thumb': iconimage, 'icon': icon, 'fanart': iconimage})
    liz.setInfo(type="Video", infoLabels={"Title": name})
    try:
        liz.setContentLookup(False)
    except:
        pass
    liz.setProperty('IsPlayable', 'true')
    ok = xbmcplugin.addDirectoryItem(handle=int(sys.argv[1]), url=u,
                                    listitem=liz, isFolder=False)
def resolve_url(url, websites):
    xbmc.log("Input URL for resolve_url: {}".format(url), level=xbmc.LOGDEBUG)
    for website in websites:
        xbmc.log("Checking website URL: {}".format(website["url"]), level=xbmc.LOGDEBUG)
        if website["url"] in url:
            xbmc.log("Matching website found: {}".format(website["name"]), level=xbmc.LOGDEBUG)
            media_url = website['play_function'](url)
            break
        else:
            xbmc.log("No match found: website URL not in input URL", level=xbmc.LOGDEBUG)
    else:
        media_url = url
    return media_url

def setView(content, viewType):
    # Setzt den Kodi View Type für das aktuelle Verzeichnis
    if content:
        xbmcplugin.setContent(int(sys.argv[1]), content)
    if addon.getSetting('auto-view') == 'true':
        xbmc.executebuiltin('Container.SetViewMode(%s)' % addon.getSetting(viewType))
                                    
def make_request(url, max_retry_attempts=3, retry_wait_time=5000):
    # Setzen von Standard-Headern und Erstellen des Request-Objekts
    req = urllib.request.Request(url)
    req.add_header('User-Agent', 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.11 (KHTML, like Gecko) Chrome/23.0.1271.64 Safari/537.11')
    
    retries = 0
    
    while retries < max_retry_attempts:
        try:
            # Öffnen der URL und Lesen der Antwort
            response = urllib.request.urlopen(req, timeout=60)
            link = response.read().decode('utf-8') if six.PY3 else response.read()
            response.close()
            return link
        except urllib.error.URLError as e:
            # Loggen der Fehlermeldung
            xbmc.log('Fehler beim Öffnen der URL "%s".' % url, level=xbmc.LOGERROR)
            if hasattr(e, 'code'):
                xbmc.log('Fehlercode: %s.' % e.code, level=xbmc.LOGERROR)
            elif hasattr(e, 'reason'):
                xbmc.log('Fehler beim Verbindungsaufbau zum Server.', level=xbmc.LOGERROR)
                xbmc.log('Grund: %s' % e.reason, level=xbmc.LOGERROR)
            
            # Erhöhen des Zählers und Warten vor dem nächsten Versuch
            retries += 1
            xbmc.sleep(retry_wait_time)
            
    # Wenn alle Wiederholungsversuche fehlschlagen, Rückgabe eines leeren Strings
    xbmc.log('Alle Wiederholungsversuche fehlgeschlagen.', level=xbmc.LOGERROR)
    return ""

def get_search_query():
    keyb = xbmc.Keyboard('', '[COLOR yellow]Enter search text[/COLOR]')
    keyb.doModal()
    if keyb.isConfirmed():
        return urllib_parse.quote_plus(keyb.getText())
    return None
