import re, sys, urllib.parse, urllib.request, html
from http.cookiejar import CookieJar
import xbmc, xbmcgui, xbmcplugin
from resources.lib.base_website import BaseWebsite

class PorntnWebsite(BaseWebsite):
    def __init__(self, addon_handle):
        super().__init__(name="porntn", base_url="https://porndd.com", search_url="https://porndd.com/search/{}/", addon_handle=addon_handle)
        self.sort_options, self.sort_paths = ["Trending", "Latest", "Most Viewed", "Top Rated", "Longest"], {"Trending": "/", "Latest": "/latest-updates/", "Most Viewed": "/most-viewed/", "Top Rated": "/top-rated/", "Longest": "/longest-videos/"}
        self.cookie_jar = CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.cookie_jar))
        self.opener.addheaders = [('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/5.0 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36')]

    def make_request(self, url, headers=None, data=None):
        try:
            req = urllib.request.Request(url, data=urllib.parse.urlencode(data).encode('utf-8') if data else None, headers=headers or {'Referer': self.base_url})
            with self.opener.open(req, timeout=60) as r: return r.read().decode('utf-8', errors='ignore')
        except: return None

    def process_content(self, url):
        content = self.make_request(url)
        if not content: return self.end_directory()
        self.add_dir('[COLOR blue]Search[/COLOR]', '', 5, self.icons['search'])
        self.add_dir('Categories', f"{self.base_url}/categories/", 8, self.icons['categories'])

        for vurl, title, thumb, dur in re.findall(r'<div class="item[^"]*">\s*<a href="([^"]+)"\s*title="([^"]+)".*?data-original="([^"]+)".*?<div class="duration">([^<]+)</div>', content, re.DOTALL):
            final_vurl = urllib.parse.urljoin(self.base_url, vurl) if not vurl.startswith('http') else vurl
            final_thumb = 'https:' + thumb if thumb.startswith('//') else thumb
            self.add_link(f'{html.unescape(title)} [COLOR yellow]({dur.strip()})[/COLOR]', final_vurl, 4, final_thumb, self.fanart)

        nm = re.search(r'<li class="next"><a href="([^"]+)"', content)
        if nm: self.add_dir("[COLOR blue]Next Page >>>>[/COLOR]", urllib.parse.urljoin(url, nm.group(1)) if not nm.group(1).startswith('http') else nm.group(1), 2, self.icons['default'])
        self.end_directory()

    def process_categories(self, url):
        content = self.make_request(f"{self.base_url}/categories/")
        if not content: return self.end_directory()
        for curl, name, count in re.findall(r'<a class="item" href="([^"]+)".*?<strong class="title">([^<]+)</strong>.*?<div class="videos">([^<]+)</div>', content, re.DOTALL):
            self.add_dir(f"{html.unescape(name.strip())} ({count.strip()})", urllib.parse.urljoin(self.base_url, curl) if not curl.startswith('http') else curl, 2, self.icons['categories'])
        self.end_directory()

    def play_video(self, url):
        c = self.make_request(url)
        if not c: return
        
        vurl = None
        for k in ['video_alt_url2', 'video_alt_url', 'video_url']:
            m = re.search(rf"{k}\s*:\s*['\"](https://[^'\"]+\.mp4[^'\"]*)['\"]", c)
            if m: vurl = m.group(1); break
        
        if not vurl:
            m = re.search(r"[\"'](https?://[^\"']+\.mp4[^\"']*)[\"']", c)
            if m: vurl = m.group(1).replace('&amp;', '&')

        if vurl:
            hdr = {'User-Agent': self.opener.addheaders[0][1], 'Referer': url, 'Cookie': "; ".join([f"{x.name}={x.value}" for x in self.cookie_jar])}
            li = xbmcgui.ListItem(path=vurl + '|' + urllib.parse.urlencode(hdr))
            li.setMimeType('video/mp4'); li.setProperty('Referer', url)
            xbmcplugin.setResolvedUrl(self.addon_handle, True, li)
        else: self.notify_error("Video not found")