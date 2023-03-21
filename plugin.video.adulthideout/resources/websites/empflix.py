import re
import xbmc
from bs4 import BeautifulSoup
from ..functions import add_dir, add_link, make_request, fanart, logos
import xbmcgui
import xbmcplugin
import xbmcaddon
import urllib.parse as urllib_parse

def process_empflix_content(url, mode=None):
    # changing the base-URl to base-URL + /new/1/
    url = url + "/new/"
    
    content = make_request(url)
    add_dir('[COLOR blue]Search[/COLOR]', 'empflix', 5, logos + 'empflix.png', fanart)
    match = re.compile('href="([^"]*)" data-trailer=".+?">.+?src="([^"]*)" alt="([^"]*)">', re.DOTALL).findall(content)
    
    # Get the base URL part from the input URL
    base_url = url.rsplit("/", 3)[0]
    
    for url, thumb, name in match:
        add_link(name, url , 4, thumb, fanart)
    try:
        match = re.compile('<a class="llNav" href="([^"]+)">').findall(content)
        add_dir('[COLOR blue]Next  Page  >>>>[/COLOR]', match[0], 2, logos + 'empflix.png', fanart)
    except:
        pass

def play_empflix_video(url):
    content = make_request(url)
    soup = BeautifulSoup(content, 'html.parser')
    video = soup.find('video')

    if video:
        source = video.find('source', type='video/mp4')
        if source:
            media_url = source.get('src', '')
            media_url = media_url.replace('amp;', '')
            return media_url
        else:
            # Hier können Sie eine Fehlermeldung oder einen Fallback-Mechanismus hinzufügen, falls das <source>-Element nicht gefunden wird
            pass
    else:
        # Hier können Sie eine Fehlermeldung oder einen Fallback-Mechanismus hinzufügen, falls das <video>-Element nicht gefunden wird
        pass
