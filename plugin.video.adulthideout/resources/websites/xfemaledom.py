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


def process_xfemaledom_content(url):
    xbmc.log("process_xfemaledom_content: " + url, xbmc.LOGINFO)

    if 'https://xfemaledom.com/categories/' == url:
        process_xfemaledom_categories(url)
    else:
        content = make_request(url).replace('\n', '').replace('\r', '')
        #xbmc.log("xfemaledom content: " + content, xbmc.LOGINFO)
        add_dir("Categories", "https://xfemaledom.com/categories/", 2, logos + 'xfemaledom.png', fanart)
        add_dir(f'Search xfemaledom', 'xfemaledom', 5, logos + 'xfemaledom.png', fanart)

        match = re.compile('<aclass="thumb ppopp" href="([^"]+)" aria-label="([^"]+)".+?src="([^"]+)">', re.DOTALL).findall(content)
        for video_url, name, thumb in match:
            #xbmc.log("xfemaledom match: " + name, xbmc.LOGINFO)
            name = html.unescape(name)
            add_link(name, video_url, 4, thumb, fanart)

        try:
            match = re.compile('<aclass="next page-link" href="([^"]+)"').findall(content)   #<a class="next page-link" href="https://xfemaledom.com/page/2/">»</a>
            add_dir('[COLOR blue]Next  Page  >>>>[/COLOR]', match[0], 2, logos + 'xfemaledom.png', fanart)
        except:
            pass

def play_xfemaledom_video(url):
    xbmc.log("Play xfemaledom URL: " + url, xbmc.LOGINFO)
    content = make_request(url).replace('\n', '').replace('\r', '')
    xbmc.log("Play xfemaledom content: " + content, xbmc.LOGINFO)
    #"preview":"https://14.cdnxsalty9.com:8081/9/c/1/9c195637-7522-4ff2-924f-ff2921d96e28_preview.mp4"
    #this is a total hack and it works about 50% of the time
    media_url = re.compile('"preview":"([^"]+)_preview.mp4"').findall(content)[0]+'_240p.mp4'
    #media_url = re.compile('"preview":"([^"]+)_preview.mp4"').findall(content)[0]+'_720p.mp4'
    xbmc.log("Media URL: " + media_url, xbmc.LOGINFO)
    return media_url


def process_xfemaledom_categories(url):
    content = make_request(url).replace('\n', '').replace('\r', '')
    xbmc.log("xfemaledom category content: " + content, xbmc.LOGINFO)
    categories = re.compile('<aclass="thumb.+?href="([^"]+)".+?title="([^"]+)"', re.DOTALL).findall(content)
    for video_url,name in categories:
        xbmc.log("xfemaledom category: " + name, xbmc.LOGINFO)
        add_dir(name, video_url, 2, logos + 'xfemaledom.png', fanart)
