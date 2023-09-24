import re
import xbmc
from ..functions import add_dir, add_link, make_request, fanart, logos
import xbmcgui
import xbmcplugin
import xbmcaddon
import urllib.parse as urllib_parse
import logging
from urllib.parse import urlparse, urljoin
import html

def process_motherless_content(url):
    content = None
    if "motherless://" in url or "shouts" in url:
        process_motherless_categories(url)
    elif "groups" in url:
        process_motherless_groups(url)
    elif "galleries" in url:
        process_motherless_galleries(url)
    else:
        if not any(term in url for term in ["term", "viewed", "porn", "/gv"]):
            url = url + "/videos/recent"
        content = make_request(url)
    if content:
        add_basic_dirs()
        process_category_paths(url)
        process_content_matches(content)

def add_basic_dirs():
    basic_dirs = [
        ('[COLOR blue]Search[/COLOR]', 'motherless', 5),
        ("Categories", "https://motherless.com/shouts?page=1", 2),
        ("Groups", "https://motherless.com/groups/", 2),
        ("Galleries", "https://motherless.com/galleries/updated", 2)
    ]
    for name, url, mode in basic_dirs:
        add_dir(name, url, mode, logos + 'motherless.png', fanart)

def process_category_paths(current_url):
    category_paths = [
        ("/live/videos", "Being Watched Now"),
        ("/videos/viewed", "Most Viewed"),
        ("/videos/commented", "Most Commented"),
    ]
    if "/live/videos" in current_url:
        add_dir('[COLOR yellow]Reload[/COLOR]', 'https://motherless.com/live/videos', 2, logos + 'motherless.png', fanart)
    for path, name in category_paths:
        url = "https://motherless.com" + path
        add_dir(name, url, 2, logos + 'motherless.png', fanart)

def process_content_matches(content):
    match = re.compile('<a href="([^"]+)" class="img-container" target="_self">.+?<span class="size">([:\\d]+)</span>.+?<img class="static" src="https://(.+?)".+?alt="([^"]+)"/>', re.DOTALL).findall(content)
    for url, duration, thumb, name in match:
        name = name.replace('&amp;', '&').replace('&quot;', '"').replace('&#039;', '\'')
        if "/g/" in url or "/G" in url:
            add_link(name + ' [COLOR lime]('+ duration + ')[/COLOR]', "https://motherless.com" + url, 4, 'http://' + thumb, fanart)
        else:
            add_link(name + ' [COLOR lime]('+ duration + ')[/COLOR]', url, 4, 'http://' + thumb, fanart)
    add_next_button(content)


def process_motherless_categories(url):
    content = make_request(url)
    categories = re.compile('<a href="/porn/([^"]+)/videos" class="pop plain"', re.DOTALL).findall(content)
    
    category_dict = {
        "extreme": [],
        "gay": [],
        "transsexual": [],
        "straight": []
    }
    
    for url in categories:
        if "extreme" in url:
            category_dict["extreme"].append(url)
        elif "gay" in url:
            category_dict["gay"].append(url)
        elif "transsexual" in url:
            category_dict["transsexual"].append(url)
        else:
            category_dict["straight"].append(url)
            
    for category, urls in category_dict.items():
        for url in urls:
            formatted_name = format_category_name(url)
            add_dir(formatted_name, f'https://motherless.com/porn/{url}/videos', 2, logos + 'motherless.png', fanart)
            
def format_category_name(category_url):
    return category_url.replace("-", " ").capitalize()


def process_motherless_groups(url):
    content = make_request(url)
    match = re.compile('src="https://([^"]*)".+?<h1 class="group-bio-name">.+?<a href="/g/([^"]*)">\s*(.+?)\s*</a>', re.DOTALL).findall(content)
    for thumb, url, name in match:
        name = html.unescape(name)
        url = 'https://motherless.com/gv/' + url
        add_dir(name, url, 2, "http://" + thumb , fanart)
    add_next_button(content)

def process_motherless_galleries(url):
    content = make_request(url)
    match = re.compile('<img class="static" src="https://([^"]*)".+?<a href="/G([^"]*)" target="_self" class="gallery-data pop plain" title="([^"]*)">.+?<span class="info">.+?<span>\s*(\d+)\s*Videos', re.DOTALL).findall(content)
    for thumb, url, name, videos in match:
        name = html.unescape(name)
        if int(videos) > 0:
            url = 'https://motherless.com/GV' + url
            add_dir(name, url, 2, "http://" + thumb , fanart)
    add_next_button(content)

def add_next_button(content):
    try:
        match = re.compile('<link rel="next" href="(.+?)"/> ').findall(content)
        if match:
            print("Next URL: ", match[0])
            add_dir('[COLOR blue]Next  Page  >>>>[/COLOR]',  match[0], 2, logos + 'motherless.png', fanart)
    except Exception as e:
        print(f"An error occurred while adding the next button: {e}")
        
def play_motherless_video(url):
    content = make_request(url)
    media_url = re.compile("__fileurl = 'https://(.+?)';").findall(content)[0]
    media_url = 'http://' + media_url
    return media_url
