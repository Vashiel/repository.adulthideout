import os
import json
import xbmcaddon
from six.moves import urllib_parse
from kodi_six import xbmc, xbmcgui
from .queries import get_all_queries

def search_handler(websites, name, url, start):
    last_query = get_last_query()
    keyb = xbmc.Keyboard(str(last_query), '[COLOR yellow]Enter search text[/COLOR]')
    all_queries = get_all_queries()
    options = ["New Search"] + all_queries
    valid_options = [option for option in options if isinstance(option, str)]
    selected_index = xbmcgui.Dialog().select("Select a Query", valid_options)
    if selected_index >= 0 and selected_index == 0:
        keyb.doModal()
        if (keyb.isConfirmed()):
            searchText = urllib_parse.quote_plus(keyb.getText())
            if searchText not in all_queries:
                save_query(searchText)
            for site in websites:
                if site["name"] in name:
                    url = site["url"] + '/search/' + searchText + '/'
                    start(url)
                    break
    elif selected_index >= 0 and selected_index > 0:
        searchText = urllib_parse.quote_plus(valid_options[selected_index])
        for site in websites:
            if site["name"] in name:
                url = site["url"] + '/search/' + searchText + '/'
                start(url)
                break

def save_query(query):
    # Get the path to the add-on directory
    home = xbmcaddon.Addon().getAddonInfo('path')
    # Use the os.path.join function to construct the file path
    file_path = os.path.join(home, 'resources/last_query.json')
    
    # Load all queries from the file, or initialize empty list if file is empty or invalid
    all_queries = []
    with open(file_path, 'r') as f:
        try:
            all_queries = json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    if not isinstance(all_queries, list):
        all_queries = []

    # Check if query already exists in list
    if query not in all_queries:
        # Add the new query to the list
        all_queries.append(query)

        # Write all queries to the file
        with open(file_path, 'w') as f:
            json.dump(all_queries, f)


def get_last_query():
    # Get the path to the add-on directory
    home = xbmcaddon.Addon().getAddonInfo('path')
    # Use the os.path.join function to construct the file path
    file_path = os.path.join(home, 'resources/last_query.json')
    if os.path.isfile(file_path) and os.path.getsize(file_path) > 0:
        with open(file_path, 'r') as f:
            queries = json.load(f)
    else:
        queries = []
    if queries:
        last_query = queries[-1]
    else:
        last_query = ""
    return last_query
