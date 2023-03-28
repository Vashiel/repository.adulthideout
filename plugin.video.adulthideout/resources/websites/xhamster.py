import re
import xbmc
from ..functions import add_dir, add_link, make_request, fanart, logos
import xbmcgui
import xbmcplugin
import xbmcaddon
import urllib.parse as urllib_parse
import logging

def process_xhamster_content(url, page=1):
        # changing the base-URl RL
    if "search" not in url:
        url = url + "/new/1.html"
    
    if page == 1:
        add_dir(f'Search xhamster', 'xhamster', 5, logos + 'xhamster.png', fanart)
    content = make_request(url)
    match = re.compile('data-role="thumb-link" href="([^"]*)".+?src="([^"]*)" alt="([^"]*)">?', re.DOTALL).findall(content)
    
    # Get the base URL part from the input URL
    base_url = url.rsplit("/", 3)[0]
    
    for url, thumb, name in match:

        name = name.replace('&amp;', '&').replace('&quot;', '"').replace('&#39;', '\'')
        add_link(name, url, 4, thumb, fanart)

def play_xhamster_video(url):
    logging.info('play_xhamster_video function called with URL: %s', url)
    content = make_request(url)
    media_url = re.compile('"mp4File":"(.+?)",').findall(content)[0]
    media_url = media_url.replace('\\','')
    return media_url
