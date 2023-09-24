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
from resources.content import load_selected_content, save_selected_content

selected_content = load_selected_content()

def process_xhamster_content(url, mobile=True):
    global selected_content
    if "select_category" in url:
        dialog = xbmcgui.Dialog()
        choices = ["Straight", "Shemale", "Gay"]
        choice_idx = dialog.select("Select Content", choices)
        if choice_idx != -1:
            selected_content = '' if choices[choice_idx] == "Straight" else choices[choice_idx].lower()
            url = f"https://xhamster.com/{selected_content}" if selected_content else "https://xhamster.com"
            
    if "/search/" in url:
        if selected_content:
            url += f"?orientations={selected_content}"
    save_selected_content(selected_content)

    if "categories" in url:
        process_xhamster_categories(url, mobile=True)
    else:
        url_prefix = f"https://xhamster.com/{selected_content}/" if selected_content else "https://xhamster.com/"
        if not any(term in url for term in ["categories", "search", "/newest/"]):
            url = url_prefix + "newest/1/"
        content = make_request(url, mobile=True)
        if content:
            add_basic_dirs()
            process_content_matches(content, url, mobile=True)

def add_basic_dirs():
    add_dir("Select Category", "https://xhamster.com/select_category", 2, logos + 'xvideos.png', fanart)
    add_dir('[COLOR blue]Search[/COLOR]', 'xhamster', 5, logos + 'xhamster.png', fanart)

def process_content_matches(content, url, mobile=True):
    match = re.compile('<a href="([^"]*)".+?<img src="([^"]*)" alt="([^"]*)"></noscript>', re.DOTALL).findall(content)
    for url, thumb, name in match:
        name = name.replace('&amp;', '&').replace('&quot;', '"').replace('&#39;', '`')
        add_link(name , url, 4, thumb, fanart)
    add_next_button(content)

def add_next_button(content):
    try:
        match = re.compile('href="([^"]*)" rel="next"').findall(content)
        next_page_url = html.unescape(match[0])
        add_dir('[COLOR blue]Next  Page  >>>>[/COLOR]',next_page_url , 2, logos + 'xhamster.png', fanart)
    except:
        match = re.compile('data-page="next" href="([^"]*)">').findall(content)
        next_page_url = html.unescape(match[0])
        add_dir('[COLOR blue]Next  Page  >>>>[/COLOR]',next_page_url , 2, logos + 'xhamster.png', fanart)
        

def ContextCategory():
    global selected_content

    categories = {'straight': 1, 'shemale': 2, 'gay': 3}
    selected_key = utils.selector('Select category', categories.keys(), sort_by=lambda x: categories[x])
    if selected_key in categories:
        selected_content = selected_key

def process_xhamster_categories(url, mobile=True):
    content = make_request("https://xhamster.com/categories", mobile=True)
    match = re.compile('href="([^"]*)"><img class=".+?" src="([^"]*)" alt="([^"]*)" loading="lazy"', re.DOTALL).findall(content)
    for url, thumb, name in match:
        add_dir(name, url, 2, thumb, fanart)

def play_xhamster_video(url, mobile=True):
    logging.info('play_xhamster_video function called with URL: %s', url)
    content = make_request(url, mobile=True)
    media_url = re.compile('"url":"(.+?)",').findall(content)[0]
    media_url = media_url.replace('/', '')
    return media_url
