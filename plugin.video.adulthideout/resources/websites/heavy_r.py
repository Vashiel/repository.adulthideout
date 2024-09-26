import re
import xbmc
import xbmcvfs
from ..functions import add_dir, add_link, make_request, fanart, logos
import xbmcgui
import xbmcplugin
import xbmcaddon
import urllib.parse as urllib_parse
import logging
from urllib.parse import urlparse, urljoin
import subprocess
import shlex
import os
import xbmcvfs
from kodi_six import xbmc, xbmcaddon

addon = xbmcaddon.Addon()

def process_heavy_r_content(url, mode=None):
    if "search" not in url and "newest" not in url:
        url = url
    if url == 'https://www.heavy-r.com/categories/':
        process_heavy_r_categories(url)
    else:
        content = make_request(url)
        add_dir('[COLOR blue]Search[/COLOR]', 'heavy-r', 5, logos + 'heavy-r.png', fanart)
        add_dir("Categories", "https://www.heavy-r.com/categories/", 2, logos + 'heavy-r.png', fanart)
        match = re.compile('<a href="([^"]+)" class="image">.+?<img src="([^"]+)".+?alt="([^"]+)"', re.DOTALL).findall(content)
        parsed_url = urlparse(url)
        base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
        for url, thumb, name in match:
            full_url = urljoin(base_url, url)
            add_link(name, full_url, 4, thumb, fanart)

        try:
            match = re.compile('<li><a class="nopopoff" href="([^"]+)">Next</a></li>').findall(content)
            add_dir('[COLOR blue]Next  Page  >>>>[/COLOR]', base_url + match[0], 2, logos + 'heavy-r.png', fanart)
        except:
            pass

def process_heavy_r_categories(url):
    content = make_request(url)
    parsed_url = urlparse(url)
    base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
    categories = re.compile('<a href="([^"]*)" class="image nopopoff">.+?<img src="([^"]*)" alt="([^"]*)" class="img-responsive">', re.DOTALL).findall(content)
    for video_url, thumb, name in categories:
        full_url = urljoin(base_url, video_url)
        add_dir(name, full_url, 2, base_url + thumb, fanart)
    

def play_heavy_r_video(url):
    content = make_request(url)
    media_url = re.compile('<source type="video/mp4" src="([^"]+)">').findall(content)[0]

    curl_command = [
        "curl", media_url,
        "-H", "sec-ch-ua: \"Not/A)Brand\";v=\"8\", \"Chromium\";v=\"126\", \"Google Chrome\";v=\"126\"",
        "-H", "Referer: https://www.heavy-r.com/",
        "-H", "sec-ch-ua-mobile: ?0",
        "-H", "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        "-H", "Range: bytes=0-",
        "-H", "sec-ch-ua-platform: \"Windows\"",
        "--output", "video.mp4"
    ]

    profile = xbmcvfs.translatePath(addon.getAddonInfo('profile'))
    curl_path = os.path.join(profile, 'curl')
    if not os.path.exists(curl_path):
        os.makedirs(curl_path)

    video_path = os.path.join(curl_path, 'video.mp4')
    curl_command[-1] = video_path

    process = subprocess.run(curl_command, capture_output=True, text=True, shell=True)

    if process.returncode == 0:
        return video_path
    else:
        xbmc.log(f"Error downloading video: {process.stderr}", level=xbmc.LOGERROR)
        return None
