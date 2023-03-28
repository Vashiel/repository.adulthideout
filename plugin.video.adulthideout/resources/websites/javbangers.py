import re
import xbmc
from ..functions import add_dir, add_link, make_request, fanart, logos
import xbmcgui
import xbmcplugin
import xbmcaddon
import urllib.parse as urllib_parse


def process_javbangers_content(url, mode=None):
    # changing the base-URl to base-URL + /new/1/
    url = url + "/latest-updates/"
    
    content = make_request(url)
    match = re.compile('<div class="video-item   ">.+?<a href="(.+?)" title="(.+?)".+?data-original="(.+?)".+?<i class="fa fa-clock-o"></i> ([\d:]+)</div>', re.DOTALL).findall(content)
    # Get the base URL part from the input URL
    base_url = url.rsplit("/", 3)[0]
    
    for url, name, thumb, duration in match:
        add_link(name + ' [COLOR lime]('+ duration + ')[/COLOR]', url, 4, thumb, fanart)
  

def play_javbangers_video(url):
    content = make_request(url)
    media_url = re.compile("video_alt_url: '(.+?)'").findall(content)[0]
    return media_url
