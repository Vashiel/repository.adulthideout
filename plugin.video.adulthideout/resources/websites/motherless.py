import re
import xbmc
from ..functions import add_dir, add_link, make_request, fanart, logos
import xbmcgui
import xbmcplugin
import xbmcaddon
import urllib.parse as urllib_parse


def process_motherless_content(url, page=1):
    # changing the base-URl to base-URL + start-URL
    url = url + "/videos/recent?page=1"
    content = make_request(url)
    add_dir('[COLOR blue]Search[/COLOR]', 'motherless', 5, logos + 'motherless.png', fanart) 
    match = re.compile('<a href="([^"]+)" class="img-container" target="_self">.+?<span class="size">([:\d]+)</span>.+?<img class="static" src="https://(.+?)" .+?alt="([^"]+)"/>', re.DOTALL).findall(content)
    for url, duration, thumb, name in match:
        name = name.replace('&amp;', '&').replace('&quot;', '"').replace('&#039;', '\'')
        if 'motherless' in url:
            add_link(name + ' [COLOR lime]('+ duration + ')[/COLOR]', url, 4, 'http://' + thumb, fanart)
        else:
            add_link(name + ' [COLOR lime]('+ duration + ')[/COLOR]', base_url + url, 4, 'http://' + thumb, fanart)
    try:
        match = re.compile('<link rel="next" href="(.+?)"/> ').findall(content)
        add_dir('[COLOR blue]Next  Page  >>>>[/COLOR]',  match[0], 2, logos + 'motherless.png', fanart)
    except:
        pass


def play_motherless_video(url):
    content = make_request(url)
    media_url = re.compile("__fileurl = 'https://(.+?)';").findall(content)[0]
    media_url = 'http://' + media_url
    return media_url
