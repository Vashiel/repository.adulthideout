import re
import xbmc
from ..functions import add_dir, add_link, make_request, fanart, logos
import xbmcgui
import xbmcplugin
import xbmcaddon
import urllib.parse as urllib_parse
import urllib.request
import logging
from urllib.parse import urlparse

def process_youjizz_content(url, page=1):
    if "search" not in url and not re.search(r"/newest-clips/\d+\.html", url):
        url = url + "/newest-clips/1.html"

    if page == 1:
        if  "{}" in url:
            search_word = re.search(r'\{\}(.*?)$', url).group(1)
            url = url.replace("{}" + search_word, search_word + "/")
    content = make_request(url)
    match = re.compile('data-original="([^"]*)".+?<a href=\'(.+?)\' class="">(.+?)</a>', re.DOTALL).findall(content)
    add_dir('[COLOR blue]Search[/COLOR]', 'youjizz', 5, logos + 'youjizz.png', fanart)
    # Get the base URL part from the input URL
    parsed_url = urlparse(url)
    base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
    
    for thumb, url, name in match:
        add_link(name, base_url + url, 4, 'https:' + thumb, fanart)
    match = re.compile('<a class="pagination-next" href="(.+?)">Next &raquo;</a></li></ul>').findall(content)
    add_dir('[COLOR blue]Next  Page  >>>>[/COLOR]', base_url + match[0], 2, logos + 'youjizz.png', fanart)

def play_youjizz_video(url):
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
