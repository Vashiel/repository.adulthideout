import re
import xbmc
from ..functions import add_dir, add_link, make_request, fanart, logos
import xbmcgui
import xbmcplugin
import xbmcaddon
import urllib.parse as urllib_parse
import logging
from urllib.parse import urlparse
import html

def process_xhamster_content(url, page=1):
        # changing the base-URl RL
    if "search" not in url and "/newest/" not in url:
        url = url + "/newest/1"
    
    if page == 1:
        add_dir(f'Search xhamster', 'xhamster', 5, logos + 'xhamster.png', fanart)
    content = make_request(url)
    match = re.compile('data-role="thumb-link" href="([^"]*)".+?src="([^"]*)" alt="([^"]*)">?', re.DOTALL).findall(content)
    
    # Get the base URL part from the input URL
    parsed_url = urlparse(url)
    base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"    
    
    for url, thumb, name in match:
        name = html.unescape(name)
        #name = name.replace('&amp;', '&').replace('&quot;', '"').replace('&#39;', '\'')
        add_link(name, url, 4, thumb, fanart)
    try:
        match = re.compile('href="([^"]*)" rel="next"').findall(content)
        next_page_url = html.unescape(match[0])  # Bereinigen der URL mit html.unescape()
        add_dir('[COLOR blue]Next  Page  >>>>[/COLOR]',next_page_url , 2, logos + 'xhamster.png', fanart)
    except:
        match = re.compile('data-page="next" href="([^"]*)">').findall(content)
        next_page_url = html.unescape(match[0])  # Bereinigen der URL mit html.unescape()
        add_dir('[COLOR blue]Next  Page  >>>>[/COLOR]',next_page_url , 2, logos + 'xhamster.png', fanart)

def play_xhamster_video(url):
    logging.info('play_xhamster_video function called with URL: %s', url)
    content = make_request(url)
    media_url = re.compile('"mp4File":"(.+?)",').findall(content)[0]
    media_url = media_url.replace('\\','')
    return media_url
