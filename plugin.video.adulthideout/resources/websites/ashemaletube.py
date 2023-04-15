import re
import xbmc
from ..functions import add_dir, add_link, make_request, fanart, logos
import xbmcgui
import xbmcplugin
import xbmcaddon
import urllib.parse as urllib_parse

def process_ashemaletube_content(url, page=1):
    xbmc.log("Entering process_ashemaletube_content with URL: " + url, xbmc.LOGINFO)  # Log-Anweisung hier
    if page == 1:
        add_dir(f'Search ashemaletube', 'ashemaletube', 5, logos + 'ashemaletube.png', fanart)
    xbmc.log("Processed URL: " + url, xbmc.LOGINFO)  # Log-Anweisung hier
    content = make_request(url)
    # Extrahiere den Inhalt bis zur angegebenen Zeile
    index = content.find('<div class="pagination" >')
    if index != -1:
        limited_content = content[:index]
    else:
        limited_content = content
    match = re.compile('<span class="thumb-inner-wrapper">.+?<a href="([^"]*)" >.+?<img src="([^"]*)" alt="([^"]*)"', re.DOTALL).findall(limited_content)
    # Get the base URL part from the input URL
    base_url = "/".join(url.split("/")[:3])
    for video_url, thumb, name, in match:
        name = name.replace('&amp;', '&')
        add_link(name, base_url + video_url, 4, thumb, fanart)
    try:
        match = re.compile('<link rel="next" href="(.+?)" />').findall(content)
        next_url = base_url + match[0]
        add_dir('[COLOR blue]Next  Page  >>>>[/COLOR]', next_url, 2, logos + 'ashemaletube.png', fanart)
    except:
        pass

def play_ashemaletube_video(url):
    content = make_request(url)
    media_url = re.compile('<source src="(.+?)" type="video/mp4">').findall(content)[0]
    media_url = media_url.replace('amp;', '')
    xbmc.log("Media URL: " + media_url, xbmc.LOGINFO)  # Log-Anweisung hie
    return media_url
    
