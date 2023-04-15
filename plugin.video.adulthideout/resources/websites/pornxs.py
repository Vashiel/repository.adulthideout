import re
import xbmc
from ..functions import add_dir, add_link, make_request, fanart, logos
import xbmcgui
import xbmcplugin
import xbmcaddon
import urllib.parse as urllib_parse
import logging
from urllib.parse import urlparse


def process_pornxs_content(url, page=1):
    if "search" not in url and "/slut/" not in url:
        url = url + "/slut/"
    content = make_request(url)
    match = re.compile('<a href="([^"]+)".+?title="([^"]+)".+?data-loader-src="([^"]+)">.+?<div class="squares__item_numbers js-video-time">.+?([:\d]+).+?</div>', re.DOTALL).findall(content)
    
        # Get the base URL part from the input URL
    parsed_url = urlparse(url)
    base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
    
    for url, name, thumb, duration in match:
        add_link(name + ' [COLOR lime]('+ duration + ')[/COLOR]', base_url + url, 4, thumb, fanart)
    try:
        match = re.compile('<a class="pagination-next" href="([^"]*)"><span></span></a></li> ').findall(content)
        add_dir('[COLOR blue]Next  Page  >>>>[/COLOR]', base_url + match[0], 2, logos + 'pornxs.png', fanart)
    except:
        pass

def play_pornxs_video(url):
    logging.info('play_pornxs_video function called with URL: %s', url)
    content = make_request(url)
    media_url = 'https:' + re.compile('<source src="(.+?)" type="video/mp4">').findall(content)[0]
    media_url = media_url.replace('&amp;','&')
    return media_url
