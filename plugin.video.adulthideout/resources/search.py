import os
import json
import sys  # Hinzufügen des Imports für sys
import xbmcaddon
from kodi_six import xbmc, xbmcgui, xbmcvfs
from .queries import get_all_queries
import importlib

addon = xbmcaddon.Addon()

def get_queries_path():
    addon_profile = xbmcvfs.translatePath(addon.getAddonInfo('profile'))
    if not xbmcvfs.exists(addon_profile):
        xbmcvfs.mkdirs(addon_profile)
    return os.path.join(addon_profile, 'queries.json')

def clear_search_history():
    file_path = get_queries_path()
    with open(file_path, 'w') as f:
        json.dump([], f)
    xbmc.executebuiltin('Notification(Search History Cleared, The search history has been cleared, 5000)')
    xbmc.executebuiltin('Container.Refresh')

def save_query(query):
    file_path = get_queries_path()
    all_queries = get_all_queries()
    if query not in all_queries:
        all_queries.append(query)
        with open(file_path, 'w') as f:
            json.dump(all_queries, f)

def get_all_queries():
    file_path = get_queries_path()
    try:
        with open(file_path, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return []

def get_last_query():
    queries = get_all_queries()
    if queries:
        last_query = queries[-1]
    else:
        last_query = ""
    return last_query

def edit_query():
    queries = get_all_queries()
    if not queries:
        xbmcgui.Dialog().notification("No Queries", "No search queries to edit.", xbmcgui.NOTIFICATION_INFO, 3000)
        return

    selected_query = xbmcgui.Dialog().select("Edit Search Query", queries)
    if selected_query == -1:
        return

    keyb = xbmc.Keyboard(queries[selected_query], "[COLOR yellow]Edit search text[/COLOR]")
    keyb.doModal()
    if keyb.isConfirmed():
        new_query = keyb.getText()
        if new_query and new_query != queries[selected_query]:
            queries[selected_query] = new_query
            save_queries(queries)
            xbmcgui.Dialog().notification("Query Edited", "Search query edited successfully.", xbmcgui.NOTIFICATION_INFO, 3000)
            xbmc.executebuiltin('Container.Refresh')  # Aktuelle Ansicht aktualisieren

def save_queries(queries):
    file_path = get_queries_path()
    with open(file_path, 'w') as f:
        json.dump(queries, f)
