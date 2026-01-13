import sys, os, json, re, urllib.parse
import xbmc, xbmcaddon, xbmcgui, xbmcplugin
from resources.lib.base_website import BaseWebsite

try:
    ADDON = xbmcaddon.Addon()
    ADDON_PATH = ADDON.getAddonInfo('path')
    VENDOR_PATH = os.path.join(ADDON_PATH, 'resources', 'lib', 'vendor')
    if VENDOR_PATH not in sys.path:
        sys.path.insert(0, VENDOR_PATH)
except: pass

try:
    import cloudscraper
    HAS_CLOUDSCRAPER = True
except ImportError:
    HAS_CLOUDSCRAPER = False
    import requests

class BeegWebsite(BaseWebsite):
    def __init__(self, addon_handle):
        super().__init__(name='beeg', base_url='https://beeg.com', search_url='https://beeg.com/search?q={}', addon_handle=addon_handle)
        self.scraper = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'windows', 'desktop': True}) if HAS_CLOUDSCRAPER else requests.Session()
        self.scraper.headers.update({'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36', 'Referer': 'https://beeg.com/', 'Origin': 'https://beeg.com'})
        self.sort_options = []

    def make_request(self, url):
        try:
            r = self.scraper.get(url, timeout=20)
            return r.text if r.status_code == 200 else None
        except: return None

    def process_content(self, url):
        final_url = url
        if url == "BOOTSTRAP" or url == self.base_url or url == self.base_url + "/":
            final_url = "https://store.externulls.com/facts/tag?id=27173&limit=24&offset=0"
        elif "/tag/" in url:
            final_url = f"https://store.externulls.com/facts/tag?slug={url.split('/tag/')[-1].strip('/')}&limit=24&offset=0"
        elif url == "TAGS_MENU":
            self.add_dir('Pornstars', 'CAT_TYPE:human', 2, self.icons.get('categories'))
            self.add_dir('Productions', 'CAT_TYPE:productions', 2, self.icons.get('categories'))
            self.add_dir('Categories', 'CAT_TYPE:other', 2, self.icons.get('categories'))
            self.end_directory()
            return
        elif url.startswith("CAT_TYPE:"):
             return self.process_categories(url.split(":")[1])

        if "id=27173" in final_url:
            self.add_dir('[COLOR blue]Search[/COLOR]', '', 5, self.icons.get('search'))
            self.add_dir('[COLOR yellow]Categories[/COLOR]', 'TAGS_MENU', 2, self.icons.get('categories'))

        try:
            headers = self.scraper.headers.copy()
            headers.update({'Accept': 'application/json, text/plain, */*', 'Sec-Fetch-Dest': 'empty', 'Sec-Fetch-Mode': 'cors', 'Sec-Fetch-Site': 'cross-site'})
            r = self.scraper.get(final_url, headers=headers, timeout=20)
            if r.status_code != 200: raise Exception()
            data = r.json()
        except: return self.notify_error("API Error") or self.end_directory()

        count = 0
        if isinstance(data, list):
            for v in data:
                try:
                    vid = str(v.get('file', {}).get('id', ''))
                    if not vid: continue
                    title = f"Video {vid}"
                    for d in v.get('file', {}).get('data', []):
                        if d.get('cd_column') == 'sf_name': title = d.get('cd_value', title); break
                    
                    thumb = self.icons.get('default')
                    if v.get('fc_facts') and v['fc_facts'][0].get('fc_thumbs'):
                        thumb = f"https://thumbs.externulls.com/videos/{vid}/{v['fc_facts'][0]['fc_thumbs'][0]}.webp?size=1280x720"
                    
                    self.add_link(title, f"{self.base_url}/{vid}", 4, thumb, self.fanart)
                    count += 1
                except: pass

        if count >= 20:
            if "offset" in final_url:
                c = int(re.search(r'offset=(\d+)', final_url).group(1))
                nxt = re.sub(r'offset=\d+', f'offset={c+24}', final_url)
                self.add_dir(f"[COLOR blue]Next Page ({c//24 + 2})[/COLOR]", nxt, 2, self.icons.get('next'))
            else:
                self.add_dir("[COLOR blue]Next Page (2)[/COLOR]", final_url + "&offset=24", 2, self.icons.get('next'))
        self.end_directory()

    def process_categories(self, cat_key):
        try:
            r = self.scraper.get("https://store.externulls.com/tag/facts/tags?get_original=true&slug=index", headers=self.scraper.headers, timeout=20)
            data = r.json()
            tags = data[cat_key] if cat_key in data else [t for s in data.values() if isinstance(s, list) for t in s]
            tags.sort(key=lambda x: x.get('tg_name', '').lower())
            
            for t in tags:
                if not t.get('tg_name') or not t.get('tg_slug'): continue
                icon = self.icons.get('default')
                if t.get('pt_photo'):
                     icon = f"https://img.externulls.com/photos/v/{t['pt_photo']}.jpg"
                elif t.get('thumbs') and t['thumbs'][0].get('crops'):
                    icon = f"https://thumbs.externulls.com/photos/{t['thumbs'][0]['id']}/to.webp?crop_id={t['thumbs'][0]['crops'][0]['id']}&size_new=300x300"
                
                self.add_dir(t['tg_name'].title(), f"https://store.externulls.com/facts/tag?slug={t['tg_slug']}&limit=24&offset=0", 2, icon)
        except: pass
        self.end_directory()

    def search(self, query):
        if not query: return
        try:
            r = self.scraper.get("https://store.externulls.com/tag/facts/tags?get_original=true&slug=index", headers=self.scraper.headers, timeout=20)
            tags = [t for s in r.json().values() if isinstance(s, list) for t in s]
            matches = [t for t in tags if query.lower() in t.get('tg_name', '').lower()]
            
            if not matches: return self.notify_error(f"No results for: {query}")
            if len(matches) == 1:
                self.process_content(f"https://store.externulls.com/facts/tag?slug={matches[0]['tg_slug']}&limit=24&offset=0")
                return

            for t in matches:
                icon = self.icons.get('default')
                if t.get('pt_photo'):
                     icon = f"https://img.externulls.com/photos/v/{t['pt_photo']}.jpg"
                elif t.get('thumbs') and t['thumbs'][0].get('crops'):
                    icon = f"https://thumbs.externulls.com/photos/{t['thumbs'][0]['id']}/to.webp?crop_id={t['thumbs'][0]['crops'][0]['id']}&size_new=300x300"
                self.add_dir(f"{t['tg_name'].title()} [Tag]", f"https://store.externulls.com/facts/tag?slug={t['tg_slug']}&limit=24&offset=0", 2, icon)
            self.end_directory()
        except: self.notify_error("Search Error")

    def play_video(self, url):
        vid = url.split('/')[-1]
        try:
            r = self.scraper.get(f"https://store.externulls.com/facts/file/{vid}", headers={'Accept': 'application/json'}, timeout=20)
            if r.status_code == 200:
                d = r.json()
                hls = d.get('file', {}).get('hls_resources') or d.get('fc_facts', [{}])[0].get('hls_resources')
                vurl = None
                if hls:
                    vurl = f"https://video.externulls.com/{hls.get('fl_cdn_multi')}.m3u8" if hls.get('fl_cdn_multi') else None
                    if not vurl:
                        for q in ['fl_cdn_1080', 'fl_cdn_720', 'fl_cdn_480', 'fl_cdn_360']:
                            if hls.get(q): vurl = f"https://video.externulls.com/{hls[q]}.m3u8"; break
                
                if vurl:
                    li = xbmcgui.ListItem(path=vurl)
                    li.setMimeType('application/vnd.apple.mpegurl')
                    li.setProperty('inputstream', 'inputstream.adaptive')
                    li.setProperty('inputstream.adaptive.manifest_type', 'hls')
                    xbmcplugin.setResolvedUrl(self.addon_handle, True, li)
                    return
        except: pass
        self.notify_error("Video not found")