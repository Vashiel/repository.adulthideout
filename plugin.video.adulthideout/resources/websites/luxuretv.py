import re
import xbmc
from ..functions import add_dir, add_link, make_request, fanart, logos
import xbmcgui
import xbmcplugin
import xbmcaddon
import urllib.parse as urllib_parse
import urllib.request
import logging
from urllib.parse import urlparse

def process_luxuretv_content(url, mode=None):
    add_dir(f'Search luxuretv', 'luxuretv', 5, logos + 'luxuretv.png', fanart)
    content = make_request(url)
    match = re.compile('a href="([^"]*)" title="([^"]*)"><img class="img lazyload" data-src="([^"]*)"', re.DOTALL).findall(content)
    # Get the base URL part from the input URL
    parsed_url = urlparse(url)
    base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
    for url, name, thumb in match:
        add_link(name, url, 4, thumb, fanart)
    try:
        match = re.compile('<a href=\'(.+?)\'>Suivante').findall(content)
        add_dir('[COLOR blue]Next  Page  >>>>[/COLOR]', base_url + '/' +  match[0], 2, logos + 'luxuretv.png', fanart)
    except:
        pass

def play_luxuretv_video(url):
    content = make_request(url)
    media_url = re.compile('source src="(.+?)" type=').findall(content)[0]
    return media_url
