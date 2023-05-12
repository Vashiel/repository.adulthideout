import re
import xbmc
from ..functions import add_dir, add_link, make_request, fanart, logos
import xbmcgui
import xbmcplugin
import xbmcaddon
import urllib.parse as urllib_parse
import logging
from urllib.parse import urlparse, urljoin

def process_motherless_content(url):
    if "search" not in url:
        url = url + "/videos/recent"
    if "porn" in url:
        url = url
    if "shouts" in url:
        process_motherless_categories(url)
    else:
        content = make_request(url)
        #parsed_url = urlparse(url)
        #base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
        add_dir('[COLOR blue]Search[/COLOR]', 'motherless', 5, logos + 'motherless.png', fanart) 
        add_dir("Categories", "https://motherless.com/shouts?page=1", 2, logos + 'motherless.png', fanart)
        match = re.compile('<a href="([^"]+)" class="img-container" target="_self">.+?<span class="size">([:\d]+)</span>.+?<img class="static" src="https://(.+?)".+?alt="([^"]+)"/>', re.DOTALL).findall(content)
        for url, duration, thumb, name in match:
            name = name.replace('&amp;', '&').replace('&quot;', '"').replace('&#039;', '\'')
            add_link(name + ' [COLOR lime]('+ duration + ')[/COLOR]', url, 4, 'http://' + thumb, fanart)
        try:
            match = re.compile('<link rel="next" href="(.+?)"/> ').findall(content)
            add_dir('[COLOR blue]Next  Page  >>>>[/COLOR]',  match[0], 2, logos + 'motherless.png', fanart)
        except:
            pass

def process_motherless_categories(url):
    content = make_request(url)
    #parsed_url = urlparse(url)
    #base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
    categories = re.compile(' <a href="/porn/([^"]+)/videos" class="pop plain"', re.DOTALL).findall(content)
    for url in categories:
        name = url
        #full_url = urljoin(base_url, video_url)  # Properly format the URL
        add_dir(name, 'https://motherless.com/porn/' + url , 2, logos + 'motherless.png', fanart)

def play_motherless_video(url):
    content = make_request(url)
    media_url = re.compile("__fileurl = 'https://(.+?)';").findall(content)[0]
    media_url = 'http://' + media_url
    return media_url
