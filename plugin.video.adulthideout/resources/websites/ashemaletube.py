import re
import xbmc
from ..functions import add_dir, add_link, make_request, fanart, logos
import xbmcgui
import xbmcplugin
import xbmcaddon
import urllib.parse as urllib_parse

def process_ashemaletube_content(url, page=1):
    # changing the base-URl to base-URL + /new/1/
    url = url + "/videos/newest/"
    
    if page == 1:
        add_dir(f'Search ashemaletube', 'ashemaletube', 5, logos + 'ashemaletube.png', fanart)
    content = make_request(url)
    match = re.compile('<div class="thumb vidItem" data-video-id=".+?">.+?<a href="([^"]*)" >.+?src="([^"]*)" alt="([^"]*)"(.+?)<span>.+?([:\d]+).+?</span>', re.DOTALL).findall(content)
   
    # Get the base URL part from the input URL
    base_url = url.rsplit("/", 3)[0]

    for url, thumb, name, dummy, duration in match:
        name = name.replace('&amp;', '&')
        if 'HD' in dummy:
            add_link(name + '[COLOR yellow]' +' [HD]' +'[/COLOR]' +' [COLOR lime]('+ duration + ')[/COLOR]', base_url + url, 4, thumb, fanart)
        else:
            add_link(name + ' [COLOR lime]('+ duration + ')[/COLOR]', base_url + url, 4, thumb, fanart)
    try:
        match = re.compile('<a class="rightKey" href="(.+?)">Next</a>').findall(content)
        add_dir('[COLOR blue]Next  Page  >>>>[/COLOR]', base_url + match[0], 2, logos + 'ashemaletube.png', fanart)
    except:
        match = re.compile('<a class="pageitem rightKey" href="(.+?)" title="Next">Next</a>').findall(content)
        add_dir('[COLOR blue]Next  Page  >>>>[/COLOR]', base_url + match[0], 2, logos + 'ashemaletube.png', fanart)

def play_ashemaletube_video(url):
    content = make_request(url)
    media_url = re.compile('<source src="(.+?)" type="video/mp4">').findall(content)[0]
    media_url = media_url.replace('amp;', '')
    return media_url
    
