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


def process_spankingtube_content(url):
    #xbmc.log("process_spankingtube_content: " + url, xbmc.LOGINFO)

    if "videos" not in url and "categories" not in url:
        url = "https://www.spankingtube.com/videos?o=mr"

    if  "categories" in url:  #'https://www.spankingtube.com/categories'
        process_spankingtube_categories(url)
    else:
        content = make_request(url).replace('\n', '').replace('\r', '')
        #xbmc.log("spankingtube content: " + content, xbmc.LOGINFO)
        add_dir("Categories", "https://www.spankingtube.com/categories", 2, logos + 'spankingtube.png', fanart)
        add_dir(f'Search spankingtube', 'spankingtube', 5, logos + 'spankingtube.png', fanart)

        match = re.compile('<div class="col-6 col-12 col-sm-6 col-md-4 col-lg-4 col-xl-3" style="margin-bottom:15px;"> <a href="([^"]+)">.+?<img src="([^"]+)" title="([^"]+)"', re.DOTALL).findall(content)
        for video_url, thumb, name in match:
            #xbmc.log("spankingtube match: " + name, xbmc.LOGINFO)
            name = html.unescape(name)
            add_link(name.strip(), "https://www.spankingtube.com"+video_url, 4, thumb, fanart)

        try:
            match = re.compile('<a class="page-link" href="([^"]+)" class="prevnext">').findall(content)   
            add_dir('[COLOR blue]Next  Page  >>>>[/COLOR]', match[0], 2, logos + 'spankingtube.png', fanart)
        except:
            pass

def play_spankingtube_video(url):
    #xbmc.log("Play spankingtube URL: " + url, xbmc.LOGINFO)
    content = make_request(url).replace('\n', '').replace('\r', '')
    #xbmc.log("Play spankingtube content: " + content, xbmc.LOGINFO)
    try:
        media_url = re.compile('<source src="([^"]+)" type=\'video\/mp4\' label=\'720p\' res=\'720\'\/>').findall(content)[0]
    except:
        media_url = re.compile('<source src="([^"]+)" type=\'video\/mp4\' label=\'540p\' res=\'540\'\/>').findall(content)[0]

    #xbmc.log("Media URL: " + media_url, xbmc.LOGINFO)
    return media_url


def process_spankingtube_categories(url):
    content = make_request(url).replace('\n', '').replace('\r', '')
    #xbmc.log("spankingtube category content: " + content, xbmc.LOGINFO)
    categories = re.compile('<div class="col-12 col-sm-12 col-md-6 col-lg-6 col-xl-4 mt-2"> <a href="([^"]+)">.+?<div class="float-left title-truncate">([^"]+)<\/div>', re.DOTALL).findall(content)
    for video_url,name in categories:
        #xbmc.log("spankingtube category: " + name, xbmc.LOGINFO)
        add_dir(name.strip(), "https://www.spankingtube.com/" + video_url, 2, logos + 'spankingtube.png', fanart)
