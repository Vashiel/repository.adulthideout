# -*- coding: utf-8 -*-

'''
Copyright (C) 2017

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program. If not, see <http://www.gnu.org/licenses/>
'''

import urllib, urllib2, re, os, sys, urlparse
import xbmc, xbmcplugin, xbmcgui, xbmcaddon

mysettings = xbmcaddon.Addon(id='plugin.video.adulthideout')
profile = mysettings.getAddonInfo('profile')
home = mysettings.getAddonInfo('path')
fanart = xbmc.translatePath(os.path.join(home, 'fanart.jpg'))
icon = xbmc.translatePath(os.path.join(home, 'icon.png'))
logos = xbmc.translatePath(os.path.join(home, 'logos\\'))  # subfolder for logos
homemenu = xbmc.translatePath(os.path.join(home, 'resources', 'playlists'))


#define webpages in order they were added.
redtube = 'https://www.redtube.com'
xvideos = 'http://www.xvideos.com'
xhamster = 'https://xhamster.com'
vikiporn = 'http://www.vikiporn.com'
tube8 = 'http://www.tube8.com'
pornxs = 'http://pornxs.com'
pornhd = 'http://www.pornhd.com'
lubetube = 'http://lubetube.com/'
porncom = 'http://www.porn.com'
youjizz = 'http://www.youjizz.com'
motherless = 'http://motherless.com'
eporner = 'http://www.eporner.com'
tubepornclassic = 'http://www.tubepornclassic.com'
efukt = 'http://efukt.com/'
pornhub = 'http://pornhub.com'
pornsocket = 'http://pornsocket.com'
hentaigasm = 'http://hentaigasm.com/'
ashemaletube = 'https://www.ashemaletube.com'
youporn = 'http://www.youporn.com'
heavyr = 'http://www.heavy-r.com'
gotporn ='http://www.gotporn.com'
empflix = 'http://www.empflix.com'
txxx ='http://www.txxx.com'
fantasti = 'http://fantasti.cc'
upornia = 'http://upornia.com'
yespornplease = 'http://yespornplease.com'
uflash = 'http://www.uflash.tv'
tubegalore = 'http://www.tubegalore.com'
youav = 'http://www.youav.com'
pornktube = 'http://www.pornktube.com'
javtasty = 'https://www.javwhores.com'
nudeflix = 'http://www.nudeflix.com'
luxuretv = 'http://en.luxuretv.com'
datoporn = 'http://datoporn.co'

def menulist():
    try:
        mainmenu = open(homemenu, 'r')
        content = mainmenu.read()
        mainmenu.close()
        match = re.compile('#.+,(.+?)\n(.+?)\n').findall(content)
        return match
    except:
        pass

def make_request(url):
    try:
        req = urllib2.Request(url)
        if yespornplease in url:
            req.add_header('User-Agent', 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.11 (KHTML, like Gecko) SamsungBrowser/3.3 Chrome/23.0.1271.64 Safari/537.11')
        else:
            req.add_header('User-Agent', 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.11 (KHTML, like Gecko) Chrome/23.0.1271.64 Safari/537.11')
        response = urllib2.urlopen(req, timeout = 60)
        link = response.read()
        response.close()
        return link
    except urllib2.URLError, e:
        print 'We failed to open "%s".' % url
        if hasattr(e, 'code'):
            print 'We failed with error code - %s.' % e.code
        elif hasattr(e, 'reason'):
            print 'We failed to reach a server.'
            print 'Reason: ', e.reason

def home():
    add_dir('...[COLOR yellow]  Home  [/COLOR]...', '', None, icon, fanart)

#define main directory and starting page
def main():
    add_dir('A Shemale Tube [COLOR yellow] Videos[/COLOR]', ashemaletube + '/videos/newest/' , 2, logos + 'ashemaletube.png', fanart)
    #(removing Beeg for now, until i find a solution for it)
    #add_dir('Beeg [COLOR yellow] Videos[/COLOR]', beeg_url(), 2, logos + 'beeg.png', fanart)
    add_dir('Efukt [COLOR yellow] Videos[/COLOR]', efukt, 2, logos + 'efukt.png', fanart)
    add_dir('Empflix [COLOR yellow] Videos[/COLOR]', empflix + '/new/' , 2, logos + 'empflix.png', fanart)
    #(removing Eporner for now, until i find a solution for it)
    #add_dir('Eporner [COLOR yellow] Videos[/COLOR]', eporner + '/0/', 2, logos + 'eporner.png', fanart)
    add_dir('Fantasti.cc [COLOR yellow] Videos[/COLOR]', fantasti + '/videos/upcoming/', 2, logos + 'fantasti.png', fanart)
    add_dir('Datoporn.com [COLOR yellow] Videos[/COLOR]', datoporn + '/category/films+XXX', 2, logos + 'datoporn.png', fanart)
    add_dir('Hentaigasm [COLOR yellow] Videos[/COLOR]', hentaigasm, 2, logos + 'hentaigasm.png', fanart)
    add_dir('Heavy-R [COLOR yellow] Videos[/COLOR]', heavyr + '/videos/' , 2, logos + 'heavyr.png', fanart)
    add_dir('JavTasty [COLOR yellow] Videos[/COLOR]', javtasty + '/latest-updates/', 2, logos + 'javtasty.png', fanart)
    add_dir('LubeTube [COLOR yellow] Videos[/COLOR]', lubetube + 'view', 2, logos + 'lubetube.png', fanart)
    add_dir('LuxureTV [COLOR yellow] Videos[/COLOR]', luxuretv + '/page1.html', 2, logos + 'luxuretv.png', fanart)
    add_dir('Motherless [COLOR yellow] Videos[/COLOR]', motherless + '/videos/recent?page=1', 2, logos + 'motherless.png', fanart)
    #add_dir('Nudeflix [COLOR yellow] Videos[/COLOR]', nudeflix + '/browse/cover?order=released', 2, logos + 'nudeflix.png', fanart)
    add_dir('PornCom [COLOR yellow] Videos[/COLOR]', porncom + '/videos?p=1', 2, logos + 'porncom.png', fanart)
    add_dir('PornHD [COLOR yellow] Videos[/COLOR]', pornhd, 2, logos + 'pornhd.png', fanart)
    add_dir('PornHub [COLOR yellow] Videos[/COLOR]', pornhub +'/video?o=cm', 2, logos + 'pornhub.png', fanart)
    # removing because videolinks are now all in html5 hidden div containers. AH can't handle this.
    #add_dir('PornkTube [COLOR yellow] Videos[/COLOR]', pornktube , 2, logos + 'pornktube.png', fanart)
    # (removing pornsocket, till i find out how to handle this Error code 22)
    #add_dir('Pornsocket [COLOR yellow] Videos[/COLOR]', pornsocket + '/media-gallery.html?display=list&filter_mediaType=4&limitstart=0', 2, logos + 'pornsocket.png', fanart)
    add_dir('PornXS [COLOR yellow] Videos[/COLOR]', pornxs + '/browse/sort-time/', 2, logos + 'pornxs.png', fanart)
    add_dir('RedTube [COLOR yellow] Videos[/COLOR]', redtube + '/newest', 2, logos + 'redtube.png', fanart)
    add_dir('Tube8 [COLOR yellow] Videos[/COLOR]', tube8 + '/newest.html',  2, logos + 'tube8.png', fanart)
    #(removing Tubegalore for now, until i find a solution for it)
    #add_dir('Tubegalore [COLOR yellow] Videos[/COLOR]', tubegalore + '/new?orientation=straight-and-shemale',  2, logos + 'tubegalore.png', fanart)
    add_dir('Tubepornclassic [COLOR yellow] Videos[/COLOR]', tubepornclassic + '/latest-updates/', 2, logos + 'tpc.png', fanart)
    add_dir('Txxx [COLOR yellow] Videos[/COLOR]', txxx + '/latest-updates/', 2, logos + 'txxx.png', fanart)
    add_dir('Uflash.TV [COLOR yellow] Videos[/COLOR]', uflash + '/videos?o=mr&type=public', 2, logos + 'uflash.png', fanart)
    #(removing Upornia for now, until i find a solution for it)
    #add_dir('Upornia [COLOR yellow] Videos[/COLOR]', upornia + '/latest-updates/', 2, logos + 'upornia.png', fanart)
    add_dir('ViKiPorn [COLOR yellow] Videos[/COLOR]', vikiporn + '/latest-updates/', 2, logos + 'vikiporn.png', fanart)
    add_dir('xHamster [COLOR yellow] Videos[/COLOR]', xhamster + '/new/1.html', 2, logos + 'xhamster.png', fanart)
    add_dir('Xvideos [COLOR yellow] Videos[/COLOR]', xvideos + '/new/1/' , 2, logos + 'xvideos.png', fanart)
    add_dir('YesPornPlease [COLOR yellow] Videos[/COLOR]', yespornplease + '/?s=date', 2, logos + 'yespornplease.png', fanart)
    add_dir('YouJizz [COLOR yellow] Videos[/COLOR]', youjizz + '/newest-clips/1.html', 2, logos + 'youjizz.png', fanart)
    add_dir('YouPorn [COLOR yellow] Videos[/COLOR]', youporn + '/browse/time/', 2, logos + 'youporn.png', fanart)



#Search part. Add url + search expression + searchtext
def search():
    try:
        keyb = xbmc.Keyboard('', '[COLOR yellow]Enter search text[/COLOR]')
        keyb.doModal()
        if (keyb.isConfirmed()):
            searchText = urllib.quote_plus(keyb.getText())
        if 'ashemaletube' in name:
            url = ashemaletube + '/search/' + searchText + '/page1.html'
            start(url)
        elif 'beeg' in name:
            url = beeg_search_url(searchText)
            start(url)
        elif 'efukt' in name:
            url = efukt + '/search/' + searchText + '/'
            start(url)
        elif 'eporner' in name:
            url = eporner + '/search/' + searchText
            start(url)
        elif 'hentaigasm' in name:
            url = hentaigasm + '/?s=' + searchText
            start(url)
        elif 'heavy-r' in name:
            url = heavyr + '/free_porn/' + searchText + '.html'
            start(url)
        elif 'lubetube.com' in name:
            url = lubetube + 'search/title/' + searchText.replace('+', '_') + '/'
            start(url)
        elif 'motherless' in name:
            if 'Groups' in name:
                url = motherless + '/search/groups?term=' + searchText + '&member=&sort=date&range=0&size=0'
                motherless_groups_cat(url)
            if 'Galleries' in name:
                url = motherless + '/search/Galleries?term=' + searchText + '&member=&sort=date&range=0&size=0'
                motherless_galeries_cat(url)
            else:
                url = motherless + '/term/videos/' + searchText
                start(url)
        elif 'fantasti' in name:
            if 'collections' in name:
                url = 'http://fantasti.cc/search/' + searchText + '/collections/trending/'
                fantasti_collections(url)
            else:
                url = 'http://fantasti.cc/search/' + searchText + '/tube/popular/'
                start(url)
        elif '.porn.com' in name:
            url = porncom + '/videos/search?q=' + searchText
            start(url)
        elif 'pornhd.com' in name:
            url = pornhd + '/search?search=' + searchText
            start(url)
        elif 'pornhub' in name:
            url = pornhub + '/video/search?search=' + searchText
            start(url)
        elif 'pornsocket' in name:
            url = pornsocket + '/media-gallery.html?filter_search=&amp;filter_tag=' + searchText
            start(url)
        elif 'pornxs' in name:
            url = 'http://pornxs.com/search.php?s=' + searchText
            start(url)
        elif 'redtube.com' in name:
            url = redtube + '/?search=' + searchText
            start(url)
        elif 'tube8.com' in name:
            url = tube8 + '/searches.html?q=' + searchText
            start(url)
        elif 'tubepornclassic' in name:
            url = 'http://www.tubepornclassic.com/search/' + searchText + '/'
            start(url)
        elif 'vikiporn.com' in name:
            url = vikiporn + '/search/?q=' + searchText
            start(url)
        elif 'xhamster.com' in name:
            url = 'https://xhamster.com/search.php?q=' + searchText
            start(url)
        elif 'xvideos.com' in name:
            url = xvideos + '/?k=' + searchText
            start(url)
        elif 'youjizz.com' in name:
            url = youjizz + '/search/' + searchText + '-1.html'
            start(url)
        elif 'youporn' in name:
            url = youporn + '/search/?query=' + searchText
            start(url)
        elif 'empflix' in name:
            url = empflix + '/search.php?what=' + searchText
            start(url)
        elif 'txxx' in name:
            url = txxx + '/search/?s=' + searchText
            start(url)
        elif 'upornia' in name:
            url = upornia + '/search/?q=' + searchText
            start(url)
        elif 'yespornplease' in name:
            url = 'http://yespornplease.com/search?q=' + searchText
            start(url)
        elif '.uflash.tv' in name:
            url = uflash + '/search?search_type=videos&search_query=' + searchText
            xbmc.log("Search url uflash: %s" % url, xbmc.LOGERROR)
            start(url)
        elif 'tubegalore' in name:
            url = tubegalore + '/search/?q='  + searchText
            start(url)
        elif 'pornktube' in name:
            url = pornktube + '/search/?q='  + searchText
            start(url)
        elif '.javtasty.com' in name:
            url = 'https://www.javwhores.com/search/' + searchText  + '/'
            start(url)
        elif 'nudeflix' in name:
            url = nudeflix +'/search/'+ searchText
            start(url)
        elif 'luxuretv' in name:
            url = luxuretv + '/search/videos/' + searchText + '/'
            start(url)
        elif 'dato' in name:
            url = datoporn + '/?k=' + searchText + '&op=search'
            start(url)
    except:
        pass

def start(url):
    home()
    if 'ashemaletube' in url:
        add_dir('[COLOR lightgreen]ashemaletube.com     [COLOR red]Search[/COLOR]', ashemaletube, 1, logos + 'ashemaletube.png', fanart)
        add_dir('[COLOR lime]Categories[/COLOR]', ashemaletube + '/tags/', 30, logos + 'ashemaletube.png', fanart)
        add_dir('[COLOR lime]Models[/COLOR]', ashemaletube + '/models/', 55, logos + 'ashemaletube.png', fanart)
        content = make_request(url)
        if 'model' in url:
            match = re.compile('<div class="thumb vidItem" data-video-id=".+?">.+?<a href="([^"]*)" >.+?src="([^"]*)" alt="([^"]*)".+?<span class="fs11 viddata flr"(.+?)>', re.DOTALL).findall(content)
            for url, thumb, name, dummy in match:
                name = name.replace('&amp;', '&')
                if 'HD' in dummy:
                    add_link(name + '[COLOR yellow]' +' [HD]' +'[/COLOR]', ashemaletube + url, 4, thumb, fanart)
                else:
                    add_link(name, ashemaletube + url, 4, thumb, fanart)
        else:
            match = re.compile('<div class="thumb vidItem" data-video-id=".+?">.+?<a href="([^"]*)" >.+?src="([^"]*)" alt="([^"]*)".+?<span class="fs11 viddata flr"(.+?)</span>([:\d]+)</span>', re.DOTALL).findall(content)
            for url, thumb, name, dummy, duration in match:
                name = name.replace('&amp;', '&')
                if 'HD' in dummy:
                    add_link(name + '[COLOR yellow]' +' [HD]' +'[/COLOR]' +' [COLOR lime]('+ duration + ')[/COLOR]', ashemaletube + url, 4, thumb, fanart)
                else:
                    add_link(name + ' [COLOR lime]('+ duration + ')[/COLOR]', ashemaletube + url, 4, thumb, fanart)
        try:
            match = re.compile('<link rel="next" href="(.+?)" />').findall(content)
            add_dir('[COLOR blue]Next  Page  >>>>[/COLOR]', ashemaletube + match[0], 2, logos + 'ashemaletube.png', fanart)
        except:
            match = re.compile('<a class="pageitem rightKey" href="(.+?)" title="Next">Next</a>').findall(content)
            add_dir('[COLOR blue]Next  Page  >>>>[/COLOR]', ashemaletube + match[0], 2, logos + 'ashemaletube.png', fanart)

    elif 'beeg' in url:
        add_dir('[COLOR lightgreen]beeg.com     [COLOR red]Search[/COLOR]', beeg_url(), 1, logos + 'beeg.png', fanart)
        try:
            selected_page = re.compile('index/(main|search)/(.+?)/pc').findall(url)[0]
            selected_page_index = int(selected_page[1])
            if selected_page[0] == 'main':
                next_url = beeg_url(selected_page_index + 1)
            else:
                query = re.compile('/pc\?query=(.*?)$').findall(url)[0]
                next_url = beeg_search_url(query, selected_page_index + 1)
        except:
            pass
        try:
            content = make_request(url)
            match = re.compile('\{"title":"([^"]*)","id":"([^"]*)","ps_name":"([^"]*)","nt_name":"([^"]*)","240p":"([^"]*)","480p":"([^"]*)","720p":"([^"]*)"\}').findall(content)
            for title, id, ps, nt, low, mid, high in match:
                thumb = 'http://img.beeg.com/236x177/' + id + '.jpg'
                url = 'http:' + re.sub('\{DATA_MARKERS\}', 'data=vad_ES_103.124.13.54_' + str(beeg_version), high)
                match2 = re.compile('\/key=(.*?)%2Cend=').findall(url)
                if len(match2) > 0:
                    key = match2[0]
                    decoded_key = decode_key(key)
                    url = re.sub('\/key=(.*?)%2Cend=', '/key=' + decoded_key + '%2Cend=', url)
                    add_link(title, url, 70, thumb, fanart)
        except:
            pass
        try:
            add_dir('[COLOR blue]Next Page >>>>[/COLOR]', next_url, 2, logos + 'beeg.png', fanart)
        except:
            pass
    elif 'efukt' in url:
        content = make_request(url)
        add_dir('[COLOR lightgreen]efukt.com     [COLOR red]Search[/COLOR]', efukt, 1, logos + 'efukt.png', fanart)
        match = re.compile('<a href="([^"]*)" title="([^"]*)" class="thumb"><img src="([^"]*)"').findall(content)
        for url, name, thumb in match:
            name = name.replace('&amp;', '&').replace('&quot;', '"').replace('&#039;', '\'')
            add_link(name, url , 4, thumb, fanart)
        try:
            match = re.compile('<a href="([^"]*)"><i class="fa fa-arrow-right"></i></a>').findall(content)
            add_dir('[COLOR blue]Next  Page  >>>>[/COLOR]', efukt + match[0], 2, logos + 'efukt.png', fanart)
        except:
            pass

    elif 'empflix' in url:
        content = make_request(url)
        add_dir('[COLOR lightgreen]empflix.com     [COLOR red]Search[/COLOR]', empflix, 1, logos + 'empflix.png', fanart)
        add_dir('[COLOR lime]Categories[/COLOR]', empflix + '/categories.php',  45, logos + 'empflix.png', fanart)
        add_dir('[COLOR lime]Sorting[/COLOR]', empflix + '/browse.php?category=mr',  46, logos + 'empflix.png', fanart)
        match = re.compile("a class='thumb' href='(.+?)'.+?data-original='(.+?)' alt=\"(.+?)\"><div class='videoDuration'>([:\d]+)</div>", re.DOTALL).findall(content)
        for url, thumb, name, duration in match:
            add_link(name + ' [COLOR lime]('+ duration + ')[/COLOR]', empflix + url , 4, thumb, fanart)
        try:
            match = re.compile('<a class="llNav" href="([^"]+)">').findall(content)
            add_dir('[COLOR blue]Next  Page  >>>>[/COLOR]', empflix + match[0], 2, logos + 'empflix.png', fanart)
        except:
            pass

    elif 'eporner' in url:
        content = make_request(url)
        add_dir('[COLOR lightgreen]eporner.com     [COLOR red]Search[/COLOR]', eporner, 1, logos + 'eporner.png', fanart)
        add_dir('[COLOR lime]Categories[/COLOR]', eporner + '/categories/',  21, logos + 'eporner.png', fanart)
        match = re.compile('<a href="([^"]*)" title="([^"]*)".+?src="([^"]*)".+?<div class="mbtim">(.+?)</div>', re.DOTALL).findall(content)
        for url, name, thumb, duration in match:
            add_link(name + ' [COLOR lime]('+ duration + ')[/COLOR]', eporner + url, 4, thumb, fanart)
        try:
            match = re.compile("<a href='([^']*)' title='Next page'>").findall(content)
            add_dir('[COLOR blue]Next  Page  >>>>[/COLOR]', eporner + match[0], 2, logos + 'eporner.png', fanart)
        except:
            match = re.compile('<a href="([^"]*)" title="Next page">').findall(content)
            add_dir('[COLOR blue]Next  Page  >>>>[/COLOR]', eporner +  match[0], 2, logos + 'eporner.png', fanart)

    elif 'datoporn' in url:
        content = make_request(url)
        add_dir('[COLOR lightgreen]datoporn.com     [COLOR red]Search[/COLOR]', datoporn, 1, logos + 'datoporn.png', fanart)
        add_dir('[COLOR lime]Categories[/COLOR]', 'https://datoporn.co/categories_all',  69, logos + 'datoporn.png', fanart)
        match = re.compile('style="background: url\(\'https://(.+?)/(.+?)\'\) no-repeat;"><span>([:\d]+)</span></a>.+?<div colspan=2 class="vb_title"><a href="https://datoporn.co/(.+?)" class="link"><b>(.+?)</b></a></div>', re.DOTALL).findall(content)
        for dummy, thumb, duration, url, name in match:
            dummy = 'https://' + dummy
            url = 'https://datoporn.co/' + url
            thumb = dummy + '/' + thumb
            content2 = make_request(url)
            match = re.compile('image\|(.+?)\|sources').findall(content2)
            for url in match:
                url = re.sub('640480.*?1280720','', url)
                url = re.sub('360.*?640480','', url)
                url = url.replace('640480|label|mp4|','').replace('|file','').replace('|','').replace('480labelmp4','')
                url = dummy + '/' + url + '/v.mp4'
                add_link(name + ' [COLOR lime]('+ duration + ')[/COLOR]', datoporn + url, 4, thumb , fanart)
        try:
            match = re.compile("<a href='([^']+)'>Next").findall(content)
            add_dir('[COLOR blue]Next  Page  >>>>[/COLOR]', match[0], 2, logos + 'datoporn.png', fanart)
        except:
            pass

    elif 'fantasti' in url:
        content = make_request(url)
        add_dir('[COLOR lightgreen]fantasti.cc     [COLOR red]Search[/COLOR]', fantasti, 1, logos + 'fantasti.png', fanart)
        add_dir('[COLOR lime]Collection[/COLOR]', fantasti + '/videos/collections/popular/31days/', 48, logos + 'fantasti.png', fanart)
        add_dir('[COLOR lime]Category [/COLOR]', fantasti + '/category/',  18, logos + 'fantasti.png', fanart)
        add_dir('[COLOR lime]Sorting [/COLOR]', fantasti + '/videos/popular/today/',  49, logos + 'fantasti.png', fanart)
        try:
            if '#collectionSubmittedVideos' in url:
                match = re.compile('data-vertical-gallery-src="([^"]+)">.+?alt="([^"]+)" src="([^"]+)">', re.DOTALL).findall(content)
                for url, name, thumb in match:
                    url = fantasti + url
                    content2 = make_request(url)
                    match = re.compile('<link rel="canonical" href="([^"]*)" />', re.DOTALL).findall(content2)
                    for url in match:
                        add_link(name, url, 4, thumb, fanart)
            if '/search/' in url:
                match = re.compile('<div class="searchVideo">.+?<a href="/watch/(.+?)/(.+?)/" >.+?<img src="(.+?)"', re.DOTALL).findall(content)
                for url, name, thumb in match:
                    url = fantasti + '/watch/' + '/' + url + '/'+ '/' +  name + '/'
                    name = name.replace('&amp;', '&').replace('&quot;', '"').replace('&#39;', '\'').replace('-', ' ')
                    add_link(name, url, 4, thumb, fanart)
            if '/category/' in url:
                match = re.compile('<span class="v_lenght">(.+?)</span>.+?<a href="/watch/([^"]+)".+?<img alt="([^"]+)"   src="([^"]+)" ', re.DOTALL).findall(content)
                for duration, url, name, thumb in match:
                    name = name.replace('&amp;', '&').replace('&quot;', '"').replace('&#39;', '\'').replace('  ', '')
                    url = fantasti + '/watch/' + url
                    add_link(name + ' [COLOR lime]('+ duration + ')[/COLOR]', url, 4, thumb, fanart)
            else:
                match = re.compile('<a href="([^"]+)"><img src="([^"]+)" alt="([^"]+)".+? <span style="font-size:11px;">\s*(.+?). Uploaded:', re.DOTALL).findall(content)
                for url, thumb, name, duration in match:
                    name = name.replace('&amp;', '&').replace('&quot;', '"').replace('&#39;', '\'').replace('  ', '')
                    url = fantasti + url
                    add_link(name + ' [COLOR lime]('+ duration + ')[/COLOR]', url, 4, thumb, fanart)

        except:
            pass
        try:
            match = re.compile('<a href="([^"]+)">next &gt;&gt').findall(content)
            add_dir('[COLOR blue]Next  Page  >>>>[/COLOR]', fantasti + match[0], 2, logos + 'fantasti.png', fanart)
        except:
            pass

    elif 'hentaigasm' in url:
        add_dir('[COLOR lime]hentaigasm     [COLOR red]Search[/COLOR]', hentaigasm, 1, logos + 'hentaigasm.png', fanart)
        add_dir('[COLOR lime]Categories[/COLOR]', hentaigasm, 29, logos + 'hentaigasm.png', fanart)
        content = make_request(url)
        match = re.compile('title="(.+?)" href="(.+?)">\s*\s*.+?\s*\s*.+?<img src="(.+?)"').findall(content)
        for name, url, thumb in match:
            thumb = thumb.replace(' ', '%20')
            if "Raw" in name :
                add_link('[COLOR lime] [Raw] [/COLOR]' + name, url, 4, thumb, fanart)
            else :
                add_link('[COLOR yellow] [Subbed] [/COLOR]' + name, url, 4, thumb, fanart)
        try:
            match = re.compile("<a href='([^']*)' class=\"next\">»").findall(content)
            add_dir('[COLOR blue]Next  Page  >>>>[/COLOR]', match[0], 2, logos + 'hentaigasm.png', fanart)
        except:
            pass

    elif 'heavy-r' in url:
        add_dir('[COLOR lightgreen]heavy-r       [COLOR red]Search[/COLOR]', heavyr, 1, logos + 'heavyr.png', fanart)
        add_dir('[COLOR lime]Categories[/COLOR]', heavyr + '/categories/', 33, logos + 'heavyr.png', fanart)
        content = make_request(url)
        match = re.compile('<a href="([^"]+)" class="image">.+?src="([^"]+)".+?alt="([^"]+)".+?<span class="duration"><i class="fa fa-clock-o"></i> ([\d:]+)</span>', re.DOTALL).findall(content)
        for url, thumb, name, duration in match:
            add_link(name + ' [COLOR lime]('+ duration + ')[/COLOR]', heavyr + url, 4, thumb, fanart)
        try:
            match = re.compile('<a href="([^"]*)">Next</a>').findall(content)
            add_dir('[COLOR blue]Next  Page  >>>>[/COLOR]', heavyr + match[0], 2, logos + 'heavyr.png', fanart)
        except:
            pass

    elif 'javwhores' in url:
        content = make_request(url)
        add_dir('[COLOR lightgreen].javtasty.com     [COLOR red]Search[/COLOR]', javtasty, 1, logos + 'javtasty.png', fanart)
        add_dir('[COLOR lime]Categories[/COLOR]', javtasty + '/categories/', 64, logos + 'javtasty.png', fanart)
        match = re.compile('<div class="video-item   ">.+?<a href="(.+?)" title="(.+?)".+?data-original="(.+?)".+?<i class="fa fa-clock-o"></i> ([\d:]+)</div>', re.DOTALL).findall(content)
        for url, name, thumb, duration in match:
            add_link(name + ' [COLOR lime]('+ duration + ')[/COLOR]', url, 4, thumb, fanart)
        try:
            if "search" in url:
                match = re.compile('<li class="page-current"><span>.+?</span></li>.+?<li class=".+?"><a href=".+?" data-action=".+?" data-container-id=".+?" data-block-id="list_videos_videos_list_search_result" data-parameters="([^"]*)"').findall(content)
                add_dir('[COLOR blue]Next  Page  >>>>[/COLOR]', 'http://www.javtasty.com/search/1pondo/?mode=async&function=get_block&block_id=list_videos_videos_list_search_result&' + match[0], 2, logos + 'javtasty.png', fanart)
            else:
                match = re.compile('<li class="next"><a href="([^"]*)" data-action="ajax"').findall(content)
                add_dir('[COLOR blue]Next  Page  >>>>[/COLOR]', javtasty + match[0].replace('&amp;','&'), 2, logos + 'javtasty.png', fanart)
        except:
            pass

    elif 'lubetube' in url:
        content = make_request(url)
        add_dir('[COLOR lightgreen]lubetube.com     [COLOR red]Search[/COLOR]', lubetube, 1, logos + 'lubetube.png', fanart)
        add_dir('[COLOR lime]Categories[/COLOR]', lubetube + 'categories', 15, logos + 'lubetube.png', fanart)
        add_dir('[COLOR lime]Pornstars[/COLOR]', lubetube + 'pornstars', 12, logos + 'lubetube.png', fanart)
        match = re.compile('href="(.+?)" title="(.+?)"><img src="(.+?)".+?Length: (.+?)<').findall(content)
        for url, name, thumb, duration in match:
            add_link(name + '[COLOR lime] (' + duration + ')[/COLOR]', url, 4, thumb, fanart)
        try:
            match = re.compile('<a class="next" href="([^"]*)">Next</a>').findall(content)
            add_dir('[COLOR blue]Next  Page  >>>>[/COLOR]', lubetube + match[0], 2, logos + 'lubetube.png', fanart)
        except:
            pass

    elif 'luxuretv' in url:
        content = make_request(url)
        add_dir('[COLOR lightgreen]luxuretv.com     [COLOR red]Search[/COLOR]', luxuretv, 1, logos + 'luxuretv.png', fanart)
        add_dir('[COLOR lime]Categories[/COLOR]', luxuretv + '/channels/', 68, logos + 'luxuretv.png', fanart)
        match = re.compile('<a href="([^"]*)"><img class="img" src="(.+?)" alt="(.+?)".+?<div class="time"><b>([\d:]+)</b></div>', re.DOTALL).findall(content)
        for url, thumb, name, duration in match:
            add_link(name + '[COLOR lime] (' + duration + ')[/COLOR]', url, 4, thumb, fanart)
        try:
            match = re.compile('a href=\'([^"]*)\'>Next').findall(content)
            add_dir('[COLOR blue]Next  Page  >>>>[/COLOR]', luxuretv + '/' +  match[0], 2, logos + 'luxuretv.png', fanart)
        except:
            pass

    elif 'motherless' in url:
        content = make_request(url)
        ###Search in def search(): and media_list(url)
        add_dir('[COLOR lightgreen]motherless.com     [COLOR red]Search[/COLOR]', motherless, 1, logos + 'motherless.png', fanart)
        ####Subfolders
        add_dir('[COLOR lime]Being watched now[/COLOR]', motherless +  '/live/videos',  61, logos + 'motherless.png', fanart)
        add_dir('[COLOR lime]Sorting[/COLOR]', motherless +  '/videos/',  44, logos + 'motherless.png', fanart)
        add_dir('[COLOR magenta]Galleries[/COLOR]', motherless + '/galleries/updated?page=1', 60, logos + 'motherless.png', fanart)
        add_dir('[COLOR magenta]Groups[/COLOR]', motherless + '/groups?s=u', 62, logos + 'motherless.png', fanart)
        ###sending video URL to resolve_url(url)
        match = re.compile('data-frames="12">.+?<a href="([^"]+)".+?src="([^"]+)".+?alt="([^"]+)".+?caption left">([:\d]+)</div>', re.DOTALL).findall(content)
        for url, thumb, name, duration in match:
            name = name.replace('Shared by ', '').replace('&quot;', '"').replace('&#39;', '\'')
            if 'motherless' in url:
                add_link(name + ' [COLOR lime]('+ duration + ')[/COLOR]', url, 4, thumb, fanart)
            else:
                add_link(name + ' [COLOR lime]('+ duration + ')[/COLOR]', motherless + url, 4, thumb, fanart)
        ###Next Button
        try :
            match = re.compile('<a href="([^"]*)" class="pop" rel="[1-9999]">NEXT &raquo;</a></div>').findall(content)
            add_dir('[COLOR blue]Next  Page  >>>>[/COLOR]', motherless + match[0], 2, logos + 'motherless.png', fanart)
        except:
            pass

    elif 'nudeflix' in url:
        content = make_request(url)
        add_dir('[COLOR lightgreen]nudeflix.com     [COLOR red]Search[/COLOR]', nudeflix, 1, logos + 'nudeflix.png', fanart)
        add_dir('[COLOR lime]Categories[/COLOR]', nudeflix,  66, logos + 'nudeflix.png', fanart)
        add_dir('[COLOR lime]Sorting[/COLOR]', nudeflix + '/browse/cover?order=released' , 67, logos + 'nudeflix.png', fanart)
        match = re.compile('<img src="http://([^"]+)" alt="([^"]+)".+?<a href="([^"]+)" class="dvd-info hidden-xs">', re.DOTALL).findall(content)
        for thumb, name, url in match:
            add_dir(name, nudeflix + url, 65, 'http://' + thumb, fanart)
        try :
            match = re.compile('<a href="([^"]*)amp;([^"]*)">\s*<strong>next &raquo;</strong>').findall(content)
            for url, dummy in match:
                add_dir('[COLOR blue]Next  Page  >>>>[/COLOR]', nudeflix + url + dummy, 2, logos + 'nudeflix.png', fanart)
        except:
            pass

    elif '.porn.com' in url:
        content = make_request(url)
        add_dir('[COLOR lightblue].porn.com     [COLOR red]Search[/COLOR]', porncom, 1, logos + 'porncom.png', fanart)
        add_dir('[COLOR lime]Categories[/COLOR]', porncom,  14, logos + 'porncom.png', fanart)
        add_dir('[COLOR lime]HD Porn[/COLOR]', porncom + '/videos/hd',  2, logos + 'porncom.png', fanart)
        match = re.compile('class="thumb"><img src="([^"]*)"(.+?)<a href="/videos/(.+?)" class="title">(.+?)</a><span class="added">(.+?)</span><span class="rating">.+?<i class="icon-thumbs-up">', re.DOTALL).findall(content)
        match = re.compile('class="thumb"><a href="([^"]*)" title="([^"]*)"><img src="([^"]*)"(.+?)</p><p><span>(.+?)</span></p></div></div>', re.DOTALL).findall(content)
        for url, name, thumb, dummy, duration in match:
            if 'hd' in dummy:
                add_link(name + '[COLOR yellow]' +' [HD]' +'[/COLOR]' +' [COLOR lime]('+ duration + ')[/COLOR]', porncom + '/videos/' + url, 4, thumb, fanart)
            else:
                add_link(name + '[COLOR lime]('+ duration + ')[/COLOR]', porncom + '/videos/' + url, 4, thumb, fanart)
        try :
            match = re.compile('</span><a href="([^"]*)" class="btn nav">Next').findall(content)
            add_dir('[COLOR blue]Next  Page  >>>>[/COLOR]', porncom + match[0], 2, logos + 'porncom.png', fanart)
        except:
            pass

    elif 'pornhd' in url:
        add_dir('[COLOR lightgreen]pornhd.com     [COLOR red]Search[/COLOR]', pornhd, 1, logos + 'pornhd.png', fanart)
        add_dir('[COLOR lime]Categories[/COLOR]', pornhd + '/category', 19, logos + 'pornhd.png', fanart)
        add_dir('[COLOR lime]Pornstars[/COLOR]', pornhd + '/pornstars?order=video_count&gender=female', 20, logos + 'pornhd.png', fanart)
        content = make_request(url)
        match = re.compile('<a class="thumb videoThumb popTrigger" href="(.+?)"><img alt="(.+?)"  src="(.+?)".+?<time>(.+?)</time>', re.DOTALL).findall(content)
        for url, name, thumb, duration in match:
            add_link(name + ' [COLOR lime]('+ duration + ')[/COLOR]', pornhd + url, 4, thumb, fanart)
        try:
            match = re.compile('<li class="next ">  <span class="icon jsFilter js-link" data-query-key="page" data-query-value="(.+?)">').findall(content)
            for dummy2 in match:
                add_dir('[COLOR blue]Next  Page  >>>>[/COLOR]', 'https://www.pornhd.com/?page=' + dummy2, 2, logos + 'pornhd.png', fanart)
        except:
            pass

    elif 'pornhub' in url:
        content = make_request(url)
        add_dir('[COLOR lightgreen]pornhub.com     [COLOR red]Search[/COLOR]', pornhub, 1, logos + 'pornhub.png', fanart)
        add_dir('[COLOR lime]Categories[/COLOR]', pornhub + '/categories', 25, logos + 'pornhub.png', fanart)
        match = re.compile('<a href="([^"]+)" title="([^"]+)" class="img " data-related-url=".+?src=".+?".+?alt=".+?".+?data-mediumthumb="([^"]+)".+?<var class="duration">([^<]+)</var>(.+?)</div>', re.DOTALL).findall(content)
        for url, name, thumb, duration, dummy in match:
            name = name.replace('&amp;#039;','\'').replace('&amp;', '&')
            url = url.replace('/view_video.php?viewkey=','')
            if 'HD' in dummy:
                add_link(name + '[COLOR yellow]' +' [HD]' +'[/COLOR]' +' [COLOR lime]('+ duration + ')[/COLOR]', 'https://www.pornhub.com/view_video.php?viewkey=' + url, 4, thumb, fanart)
            else:
                add_link(name + ' [COLOR lime]('+ duration + ')[/COLOR]', 'https://www.pornhub.com/view_video.php?viewkey=' + url, 4, thumb, fanart)
        try:
            match = re.compile('<a href="([^"]+)" class="orangeButton">Next').findall(content)
            add_dir('[COLOR blue]Next  Page  >>>>[/COLOR]', pornhub + match[0].replace('&amp;','&'), 2, logos + 'pornhub.png', fanart)
        except:
            pass

    elif 'pornktube' in url:
        content = make_request(url)
        add_dir('[COLOR lightgreen]pornktube.com     [COLOR red]Search[/COLOR]', pornktube, 1, logos + 'pornktube.png', fanart)
        add_dir('[COLOR lime]Categories[/COLOR]', pornktube, 63, logos + 'pornktube.png', fanart)
        match = re.compile('<a href="([^"]+)"><img src="([^"]+)" alt="([^"]+)".+?<div class="vlength">([^<]+)</div>', re.DOTALL).findall(content)
        for url, thumb, name, duration in match:
            add_link(name + ' [COLOR lime]('+ duration + ')[/COLOR]', pornktube + url, 4, thumb, fanart)
        try:
            match = re.compile('<a href="([^"]+)" class="mpages">Next &raquo;</a>').findall(content)
            add_dir('[COLOR blue]Next  Page  >>>>[/COLOR]', pornktube + match[0], 2, logos + 'pornktube.png', fanart)
        except:
            pass

    elif 'pornsocket' in url:
        content = make_request(url)
        add_dir('[COLOR lightgreen]pornsocket.com     [COLOR red]Search[/COLOR]', pornsocket, 1, logos + 'pornsocket.png', fanart)
        add_dir('[COLOR lime]Categories[/COLOR]', pornsocket + '/categories-media.html', 26, logos + 'pornsocket.png', fanart)
        match = re.compile('<div class="media-duration">\s*([^<]+)</div>\s*<a href="([^"]+)"> <img src="([^"]+)" border="0" alt="([^"]+)"').findall(content)
        for duration, url, thumb, name in match:
            add_link(name + ' [COLOR lime]('+ duration + ')[/COLOR]', pornsocket + url, 4, pornsocket + thumb, fanart)
        match = re.compile('><a title="Next" href="([^"]+)" class="pagenav">Next</a>', re.DOTALL).findall(content)
        add_dir('[COLOR blue]Next  Page  >>>>[/COLOR]', pornsocket + match[0].replace('&amp;','&'), 2, logos + 'pornsocket.png', fanart)

    elif 'pornxs' in url:
        content = make_request(url)
        add_dir('[COLOR lightgreen]pornxs.com     [COLOR red]Search[/COLOR]', pornxs, 1, logos + 'pornxs.png', fanart)
        add_dir('[COLOR lime]Categories[/COLOR]', pornxs + '/new-categories/?mode=static&width=wide', 39, logos + 'pornxs.png', fanart)
        match = re.compile('<a href="([^"]+).html".+?<img src="([^"]+)".+?alt="([^"]+)".+?<div class="time">([:\d]+)<', re.DOTALL).findall(content)
        for url, thumb, name, duration in match:
            add_link(name + ' [COLOR lime]('+ duration + ')[/COLOR]', pornxs + url + '.html', 4, thumb, fanart)
        try:
            match = re.compile('<a class="pagination-next" href="([^"]*)"><span></span></a></li> ').findall(content)
            add_dir('[COLOR blue]Next  Page  >>>>[/COLOR]', pornxs + match[0], 2, logos + 'pornxs.png', fanart)
        except:
            pass

    elif 'redtube' in url:
        content = make_request(url)
        add_dir('[COLOR lightgreen]redtube.com     [COLOR red]Search[/COLOR]', redtube, 1, logos + 'redtube.png', fanart)
        add_dir('[COLOR lime]Sorting[/COLOR]', redtube , 8, logos + 'redtube.png', fanart)
        add_dir('[COLOR lime]Categories[/COLOR]', redtube + '/categories', 9, logos + 'redtube.png', fanart)
        add_dir('[COLOR lime]Channels[/COLOR]', redtube + '/channel/recently-updated', 10, logos + 'redtube.png', fanart)
        try:
            if 'newest' in url:
                match = re.compile('<div class="preloadLine"></div>.+?<a class="video_link js_mpop".+?href="([^"]+)">.+?src="([^"]+)".+?alt="([^"]+)".+?<span class="(.+?)"></span>.+?<span class="duration">.+?([:\d]+)', re.DOTALL).findall(content)
                for url, thumb, name, dummy, duration in match:
                    name = name.replace('&#39;', ' ').replace('&amp;', '&').replace('&quot;', '"').replace('    ', '')
                    if 'hd' in dummy:
                        add_link(name + '[COLOR yellow]' +' [HD]' +'[/COLOR]' +' [COLOR lime]('+ duration + ')[/COLOR]', redtube + url, 4, thumb,  fanart)
                    else:
                        add_link(name + ' [COLOR lime]('+ duration + ')[/COLOR]', redtube + url, 4, thumb,  fanart)

            elif '/redtube/' in url:
                match = re.compile('<div class="widget-video-holder">.+?<a href="([^"]+)" title="([^"]+)".+?span class="video-duration">.+?([:\d]+).+?</span>.+?src="([^"]+)"', re.DOTALL).findall(content)
                for url, name, duration, thumb in match:
                    name = name.replace('&#39;', ' ').replace('&amp;', '&').replace('&quot;', '"').replace('    ', '')
                    add_link(name + ' [COLOR lime]('+ duration + ')[/COLOR]', redtube + url, 4, thumb,  fanart)

            elif 'mostviewed' or 'hot' or 'top' or 'recommended' or 'mostviewed' or 'mostfavored' or 'longest' in url:
                match = re.compile('<div class="widget-video-holder">.+?<a href="([^"]+)" title="([^"]+)" class="video-thumb" >.+?<span class="video-duration">.+?([:\d]+).+?</span>.+?src="([^"]+)"', re.DOTALL).findall(content)
                for url, name, duration, thumb in match:
                    name = name.replace('&#39;', ' ').replace('&amp;', '&').replace('&quot;', '"').replace('    ', '')
                    add_link(name + ' [COLOR lime]('+ duration + ')[/COLOR]', redtube + url, 4, thumb,  fanart)

            else:
                pass

        except:
            pass
        try:
            match = re.compile('rel="next" href="([^"]+)">').findall(content)
            add_dir('[COLOR blue]Next  Page  >>>>[/COLOR]', match[0], 2, logos + 'redtube.png', fanart)
        except:
            pass

    elif 'tube8' in url:
        content = make_request(url)
        add_dir('[COLOR lightgreen]tube8.com     [COLOR red]Search[/COLOR]', tube8, 1, logos + 'tube8.png', fanart)
        add_dir('[COLOR lime]Categories[/COLOR]', tube8 + '/categories.html', 22, logos + 'tube8.png', fanart)
        match = re.compile('class="thumb_box">.+?<a href="([^"]+)"(.+?)src="([^"]+)".+?alt="([^"]+)".+?video_duration">([:\d]+)</div>', re.DOTALL).findall(content)
        for url, dummy, thumb, name, duration in match:
            name = name.replace('&#39;', ' ').replace('&amp;', '&').replace('&quot;', '"').replace('    ', '')
            if 'hdIcon' in dummy:
                add_link(name + '[COLOR yellow]' +' [HD]' +'[/COLOR]' +' [COLOR lime]('+ duration + ')[/COLOR]', url, 4, thumb, fanart)
            else:
                add_link(name + ' [COLOR lime]('+ duration + ')[/COLOR]', url, 4, thumb, fanart)
        match = re.compile('<link rel="next" href="([^"]*)">').findall(content)
        add_dir('[COLOR blue]Next  Page  >>>>[/COLOR]', match[0], 2, logos + 'tube8.png', fanart)

    elif 'tubegalore' in url:
        content = make_request(url)
        add_dir('[COLOR lightgreen]tubegalore.com     [COLOR red]Search[/COLOR]', tubegalore, 1, logos + 'tubegalore.png', fanart)
        add_dir('[COLOR lime]Categories[/COLOR]', tubegalore , 53, logos + 'tubegalore.png', fanart)
        match = re.compile('<span class="source">(.+?)</span>.+?href="/out/?.+?http(.+?)" target="_blank" title="(.+?)">.+?<img src="(.+?)".+?<span class="length">(.+?)</span>', re.DOTALL).findall(content)
        for dummy, url, name, thumb, duration in match:
            url = url.replace('%3A', ':').replace('%2F', '/').replace('%3F', '?').replace('%3D', '=').replace('%26', '&')
            dummy = dummy.replace('</a>', '')
            if 'GotPorn' in dummy :
                pass
            elif 'porn.porn' in dummy:
                pass
            elif 'PornXOom' in dummy:
                pass
            elif 'PorndoePremium' in dummy:
                pass
            elif 'BonerTube' in dummy:
                pass
            elif 'Gay' in name:
                pass
            elif 'Gay' in dummy:
                pass
            elif 'Beeg' in dummy:
                pass
            elif 'Fantasti.cc' in dummy:
                pass
            elif 'MenHDV' in dummy:
                pass
            elif 'Homosexual' in dummy:
                pass
            elif 'BoyfriendTV' in dummy:
                pass
            elif 'Jock' in dummy:
                pass
            else:
                add_link(name + ' [COLOR lime]('+ duration +')[/COLOR]' ' [COLOR yellow]['+ dummy +'][/COLOR]', 'http' + url, 4, thumb, fanart)
        try:
            match = re.compile('<a href="([^"]+)"><i class="fa fa-chevron-right"></i></a>.+?<div class="content-filter"', re.DOTALL).findall(content)
            for url in match:
                url = url.replace('&amp;','&')
                name = tubegalore + url
                add_dir('[COLOR blue]Next  Page  >>>>[/COLOR]', name, 2, logos + 'tubegalore.png', fanart)
        except:
            pass

    elif 'tubepornclassic' in url:
        content = make_request(url)
        add_dir('[COLOR lightgreen]Tubepornclassic   [COLOR red]Search[/COLOR]', tubepornclassic, 1, logos + 'tubepornclassic.png', fanart)
        add_dir('[COLOR lime]Categories[/COLOR]', tubepornclassic + '/categories/old-young/',  38, logos + 'tubepornclassic.png', fanart)
        match = re.compile('<div class="item  ">.+?<a href="([^"]+)" >.+?src="([^"]+).+?<strong class="title">([^"]+)</strong>.*?duration">([^<]+)<', re.DOTALL).findall(content)
        for url, thumb, name, duration in match:
            add_link(name + ' [COLOR lime]('+ duration + ')[/COLOR]',  url,  4, thumb, fanart)
        try:
            match = re.compile('<a href="([^"]*)" data-action=".+?" data-container-id=".+?" data-block-id=".+?" data-parameters=".+?" title=\"Next Page\">Next</a>').findall(content)
            add_dir('[COLOR blue]Next  Page  >>>>[/COLOR]', tubepornclassic + match[0], 2, logos + 'tubepornclassic.png', fanart)
        except:
            pass

    elif 'txxx' in url:
        content = make_request(url)
        add_dir('[COLOR lightgreen]txxx   [COLOR red]Search[/COLOR]', txxx, 1, logos + 'txxx.png', fanart)
        add_dir('[COLOR lime]Categories[/COLOR]', txxx + '/categories/' ,  47, logos + 'txxx.png', fanart)
        match = re.compile('<a href="([^"]+)" class="image js-thumb-pagination".+?<img src="([^"]+)" alt="([^"]+)"(.+?)<div class="thumb-pagination">.+?<div class="thumb__duration">([^<]+)</div>', re.DOTALL).findall(content)
        for url, thumb, name, dummy, duration in match:
            if 'HD' in dummy:
                add_link(name + '[COLOR yellow]' +' [HD]' +'[/COLOR]' +' [COLOR lime]('+ duration + ')[/COLOR]',  url,  4, thumb, fanart)
            else:
                add_link(name + ' [COLOR lime]('+ duration + ')[/COLOR]',  url,  4, thumb, fanart)
        try:
            match = re.compile('<a class=" btn btn--size--l btn--next" href="([^"]+)" title="Next Page"').findall(content)
            add_dir('[COLOR blue]Next  Page  >>>>[/COLOR]', txxx + match[0], 2, logos + 'txxx.png', fanart)
        except:
            pass

    elif '.uflash.tv' in url:
        xbmc.log("saga: Making request to %s" % url, xbmc.LOGERROR)
        content = make_request(url)
        current_url = url
        add_dir('[COLOR lightgreen].uflash.tv   [COLOR red]Search[/COLOR]', uflash, 1, logos + 'uflash.png', fanart)
        add_dir('[COLOR lime]Categories[/COLOR]', uflash + '/videos?o=mr', 54, logos + 'uflash.png', fanart)
        add_dir('[COLOR magenta]Female Exhibitionist Videos[/COLOR]', uflash + '/videos?g=female&o=mr',  2, logos + 'uflash.png', fanart)
        add_dir('[COLOR magenta]Male Exhibitionist Videos[/COLOR]', uflash + '/videos?g=male&o=mr',  2, logos + 'uflash.png', fanart)
        add_dir('[COLOR magenta]Recently Viewed - Exhibitionist Videos[/COLOR]', uflash + '/videos?o=bw',  2, logos + 'uflash.png', fanart)
        match = re.compile('<a href="/video/(.+?)/.+?title="(.+?)">.+?<img src="(.+?)".+?<span class="duration">([^<]+)</span>', re.DOTALL).findall(content)
        for url, name, thumb, duration in match:
            add_link(name + ' [COLOR lime]('+ duration + ')[/COLOR]', 'http://www.uflash.tv/media/player/config.v89x.php?vkey=' + url,  4, 'http://www.uflash.tv/' + thumb, fanart)
        try:
            next_page = uflash_nextpage(current_url, content)
            raise Exception(next_page)
        except Exception as e:
            xbmc.log(str(e), xbmc.LOGERROR)
            pass

    elif 'upornia' in url:
        content = make_request(url)
        add_dir('[COLOR lightgreen]upornia   [COLOR red]Search[/COLOR]', upornia, 1, logos + 'upornia.png', fanart)
        add_dir('[COLOR lime]Categories[/COLOR]', upornia + '/categories/',  50, logos + 'upornia.png', fanart)
        add_dir('[COLOR lime]Models[/COLOR]', upornia + '/models/',  51, logos + 'upornia.png', fanart)
        match = re.compile('class="thumbnail thumbnail-pagination" href="([^"]*)".+?<img src="([^"]*)"alt="([^"]*)".+?class="thumbnail__info__right">([:\d]+)</div>', re.DOTALL).findall(content)

        for url, thumb, name, duration in match:
            add_link(name + ' [COLOR lime]('+ duration + ')[/COLOR]',  url,  4, thumb, fanart)
        try:
            match = re.compile('<li class="next">.+?<a href="(.+?)"', re.DOTALL).findall(content)
            add_dir('[COLOR blue]Next  Page  >>>>[/COLOR]', upornia + match[0], 2, logos + 'upornia.png', fanart)
        except:
            pass

    elif 'vikiporn' in url:
        content = make_request(url)
        add_dir('[COLOR lightgreen]vikiporn.com     [COLOR red]Search[/COLOR]', vikiporn, 1, logos + 'vikiporn.png', fanart)
        add_dir('[COLOR lime]Categories[/COLOR]', vikiporn + '/categories/', 16, logos + 'vikiporn.png', fanart)
        #match = re.compile('<a href="(.+?)">\s*<div class=".+?">\s*<img style=".+?" class=".+?"  src=".+?" data-original="(.+?)" alt="(.+?)" onmouseover=".+?" onmouseout=".+?">\s*<span class=".+?">(.+?)</span>').findall(content)
        match = re.compile('<a href="([^"]*)">.+?src="([^"]*)" alt="(.+?)".+?<span class="time-info">([:\d]+)</span>', re.DOTALL).findall(content)
        for url, thumb, name, duration in match:
            add_link(name + ' [COLOR lime]('+ duration + ')[/COLOR]', url,  4, thumb, fanart)
        match = re.compile('<a href="([^"]*)">NEXT</a>').findall(content)
        add_dir('[COLOR blue]Next  Page  >>>>[/COLOR]', vikiporn + match[0], 2, logos + 'vikiporn.png', fanart)

    elif 'xhamster' in url:
        content = make_request(url)
        add_dir('[COLOR lightgreen]xhamster.com     [COLOR red]Search[/COLOR]', xhamster, 1, logos + 'xhamster.png', fanart)
        add_dir('[COLOR lime]Categories[/COLOR]', xhamster, 17, logos + 'xhamster.png', fanart)
        add_dir('[COLOR lime]Rankings[/COLOR]', xhamster + '/rankings/weekly-top-viewed.html' , 42, logos + 'xhamster.png', fanart)
        add_dir('[COLOR lime]Change Content[/COLOR]', xhamster , 24, logos + 'xhamster.png', fanart)
        match = re.compile('><a href="https://xhamster.com/videos/(.+?)".+?<img src=\'(.+?)\'.+?alt="([^"]*)".+?<b>(.+?)</b>.+?<div class="(.+?)"', re.DOTALL).findall(content)
        for url, thumb, name, duration, dummy in match:
            name = name.replace('&amp;', '&').replace('&quot;', '"').replace('&#39;', '\'')
            if '?from=video_promo' in url:
                pass
            if 'hSpriteHD' in dummy:
                add_link(name + '[COLOR yellow]' +' [HD]' +'[/COLOR]' +' [COLOR lime]('+ duration + ')[/COLOR]', 'http://xhamster.com/videos/' + url, 4, thumb, fanart)
            else:
                add_link(name + ' [COLOR lime]('+ duration +')[/COLOR]', 'http://xhamster.com/videos/' + url, 4, thumb, fanart)
        match = re.compile('<div id="cType"><div class="([^"]*)"></div>').findall(content)
        if "iconL iconTrans" in match :
            match = re.compile('<link rel="next" href="([^"]*)"><link rel="dns-prefetch"').findall(content)
            add_dir('[COLOR blue]Next  Page  >>>>[/COLOR]', match[0] + '?content=shemale', 2, logos + 'xhamster.png', fanart)
        if "iconL iconGays" in match :
            match = re.compile('<link rel="next" href="([^"]*)"><link rel="dns-prefetch"').findall(content)
            add_dir('[COLOR blue]Next  Page  >>>>[/COLOR]', match[0] + '?content=gay', 2, logos + 'xhamster.png', fanart)
        if "iconL iconStraight" in match :
            match = re.compile('<link rel="next" href="([^"]*)"><link rel="dns-prefetch"').findall(content)
            add_dir('[COLOR blue]Next  Page  >>>>[/COLOR]', match[0] + '?content=straight', 2, logos + 'xhamster.png', fanart)
        try:
            match = re.compile('<a href=\'(.+?)\' class=\'last\' overicon=\'iconPagerNextHover\'><div class=\'icon iconPagerNext\'>').findall(content)
            match = [item.replace('&amp;', '&') for item in match]
            for url in match:
                if "search" in url:
                    add_dir('[COLOR blue]Next  Page  >>>>[/COLOR]', match[0] , 2, logos + 'xhamster.png', fanart)
                else:pass
        except:
            pass

    elif 'xvideos' in url:
        content = make_request(url)
        add_dir('[COLOR lightgreen]xvideos.com     [COLOR red]Search[/COLOR]', xvideos, 1, logos + 'xvideos.png', fanart)
        add_dir('[COLOR lime]Categories[/COLOR]', xvideos,  27, logos + 'xvideos.png', fanart)
        add_dir('[COLOR lime]Pornstars[/COLOR]', xvideos + '/pornstars/2weeks',  32, logos + 'xvideos.png', fanart)
        add_dir('[COLOR lime]Rankings[/COLOR]', xvideos + '/best' , 71, logos + 'xvideos.png', fanart)
        if 'profiles' in url:
            match = re.compile('<a href="([^"]*)"><img src="([^"]+)"(.+?)title="([^"]*)">.+?<strong>(.+?)</strong>', re.DOTALL).findall(content)
            for url, thumb, dummy, name, duration in match:
                name = name.replace('&amp;', '&').replace('&quot;', '"').replace('&#39;', '`')
                url = url.replace('THUMBNUM/','')
                add_link(name + ' [COLOR lime]('+ duration + ')[/COLOR]', xvideos + url, 4, thumb, fanart)
        else:
            match = re.compile('<a href="([^"]*)"><img src=".+?" data-src="([^"]*)"(.+?)title="([^"]*)".+?<span class="duration">(.+?)</span></span>', re.DOTALL).findall(content)
            for url, thumb, dummy, name, duration in match:
                name = name.replace('&amp;', '&').replace('&quot;', '"').replace('&#39;', '`')
                url = url.replace('THUMBNUM/','')
                if '>HD+<' in dummy:
                    add_link(name + '[COLOR yellow]' +' [1080p]' +'[/COLOR]' +' [COLOR lime]('+ duration + ')[/COLOR]', xvideos + url, 4, thumb, fanart)
                elif '>HD<' in dummy:
                    add_link(name + '[COLOR yellow]' +' [720p]' +'[/COLOR]' +' [COLOR lime]('+ duration + ')[/COLOR]', xvideos + url, 4, thumb, fanart)
                else:
                    add_link(name + ' [COLOR lime]('+ duration + ')[/COLOR]', xvideos + url, 4, thumb, fanart)
        try:
            match = re.compile('<a href="([^"]+)" class="no-page next-page">Next</a>').findall(content)
            match = [item.replace('&amp;', '&') for item in match]
            add_dir('[COLOR blue]Next  Page  >>>>[/COLOR]', xvideos + match[0], 2, logos + 'xvideos.png', fanart)
        except:
            pass

    elif 'youav' in url:
        add_dir('[COLOR blue]Can\'t see text? Turn your skin font to arial based[/COLOR]', youav, 2, logos + 'youav.png', fanart)
        add_dir('[COLOR lime]Categories[/COLOR]', youav + '/categories', 34, logos + 'youav.png', fanart)
        content = make_request(url)
        match = re.compile('<a href="/video/(.+?)/.+?>.+?<div class=".+?">.+?<img src="(.+?)" onerror="this.src=\'images/404sub.jpg\'" title="(.+?)".+?<div class="duration">.+?([:\d]+).+?</div>', re.DOTALL).findall(content)
        for url, thumb, name, duration in match:
            add_link(name + ' [COLOR lime]('+ duration + ')[/COLOR]', 'http://www.youav.com/load.php?pid=' + url, 4, thumb, fanart)
        try:
            match = re.compile('<a href="([^"]*)" class="prevnext">&raquo;</a></li></ul>').findall(content)
            add_dir('[COLOR blue]Next  Page  >>>>[/COLOR]', match[0], 2, logos + 'youav.png', fanart)
        except:
            pass

    elif 'youjizz' in url:
        content = make_request(url)
        add_dir('[COLOR lightgreen]youjizz.com  [COLOR red]Search[/COLOR]', youjizz, 1, logos + 'youjizz.png', fanart)
        add_dir('[COLOR lime]Categories[/COLOR]', youjizz + '/newest-clips/1.html' , 28, logos + 'youjizz.png', fanart)
        match = re.compile('data-original="([^"]+)"(.+?)<div class="video-title"><a href=\'([^\']+)\'>(.+?)</a>&nbsp;</div>.+?<span class="time">([:\d]+)</span>', re.DOTALL).findall(content)
        for thumb, dummy, url, name, duration in match:
            if 'hd' in dummy:
                add_link(name + '[COLOR yellow]' +' [HD]' +'[/COLOR]'+ ' [COLOR lime]('+ duration + ')[/COLOR]', 'https://www.youjizz.com' + url, 4, 'https:' + thumb, fanart)
            else:
                add_link(name + ' [COLOR lime]('+ duration + ')[/COLOR]', 'https://www.youjizz.com' + url, 4, 'https:' + thumb, fanart)
        try:
            match = re.compile('<a href="([^"]+)">Next', re.DOTALL).findall(content)
            add_dir('[COLOR blue]Next  Page  >>>>[/COLOR]', youjizz + match[0], 2, logos + 'youjizz.png', fanart)
        except:
            pass

    elif 'youporn' in url:
        add_dir('[COLOR lightgreen]youporn.com  [COLOR red]Search[/COLOR]', youporn, 1, logos + 'youporn.png', fanart)
        add_dir('[COLOR lime]Categories[/COLOR]', youporn + '/categories/', 31, logos + 'youporn.png', fanart)
        add_dir('[COLOR lime]Sorting[/COLOR]', youporn, 43, logos + 'youporn.png', fanart)
        content = make_request(url)
        #match = re.compile('<a href="([^"]*)" class=\'video-box-image\'>.+?<img src="(.+?)" class=".+?" alt=\'(.+?)\'(.+?)<span class="video-box-duration">.+?([:\d]+).+?</span>', re.DOTALL).findall(content)
        match = re.compile('<a href="([^"]*)" class=\'video-box-image\'>.+?alt=\'(.+?)\'.+?data-original="(.+?)".+?<div class="video-duration">([:\d]+)</div>.+?<div class="video-hd-vr-icons">(.+?)</div>', re.DOTALL).findall(content)
        for url, name, thumb, duration, dummy in match:
            if 'icon icon-hd-text' in dummy:
                add_link(name + '[COLOR yellow]' +' [HD]' +'[/COLOR]' + ' [COLOR lime]('+ duration + ')[/COLOR]', youporn + url, 4, thumb, fanart)
            else:
                add_link(name + ' [COLOR lime]('+ duration + ')[/COLOR]', youporn + url, 4, thumb, fanart)
        try:
            match = re.compile('<link rel="next" href="([^"]*)" />').findall(content)
            add_dir('[COLOR blue]Next  Page  >>>>[/COLOR]', match[0], 2, logos + 'youporn.png', fanart)
        except:
            pass

    elif 'yespornplease' in url:
        content = make_request(url)
        add_dir('[COLOR lightgreen]yespornplease    [COLOR red]Search[/COLOR]', yespornplease, 1, logos + 'yespp.png', fanart)
        add_dir('[COLOR lime]Categories[/COLOR]', yespornplease + '/categories', 52, logos + 'yespp.png', fanart)
        if 'search' in url:
            match = re.compile('class="video-link" href="([^"]*)">.+?<img src="([^"]*)".+?alt="([^"]*)".+?<div class="duration">([:\d]+)</div>', re.DOTALL).findall(content)
            for url, thumb, name, duration in match:
                url = 'http://yespornplease.com'+ url
                add_link(name + ' [COLOR lime]('+ duration + ')[/COLOR]', url,  4, 'http:' + thumb, fanart)
        else:
            match = re.compile('class="video-link" href="([^"]*)">.+?<img src="([^"]*)".+?alt="([^"]*)".+?<div class="duration">([:\d]+)</div>', re.DOTALL).findall(content)
            for url, thumb, name, duration in match:
                url = 'http://yespornplease.com'+ url
                add_link(name + ' [COLOR lime]('+ duration + ')[/COLOR]', url,  4, 'http:' + thumb, fanart)
        try:
            match = re.compile('</li><li><a href="(.+?)" class="prevnext">Next &raquo;</a></li> </ul></div>').findall(content)
            add_dir('[COLOR blue]Next  Page  >>>>[/COLOR]', yespornplease + match[0], 2, logos + 'yespp.png', fanart)
        except:
            pass

def pornhd_categories(url):
    home()
    content = make_request(url)
    match = re.compile('<a href="([^"]*)">.+?alt="([^"]*)".+?data-original="([^"]*)"', re.DOTALL).findall(content)
    for url, name, thumb in match:
        add_dir(name, pornhd + url, 2, thumb, fanart)#


def pornhd_pornstars(url):
    home()
    content = make_request(url)
    match = re.compile('<li class="pornstar">.+?<a href="(.+?)">.+?data-original="(.+?)".+?alt="(.+?)"', re.DOTALL).findall(content)
    for url, thumb, name in match:
        add_dir(name, pornhd + url, 2, thumb, fanart)
    try:
        match = re.compile('<li class="next ">  <span class="icon jsFilter js-link" data-query-key="page" data-query-value="(.+?)">').findall(content)
        for dummy2 in match:
            add_dir('[COLOR blue]Next  Page  >>>>[/COLOR]', 'https://www.pornhd.com/pornstars?page=' + dummy2, 20, logos + 'pornhd.png', fanart)
    except:
        pass

def eporner_categories(url):
    home()
    content = make_request(url)
    match = re.compile('href="/category/([^"]*)" title="([^"]*)"><img src="([^"]*)"').findall(content)
    for url, name, thumb in match:
        add_dir(name, eporner + '/category/' + url, 2, thumb, fanart)


def youav_categories(url) :
    home()
    content = make_request(url)
    match = re.compile('<a href="([^"]*)">.+?<div class="thumb-overlay">.+?<img src="([^"]*)" title="([^"]*)" ', re.DOTALL).findall(content)
    for url, thumb, name in match:
        add_dir(name, youav + url, 2, youav + thumb, fanart)

def lubtetube_pornstars(url):
    home()
    content = make_request(url)
    match = re.compile('class="score">(.+?)</strong></span><a class="frame" href="/(.+?)"><img src="(.+?)" alt="(.+?)"', re.DOTALL).findall(content)
    for duration, url, thumb, name in match:
        duration = duration.replace('<strong>', ' ')
        add_dir(name + ' [COLOR lime]('+ duration + ')[/COLOR]', lubetube + url,  2, lubetube + thumb, fanart)
    try:
        match = re.compile('<a class="next" href="([^"]*)">Next</a>').findall(content)
        add_dir('[COLOR blue]Next  Page  >>>>[/COLOR]', lubetube + match[0], 12, logos + 'lubetube.png', fanart)
    except:
        pass

def lubetube_categories(url):
    home()
    content = make_request(url)
    match = re.compile('href="http://lubetube.com/search/adddate/cat/([^"]*)"><img src="(.+?)" alt="(.+?)"').findall(content)
    for url, thumb, name in match:
        add_dir(name, lubetube + 'search/adddate/cat/' + url,  2, logos + 'lubetube.png', fanart)

def porncom_channels_list(url):
    home()
    content = make_request(url)
    match = re.compile('href="/videos/(.+?)" title="(.+?)"').findall(content)[31:200]
    for url, name in match:
        add_dir(name, porncom + '/videos/' + url,  2, logos + 'porncom.png', fanart)

def motherless_galeries_cat(url):
    home()
    add_dir('[COLOR lightgreen]motherless.com Galleries    [COLOR red]Search[/COLOR]', motherless + '/search/Galleries', 1, logos + 'motherless.png', fanart)
    content = make_request(url)
    match = re.compile('href="/G(.+?)".+?src="(.+?)".+?alt="(.+?)"', re.DOTALL).findall(content)
    for url, thumb, name in match:
        name = name.replace('&amp;', '&').replace('&quot;', '"').replace('&#39;', '\'')
        url = '/GV' + url
        add_dir(name, motherless + url, 2, thumb, fanart)
    match = re.compile('<a href="([^"]*)" class=".+?" rel="[1-9999]">NEXT &raquo;</a></div>').findall(content)
    add_dir('[COLOR blue]Next  Page  >>>>[/COLOR]', motherless + match[0], 60, logos + 'motherless.png', fanart)


def motherless_groups_cat(url):
    home()
    add_dir('[COLOR lightgreen]motherless.com Groups    [COLOR red]Search[/COLOR]', motherless + '/search/groups?term=', 1, logos + 'motherless.png', fanart)
    content = make_request(url)
    match = re.compile('<a href="/g/(.+?)">.+?src="(.+?)".+?class="grunge motherless-red">.+?(.+?)</a>', re.DOTALL).findall(content)
    for url, thumb, name in match:
        name = name.replace('&amp;', '&').replace('&quot;', '"').replace('&#39;', '\'').replace('  ', '')
        add_dir(name, motherless + '/gv/' + url, 2, thumb, fanart)
    match = re.compile('<a href="([^"]*)" class="pop" rel="[1-9999]">NEXT &raquo;</a></div>').findall(content)
    add_dir('[COLOR blue]Next  Page  >>>>[/COLOR]', motherless + match[0], 62, logos + 'motherless.png', fanart)

def motherless_being_watched_now(url):
    home()
    content = make_request(url)
    match = re.compile("<a href=\"(.+?)\" title=\"All Media\">").findall(content)
    add_dir('[COLOR lime]REFRESH[COLOR orange]  Page[COLOR red]  >>>>[/COLOR]', motherless + match[0], 61, logos + 'motherless.png', fanart)
    match = re.compile('data-frames="12">.+?<a href="([^"]+)".+?src="([^"]+)".+?alt="([^"]+)".+?caption left">([:\d]+)</div>', re.DOTALL).findall(content)
    for url, thumb, name, duration in match:
        name = name.replace('&amp;', '&').replace('&quot;', '"').replace('&#39;', '\'')
        add_link(name + ' [COLOR lime]('+ duration + ')[/COLOR]', url , 4, thumb, fanart)

def redtube_sorting(url):
    home()
    content = make_request(url)
    match = re.compile('<a href="([^"]*)" class="js_setCookieHandle" data-op="linkId" data-what="(hot|top|recommended|mostviewed|mostfavored|longest)" data-ttl="2000">(.+?)</a>', re.DOTALL).findall(content)
    for url, name, dummy in match:
        dummy = dummy.replace(' ','').replace('  ','')
        name = dummy
        add_dir(name , 'https://www.redtube.com' + url, 2, logos + 'redtube.png', fanart)

def redtube_categories(url):
    home()
    content = make_request(url)
    match = re.compile('<a href="(.+?)" title=".+?">.+?<img     alt="(.+?)".+?data-src="(.+?)"', re.DOTALL).findall(content)
    for url, name, thumb in match:
        add_dir(name, 'https://www.redtube.com' +  url, 2, thumb, fanart)

def redtube_channels_cat(url):
    home()
    content = make_request(url)
    match = re.compile('href="/channel/(.+?)" title="(.+?)">').findall(content)
    for url, name in match:
        add_dir(name, redtube + '/channel/' + url, 11, logos + 'redtube.png', fanart)

def redtube_channels_list(url):
    home()
    content = make_request(url)
    match = re.compile('href="([^"]+)" class="channels-list-img">.+?<img src="([^"]+)" alt="([^"]+)">', re.DOTALL).findall(content)
    for url, thumb, name in match:
        if 'https' in thumb:
            add_dir(name, redtube + url, 2, thumb, fanart)
        else:
            add_dir(name, redtube + url, 2, "https:" + thumb, fanart)
    try:
        match = re.compile('rel="next" href="([^"]+)">').findall(content)
        add_dir('[COLOR blue]Next  Page  >>>>[/COLOR]', match[0], 11, logos + 'redtube.png', fanart)
    except:
        pass

def vikiporn_categories(url):
    home()
    content = make_request(url)
    match = re.compile('href="(.+?)">(.+?)<span>(\(\d+\))<').findall(content)[42:]
    for url, name, inum in match:
        inum = inum.replace(')', ' videos)')
        add_dir(name + '[COLOR lime] ' + inum + '[/COLOR]', url,  2, logos + 'vikiporn.png', fanart)

def xhamster_categories(url):
    home()
    content = make_request(url)
    match = re.compile('<a href="https://xhamster.com/channels/([^"]*)"').findall(content)
    for url in match:
        name = url
        name = name.replace('&amp;', '&').replace('&quot;', '"').replace('&#39;', '´').replace('new-', '').replace('-1.html', '').replace('_', '')
        name = name.capitalize()
        add_dir(name, xhamster + '/channels/' + url, 2, logos + 'xhamster.png', fanart)

def xhamster_content(url) :
    home()
    content = make_request(url)
    match = re.compile("<a href=\"(.+?)\" hint='(.+?)'><div class='iconL").findall(content)
    for url, name in match:
        add_dir(name, url,  2, logos + 'xhamster.png', fanart)

def tube8_categories(url) :
    home()
    content = make_request(url)
    match = re.compile('<a href="http://www.tube8.com/cat/([^"]*)">([^"]*)</a>\s*               </li>').findall(content)
    for url, name in match:
        add_dir(name, tube8 + '/cat/' + url, 2, logos + 'tube.png', fanart)

def pornhub_categories(url) :
    home()
    content = make_request(url)
    match = re.compile('<div class="category-wrapper">.+?<a href="([^"]*)" alt="(.+?)" class="js-mxp" data-mxptype="Category" data-mxptext=".+?<img src="(.+?)" alt=".+?" />.+?</a>.+?<h5>', re.DOTALL).findall(content)
    for url, name, thumb in match:
        add_dir(name, pornhub + url, 2, thumb, fanart)

def pornsocket_categories(url) :
    home()
    content = make_request(url)
    match = re.compile('<a href="([^"]*)"> <img src="([^"]*)" border="0" alt="([^"]*)" class="media-thumb "').findall(content)
    for url, thumb, name in match:
        add_dir(name, pornsocket + url + '?filter_mediaType=4', 2, pornsocket + thumb, fanart)

def youjizz_categories(url) :
    home()
    content = make_request(url)
    match = re.compile('<li><a href="/categories/([^"]+)">([^"]+)</a></li>').findall(content)
    for url,name in match:
        url = url.replace('High Definition', 'HighDefinition');
        add_dir(name, youjizz + '/categories/' + url, 2, logos + 'youjizz.png', fanart)

def hentaigasm_categories(url) :
    home()
    content = make_request(url)
    match = re.compile("<a href='http://hentaigasm.com/tag/([^']+)'").findall(content)
    for url in match:
        name = url.replace('http://hentaigasm.com/tag/', '').replace ('/', '')
        add_dir(name, 'http://hentaigasm.com/tag/' + url, 2, logos + 'hentaigasm.png', fanart)

def youporn_categories(url) :
    home()
    content = make_request(url)
    match = re.compile('<a href="([^"]+)".+?<img src=".+?" alt="([^"]+)" class=".+?" data-original="([^"]+)"', re.DOTALL).findall(content)
    for url, name, thumb in match:
        add_dir(name, youporn + url, 2, thumb, fanart)

def ashemaletube_categories(url) :
    home()
    content = make_request(url)
    match = re.compile('Galleries" src="([^"]+)".+?href="/videos/([^"]+)/best-recent/"><i class=".+?"></i>([^>]+)</a>', re.DOTALL).findall(content)
    for thumb, url, name in match:
        add_dir(name, ashemaletube + '/videos/' + url + '/newest/', 2, thumb, fanart)

def ashemaletube_pornstars(url) :
    home()
    content = make_request(url)
    match = re.compile('<div class="modelspot modelItem" data-model-id=".+?">.+?<a href="(.+?)".+?alt="(.+?)" src="(.+?)"', re.DOTALL).findall(content)
    for url, name, thumb in match:
        add_dir(name, 'https://www.ashemaletube.com/' +  url, 2, thumb, fanart)
    try:
        match = re.compile('<link rel="next" href="(.+?)" />').findall(content)
        add_dir('[COLOR blue]Next  Page  >>>>[/COLOR]', ashemaletube + match[0], 55, logos + 'ashemaletube.png', fanart)
    except:
        pass

def heavyr_categories(url) :
    home()
    content = make_request(url)
    match = re.compile('<a href="([^"]+)" class="image">.+?<img src="([^"]+)" alt="([^"]+)', re.DOTALL).findall(content)
    for url, thumb, name in match:
        add_dir(name, heavyr + url, 2, heavyr + thumb, fanart)

def xvideos_categories(url) :
    home()
    content = make_request(url)
    match = re.compile('<a class="btn btn-default" href="(.+?)">(.+?)</a></li>', re.DOTALL).findall(content)
    for url, name in match:
        url = url.replace('\\','')
        add_dir(name, xvideos + url, 2, logos + 'xvideos.png', fanart)

def xvideos_pornstars(url) :
    home()
    content = make_request(url)
    match = re.compile('"img":"([^"]+)"}].+?class="profile-name"><a href="([^"]+)">([^"]+)</a><span class=".+?">', re.DOTALL).findall(content)
    for thumb, url, name in match:
        thumb = thumb.replace('\\', '')
        add_dir(name, xvideos + url + '/videos/new', 2, thumb, fanart)
    try:
        match = re.compile('<a class="active" href=".+?">.+?</a></li><li><a href="([^"]+)">.+?</a></li><li>', re.DOTALL).findall(content)
        add_dir('[COLOR blue]Next  Page  >>>>[/COLOR]', xvideos + match[0], 32, logos + 'xvideos.png', fanart)
    except:
        pass

def tubepornclassic_categories(url) :
    home()
    content = make_request(url)
    match = re.compile('href="([^"]+)" title="([^"]+)">.+?data-original="([^"]+)"', re.DOTALL).findall(content)
    for url, name, thumb in match:
        add_dir(name,  url,  2, thumb, fanart)

def pornxs_categories(url) :
    home()
    content = make_request(url)
    match = re.compile('<a id=".+?" href="(.+?)".+?/img/categories/175x215/(.+?).jpg.+?caption">([^"]+)</div>', re.DOTALL).findall(content)
    for url, thumb, name in match:
        name = name.replace (' ', '')
        add_dir(name, pornxs + url,  2,  pornxs + '/img/categories/175x215/' + thumb + '.jpg', fanart)

def xhamster_rankigs(url) :
    home()
    content = make_request(url)
    match = re.compile('<a href="([^"]+)" >(.+?)</a>', re.DOTALL).findall(content)
    for url, name in match:
        add_dir(name, url,  2, logos + 'xhamster.png', fanart)

def youporn_sorting(url) :
    home()
    content = make_request(url)
    match = re.compile('href="([^"]+)">(Top.+?|Most.+?)</a></li>').findall(content)
    for url, name in match:
        add_dir(name, youporn + url,  2, logos + 'youporn.png', fanart)

def motherless_sorting(url) :
    home()
    content = make_request(url)
    match = re.compile('<a href="([^"]+)" title=".+?">(Most.+?|Popular.+?)</a>').findall(content)
    for url, name in match:
        add_dir(name, motherless + url,  2, logos + 'motherless.png', fanart)

def emplix_categories(url) :
    home()
    content = make_request(url)
    match = re.compile(' <a class="thumb" href="(.+?)">.+?<img src="(.+?)" alt="(.+?)">.+?<div class="vidcountSp">(.+?)</div>', re.DOTALL).findall(content)
    for url, thumb, name, duration in match:
        name = name.replace('&amp;', '&').replace('&quot;', '"').replace('&#39;', '\'')
        add_dir(name + ' [COLOR lime]('+ duration + ')[/COLOR]', empflix + url, 2, 'http:' + thumb, fanart)

def emplix_sorting(url) :
    home()
    content = make_request(url)
    match = re.compile('<a href="([^"]*)">(Most Recent|Most Popular|Top Rated)</a>').findall(content)
    for url, name in match:
        add_dir(name, empflix  + url,  2, logos + 'empflix.png', fanart)

def txxx_categories(url):
    home()
    content = make_request(url)
    match = re.compile('<a href="([^"]+)" title="([^"]+)".+?<img src="([^"]+)"', re.DOTALL).findall(content)
    for url, name, thumb in match:
        add_dir(name, url ,  2, thumb, fanart)

def fantasti_collections(url):
    home()
    content = make_request(url)
    add_dir('[COLOR lightgreen]fantasti.cc  collections   [COLOR red]Search[/COLOR]', fantasti, 1, logos + 'fantasti.png', fanart)
    add_dir('[COLOR lime]Sorting [/COLOR]', fantasti + '/videos/collections/popular/today/',  49, logos + 'fantasti.png', fanart)
    match = re.compile('<a class="clnk" href="([^"]+)">([^"]+)</a>.+?http://(.+?).jpg.+?<span class="videosListNumber"><b>(.+?)</b> <br>videos', re.DOTALL).findall(content)
    for url, name, thumb, duration in match:
        name = name.replace('&amp;', '&').replace('&quot;', '"').replace('&#39;', '\'')
        add_dir(name + ' [COLOR lime]('+ duration + ')[/COLOR]', fantasti + url + '#collectionSubmittedVideos',  2, 'http://' + thumb + '.jpg', fanart)
    try:
        match = re.compile('<a href="(.+?)">next &gt;&gt;</a>').findall(content)
        add_dir('[COLOR blue]Next  Page  >>>>[/COLOR]', fantasti + match[0], 48, logos + 'fantasti.png', fanart)
    except:
        pass

def fatasti_sorting(url) :
    home()
    content = make_request(url)
    if 'collections' in url:
        match = re.compile('<a href="/videos/collections/popular/(.+?)">(Today|This Week|This Month|All Time)</a>').findall(content)
        for url, name in match:
            add_dir('Popular Videos ' + name, fantasti + '/videos/collections/popular/' + url + '/',  48, logos + 'fantasti.png', fanart)
    else:
        match = re.compile('<a href="/videos/popular/(.+?)" style=".+?">(today|this week|this month|all time)</a>').findall(content)
        for url, name in match:
            add_dir('Popular Videos ' + name, fantasti + '/videos/popular/' + url,  2, logos + 'fantasti.png', fanart)

def upornia_categories(url):
    home()
    content = make_request(url)
    match = re.compile('<a class="thumbnail" href="(.+?)" title="(.+?)">.+?<img src="(.+?)" alt=".+?">', re.DOTALL).findall(content)
    for url, name, thumb in match:
        add_dir(name , url,  2, thumb, fanart)

def upornia_models(url):
    home()
    content = make_request(url)
    match = re.compile('<a class="thumbnail" href="([^"]+)" title="(.+?)">.+?<img src="(.+?)"', re.DOTALL).findall(content)
    for url, name, thumb in match:
        add_dir(name , url,  2, thumb, fanart)
    try:
        match = re.compile('<li class="next">.+?<a href="(.+?)"', re.DOTALL).findall(content)
        add_dir('[COLOR blue]Next  Page  >>>>[/COLOR]', upornia + match[0], 51, logos + 'upornia.png', fanart)
    except:
        pass

def yespornplease_categories(url):
    home()
    content = make_request(url)
    match = re.compile('<a title=".+?" alt=".+?" href="(.+?)">.+?title="(.+?)".+?<span class="badge">(.+?)</span>', re.DOTALL).findall(content)
    for url, name, duration in match:
        add_dir(name + ' [COLOR lime]('+ duration + ')[/COLOR]', yespornplease + url,  2, logos + 'yespp.png', fanart)

def tubegalore_categories(url):
    home()
    content = make_request(url)
    match = re.compile('<a href="(.+?)" class="category" target="_blank">([^<]+)</a>', re.DOTALL).findall(content)
    for url, name in match:
        add_dir(name, tubegalore + url,  2, logos + 'tubegalore.png', fanart)

def uflash_categories(url):
    home()
    content = make_request(url)
    match = re.compile('<li><a href="(.+?)">([^<]+)</a></li>', re.DOTALL).findall(content)
    for url, name in match:
        add_dir(name, uflash + url,  2, logos + 'uflash.png', fanart)

def fantasti_categories(url):
    home()
    add_dir('[COLOR lightgreen]fantasti.cc     [COLOR red]Search[/COLOR]', fantasti, 1, logos + 'fantasti.png', fanart)
    add_dir('[COLOR lime]Collection[/COLOR]', fantasti + '/videos/collections/popular/31days/', 48, logos + 'fantasti.png', fanart)
    add_dir('[COLOR lime]Category [/COLOR]', fantasti + '/category/',  18, logos + 'fantasti.png', fanart)
    add_dir('[COLOR lime]Sorting [/COLOR]', fantasti + '/videos/popular/today/',  49, logos + 'fantasti.png', fanart)
    content = make_request(url)
    match = re.compile('<div class="content-block content-block-category grid">.+?<a href="/category/(.+?)/".+?http://([^"]*).jpg', re.DOTALL).findall(content)
    for url, thumb in match:
        name = url
        add_dir(name, fantasti + '/category/' + url + '/videos/' ,  2, 'http://' + thumb + '.jpg', fanart)

def javtasty_categories(url):
    home()
    content = make_request(url)
    match = re.compile('<a class="item" href="(.+?)" title="(.+?)">.+?<img class="thumb" src="(.+?)"', re.DOTALL).findall(content)
    for url, name, thumb in match:
        add_dir(name, url,  2, javtasty + thumb, fanart)

def pornktube_categories(url):
    home()
    content = make_request(url)
    match = re.compile('<li><a href="/categories/(.+?)">(.+?)</a></li>', re.DOTALL).findall(content)
    for url, name in match:
        add_dir(name, pornktube + '/categories/' + url,  2, logos + 'pornktube.png', fanart)

def nudeflix_list(url):
    home()
    content = make_request(url)
    match = re.compile('<a href="([^"]+)" class="thumbnail fancy-thumbnail fancy-no-cover" data-current-time="0" data-video-id=".+?">.+?<img class="poster" src="([^"]+)".+?<div class="info">(.+?)&middot;', re.DOTALL).findall(content)
    for url, thumb, name in match:
        add_link(name, nudeflix  + url,  4, thumb, fanart)

def nudeflix_categories(url):
    home()
    content = make_request(url)
    match = re.compile('<a href="/browse/category/([^"]+)">([^"]+)</a>', re.DOTALL).findall(content)
    for url, name in match:
        add_dir(name, nudeflix  +'/browse/category/' + url + '/cover?order=released',  2, logos + 'nudeflix.png', fanart)

def nudeflix_sorting(url):
    home()
    content = make_request(url)
    match = re.compile('<option value="(.+?)">(.+?)</option>').findall(content)
    for url, name in match:
        add_dir(name, 'http://www.nudeflix.com/browse/cover?order=' + url,  2, logos + 'nudeflix.png', fanart)

def luxuretv_categories(url):
    home()
    content = make_request(url)
    match = re.compile('<a href="(.+?)">.+?<img class="img" src="(.+?)" alt="(.+?)"', re.DOTALL).findall(content)
    for url, thumb, name in match:
        add_dir(name, url,  2, thumb, fanart)

def datoporn_categories(url):
    home()
    content = make_request(url)
    match = re.compile('<a href="https://datoporn.co/category/([^"]+)" class="morevids" style="background-image:url\((.+?)\);"><span>(.+?)</span></a>', re.DOTALL).findall(content)
    for url, thumb, duration in match:
        name = url
        name = name.replace('+',' ')
        add_dir(name + ' [COLOR lime]('+ duration + ')[/COLOR]', 'http://datoporn.co/category/' + url,  2, thumb, fanart)

def xvideos_sorting(url) :
    home()
    content = make_request(url)
    match = re.compile('<li><a href="/best/([^"]+)" class="btn btn.+?">(.+?)</a></li', re.DOTALL).findall(content)
    for url, name in match:
        add_dir(name, xvideos + '/best/' + url,  2, logos + 'xvideos.png', fanart)

####beeg added by Digonly begin####
beeg_version = 2239
beeg_jsalt = "TTC0Z5t4efl5HicjgeiCJgb5vclSKLJgf7413"

def beeg_url(beeg_index = 0):
    return 'http://api2.beeg.com/api/v6/' + str(beeg_version) + '/index/main/' + str(beeg_index) + '/pc'

def beeg_search_url(query, beeg_index = 0):
    return 'https://api.beeg.com/api/v6/' + str(beeg_version) + '/index/search/' + str(beeg_index) + '/pc?query=' + query

def decode_key(key):
    e = urllib.unquote(key).decode('utf-8')
    s = len(beeg_jsalt)
    t = ""
    for o in range(0, len(e)):
        l = ord(e[o])
        n = o % s
        i = ord(beeg_jsalt[n]) % 21
        t += chr(l-i)
    res = ""
    for r in reversed(str_split(t)):
        res += str(r)
    return res


####beeg added by Digonly end####


def resolve_url(url):
    content = make_request(url)
    if 'xvideos' in url:
        if '[1080p]' in name:
            media_url = re.compile('html5player.setVideoHLS(.+?);').findall(content) [0]
            media_url = media_url.replace('(\'','').replace(')','').replace('hls.m3u8','hls-1080p.m3u8').replace('\'','')
        elif '[720p]' in name:
            media_url = re.compile('html5player.setVideoHLS(.+?);').findall(content) [0]
            media_url = media_url.replace('(\'','').replace(')','').replace('hls.m3u8','hls-720p.m3u8').replace('\'','')
        else:
            media_url = urllib.unquote(re.compile("flv_url=(.+?)&amp").findall(content)[-1])
    elif 'tube8' in url:
        media_url = re.compile('videoUrlJS = "(.+?)"').findall(content)[0]
    elif 'redtube' in url:
        media_url = re.compile('"videoUrl":"(.+?)"').findall(content)[0]
        media_url = media_url.replace('\\','')
    elif '.porn.com' in url:
        try:
            media_url = re.compile('id:"720p",url:"(.+?)",definition:"HD"').findall(content)[0]
        except:
            try:
                media_url = re.compile('id:"480p",url:"(.+?)"').findall(content)[0]
            except:
                media_url = re.compile('id:".+?",url:"(.+?)"').findall(content)[0]
    elif 'vikiporn' in url:
        media_url = re.compile("src: '(.+?)',").findall(content)[0]
    elif 'xhamster' in url:
        media_url = re.compile("file: '(.+?)',").findall(content)[0]
    elif 'lubetube' in url:
        media_url = re.compile('id="video-.+?" href="(.+?)"').findall(content)[0]
    elif 'pornxs.com' in url:
        media_url = re.compile('config-final-url="(.+?)"').findall(content)[0]
    elif 'zbporn' in url:
        media_url = re.compile('file: "(.+?)",').findall(content)[0]
    elif 'pornhd' in url:
        try:
            media_url = re.compile('"720p":"(.+?)"').findall(content)[0]
            media_url = media_url.replace('\\','')
        except:
            media_url = re.compile('"480p":"(.+?)"').findall(content)[0]
            media_url = media_url.replace('\\','')
    elif 'motherless' in url:
        media_url = re.compile('__fileurl = \'(.+?)\';').findall(content)[0]
    elif 'tubepornclassic' in url:
        media_url = 'https://tubepornclassic.com' + re.compile('file: "(.+?)",kind: "thumbnails"').findall(content)[0]
    elif 'efukt' in url:
        media_url = re.compile('<source src="(.+?)" type="video/mp4">').findall(content)[0]
        media_url = media_url.replace('&amp;','&')
    elif 'pornhub' in url:
        try:
            media_url = re.compile('"quality":"720","videoUrl":"([^"]+.mp4[^"]*)"},').findall(content)[0]
            media_url = media_url.replace('/','')
        except:
            media_url = re.compile('"quality":"480","videoUrl":"([^"]+.mp4[^"]*)"},').findall(content)[0]
            media_url = media_url.replace('/','')
    elif 'pornsocket' in url:
        media_url = pornsocket + re.compile('<source src="(.+?)" type="video/mp4"/>').findall(content)[0]
    elif 'youjizz' in url:
        try:
            media_url = 'https:' + re.compile('"filename":"([^"]+.mp4[^"]*)",').findall(content)[-1]
            media_url = media_url.replace('/','')
        except:
            media_url = 'https:' + re.compile('"filename":"([^"]+.mp4[^"]*)",').findall(content)[0]
            media_url = media_url.replace('/','')
    elif 'hentaigasm' in url:
        media_url = re.compile('file: "(.+?)",').findall(content)[0]
    elif 'ashemaletube' in url:
        media_url = re.compile('"src":"(.+?)","desc":".+?"').findall(content)[0]
        media_url = media_url.replace('/','')
    elif 'youporn' in url:
        try:
            media_url = re.compile('"quality":"720","videoUrl":"(.+?)"').findall(content)[0]
            media_url = media_url.replace('/','')
        except:
            try:
                media_url = re.compile('"quality":"480,"videoUrl":"(.+?)"').findall(content)[0]
                media_url = media_url.replace('/','')
            except:
                media_url = re.compile('"quality":"240","videoUrl":"(.+?)"').findall(content)[0]
                media_url = media_url.replace('/','')
    elif 'heavy-r' in url:
            media_url = re.compile('<source type="video/mp4" src="([^"]+)">').findall(content)[0]
    elif 'gotporn' in url:
            media_url = re.compile('<source src="([^"]+)"').findall(content)[0]
    elif 'empflix' in url:
        media_url = re.compile('<meta itemprop="contentUrl" content="(.+?)" />').findall(content)[0]
    elif 'txxx' in url:
        media_url = re.compile('style="display: none;"><a href="(.+?)" id="download_link').findall(content) [0]
    elif 'drtuber' in url:
        media_url = re.compile('<source src="(.+?)"').findall(content)[0]
    elif 'upornia' in url:
        media_url = re.compile('file: \'(.+?)\',').findall(content)[0]
    elif 'vshare.io' in url:
        media_url = 'http:' + re.compile('<source src="(.+?)"').findall(content)[0]
    elif 'yespornplease' in url:
        media_url = 'http:' + re.compile('<source src="(.+?)"').findall(content)[0]
    elif 'fantasti.cc' in url:
        url = re.compile('<div class="video-wrap" data-origin-source="([^"]+)">').findall(content)[0]
        return resolve_url(url)
    elif 'tnaflix' in url:
        media_url = re.compile('<meta itemprop="contentUrl" content="([^"]+)" />').findall(content)[0]
    elif 'uflash' in url:
        try:
            media_url = re.compile('<hd>(.+?)</hd>').findall(content)[0]
        except:
            media_url = re.compile('<src>(.+?)</src>').findall(content)[0]
    elif 'xtwisted' in url:
        media_url = re.compile('"top-right" }, \'file\': "(.+?).mp4",').findall(content)[0] + '.mp4'
    elif 'dansmovies' in url:
        media_url = re.compile('clip: {.+?url: \'(.+?)\',', re.DOTALL).findall(content) [0]
    elif 'nudez' in url:
        media_url = re.compile('file:"(.+?)",').findall(content)[0]
    elif 'xvicious' in url:
        media_url = re.compile('file:"(.+?)",').findall(content)[0]
    elif 'katestube' in url:
        media_url = re.compile('video_url: \'(.+?)\',').findall(content)[0]
    elif 'porndreamer' in url:
        media_url = re.compile('video_url: \'(.+?)\',').findall(content)[0]
    elif 'xfig' in url:
        media_url = re.compile('var videoFile="(.+?)";').findall(content)[0]
    elif 'viptube' in url:
        media_url = re.compile('<source src="(.+?)" type="video/mp4"/>').findall(content)[0]
    elif 'azzzian' in url:
        media_url = re.compile('video_url: \'(.+?)\',').findall(content)[0]
    elif 'hotmovs' in url:
        media_url = re.compile('file\': \'(.+?)\',').findall(content)[0]
    elif 'thenewporn' in url:
        media_url = re.compile('video_url: \'(.+?)\',').findall(content)[0]
    elif 'fetishshrine' in url:
        media_url = re.compile('video_url: \'(.+?)\',').findall(content)[0]
    elif 'yuvutu' in url:
        media_url = 'http://www.yuvutu.com' + re.compile('<iframe src="(.+?)" width="100%"').findall(content)[0]
    elif 'pinkrod' in url:
        media_url = re.compile('video_url: \'(.+?)\',').findall(content)[0]
    elif 'updatetube' in url:
        media_url = re.compile('video_url: \'(.+?)\',').findall(content)[0]
    elif 'tryboobs' in url:
        media_url = re.compile('video_url: \'(.+?)\',').findall(content)[0]
    elif 'wetplace' in url:
        media_url = re.compile('video_url: \'(.+?)\',').findall(content)[0]
    elif 'fetishpapa' in url:
        media_url = re.compile('{file: "(.+?)", label: "High Quality"}').findall(content)[0]
    elif 'xstigma' in url:
        media_url = re.compile('<source src="(.+?)" type="video/mp4"').findall(content)[0]
    elif 'vporn' in url:
        media_url = re.compile('flashvars.videoUrlMedium2 = "(.+?)";').findall(content)[0]
    elif 'fapd' in url:
        media_url = re.compile('file:"(.+?)"').findall(content)[0]
    elif 'spankwire' in url:
        media_url = re.compile('playerData.cdnPath480         = \'(.+?)\';').findall(content)[0]
    elif 'theclassicporn' in url:
        media_url = re.compile('video_url: \'(.+?)\',').findall(content)[0]
    elif 'voyeurhit' in url:
        media_url = re.compile('video_url: \'(.+?)\',').findall(content)[0]
    elif 'neathdporn' in url:
        media_url = re.compile('video_url: \'(.+?)\',').findall(content)[0]
    elif 'romptube' in url:
        media_url = re.compile('video_url: \'(.+?)\',').findall(content)[0]
    elif 'extremetube' in url:
        try:
            media_url = re.compile('quality_480p":"(.+?)"').findall(content)[0]
            media_url = media_url.replace('/','')
        except:
            media_url = re.compile('quality_240p":"(.+?)"').findall(content)[0]
            media_url = media_url.replace('/','')
    elif 'pornomovies' in url:
        media_url = re.compile('file: "(.+?)"').findall(content)[0]
    elif 'beardedperv' in url:
        media_url = re.compile('file: "(.+?)"').findall(content)[0]
    elif 'eporner' in url:
        media_url = 'http://www.eporner.com/dload/' + re.compile('<a href="/dload/(.+?)">Download MP4').findall(content)[0]
    elif 'pornicom' in url:
        media_url = re.compile('video_url: \'(.+?)\',').findall(content)[0]
    elif 'sheshaft' in url:
        media_url = re.compile('video_url: \'(.+?)\',').findall(content)[0]
    elif 'ashemaletv' in url:
        media_url = re.compile('<source src="(.+?)" type=\'video/mp4\'>').findall(content)[0]
    elif 'hclips' in url:
        media_url = re.compile('video_url: \'(.+?)\',').findall(content)[0]
    elif 'x3xtube' in url:
        media_url = re.compile('file: "(.+?)"').findall(content)[0]
    elif 'roxtube' in url:
        media_url = re.compile('video_url: \'(.+?)\',').findall(content)[0]
    elif 'xtube' in url:
        media_url = re.compile('"video_url":"(.+?)","autoplay":true,').findall(content)[0]
        media_url = media_url.replace('%3A', ':').replace('%2F', '/').replace('%3F', '?').replace('%3D', '=').replace('%26', '&')
    elif 'sleazyneasy' in url:
        media_url = re.compile('video_url: \'(.+?)\',').findall(content)[0]
    elif 'pervclips' in url:
        media_url = re.compile('video_url: \'(.+?)\',').findall(content)[0]
    elif 'hdzog' in url:
        media_url = re.compile('video_url: \'(.+?)\',').findall(content)[0]
    elif 'pornpillow' in url:
        media_url = re.compile('file\': \'(.+?)\',').findall(content)[0]
    elif 'aporntv' in url:
        media_url = re.compile('<source src="(.+?)" type=\'video/mp4\'>').findall(content)[0]
    elif '3movs' in url:
        media_url = re.compile('video_url: \'(.+?)\',').findall(content)[0]
    elif 'pornoxo.com' in url:
        media_url = re.compile('<source src="(.+?)" type="video/mp4"').findall(content)[0]
    elif 'tubeq' in url:
        media_url = re.compile('url: \'(.+?)\',').findall(content)[0]
    elif 'free-sex-video' in url:
        media_url = re.compile('var defFile = \'(.+?)\';').findall(content)[0]
    elif 'keezmovies' in url:
        try:
            media_url = re.compile('quality_480p":"(.+?)"').findall(content)[0]
            media_url = media_url.replace('/','')
        except:
            media_url = re.compile('quality_240p":"(.+?)"').findall(content)[0]
            media_url = media_url.replace('/','')
    elif 'xxxkingtube' in url:
        media_url = re.compile('var defFile = \'(.+?)\';').findall(content)[0]
    elif 'sunporno' in url:
        media_url = re.compile('data-src="(.+?)"').findall(content)[0]
    elif 'tubous' in url:
        media_url = re.compile('<video src="(.+?)"').findall(content)[0]
    elif 'hotamateurs' in url:
        media_url = re.compile('video_url: \'(.+?)\',').findall(content)[0]
    elif 'h2porn' in url:
        media_url = re.compile('video_url: \'(.+?)\',').findall(content)[0]
    elif 'winporn' in url:
        media_url = re.compile('<source src="(.+?)" type="video/mp4"').findall(content)[0]
    elif 'vivatube' in url:
        media_url = re.compile('<source src="(.+?)" type="video/mp4"').findall(content)[0]
    elif 'egbo' in url:
        media_url = re.compile('video_url: \'(.+?)\',').findall(content)[0]
    elif 'hd21' in url:
        media_url = re.compile('<source src="(.+?)" type="video/mp4"').findall(content)[0]
    elif 'pornalized' in url:
        media_url = re.compile('video_url: \'(.+?)\',').findall(content)[0]
    elif 'proporn' in url:
        media_url = re.compile('<source src="(.+?)" type="video/mp4"').findall(content)[0]
    elif 'pornwhite' in url:
        media_url = re.compile('video_url: \'(.+?)\',').findall(content)[0]
    elif 'faphub' in url:
        media_url = re.compile('url: \'(.+?)\',').findall(content)[0]
    elif 'porndoe.com' in url:
        try:
            media_url = re.compile('file: "(.+?)","default": "true",label:"720p HD"').findall(content)[0]
        except:
            media_url = re.compile('file: "(.+?)","default": "true",label:"480p"').findall(content)[0]
    elif 'finevids' in url:
        media_url = re.compile('video_url: \'(.+?)\',').findall(content)[0]
    elif 'japan-whores' in url:
        media_url = re.compile('<link itemprop="contentUrl" href="(.+?)">').findall(content)[0]
    elif '5fing' in url:
        media_url = re.compile('video_url: \'(.+?)\',').findall(content)[0]
    elif 'wankoz.com' in url:
        media_url = re.compile('video_html5_url\']=\'(.+?)/\';').findall(content)[0]
    elif 'worldsex.com' in url:
        media_url = re.compile('file:"(.+?)",').findall(content)[0]
    elif 'xpage.com' in url:
        media_url = re.compile('data-video240p="(.+?)"').findall(content)[0]
    elif 'fat-tube.com' in url:
        media_url = re.compile('<source src="(.+?)" type=\'video/mp4;').findall(content)[0]
    elif 'hotshame.com' in url:
        media_url = re.compile('video_url: \'(.+?)/\',  ').findall(content)[0]
    elif 'fantasy8.com' in url:
        media_url = re.compile('var videoFile="(.+?)";').findall(content)[0]
    elif 'palmtube.com' in url:
        media_url = re.compile('<source type="video/mp4" src="(.+?)" >').findall(content)[0]
    elif 'freepornvs.com' in url:
        media_url = re.compile("video_url: '(.+?)'").findall(content)[0]
    elif 'hotclips24.com' in url:
        media_url = re.compile("var defFile = '(.+?)';").findall(content)[0]
    elif 'pornspot.com' in url:
        media_url = re.compile('data-video240p="(.+?)"').findall(content)[0]
    elif 'vid2c.com' in url:
        media_url = re.compile('var videoFile="(.+?)/";').findall(content)[0]
    elif 'mofosex.com' in url:
        media_url = re.compile("flashvars.video_url = '(.+?)';").findall(content)[0]
        media_url = media_url.replace('%3A', ':').replace('%2F', '/').replace('%3F', '?').replace('%3D', '=').replace('%26', '&')
    elif 'youav' in url:
        media_url = re.compile("{file:'(.+?)'").findall(content)[-1]
    elif 'faplust.com' in url:
        media_url = re.compile("video_url: '(.+?)\',").findall(content)[0]
    elif 'freegrannytube.com' in url:
        media_url = 'Http:' + re.compile('src="(.+?)" type="video/mp4"></video>').findall(content)[0]
    elif 'ghettotube.com' in url:
        try:
            media_url = re.compile('file: "(.+?)",\s*\s*.+?label: "720p HD"').findall(content)[0]
        except:
            media_url = re.compile('file: "(.+?)",\s*\s*.+?label: "360p SD"').findall(content)[0]
    elif 'pornktube.com' in url:
        try:
            media_url = re.compile('video_alt_url3: \'(.+?)\',').findall(content)[0]
        except:
            media_url = re.compile('video_alt_url2: \'(.+?)\',').findall(content)[0]
    elif 'javwhores' in url:
        try:
            media_url = re.compile("video_alt_url: '(.+?)'").findall(content)[0]
        except:
            media_url = re.compile("video_url: '(.+?)'").findall(content)[0]
    elif 'rude.com' in url:
        media_url = re.compile('file: "(.+?)", type:').findall(content)[0]
    elif 'nudeflix' in url:
        if 'Scene 1' in name:
            media_url = re.compile('<video data-src="(.+?)"></video>').findall(content)[0]
        elif 'Scene 2' in name:
            media_url = re.compile('<video data-src="(.+?)"></video>').findall(content)[1]
        elif 'Scene 3' in name:
            media_url = re.compile('<video data-src="(.+?)"></video>').findall(content)[2]
        elif 'Scene 4' in name:
            media_url = re.compile('<video data-src="(.+?)"></video>').findall(content)[3]
        elif 'Scene 5' in name:
            media_url = re.compile('<video data-src="(.+?)"></video>').findall(content)[4]
        elif 'Scene 6' in name:
            media_url = re.compile('<video data-src="(.+?)"></video>').findall(content)[5]
        elif 'Scene 7' in name:
            media_url = re.compile('<video data-src="(.+?)"></video>').findall(content)[6]
        elif 'Scene 8' in name:
            media_url = re.compile('<video data-src="(.+?)"></video>').findall(content)[7]
        elif 'Scene 9' in name:
            media_url = re.compile('<video data-src="(.+?)"></video>').findall(content)[8]
        elif 'Scene 10' in name:
            media_url = re.compile('<video data-src="(.+?)"></video>').findall(content)[9]
        else:
            pass
    elif 'luxuretv.com' in url:
        media_url = re.compile('source src="(.+?)" type=').findall(content)[0]
    elif 'dato' in url:
        media_url = url
        media_url = media_url.replace('http://datoporn.co','')
    elif 'plyplv' in url:
        media_url = re.compile('var fileUrl="(.+?)"').findall(content)[0]
    else:
        media_url = url
    item = xbmcgui.ListItem(name, path = media_url)
    item.setMimeType('video/mp4')
    xbmcplugin.setResolvedUrl(int(sys.argv[1]), True, item)
    return

def get_params():
    param = []
    paramstring = sys.argv[2]
    if len(paramstring)>= 2:
        params = sys.argv[2]
        cleanedparams = params.replace('?', '')
        if (params[len(params)-1] == '/'):
            params = params[0:len(params)-2]
        pairsofparams = cleanedparams.split('&')
        param = {}
        for i in range(len(pairsofparams)):
            splitparams = {}
            splitparams = pairsofparams[i].split('=')
            if (len(splitparams)) == 2:
                param[splitparams[0]] = splitparams[1]
    return param

def add_dir(name, url, mode, iconimage, fanart):
    u = sys.argv[0] + "?url=" + urllib.quote_plus(url) + "&mode=" + str(mode) + "&name=" + urllib.quote_plus(name) + "&iconimage=" + urllib.quote_plus(iconimage)
    ok = True
    liz = xbmcgui.ListItem(name, iconImage = "DefaultFolder.png", thumbnailImage = iconimage)
    liz.setInfo( type="Video", infoLabels={ "Title": name, "overlay":"6"})
    liz.setProperty('fanart_image', fanart)
    ok = xbmcplugin.addDirectoryItem(handle = int(sys.argv[1]), url = u, listitem = liz, isFolder = True)
    return ok

def add_link(name, url, mode, iconimage, fanart):
    u = sys.argv[0] + "?url=" + urllib.quote_plus(url) + "&mode=" + str(mode) + "&name=" + urllib.quote_plus(name) + "&iconimage=" + urllib.quote_plus(iconimage)
    ok = True
    liz = xbmcgui.ListItem(name, iconImage = "DefaultVideo.png", thumbnailImage = iconimage)
    liz.setProperty('fanart_image', fanart)
    liz.setInfo(type="Video", infoLabels={"Title": name})
    try:
        liz.setContentLookup(False)
    except:
        pass
    liz.setProperty('IsPlayable', 'true')
    ok = xbmcplugin.addDirectoryItem(handle = int(sys.argv[1]), url = u, listitem = liz)
    return ok

def uflash_nextpage(current_url, content):
    match = re.compile('<span class="currentpage">([0-9]+)</span>', re.DOTALL).findall(content)
    next_page = int(match.pop()) + 1
    parsed_url = urlparse.urlparse(current_url)
    queries = parsed_url.query.split('&')
    result = []
    has_page = False

    for query in queries:
        if query.startswith('page='):
            next_page_query = "page=%s" % str(next_page)
            result.append(next_page_query)
            has_page = True
            continue
        result.append(query)
    # First page doesn't have page query parameter
    if not has_page:
        result.append("page=%s" % str(next_page))

    modified_query = '&'.join(result)
    parsed_url = parsed_url._replace(query=modified_query)
    add_dir('[COLOR blue]Next  Page  >>>>[/COLOR]', parsed_url.geturl(), 2, logos + 'uflash.png', fanart)
    return parsed_url.geturl()


params = get_params()
url = None
name = None
mode = None
iconimage = None

try:
    url = urllib.unquote_plus(params["url"])
except:
    pass
try:
    name = urllib.unquote_plus(params["name"])
except:
    pass
try:
    mode = int(params["mode"])
except:
    pass
try:
    iconimage = urllib.unquote_plus(params["iconimage"])
except:
    pass

print "Mode: " + str(mode)
print "URL: " + str(url)
print "Name: " + str(name)
print "iconimage: " + str(iconimage)

if mode == None or url == None or len(url) < 1:
    main()

elif mode == 1:
    search()

elif mode == 2:
    xbmc.log("mode==2, starturl=%s" % url, xbmc.LOGERROR)
    start(url)

elif mode == 3:
    media_list(url)

elif mode == 4:
    resolve_url(url)

elif mode == 8:
    redtube_sorting(url)

elif mode == 9:
    redtube_categories(url)

elif mode == 10:
    redtube_channels_cat(url)

elif mode == 11:
    redtube_channels_list(url)

elif mode == 12:
    lubtetube_pornstars(url)

elif mode == 13:
    flv_channels_list(url)

elif mode == 14:
    porncom_channels_list(url)

elif mode == 15:
    lubetube_categories(url)

elif mode == 16:
    vikiporn_categories(url)

elif mode == 17:
    xhamster_categories(url)

elif mode == 18:
    fantasti_categories(url)

elif mode == 19:
    pornhd_categories(url)

elif mode == 20:
    pornhd_pornstars(url)

elif mode == 21:
    eporner_categories(url)

elif mode == 22:
    tube8_categories(url)

elif mode == 23:
    zbporn_categories(url)

elif mode == 24:
    xhamster_content(url)

elif mode == 25:
    pornhub_categories(url)

elif mode == 26:
    pornsocket_categories(url)

elif mode == 27:
    xvideos_categories(url)

elif mode == 28:
    youjizz_categories(url)

elif mode == 29:
    hentaigasm_categories(url)

elif mode == 30:
    ashemaletube_categories(url)

elif mode == 31:
    youporn_categories(url)

elif mode == 32:
    xvideos_pornstars(url)

elif mode == 33:
    heavyr_categories(url)

elif mode == 34:
    youav_categories(url)

elif mode == 38:
    tubepornclassic_categories(url)

elif mode == 39:
    pornxs_categories(url)

elif mode == 40:
    gotporn_categories(url)

elif mode == 41:
    gotporn_content(url)

elif mode == 42:
    xhamster_rankigs(url)

elif mode == 43:
    youporn_sorting(url)

elif mode == 44:
    motherless_sorting(url)

elif mode == 45:
    emplix_categories(url)

elif mode == 46:
    emplix_sorting(url)

elif mode == 47:
    txxx_categories(url)

elif mode == 48:
    fantasti_collections(url)

elif mode == 49:
    fatasti_sorting(url)

elif mode == 50:
    upornia_categories(url)

elif mode == 51:
    upornia_models(url)

elif mode == 52:
    yespornplease_categories(url)

elif mode == 53:
    tubegalore_categories(url)

elif mode == 54:
    uflash_categories(url)

elif mode == 55:
    ashemaletube_pornstars(url)

elif mode == 60:
    motherless_galeries_cat(url)

elif mode == 61:
    motherless_being_watched_now(url)

elif mode == 62:
    motherless_groups_cat(url)

elif mode == 63:
    pornktube_categories(url)

elif mode == 64:
    javtasty_categories(url)

elif mode == 65:
    nudeflix_list(url)

elif mode == 66:
    nudeflix_categories(url)

elif mode == 67:
    nudeflix_sorting(url)

elif mode == 68:
    luxuretv_categories(url)

elif mode == 69:
    datoporn_categories(url)

elif mode == 71:
    xvideos_sorting(url)

elif mode == 70:
    item = xbmcgui.ListItem(name, path = url)
    item.setMimeType('video/mp4')
    xbmcplugin.setResolvedUrl(int(sys.argv[1]), True, item)
xbmcplugin.endOfDirectory(int(sys.argv[1]))
