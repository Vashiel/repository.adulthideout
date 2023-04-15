import re
import xbmc
from ..functions import add_dir, add_link, make_request, fanart, logos
import xbmcgui
import xbmcplugin
import xbmcaddon
import urllib.parse as urllib_parse
import logging
from urllib.parse import urlparse
from urllib.parse import urlparse, urljoin

def process_heavy_r_content(url, mode=None):
    xbmc.log("Entering process_heavyr_r_content with URL: " + url, xbmc.LOGINFO)
    content = make_request(url)
    add_dir('[COLOR blue]Search[/COLOR]', 'heavy-r', 5, logos + 'heavy-r.png', fanart)
    match = re.compile('<a href="([^"]+)" class="image">.+?<img src="([^"]+)".+?alt="([^"]+)"', re.DOTALL).findall(content)
    
    # Get the base URL part from the input URL
    parsed_url = urlparse(url)
    base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
    
    for url, thumb, name in match:
        # Join the base URL and the URL from the regex match using urljoin
        full_url = urljoin(base_url, url)
        add_link(name, full_url, 4, thumb, fanart)

    try:
        match = re.compile('<li><a class="nopopoff" href="([^"]+)">Next</a></li>').findall(content)
        add_dir('[COLOR blue]Next  Page  >>>>[/COLOR]', base_url + match[0], 2, logos + 'heavy-r.png', fanart)
    except:
        pass
    
    
def play_heavy_r_video(url):
    content = make_request(url)
    media_url = re.compile('<source type="video/mp4" src="([^"]+)">').findall(content)[0]
    return media_url