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

def process_uflash_content(url, page=1):
    if "search" not in url and "/videos" not in url:
        url = url + "/videos?g=female&o=mr&type=public"
    content = make_request(url)
    add_dir('[COLOR blue]Search[/COLOR]', 'uflash', 5, logos + 'uflash.png', fanart)
    match = re.compile('<a href="([^"]*)".+?<img src="([^"]*)" alt="([^"]*)"', re.DOTALL).findall(content)
    for url, thumb, name in match:
        name = name.replace('&amp;', '&').replace('&quot;', '"').replace('&#039;', '\'')
        add_link(name, 'http://www.uflash.tv' + url,  4, thumb, fanart)
    add_next_button(content)

def add_next_button(content):
    match = re.compile('<span class="currentpage">.+?</span></li><li><a href="([^"]*)"').findall(content)
    add_dir('[COLOR blue]Next  Page  >>>>[/COLOR]', match[0], 2, logos + 'uflash.png', fanart)

def play_uflash_video(url):
    content = make_request(url)
    media_url = re.compile('var video_source = "([^"]*)"').findall(content)[0]

    return media_url

