import re
import xbmc
from ..functions import add_dir, add_link, make_request, fanart, logos
import xbmcgui
import xbmcplugin
import xbmcaddon
import urllib.parse as urllib_parse
import logging
import json
import re
import xbmc
import urllib.request
import urllib.error
import six
import logging
from urllib.parse import urlparse
import urllib.parse as urllib_parse
import html

def process_redtube_content(url, page=1):
    if "search" not in url and "/newest" not in url:
        url = url + "/newest"
    if page == 1:
        add_dir(f'Search redtube', 'redtube', 5, logos + 'redtube.png', fanart)
    content = make_request(url)
    match = re.compile('class="video_link.+?data-o_thumb="([^"]+).+?duration">\s*(?:<span.+?</span>)?\s*([\d:]+).+?href="([^"]+)"\s*>\s*(.*?)\s*<', re.DOTALL).findall(content)
        # Get the base URL part from the input URL
    parsed_url = urlparse(url)
    base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
    for thumb, duration, url, name in match:
        clean_url = html.unescape(url)  # Bereinigen der URL mit html.unescape()
        clean_name = html.unescape(name)  # Bereinigen des Namens mit html.unescape()
        add_link(clean_name + ' [COLOR lime]('+ duration + ')[/COLOR]', base_url + clean_url, 4, thumb, fanart)
    try:
        match = re.compile('<link rel="next" href="([^"]+)" />').findall(content)
        add_dir('[COLOR blue]Next  Page  >>>>[/COLOR]', match[0], 2, logos + 'redtube.png', fanart)
    except:
        pass


def play_redtube_video(url):
    content = make_request(url)
    video_page_url = re.compile('{"format":"mp4","videoUrl":"(.+?)","remote":true}],').findall(content)[0]
    video_page_url = video_page_url.replace('\\', '')
    
    # Anfrage an die zusätzliche Seite
    video_page_content = make_request(video_page_url)
    
    # Extrahieren aller verfügbaren Videolinks und Qualitäten
    available_qualities = re.compile('(\d+?)","videoUrl":"([^"]+)"').findall(video_page_content)
    
    # Sortieren der verfügbaren Qualitäten in absteigender Reihenfolge
    available_qualities.sort(key=lambda x: int(x[0]), reverse=True)
    
    # Wählen Sie die beste verfügbare Qualität
    best_quality = available_qualities[0]
    media_url = best_quality[1].replace('\\', '')
    
    return media_url
