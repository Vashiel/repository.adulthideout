import re
import xbmc
from ..functions import add_dir, add_link, make_request, fanart, logos
import xbmcgui
import xbmcplugin
import xbmcaddon
import urllib.parse as urllib_parse
import urllib.request

def process_luxuretv_content(url, mode=None):
    if "search" not in url:
        url = 'https://luxuretv.com' + "/page1.html"

    add_dir(f'Search luxuretv', 'luxuretv', 5, logos + 'luxuretv.png', fanart)
    content = make_request(url)
    match = re.compile('a href="([^"]*)" title="([^"]*)"><img class="img lazyload" data-src="([^"]*)"', re.DOTALL).findall(content)
    for url, name, thumb in match:
        add_link(name, url, 4, thumb, fanart)
    try:
        match = re.compile('a href=\'([^"]*)\'>Next').findall(content)
        add_dir('[COLOR blue]Next  Page  >>>>[/COLOR]', 'https://luxuretv.com/' +  match[0], 2, logos + 'luxuretv.png', fanart)
    except:
        pass

def play_luxuretv_video(url):
    content = make_request(url)
    data = re.compile('"filename":"([^"]+.mp4[^"]*)",').findall(content)

    preferred_order = ["1080", "720"]

    for quality in preferred_order:
        for media_url in data:
            if quality in media_url:
                media_url = 'https:' + media_url.replace('/', '')
                return media_url

    # If 1080 and 720 are not found, return the first available media_url
    media_url = 'https:' + data[0].replace('/', '')
    return media_url
