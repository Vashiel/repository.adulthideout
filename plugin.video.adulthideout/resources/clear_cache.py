#!/usr/bin/env python
# -*- coding: utf-8 -*-

import shutil
import os
import xbmc
import xbmcgui
import xbmcvfs

# Protokollierung des Skriptstarts
xbmc.log("[ClearCache] Running clear_cache.py (Recursive Version)", level=xbmc.LOGINFO)

try:
    # Pfad zum Addon-Verzeichnis (eine Ebene höher als der aktuelle Skript-Ordner 'resources')
    addon_path = xbmcvfs.translatePath(os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__)))))
    xbmc.log(f"[ClearCache] Addon path resolved to: {addon_path}", level=xbmc.LOGINFO)
    
    deleted_count = 0
    failed_count = 0
    
    # Rekursiv durch alle Ordner im Addon-Pfad gehen
    # os.walk funktioniert zuverlässig mit den übersetzten Pfaden
    for root, dirs, files in os.walk(addon_path):
        if '__pycache__' in dirs:
            pycache_path = os.path.join(root, '__pycache__')
            try:
                # shutil.rmtree ist der zuverlässigste Weg, Ordner rekursiv zu löschen
                shutil.rmtree(pycache_path)
                xbmc.log(f"[ClearCache] SUCCESS: Deleted {pycache_path}", level=xbmc.LOGINFO)
                deleted_count += 1
            except Exception as e:
                xbmc.log(f"[ClearCache] ERROR: Failed to delete {pycache_path}: {e}", level=xbmc.LOGERROR)
                failed_count += 1
        
        # Zusätzlich .pyc-Dateien im Hauptverzeichnis löschen (falls vorhanden)
        # Dieser Teil ist oft nicht nötig, aber sicher ist sicher
        for file in files:
            if file.endswith('.pyc'):
                file_path = os.path.join(root, file)
                try:
                    os.remove(file_path)
                    xbmc.log(f"[ClearCache] SUCCESS: Deleted stray .pyc file: {file_path}", level=xbmc.LOGINFO)
                except Exception as e:
                    xbmc.log(f"[ClearCache] ERROR: Failed to delete stray .pyc: {file_path}: {e}", level=xbmc.LOGERROR)


    dialog = xbmcgui.Dialog()
    if deleted_count > 0:
        dialog.notification('AdultHideout', f'{deleted_count} Cache-Ordner gelöscht.', xbmcgui.NOTIFICATION_INFO, 3000)
    elif failed_count > 0:
        dialog.notification('AdultHideout', 'Fehler beim Cache löschen. Siehe Log.', xbmcgui.NOTIFICATION_ERROR, 3000)
    else:
        dialog.notification('AdultHideout', 'Keine Cache-Ordner gefunden.', xbmcgui.NOTIFICATION_INFO, 3000)

except Exception as e:
    xbmc.log(f"[ClearCache] CRITICAL ERROR in clear_cache.py: {e}", level=xbmc.LOGERROR)
    xbmcgui.Dialog().notification('AdultHideout', f'Fehler: {e}', xbmcgui.NOTIFICATION_ERROR, 3000)