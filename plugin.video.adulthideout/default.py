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
import urllib.parse
import logging


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


def process_website(url):
    parsed_input_url = urlparse(url)
    input_domain = parsed_input_url.netloc.replace("www.", "")
    
    # Entfernen des Länderkürzels, wenn vorhanden
    input_domain = re.sub(r'^[a-z]{2}\.', "", input_domain)
    
    print(f"Input domain: {input_domain}")  # Log statement
    
    for site in websites:
        parsed_site_url = urlparse(site["url"])
        site_domain = parsed_site_url.netloc.replace("www.", "")
        
        # Entfernen des Länderkürzels, wenn vorhanden
        site_domain = re.sub(r'^[a-z]{2}\.', "", site_domain)
        
        print(f"Comparing input domain '{input_domain}' with site domain '{site_domain}'")  # Log statement
        
        if site_domain == input_domain:
            function_name = site["function"].replace("-", "_")
            print(f"Matching website found: {site['name']}. Calling function {function_name}.")
            try:
                exec(f"{function_name}(url)")
            except Exception as e:
                print(f"An error occurred while executing the function {function_name}: ", e)
        return

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
            search_word = keyb.getText()
            search_word_encoded = urllib.parse.quote_plus(search_word)
            if search_word not in all_queries:
                save_query(search_word)

            search_url = site["search_url"].replace("{}", search_word_encoded)
            xbmc.log("Search URL: " + search_url, xbmc.LOGINFO)
            site["function"](search_url, 1)
    elif selected_index >= 0 and selected_index > 0 and selected_index < len(valid_options) - 1:
        search_word = valid_options[selected_index]
        search_word_encoded = urllib.parse.quote_plus(search_word)

        search_url = site["search_url"].replace("{}", search_word_encoded)
        site["function"](search_url, 1)
    elif selected_index >= 0 and selected_index == len(valid_options) - 1:
        clear_search_history()
    xbmcplugin.setPluginCategory(int(sys.argv[1]), 'Search Results')
    xbmcplugin.endOfDirectory(int(sys.argv[1]))


def start(url):
    add_home_button()
    xbmc.log('start function called with URL: ' + url, xbmc.LOGINFO)
    for site in websites:
        if url.startswith(site["url"]):
            site["function"](url)
            break


def add_home_button():
    add_dir("Home", "", 100, os.path.join(logos, 'adulthideout.png'), fanart)

def play_video(url):
    logging.info('play_video function called with URL: %s', url)
    media_url = resolve_url(url, websites)
    item = xbmcgui.ListItem(name, path=media_url)
    item.setMimeType('video/mp4')
    xbmcplugin.setResolvedUrl(int(sys.argv[1]), True, item)

def setView(content, viewType):
    # Setzt den Kodi View Type für das aktuelle Verzeichnis
    if content:
        xbmcplugin.setContent(int(sys.argv[1]), content)
    if addon.getSetting('auto-view') == 'true':
        view_type_map = {
            "0": "50",  # List
            "1": "51",  # Big List
            "2": "500", # Thumbnail
            "3": "501"  # Big Thumbnail
        }
        selected_view_index = addon.getSetting('viewType')
        selected_view_id = view_type_map[selected_view_index]
        xbmc.executebuiltin('Container.SetViewMode(%s)' % selected_view_id)
        xbmcplugin.addSortMethod(int(sys.argv[1]), xbmcplugin.SORT_METHOD_UNSORTED)


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
        
    elif mode == 100:
        main()

    elif mode == 70:
        item = xbmcgui.ListItem(name, path=url)
        item.setMimeType('video/mp4')
        xbmcplugin.setResolvedUrl(int(sys.argv[1]), True, item)

    xbmcplugin.endOfDirectory(int(sys.argv[1]))
