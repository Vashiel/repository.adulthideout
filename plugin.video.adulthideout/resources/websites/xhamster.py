import re
import xbmc
import xbmcgui
import xbmcplugin
import xbmcaddon
import urllib.parse as urllib_parse
import logging
import sys
from urllib.parse import urlparse
import html
import json
from resources.content import load_selected_content, save_selected_content
from ..functions import add_dir, add_link, make_request, fanart, logos
import urllib.request
import urllib.error
from urllib.parse import urljoin

selected_content = load_selected_content()
addon_handle = int(sys.argv[1])


def process_xhamster_content(url, mobile=True):
    global selected_content
    if "select_category" in url:
        dialog = xbmcgui.Dialog()
        choices = ["Straight", "Shemale", "Gay"]
        choice_idx = dialog.select("Select Content", choices)
        if choice_idx != -1:
            selected_content = '' if choices[choice_idx] == "Straight" else choices[choice_idx].lower()
            url = f"https://xhamster.com/{selected_content}" if selected_content else "https://xhamster.com"
                
    save_selected_content(selected_content)

    if "categories" in url:
        process_xhamster_categories(url, mobile=mobile)
    else:
        url_prefix = f"https://xhamster.com/{selected_content}/" if selected_content else "https://xhamster.com/"
        if not any(term in url for term in ["categories", "search", "/newest/"]):
            url = url_prefix + "newest/1/"
        content = make_request(url, mobile=mobile)
        if content:
            add_basic_dirs()
            process_content_matches(content, url, mobile=mobile)

def add_basic_dirs():
    add_dir("Select Category", "https://xhamster.com/select_category", 2, logos + 'xvideos.png', fanart)
    add_dir('[COLOR blue]Search[/COLOR]', 'xhamster', 5, logos + 'xhamster.png', fanart)

def process_content_matches(content, url, mobile=True):
    match = re.compile('<a href="([^"]*)".+?<img src="([^"]*)" alt="([^"]*)"></noscript>', re.DOTALL).findall(content)
    for url, thumb, name in match:
        name = name.replace('&amp;', '&').replace('&quot;', '"').replace('&#39;', '`')
        add_link(name, url, 4, thumb, fanart)
    add_next_button(content)

def add_next_button(content):
    try:
        match = re.search(r'href="([^"]*)" rel="next"', content)
        if match:
            next_page_url = html.unescape(match.group(1))
            add_dir('[COLOR blue]Next Page >>>>[/COLOR]', next_page_url, 2, logos + 'xhamster.png', fanart)
        else:
            match = re.search(r'data-page="next" href="([^"]*)">', content)
            if match:
                next_page_url = html.unescape(match.group(1))
                add_dir('[COLOR blue]Next Page >>>>[/COLOR]', next_page_url, 2, logos + 'xhamster.png', fanart)
    except Exception as e:
        logging.error("Failed to add next button: %s", e)

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



def make_request_with_headers(url, headers, timeout=10):
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return response.read().decode('utf-8')
    except urllib.error.HTTPError as e:
        logging.error('HTTPError beim Abrufen von %s: %s', url, e)
        return None
    except urllib.error.URLError as e:
        logging.error('URLError beim Abrufen von %s: %s', url, e)
        return None
    except Exception as e:
        logging.error('Allgemeiner Fehler beim Abrufen von %s: %s', url, e)
        return None

def play_video(videourl):
    logging.info('Video wird abgespielt: %s', videourl)
    try:
        listitem = xbmcgui.ListItem(path=videourl)
        listitem.setProperty('IsPlayable', 'true')
        xbmcplugin.setResolvedUrl(addon_handle, True, listitem)
    except Exception as e:
        logging.error('Fehler beim Abspielen des Videos: %s', e)

def play_video(videourl):
    logging.info('Video wird abgespielt: %s', videourl)
    try:
        listitem = xbmcgui.ListItem(path=videourl)
        listitem.setProperty('IsPlayable', 'true')
        xbmcplugin.setResolvedUrl(addon_handle, True, listitem)
    except Exception as e:
        logging.error('Fehler beim Abspielen des Videos: %s', e)

def play_xhamster_video(url, mobile=True):
    logging.info('play_xhamster_video function called with URL: %s', url)
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36',
        'Accept': '*/*',
        'Accept-Language': 'de-DE,de;q=0.9',
        'Referer': url,
        'DNT': '1',
        'Connection': 'keep-alive',
    }
    logging.debug('Sende Anfrage an URL: %s mit Headers: %s', url, headers)
    content = make_request_with_headers(url, headers=headers)
    
    if content:
        media_url_matches = re.findall(r'"(.+?)"', content)
        logging.debug('Gefundene Media-URLs: %s', media_url_matches)
        media_url_matches = [url for url in media_url_matches if url.endswith(('.m3u8', '.mp4')) and "xhamsterlive" not in url and "ads" not in url]
        if media_url_matches:
            for media_url in media_url_matches:
                cleaned_media_url = media_url.replace('\\/', '/')
                if cleaned_media_url.endswith('.m3u8'):
                    logging.info(f'Gefundene Media-URL: {cleaned_media_url}')
                    m3u8_content = make_request_with_headers(cleaned_media_url, headers=headers)
                    if m3u8_content:
                        resolution_matches = re.findall(r'#EXT-X-STREAM-INF:.*?RESOLUTION=(\d+x\d+).*?\n(.+?\.m3u8)', m3u8_content)
                        if resolution_matches:
                            sorted_resolutions = sorted(resolution_matches, key=lambda x: int(x[0].split('x')[1]), reverse=True)
                            highest_resolution_url = sorted_resolutions[0][1]
                            full_video_url = urljoin(cleaned_media_url, highest_resolution_url)
                            logging.info(f'Stream wird in höchster Qualität abgespielt: {sorted_resolutions[0][0]} - {full_video_url}')
                            play_video(full_video_url)
                            return full_video_url
                        else:
                            logging.error('Keine gültigen Auflösungen in der m3u8-Datei gefunden.')
                    else:
                        logging.error('Fehler beim Abrufen der m3u8-Datei.')
                elif cleaned_media_url.endswith('.mp4'):
                    logging.info(f'Fallback auf MP4: {cleaned_media_url}')
                    resolution_matches = re.findall(r'multi=\d+x\d+:(\d+p)', cleaned_media_url)
                    if resolution_matches:
                        highest_resolution = max(resolution_matches, key=lambda x: int(x.replace('p', '')))
                        highest_quality_url = cleaned_media_url.replace('_TPL_', highest_resolution)
                        logging.info(f'Fallback-Video wird in höchster Qualität abgespielt: {highest_quality_url}')
                        play_video(highest_quality_url)
                        return highest_quality_url
                    else:
                        logging.error('Keine gültige .h264.mp4-URL gefunden.')
        
        else:
            logging.error('Keine gültige Media-URL gefunden für %s', url)
    else:
        logging.error('Fehler beim Abrufen des Inhalts von %s', url)
    
    return None
