import sys, os, xbmcaddon, xbmcgui, xbmcplugin, re, urllib.parse, urllib.request, html, ssl
from resources.lib.base_website import BaseWebsite

try:
    _addon = xbmcaddon.Addon()
    _vendor = os.path.join(_addon.getAddonInfo('path'), 'resources', 'lib', 'vendor')
    if _vendor not in sys.path: sys.path.insert(0, _vendor)
except: pass

class HentaigasmWebsite(BaseWebsite):
    def __init__(self, addon_handle):
        super().__init__(name="hentaigasm", base_url="https://hentaigasm.com", search_url="https://hentaigasm.com/?s={}", addon_handle=addon_handle)
        self.sort_options = ['Date', 'Views', 'Likes', 'Title', 'Random']
        self.sort_paths = {'Date': '/?orderby=date', 'Views': '/?orderby=views', 'Likes': '/?orderby=likes', 'Title': '/?orderby=title', 'Random': '/?orderby=rand'}

    def get_headers(self):
        return {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36', 'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8', 'Accept-Language': 'en-US,en;q=0.5'}

    def make_request(self, url):
        try:
            req = urllib.request.Request(url, headers=self.get_headers())
            ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
            with urllib.request.urlopen(req, context=ctx, timeout=60) as r: return r.read().decode('utf-8', errors='ignore')
        except: return None

    def process_content(self, url):
        if not url or url == "BOOTSTRAP": url = self.base_url
        if 's=' not in url and not urllib.parse.urlparse(url).query:
            idx = int(self.addon.getSetting('hentaigasm_sort_by') or '0')
            if 0 <= idx < len(self.sort_options):
                path = self.sort_paths.get(self.sort_options[idx])
                if path:
                    if path.startswith('/?'): url += ('&' if '?' in url else '?') + path[2:]
                    else: url = urllib.parse.urljoin(self.base_url, path)

        content = self.make_request(url)
        if not content: return self.end_directory()

        self.add_dir('[COLOR blue]Search[/COLOR]', '', 5, self.icons['search'])
        self.add_dir('[COLOR blue]Categories[/COLOR]', self.base_url, 8, self.icons['default'])

        for block in re.findall(r'(<div id="post-[\s\S]+?</div>\s*</div>)', content):
            if 'tag-preview' in block: continue

            tm = re.search(r'<h2 class="title"><a href="([^"]+)"[^>]+title="([^"]+)">([^<]+)</a></h2>', block)
            im = re.search(r'<img src="([^"]+)"', block)
            vm = re.search(r'<span class="views"><i class="count">([^<]+)</i>', block)

            if tm and im:
                vid_url, title, thumb = tm.group(1), html.unescape(tm.group(3).strip()), im.group(1)
                if vid_url.startswith('http') and 'hentaigasm.com' not in vid_url: continue
                if "AI JERK OFF" in title.upper(): continue

                cm = re.search(r'class="([^"]+)"', block)
                if cm:
                    genres = [c.replace('tag-', '').replace('-', ' ').title() for c in cm.group(1).split() if c.startswith('tag-') and c != 'tag-preview']
                    if genres: title += f" [COLOR lightgreen][{', '.join(genres[:4])}{'...' if len(genres)>4 else ''}][/COLOR]"
                
                if vm: title += f" [COLOR yellow]({vm.group(1).strip()} Views)[/COLOR]"

                if thumb.startswith('//'): thumb = 'https:' + thumb
                elif not thumb.startswith('http'): thumb = urllib.parse.urljoin(self.base_url, thumb)
                thumb = thumb.replace('/preview/', '/thumbnail/').replace('.webp', '.jpg').replace(' ', '%20')
                thumb += "|" + urllib.parse.urlencode({'User-Agent': self.get_headers()['User-Agent'], 'Referer': self.base_url + '/'})

                self.add_link(title, vid_url, 4, thumb, self.fanart)

        next_match = re.search(r'<a class="nextpostslink" rel="next"[^>]+href="([^"]+)">', content)
        if next_match: self.add_dir('[COLOR blue]Next Page >>>>[/COLOR]', html.unescape(next_match.group(1)), 2, self.icons['default'], self.fanart)
        self.end_directory()

    def process_categories(self, url):
        content = self.make_request(url)
        if not content: return self.end_directory()
        self.add_dir('[COLOR blue]Search[/COLOR]', '', 5, self.icons['search'])
        
        tm = re.search(r'<div class="tagcloud">([\s\S]+?)</div>', content)
        if tm:
            for link, name in re.findall(r'<a href="([^"]+)"[^>]+>([^<]+)</a>', tm.group(1)):
                if '/genre/' in link: self.add_dir(name.strip(), link, 2, self.icons['default'], self.fanart)
        self.end_directory()

    def play_video(self, url):
        content = self.make_request(url)
        if not content: return
        match = re.search(r'file:\s*"([^"]+)"', content) or re.search(r'<source[^>]+src=["\']([^"\']+\.mp4)["\']', content)
        if match:
            vurl = match.group(1)
            p = urllib.parse.urlparse(vurl)
            vurl = urllib.parse.urlunparse(p._replace(path=urllib.parse.quote(p.path.lstrip('.'))))
            if vurl.startswith('//'): vurl = 'https:' + vurl
            vurl += f"|User-Agent={urllib.parse.quote(self.get_headers()['User-Agent'])}"
            li = xbmcgui.ListItem(path=vurl); li.setProperty('IsPlayable', 'true')
            xbmcplugin.setResolvedUrl(self.addon_handle, True, li)
        else: self.notify_error("Video source not found")

    def search(self, query):
        if query: self.process_content(self.search_url.format(urllib.parse.quote_plus(query)))