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


def process_ashemaletube_content(url):
    if "search" not in url and "newest" not in url:
        url = url + "/videos/newest/?s="
    if 'tags' in url:
        process_ashemaletube_categories(url)
    else:
        content = make_request(url, mobile=True)
        add_dir("Categories", "https://ashemaletube.com/tags/", 2, logos + 'ashemaletube.png', fanart)
        add_dir(f'Search ashemaletube', 'ashemaletube', 5, logos + 'ashemaletube.png', fanart)
        match = re.compile('a href="([^"]*)">.+?src="([^"]*)" alt="([^"]*)"', re.DOTALL).findall(content)
        parsed_url = urlparse(url)
        base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
        for video_url, thumb, name, in match:
            name = html.unescape(name)
            add_link(name, base_url + video_url, 4, thumb, fanart)

        try:
            match = re.compile('<link rel="next" href="(.+?)" />').findall(content)
            next_url = base_url + match[0]
            add_dir('[COLOR blue]Next  Page  >>>>[/COLOR]', next_url, 2, logos + 'ashemaletube.png', fanart)
        except:
            pass

def process_ashemaletube_categories(url):
    content = make_request("https://ashemaletube.com/tags/", mobile=True)
    parsed_url = urlparse(url)
    base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
    categories = re.compile('<a title="([^"]*)" href="([^"]*)" class="btn btn-colored"', re.DOTALL).findall(content)
    for name, video_url in categories:
        add_dir(name, base_url + video_url, 2, logos + 'ashemaletube.png', fanart)

def play_ashemaletube_video(url):
    content = make_request(url, mobile=True)
    #media_url = re.compile('<source src="(.+?)" type="video/mp4">').findall(content)[0]
    media_url = re.compile('"src":"(.+?)"').findall(content)[0]
    media_url = media_url.replace('/', '')
    media_url = media_url.replace('amp;', '')
    xbmc.log("Media URL: " + media_url, xbmc.LOGINFO)
    return media_url
