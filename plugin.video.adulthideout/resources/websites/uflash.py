import re
import xbmc
from ..functions import add_dir, add_link, make_request, fanart, logos
import xbmcgui
import xbmcplugin
import xbmcaddon
import urllib.parse as urllib_parse
import logging
from urllib.parse import urlparse
import base64

def process_uflash_content(url, page=1):
    if "search" not in url and "/videos" not in url:
        url = url + "/videos?g=female&o=mr&type=public"
    content = make_request(url)
    add_dir('[COLOR blue]Search[/COLOR]', 'uflash', 5, logos + 'uflash.png', fanart)
    match = re.compile('<a href="([^"]*)">.+?<img src="([^"]*)" alt="([^"]*)"/>', re.DOTALL).findall(content)
    
    # Get the base URL part from the input URL
    parsed_url = urlparse(url)
    base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"    
    
    for url, thumb, name in match:
        name = name.replace('&amp;', '&').replace('&quot;', '"').replace('&#039;', '\'')
        add_link(name, base_url + url,  4, base_url + thumb, fanart)
    try:
        match = re.compile('<a href="([^"]*)" class="prevnext">').findall(content)
        add_dir('[COLOR blue]Next  Page  >>>>[/COLOR]', match[0], 2, logos + 'uflash.png', fanart)
    except:
        pass

def play_uflash_video(url):
    content = make_request(url)
    match = re.compile(r'_8xHp9vZ2\s*=\s*"([^"]+)"', re.IGNORECASE | re.DOTALL).findall(content)
    for media_url in match:
        media_url = base64.b64decode(match[0]).decode("utf-8")
        return media_url

