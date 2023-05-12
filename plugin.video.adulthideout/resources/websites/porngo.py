import re
import xbmc
from ..functions import add_dir, add_link, make_request, fanart, logos
import xbmcgui
import xbmcplugin
import xbmcaddon
import urllib.parse as urllib_parse
import logging
from urllib.parse import urlparse, urljoin
def process_porngo_content(url, page=1):
    if "search" not in url and "/latest-updates/" not in url and "/categories/" not in url:
        url = url + "/latest-updates/"

    if url == 'https://www.porngo.com/categories/':
        process_porngo_categories(url)

    if page == 1:
        add_dir(f'Search porngo', 'porngo', 5, logos + 'porngo.png', fanart)

    add_dir("Categories", "https://www.porngo.com/categories/", 2, logos + 'porngo.png', fanart)
    content = make_request(url)
    match = re.compile('<a href="([^"]*)" class="thumb__top ">.+?<div class="thumb__img" data-preview=".+?">.+?<img src="([^"]*)" alt="([^"]*)".+?<span class="thumb__duration">([:\d]+)</span>', re.DOTALL).findall(content)
    
    # Get the base URL part from the input URL
    parsed_url = urlparse(url)
    base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"

    for url, thumb, name, duration in match:
        add_link(name + ' [COLOR lime]('+ duration + ')[/COLOR]', url,  4, thumb, fanart)
    try:
        match = re.compile('href="(.+?)">Next</a></div>').findall(content)
        add_dir('[COLOR blue]Next  Page  >>>>[/COLOR]', base_url + match[0], 2, logos + 'porngo.png', fanart)
    except:
        pass
        
def process_porngo_categories(url):
    content = make_request(url)
    parsed_url = urlparse(url)
    base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
    categories = re.compile('<a href="([^"]*)" class="letter-block__link">.+?<span>(.+?)</span>', re.DOTALL).findall(content)
    for video_url, name in categories:
        full_url = urljoin(base_url, video_url)  # Properly format the URL
        add_dir(name, full_url, 2, logos + 'porngo.png', fanart)

def play_porngo_video(url):
    logging.info('play_porngo_video function called with URL: %s', url)
    content = make_request(url)
    media_url = re.compile("<source src='(.+?)' type='video/mp4'").findall(content)[0]
    return media_url

