import re
import xbmc
from ..functions import add_dir, add_link, make_request, fanart, logos
import xbmcgui
import xbmcplugin
import xbmcaddon
import urllib.parse as urllib_parse


def process_xvideos_content(url, mode=None):
    # changing the base-URl to base-URL + /new/1/
    if "search" not in url:
        url = url + "/new/1/"
    
    content = make_request(url)
    add_dir('[COLOR blue]Search[/COLOR]', 'xvideos', 5, logos + 'xvideos.png', fanart)
    match = re.compile('<img src=".+?" data-src="([^"]*)"(.+?)<p class="title"><a href="([^"]*)" title="([^"]*)".+?<span class="duration">([^"]*)</span>', re.DOTALL).findall(content)
    
    # Get the base URL part from the input URL
    base_url = url.rsplit("/", 3)[0]
    
    for thumb, dummy, url, name, duration in match:
        name = name.replace('&amp;', '&').replace('&quot;', '"').replace('&#39;', '`')
        url = url.replace('THUMBNUM/', '')
        add_link(name + ' [COLOR lime]('+ duration + ')[/COLOR]', base_url + url, 4, thumb, fanart)
    
    try:
        match = re.compile('<a href="([^"]+)" class="no-page next-page">Next</a>').findall(content)
        match = [item.replace('&amp;', '&') for item in match]
        add_dir('[COLOR blue]Next  Page  >>>>[/COLOR]', base_url + match[0], 2, logos + 'xvideos.png', fanart)
    except:
        pass

def play_xvideos_video(url):
    content = make_request(url)
    media_url = re.search(r"html5player\.setVideoUrlHigh\('(.+?)'\)", content).group(1)
    return media_url

