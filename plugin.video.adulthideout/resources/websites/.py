import re
import xbmc
from ..functions import add_dir, add_link, make_request, fanart, logos
import xbmcgui
import xbmcplugin
import xbmcaddon
import urllib.parse as urllib_parse

def process__content(url, page=1):
    if page == 1:
        add_dir(f'Search ', '', 5, logos + '.png', fanart)
    content = make_request(url)
    match = re.compile('<a  href="([^\"]*)" title="([^\"]*)".+?https://(.*?).jpg').findall(content)
    for url, name, thumb in match:
        name = name.replace('&amp;', '&').replace('&quot;', '"').replace('&#039;', "'")
        add_link(name, url, 4, f'https://{thumb}.jpg', fanart)

    try:
        match = re.compile('class="anchored_item active ">.+?</a><a href="(.+?)"').findall(content)
        if match:
            add_dir('[COLOR blue]Next Page >>>>[/COLOR]',  + match[0], 2, logos + '.png', fanart)
    except:
        pass

def play__video(url):
    content = make_request(url)
    media_url = re.compile('<source src="(.+?)" type="video/mp4">').findall(content)[0]
    media_url = media_url.replace('amp;', '')
    return media_url
