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


def process_punishworld_content(url):
    #xbmc.log("process_punishworld_content: " + url, xbmc.LOGINFO)

    if  url == "https://punishworld.com/categories/":
        process_punishworld_categories(url)
    else:
        content = make_request(url).replace('\n', '').replace('\r', '')
        #xbmc.log("punishworld content: " + content, xbmc.LOGINFO)
        add_dir("Categories", "https://punishworld.com/categories/", 2, logos + 'punishworld.png', fanart)
        add_dir(f'Search punishworld', 'punishworld', 5, logos + 'punishworld.png', fanart)

        match = re.compile('<aclass="thumb ppopp" href="([^"]+)" aria-label="([^"]+)">.+?data-src="([^"]+)"', re.DOTALL).findall(content)
        for video_url, name, thumb in match:
            #xbmc.log("punishworld match: " + name, xbmc.LOGINFO)
            name = html.unescape(name)
            add_link(name.strip(), video_url, 4, thumb, fanart)

        try:
            match = re.compile('<a class="next page-link" href="([^"]+)">').findall(content)   
            add_dir('[COLOR blue]Next  Page  >>>>[/COLOR]', match[0], 2, logos + 'punishworld.png', fanart)
        except:
            pass

def play_punishworld_video(url):
    xbmc.log("Play punishworld URL: " + url, xbmc.LOGINFO)
    content = make_request(url, mobile=True).replace('\n', '').replace('\r', '')
    #xbmc.log("Play punishworld content: " + content, xbmc.LOGINFO)
    media_url = re.compile('var videoHigh."([^"]+)"').findall(content)[0]
    #media_url = media_url.replace('/', '')  #Not sure why we would replace the '/'
    xbmc.log("Media URL: " + media_url, xbmc.LOGINFO)
    return media_url


def process_punishworld_categories(url):
    content = make_request(url).replace('\n', '').replace('\r', '')
    #xbmc.log("punishworld category content: " + content, xbmc.LOGINFO)
    categories = re.compile('<aclass="infos ppopp" href="([^"]+)" title="([^"]+)">', re.DOTALL).findall(content)
    for video_url,name in categories:
        #xbmc.log("punishworld category: " + name, xbmc.LOGINFO)
        add_dir(name.strip(), video_url, 2, logos + 'punishworld.png', fanart)
