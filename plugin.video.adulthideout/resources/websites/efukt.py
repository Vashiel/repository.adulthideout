import re
import xbmc
from ..functions import add_dir, add_link, make_request, fanart, logos
import xbmcgui
import xbmcplugin
import xbmcaddon
import urllib.parse as urllib_parse
import logging
from urllib.parse import urlparse

def process_efukt_content(url, page=1):
    xbmc.log("Entering process_efukt_content with URL: " + url, xbmc.LOGINFO)  # Log-Anweisung hier
    if page == 1:
        add_dir(f'Search Efukt', 'efukt', 5, logos + 'efukt.png', fanart)
    content = make_request(url)
    match = re.compile('<a  href="([^"]*)" title="([^"]*)".+?https://(.*?).jpg').findall(content)
    # Get the base URL part from the input URL
    parsed_url = urlparse(url)
    base_url = f"{parsed_url.scheme}://{parsed_url.netloc}" 
    for url, name, thumb in match:
        name = name.replace('&amp;', '&').replace('&quot;', '"').replace('&#039;', '\'')
        add_link(name, url, 4, f'https://{thumb}.jpg', fanart)
    
    try:
        match = re.compile('class="anchored_item active ">.+?</a><a href="(.+?)"').findall(content)
        add_dir('[COLOR blue]Next Page >>>>[/COLOR]', base_url + match[0], 2, logos + 'efukt.png', fanart)
    except:
        pass

def play_efukt_video(url):
    content = make_request(url)
    media_url = re.compile('<source src="(.+?)" type="video/mp4">').findall(content)[0]
    media_url = media_url.replace('amp;', '')
    xbmc.log('Resolved media URL: ' + media_url, xbmc.LOGINFO)  # Hinzufügen dieser Log-Anweisung
    return media_url
