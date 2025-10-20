import xbmc
import xbmcaddon
import xbmcgui
import os
import xbmcvfs

ADDON_ID = 'plugin.video.adulthideout'

try:
    addon = xbmcaddon.Addon(ADDON_ID)
    profile_path = xbmcvfs.translatePath(addon.getAddonInfo('profile'))
    settings_file = os.path.join(profile_path, 'settings.xml')

    line1 = "Are you sure you want to reset all addon settings to their default values?"
    line2 = "This will clear old data and may improve performance. Kodi will restart."
    full_text = f"{line1}\n{line2}"

    if xbmcgui.Dialog().yesno("Confirm Reset", full_text):
        try:
            if xbmcvfs.exists(settings_file):
                if xbmcvfs.delete(settings_file):
                    xbmcgui.Dialog().notification("Success", "Settings reset. Restarting Kodi...", xbmcgui.NOTIFICATION_INFO, 3000)
                    xbmc.executebuiltin("RestartApp")
                else:
                    xbmcgui.Dialog().notification("Error", "Failed to delete settings file.", xbmcgui.NOTIFICATION_ERROR, 5000)
            else:
                xbmcgui.Dialog().notification("Info", "No settings file to delete. Restarting Kodi...", xbmcgui.NOTIFICATION_INFO, 3000)
                xbmc.executebuiltin("RestartApp")
                
        except Exception as e:
            xbmcgui.Dialog().notification("Error", f"Failed to delete settings file: {e}", xbmcgui.NOTIFICATION_ERROR, 5000)

except Exception as e:
    xbmcgui.Dialog().notification("Error", f"Could not get addon object: {e}", xbmcgui.NOTIFICATION_ERROR, 5000)