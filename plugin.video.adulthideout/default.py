# -*- coding: utf-8 -*-
# Importieren der benötigten Module und Funktionen
import os
import re
import json
import six
import urllib
import sys
from kodi_six import xbmc, xbmcvfs, xbmcaddon, xbmcplugin, xbmcgui
from six.moves import urllib_request, urllib_parse, http_cookiejar
from resources.functions import *
from resources.search import search_handler

# Liste der Websites
websites = [
    {"name": "efukt", "url": "http://efukt.com/"},
    {"name": "website2", "url": "http://website2.com/"},
    {"name": "website3", "url": "http://website3.com/"},
    {"name": "website4", "url": "http://website4.com/"}
]

# Variablen für die Websites erstellen
for site in websites:
    exec(f"{site['name']} = '{site['url']}'")

# menulist-Funktion: Liest das Hauptmenü und gibt die gefundenen Übereinstimmungen zurück
def menulist():
    try:
        with open(homemenu, 'r') as mainmenu:
            content = mainmenu.read()
            match = re.findall('#.+,(.+?)\n(.+?)\n', content)
            return match
    except FileNotFoundError:
        print("Error: File not found.")
    except Exception as e:
        print("An unknown error occurred: ", e)

# main-Funktion: Hauptverzeichnis und Startseite
def main():
    add_dir('Efukt [COLOR yellow] Videos[/COLOR]', efukt, 2, logos + 'efukt.png', fanart)
    setView('videos', 'DEFAULT')

# Verarbeitet die angegebene URL, um Inhalte von der gewählten Website anzuzeigen und verfügbar zu machen
def start(url):
    setView('Videos', 'DEFAULT')
    if 'efukt' in url:
        content = make_request(url)
        add_dir('[COLOR lightgreen]efukt.com	 [COLOR red]Search[/COLOR]', efukt, 1, logos + 'efukt.png', fanart)
        match = re.compile('<a  href="([^"]*)" title="([^"]*)" class="thumb" style="background-image: url\(\'([^"]*)\'\);"></a>').findall(content)
        for url, name, thumb in match:
            name = name.replace('&amp;', '&').replace('&quot;', '"').replace('&#039;', '\'')
            add_link(name, url , 4, thumb, fanart)
        try:
            match = re.compile('class="anchored_item active ">.+?</a><a href="(.+?)"').findall(content)
            add_dir('[COLOR blue]Next  Page  >>>>[/COLOR]', efukt + match[0], 2, logos + 'efukt.png', fanart)
        except:
            pass

# Löst die Medien-URL auf, um das Video abzuspielen
def resolve_url(url):
    content = make_request(url)
    if 'efukt' in url:    
        media_url = re.compile('<source src="(.+?)" type="video/mp4">').findall(content)[0]    
        media_url = media_url.replace('amp;','')
    else:
        media_url = url
    item = xbmcgui.ListItem(name, path = media_url)
    item.setMimeType('video/mp4')
    xbmcplugin.setResolvedUrl(int(sys.argv[1]), True, item)
    return

# Verarbeitet die Parameter aus der URL und gibt sie als ein Dictionary zurück
def get_params():
    param = []
    paramstring = sys.argv[2]
    if len(paramstring)>= 2:
        params = sys.argv[2]
        cleanedparams = params.replace('?', '')
        if (params[len(params)-1] == '/'):
            params = params[0:len(params)-2]
        pairsofparams = cleanedparams.split('&')
        param = {}
        for i in range(len(pairsofparams)):
            splitparams = {}
            splitparams = pairsofparams[i].split('=')
            if (len(splitparams)) == 2:
                param[splitparams[0]] = splitparams[1]
    return param

# Führt den Hauptcode nur aus, wenn das Skript direkt aufgerufen wird
if __name__ == '__main__':
    params = get_params()
    url = None
    name = None
    mode = None
    iconimage = None

 # Parameterverarbeitung
try:
	url = urllib_parse.unquote_plus(params["url"])
except:
	pass
try:
	name = urllib_parse.unquote_plus(params["name"])
except:
	pass
try:
	mode = int(params["mode"])
except:
	pass
try:
	iconimage = urllib_parse.unquote_plus(params["iconimage"])
except:
	pass

print ("Mode: " + str(mode))
print ("URL: " + str(url))
print ("Name: " + str(name))
print ("iconimage: " + str(iconimage))

# Hauptverarbeitung
if mode == None or url == None or len(url) < 1:
    main()

elif mode == 1:
    search_handler(websites, name, url, start)

elif mode == 2:
    xbmc.log("mode==2, starturl=%s" % url, xbmc.LOGERROR)
    start(url)

elif mode == 3:
    media_list(url)

elif mode == 4:
    resolve_url(url)

elif mode == 70:
    item = xbmcgui.ListItem(name, path=url)
    item.setMimeType('video/mp4')
    xbmcplugin.setResolvedUrl(int(sys.argv[1]), True, item)

xbmcplugin.endOfDirectory(int(sys.argv[1]))
