import re
import xbmc
from ..functions import add_dir, add_link, make_request, fanart, logos
import xbmcgui
import xbmcplugin
import urllib.parse as urllib_parse
from urllib.parse import urlparse
import html
from resources.content import load_selected_content, save_selected_content

selected_content = load_selected_content()

def process_xvideos_content(url):
    global selected_content
    if "select_category" in url:
        dialog = xbmcgui.Dialog()
        choices = ["Straight", "Shemale", "Gay"]
        choice_idx = dialog.select("Select Content", choices)
        if choice_idx != -1:
            selected_content = '' if choices[choice_idx] == "Straight" else choices[choice_idx].lower()
            url = f"https://xvideos.com/{selected_content}" if selected_content else "https://xvideos.com"
        else:
            return
    if "p=" not in url and "?k=" in url:
        url = url + f"&typef={selected_content}&p=1" if selected_content else url
    content = make_request(url)
    if content:
        add_basic_dirs()
        process_content_matches(content, url)
    save_selected_content(selected_content)

def add_basic_dirs():
    add_dir("Select Category", "https://xvideos.com/select_category", 2, logos + 'xvideos.png', fanart)
    add_dir('[COLOR blue]Search[/COLOR]', 'xvideos', 5, logos + 'xvideos.png', fanart)

def process_content_matches(content, url):
    match = re.compile('<img src=".+?" data-src="([^"]*)"(.+?)<p class="title"><a href="([^"]*)" title="([^"]*)".+?<span class="duration">([^"]*)</span>', re.DOTALL).findall(content)
    parsed_url = urlparse(url)
    base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
    
    for thumb, dummy, relative_url, name, duration in match:
        name = name.replace('&amp;', '&').replace('&quot;', '"').replace('&#39;', '`')
        relative_url = relative_url.replace('THUMBNUM/', '')
        add_link(name + ' [COLOR lime]('+ duration + ')[/COLOR]', base_url + relative_url, 4, thumb, fanart)
    add_next_button(content, url)

def add_next_button(content, url):
    match = re.findall('<li><a href="([^"]*)" class="no-page next-page">', content)
    if not match:
        return
    next_page_url = html.unescape(match[0])
    parsed_url = urlparse(next_page_url)
    if not bool(parsed_url.netloc):
        parsed_base_url = urlparse(url)
        next_page_url = f"{parsed_base_url.scheme}://{parsed_base_url.netloc}{next_page_url}"
    add_dir('[COLOR blue]Next  Page  >>>>[/COLOR]', next_page_url , 2, logos + 'xvideos.png', fanart)

def play_xvideos_video(url):
    content = make_request(url)
    high_quality = re.search(r"html5player\.setVideoHLS\('(.+?)'\)", content)
    med_quality = re.search(r"html5player\.setVideoUrlHigh\('(.+?)'\)", content)
    low_quality = re.search(r"html5player\.setVideoUrlLow\('(.+?)'\)", content)

    if high_quality:
        return high_quality.group(1)
    elif med_quality:
        return med_quality.group(1)
    elif low_quality:
        return low_quality.group(1)
    else:
        raise ValueError("No video found")
