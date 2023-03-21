import os
import re
import json
import six
import urllib
import sys
import importlib
from kodi_six import xbmc, xbmcvfs, xbmcaddon, xbmcplugin, xbmcgui
from six.moves import urllib_request, urllib_parse, http_cookiejar
from resources.search import *
from resources.websites.websites import websites
from resources.functions import *

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

def main():
    for site in websites:
        name = site['name']
        url = site['url']
        add_dir(f'{name.capitalize()} [COLOR yellow] Videos[/COLOR]', url, 2, logos + f'{name}.png', fanart)
    setView('videos', 'DEFAULT')

def process_website(url):
    for site in websites:
        if site["url"] == url:
            return site["function"]
    return None

def search_website(website_name):
    site = next((site for site in websites if site["name"] == website_name or site["url"].find(website_name) != -1), None)
    if site is None:
        return

    last_query = get_last_query()
    keyb = xbmc.Keyboard(str(last_query), "[COLOR yellow]Enter search text[/COLOR]")
    all_queries = get_all_queries()
    options = ["[COLOR yellow]New Search[/COLOR]"] + all_queries + ["[COLOR yellow]Clear Search History[/COLOR]"]
    valid_options = [option for option in options if isinstance(option, str)]
    selected_index = xbmcgui.Dialog().select("Select a Query", valid_options)

    if selected_index >= 0 and selected_index == 0:
        keyb.doModal()
        if keyb.isConfirmed():
            search_word = urllib.parse.quote_plus(keyb.getText())
            if search_word not in all_queries:
                save_query(search_word)

            if website_name in site["url"]:
                search_url = site["search_url"] + search_word
            else:
                search_url = site["search_url"].format(search_word)

            site["function"](search_url, 1)
    elif selected_index >= 0 and selected_index > 0 and selected_index < len(valid_options) - 1:
        search_word = urllib.parse.quote_plus(valid_options[selected_index])
        if website_name in site["url"]:
            search_url = site["search_url"] + search_word
        else:
            search_url = site["search_url"].format(search_word)

        site["function"](search_url, 1)
    elif selected_index >= 0 and selected_index == len(valid_options) - 1:
        clear_search_history()

def start(url):
    for site in websites:
        if site["url"] == url:
            site["function"](url)
            break

def play_video(url):
    media_url = resolve_url(url, websites)
    item = xbmcgui.ListItem(name, path=media_url)
    item.setMimeType('video/mp4')
    xbmcplugin.setResolvedUrl(int(sys.argv[1]), True, item)

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

if __name__ == '__main__':
    params = get_params()
    url = None
    name = None
    mode = None
    iconimage = None

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

    if mode == None or url == None or len(url) < 1:
        main()

    elif mode == 1:
        search_website(name)

    elif mode == 2:
        start(url)

    elif mode == 3:
        media_list(url)

    elif mode == 4:
        play_video(url)
        
    elif mode == 5:
        search_website(url)

    elif mode == 70:
        item = xbmcgui.ListItem(name, path=url)
        item.setMimeType('video/mp4')
        xbmcplugin.setResolvedUrl(int(sys.argv[1]), True, item)

    xbmcplugin.endOfDirectory(int(sys.argv[1]))
