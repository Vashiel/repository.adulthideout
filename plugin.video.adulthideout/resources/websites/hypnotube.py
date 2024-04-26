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


def process_hypnotube_content(url):
    #xbmc.log("process_hypnotube_content: " + url, xbmc.LOGINFO)
    if "search" not in url and "channels" not in url:
        url = url + "/videos/"
    if 'https://hypnotube.com/channels/' == url:
        process_hypnotube_categories(url)
    else:
        content = make_request(url, mobile=True).replace('\n', '').replace('\r', '')
        #xbmc.log("Hypnotube content: " + content, xbmc.LOGINFO)
        add_dir("Categories", "https://hypnotube.com/channels/", 2, logos + 'hypnotube.png', fanart)
        add_dir(f'Search hypnotube', 'hypnotube', 5, logos + 'hypnotube.png', fanart)
        match = re.compile('<div class="item-inner-col inner-col">.+?<a href="([^"]+)" title="([^"]+)".+?src="([^"]+)".+?<span class="time">([^"]+)<\/span>', re.DOTALL).findall(content)
        for video_url, name, thumb, duration, in match:
            #xbmc.log("Hypnotube match: " + name, xbmc.LOGINFO)
            name = html.unescape(name)
            add_link(name, video_url, 4, thumb, fanart)
        try:
            match = re.compile('<a rel="Next" href="(.+?)" class="next"').findall(content)
            next_url = base_url + match[0]
            add_dir('[COLOR blue]Next  Page  >>>>[/COLOR]', next_url, 2, logos + 'hypnotube.png', fanart)
        except:
            pass

def process_hypnotube_categories(url):
    content = make_request(url, mobile=True).replace('\n', '').replace('\r', '')
    #xbmc.log("Hypnotube category content: " + content, xbmc.LOGINFO)
    categories = re.compile('<li><a title=\'([^"]+)\' href=\'([^"]+)\' class=\'has-counter\'>', re.DOTALL).findall(content)
    for name, video_url in categories:
        #xbmc.log("Hypnotube category: " + name, xbmc.LOGINFO)
        add_dir(name, video_url, 2, logos + 'hypnotube.png', fanart)

def play_hypnotube_video(url):
    #xbmc.log("Play Hypnotube URL: " + url, xbmc.LOGINFO)
    content = make_request(url).replace('\n', '').replace('\r', '')
    #xbmc.log("Play Hypnotube content: " + content, xbmc.LOGINFO)
    media_url = re.compile('<video id=.+?src="([^"]+)"').findall(content)[0]
    media_url = media_url.replace('amp;', '')
    #xbmc.log("Media URL: " + media_url, xbmc.LOGINFO)
    return media_url
