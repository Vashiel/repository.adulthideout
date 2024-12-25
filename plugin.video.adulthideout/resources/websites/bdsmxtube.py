import re
import xbmc
from ..functions import add_dir, add_link, make_request, fanart, logos
import xbmcgui
import xbmcplugin
import xbmcaddon
import urllib.parse as urllib_parse
from urllib.parse import urlparse
import html
import json


def process_bdsmxtube_content(url):
    xbmc.log("process_bdsmxtube_content: " + url, xbmc.LOGINFO)

    if "videos2" not in url and "categories" not in url:
        url = "https://bdsmx.tube/api/json/videos2/86400/str/latest-updates/60/categories.spanking.1.all...json"

    if  url == "https://bdsmx.tube/categories/":
        process_bdsmxtube_categories(url)
    else:
        add_dir("Categories", "https://bdsmx.tube/categories/", 2, logos + 'bdsmxtube.png', fanart)
        add_dir(f'Search bdsmxtube', 'bdsmxtube', 5, logos + 'bdsmxtube.png', fanart)
        content = make_request(url)
        videos = json.loads(content)['videos']
        for video in videos:
            id=video['video_id']
            title=video['title']
            dir=video['dir']
            thumb=video['scr']
            add_link(title, "https://bdsmx.tube/api/videofile.php?video_id="+id+"&lifetime=8640000", 4, thumb, fanart)

def play_bdsmxtube_video(url):
    #xbmc.log("bdsmxtube video: " + url, xbmc.LOGINFO)

    #https://bdsmx.tube/api/videofile.php?video_id=16397&lifetime=8640000
    content = json.loads(make_request(url))
    coded_url = content[0]['video_url']
    e = coded_url

    t = "АВСDЕFGHIJKLМNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789.,~"
    n = ""
    o = 0
    e = re.sub('/[^АВСЕМA-Za-z0-9\.\,\~]/g', "", e)
    while (o < len(e)):
        r = t.index(e[o])
        o+=1
        s = t.index(e[o])  
        o+=1
        i = t.index(e[o])  
        o+=1
        a = t.index(e[o])  
        o+=1
        r = r << 2 | s >> 4         
        s = (15 & s) << 4 | i >> 2  
        l = (3 & i) << 6 | a        
        n += chr(r) 
        if i != 64:
            n += chr(s)
        if a != 64:
            n += chr(l)
        
    media_url = "https://bdsmx.tube/"+ n
    xbmc.log("bdsmxtube video decoded: " + media_url, xbmc.LOGINFO)
    return media_url

def process_bdsmxtube_categories(url):
    #https://bdsmx.tube/get_file/1/2da464bcd19f22ac91d0285abb70e4813e3e039b35/404000/404517/404517_sd.mp4/?d=480&br=139&ti=1703955172
    category_url="https://bdsmx.tube/api/json/categories/14400/str.toptn.en.json"
    content = make_request(category_url)
    categories = json.loads(content)['categories']

    for category in categories:
        name=category['title']
        dir=category['dir']
        try:
            thumb=category['toptn'][0]['scr']
        except:
            thumb=logos + 'bdsmxtube.png'
        xbmc.log("bdsmxtube category: " + name, xbmc.LOGINFO)
        add_dir(name, "https://bdsmx.tube/api/json/videos2/86400/str/latest-updates/60/categories." + dir +".1.all...json", 2, thumb, fanart)


