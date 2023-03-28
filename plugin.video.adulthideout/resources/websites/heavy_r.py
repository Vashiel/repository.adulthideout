import re
import xbmc
from ..functions import add_dir, add_link, make_request, fanart, logos
import xbmcgui
import xbmcplugin
import xbmcaddon
import urllib.parse as urllib_parse


def process_heavy_r_content(url, mode=None):
    print(f"Inside the process_heavy_r_content function with url: {url}")  # Log statement
    # changing the base-URl to base-URL + /new/1/
    url = url + "/videos/recent/"
    
    content = make_request(url)
    add_dir('[COLOR blue]Search[/COLOR]', 'heavy-r', 5, logos + 'heavy-r.png', fanart)
    match = re.compile('<a href="([^"]+)" class="image">.+?<img src="([^"]+)".+?alt="([^"]+)"', re.DOTALL).findall(content)
    # Get the base URL part from the input URL
    base_url = url.rsplit("/", 3)[0]
    
    for url, thumb, name in match:
        add_link(name, base_url + url, 4, thumb, fanart)
    try:
        match = re.compile('<li><a class="nopopoff" href="([^"]+)">Next</a></li>').findall(content)
        add_dir('[COLOR blue]Next  Page  >>>>[/COLOR]', base_url + match[0], 2, logos + 'heavy-r.png', fanart)
    except:
        pass


def play_heavy_r_video(url):
    content = make_request(url)
    media_url = re.compile('<source type="video/mp4" src="([^"]+)">').findall(content)[0]
    return media_url
