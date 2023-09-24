import os
import json
import xbmcaddon
# Get the path to the add-on directory
home = xbmcaddon.Addon().getAddonInfo('path')
# Use the os.path.join function to construct the file path
json_file_path = os.path.join(home, 'resources/last_content.json')

def get_last_content():
    # Get the path to the add-on directory
    home = xbmcaddon.Addon().getAddonInfo('path')
    # Use the os.path.join function to construct the file path
    file_path = os.path.join(home, 'resources/last_content.json')

def save_selected_content(selected_content):
    try:
        with open(json_file_path, 'r+') as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError:  # Wenn die Datei leer oder ungültig ist
                data = {}  # Initialisieren Sie data als leeres Wörterbuch
                
            data['selected_content'] = selected_content
            f.seek(0)
            json.dump(data, f)
            f.truncate()
    except Exception as e:
        print(f"Fehler beim Speichern des selected_content: {e}")

def load_selected_content():
    try:
        with open(json_file_path, 'r') as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError:  # Wenn die Datei leer oder ungültig ist
                data = {}  # Initialisieren Sie data als leeres Wörterbuch
                
            return data.get('selected_content', "")
    except Exception as e:
        print(f"Fehler beim Laden des selected_content: {e}")
        return ""
