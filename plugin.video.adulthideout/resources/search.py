import os
import json
import sys
import xbmcaddon
from six.moves import urllib_parse
from kodi_six import xbmc, xbmcgui
from .queries import get_all_queries
import importlib
import sys

def clear_search_history():
    # Get the path to the add-on directory
    home = xbmcaddon.Addon().getAddonInfo('path')
    # Use the os.path.join function to construct the file path
    file_path = os.path.join(home, 'resources/last_query.json')
    # Clear the contents of the file
    with open(file_path, 'w') as f:
        json.dump([], f)

    # Display a notification that the search history was cleared
    xbmc.executebuiltin('Notification(Search History Cleared, The search history has been cleared, 5000)')

    # Refresh the current directory
    xbmc.executebuiltin('Container.Refresh')


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
