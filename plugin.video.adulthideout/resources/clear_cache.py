import shutil
import os
import xbmc
import xbmcgui

# Protokollierung des Skriptstarts
xbmc.log("Running clear_cache.py", level=xbmc.LOGINFO)

# Pfad zum Addon-Verzeichnis (eine Ebene höher als der aktuelle Pfad)
addon_path = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))

# Pfade zu den __pycache__-Verzeichnissen
pycache_paths = [
    os.path.join(addon_path, '__pycache__'),
    os.path.join(addon_path, 'resources', '__pycache__'),
]

# Löschen der __pycache__-Verzeichnisse
for pycache_path in pycache_paths:
    if os.path.exists(pycache_path):
        shutil.rmtree(pycache_path)
        xbmc.log(f"{pycache_path} wurde gelöscht.", level=xbmc.LOGINFO)  # Protokollierung des Löschens
    else:
        xbmc.log(f"{pycache_path} existiert nicht.", level=xbmc.LOGINFO)  # Protokollierung der Nichtexistenz

# Anzeigen einer Benachrichtigung
dialog = xbmcgui.Dialog()
dialog.notification('AdultHideout', 'Cache wurde gelöscht.', xbmcgui.NOTIFICATION_INFO, 5000)
