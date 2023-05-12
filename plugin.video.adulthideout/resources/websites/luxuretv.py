import re
import xbmc
from ..functions import add_dir, add_link, make_request, fanart, logos
import xbmcgui
import xbmcplugin
import xbmcaddon
import urllib.parse as urllib_parse
from urllib.parse import urlparse
import html
import sys
from urllib.parse import urljoin

def process_luxuretv_content(url, mode=None):
    if "search" not in url and "newest" not in url:
        url = url
    if url == 'https://en.luxuretv.com/channels/':
        process_luxuretv_categories(url)
    else:
        content = make_request(url)
        add_dir(f'Search luxuretv', 'luxuretv', 5, logos + 'luxuretv.png', fanart)
        add_dir("Categories", "https://en.luxuretv.com/channels/", 2, logos + 'luxuretube.png', fanart)
        match = re.compile('a href="([^"]*)" title="([^"]*)"><img class="img lazyload" data-src="([^"]*)"', re.DOTALL).findall(content)
        # Get the base URL part from the input URL
        parsed_url = urlparse(url)
        base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
        for url, name, thumb in match:
            full_url = urljoin(base_url, url)  # Properly format the URL
            add_link(name, full_url, 4, thumb, fanart)
        try:
            match = re.compile('<a href=\'(.+?)\'>Next').findall(content)
            next_page_url = urljoin(base_url, match[0])  # Properly format the URL
            add_dir('[COLOR blue]Next  Page  >>>>[/COLOR]', next_page_url, 2, logos + 'luxuretv.png', fanart)
        except:
            pass

def process_luxuretv_categories(url):
    content = make_request(url)
    parsed_url = urlparse(url)
    base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
    categories = re.compile('<a href="([^"]*)">.+?src="([^"]*)" alt="([^"]*)"', re.DOTALL).findall(content)
    for video_url, thumb, name in categories:
        full_url = urljoin(base_url, video_url)  # Properly format the URL
        add_dir(name, full_url, 2, thumb, fanart)

def play_luxuretv_video(url):
    content = make_request(url)
    media_url = re.compile('source src="(.+?)" type=').findall(content)[0]
    return media_url
