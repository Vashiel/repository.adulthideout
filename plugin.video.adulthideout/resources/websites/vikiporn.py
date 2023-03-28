import re
import xbmc
from ..functions import add_dir, add_link, make_request, fanart, logos
import xbmcgui
import xbmcplugin
import xbmcaddon
import urllib.parse as urllib_parse
import logging

def process_vikiporn_content(url, page=1):
        # changing the base-URl RL
    if "search" not in url:
        url = url + "/latest-updates/"
    
    if page == 1:
        add_dir(f'Search Vikiporn', 'vikiporn', 5, logos + 'vikiporn.png', fanart)
    content = make_request(url)
    match = re.compile('ImageObject\">.+?<a href="([^"]*)".+?<img src="([^"]*)" alt="([^"]*)">', re.DOTALL).findall(content)
    
    # Get the base URL part from the input URL
    base_url = url.rsplit("/", 3)[0]
    
    for url, thumb, name in match:
        add_link(name, url,  4, thumb, fanart)
    try:
        match = re.compile('<a href="(.+?)">Next</a>').findall(content)
        add_dir('[COLOR blue]Next  Page  >>>>[/COLOR]', base_url + match[0], 2, logos + 'vikiporn.png', fanart)
    except:
        pass



def play_vikiporn_video(url):
    logging.info('play_vikiporn_video function called with URL: %s', url)
    content = make_request(url)
    media_url = re.compile("video_url: '(.+?)',").findall(content)[0]
    return media_url
