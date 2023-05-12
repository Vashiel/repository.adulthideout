import os
import json
import xbmcaddon

def get_all_queries():
    # Get the path to the add-on directory
    home = xbmcaddon.Addon().getAddonInfo('path')
    # Use the os.path.join function to construct the file path
    file_path = os.path.join(home, 'resources/last_query.json')
    
    # Load all queries from the file, or initialize empty list if file is empty or invalid
    try:
        with open(file_path, 'r') as f:
            all_queries = json.load(f)
    except (json.JSONDecodeError, IOError):
        all_queries = []
        
    if not isinstance(all_queries, list):
        all_queries = []

    return all_queries

def add_query(query):
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

    # Add the new query to the list
    all_queries.append(query)

    # Write all queries to the file
    with open(file_path, 'w') as f:
        json.dump(all_queries, f)

def remove_query(query):
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
    
    # Remove the query from the list
    all_queries.remove(query)

    # Write all queries to the file
    with open(file_path, 'w') as f:
        json.dump(all_queries, f)
