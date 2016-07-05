# -*- coding: utf-8 -*-

'''
Copyright (C) 2015                                                     

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

import urllib, urllib2, re, os, sys
import xbmc, xbmcplugin, xbmcgui, xbmcaddon

mysettings = xbmcaddon.Addon(id = 'plugin.video.adulthideout')
profile = mysettings.getAddonInfo('profile')
home = mysettings.getAddonInfo('path')
fanart = xbmc.translatePath(os.path.join(home, 'fanart.jpg'))
icon = xbmc.translatePath(os.path.join(home, 'icon.png'))
logos = xbmc.translatePath(os.path.join(home, 'logos\\')) # subfolder for logos
homemenu = xbmc.translatePath(os.path.join(home, 'resources', 'playlists'))

#define webpages in order they were added.
redtube = 'http://www.redtube.com'
xvideos = 'http://www.xvideos.com'
xhamster = 'http://xhamster.com'
vikiporn = 'http://www.vikiporn.com'
tube8 = 'http://www.tube8.com'
pornxs = 'http://pornxs.com'
pornhd = 'http://www.pornhd.com'
lubetube = 'http://lubetube.com/'
porncom = 'http://www.porn.com'
zbporn = 'http://zbporn.com'
yesxxx = 'http://www.yes.xxx/'
youjizz = 'http://www.youjizz.com'
motherless = 'http://motherless.com'
eporner = 'http://www.eporner.com'
tubepornclassic = 'http://www.tubepornclassic.com'
efukt = 'http://efukt.com/'
pornhub = 'http://pornhub.com'
pornsocket = 'http://pornsocket.com'
hentaigasm = 'http://hentaigasm.com/'
ashemaletube = 'http://www.ashemaletube.com'
youporn = 'http://www.youporn.com'
heavyr = 'http://www.heavy-r.com'
japanesehd = 'http://jav720p.net'
gotporn ='http://www.gotporn.com'
empflix = 'http://www.empflix.com'
txxx ='http://www.txxx.com'
fantasti = 'http://fantasti.cc'
upornia = 'http://upornia.com'
yespornplease = 'http://yespornplease.com'
uflash = 'http://www.uflash.tv'
tubegalore = 'http://www.tubegalore.com'

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
		req.add_header('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/50.0.2661.102 Safari/537.36')
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
	add_dir('Efukt [COLOR yellow] Videos[/COLOR]', efukt, 2, logos + 'efukt.png', fanart)
	add_dir('Empflix [COLOR yellow] Videos[/COLOR]', empflix + '/browse.php?category=mr' , 2, logos + 'empflix.png', fanart)
	add_dir('Eporner [COLOR yellow] Videos[/COLOR]', eporner + '/0/', 2, logos + 'eporner.png', fanart)
	add_dir('Fantasti.cc [COLOR yellow] Videos[/COLOR]', fantasti + '/videos/popular/today/', 2, logos + 'fantasti.png', fanart)
	#(removing gotporn for now, because adulthideout can't handle cookies)
	#add_dir('Gotporn [COLOR yellow] Videos[/COLOR]', gotporn + '/?duration=20-&page=1', 2, logos + 'gotporn.png', fanart)
	add_dir('Hentaigasm [COLOR yellow] Videos[/COLOR]', hentaigasm, 2, logos + 'hentaigasm.png', fanart)
	add_dir('Heavy-R [COLOR yellow] Videos[/COLOR]', heavyr + '/videos/' , 2, logos + 'heavyr.png', fanart)
	add_dir('Jav720p [COLOR yellow] Videos[/COLOR]', japanesehd + '/?orderby=date', 2, logos + 'j720p.png', fanart)
	add_dir('LubeTube [COLOR yellow] Videos[/COLOR]', lubetube + 'view', 2, logos + 'lubetube.png', fanart) 
	add_dir('Motherless [COLOR yellow] Videos[/COLOR]', motherless + '/videos/recent?page=1', 2, logos + 'motherless.png', fanart)
	add_dir('PornCom [COLOR yellow] Videos[/COLOR]', porncom + '/videos?p=1', 2, logos + 'porncom.png', fanart)
	add_dir('PornHD [COLOR yellow] Videos[/COLOR]', pornhd, 2, logos + 'pornhd.png', fanart)
	add_dir('PornHub [COLOR yellow] Videos[/COLOR]', pornhub +'/video?page=1', 2, logos + 'pornhub.png', fanart)
	#(removing pornsocket for now, because adulthideout can't handle cloudflare's anti bot page)
	#add_dir('Pornsocket [COLOR yellow] Videos[/COLOR]', pornsocket + '/media-gallery.html?display=list&filter_mediaType=4&limitstart=0', 2, logos + 'pornsocket.png', fanart)	
	add_dir('PornXS [COLOR yellow] Videos[/COLOR]', pornxs + '/browse/sort-time/', 2, logos + 'pornxs.png', fanart)		
	add_dir('RedTube [COLOR yellow] Videos[/COLOR]', redtube + '/?page=1', 2, logos + 'redtube.png', fanart)
	add_dir('Tube8 [COLOR yellow] Videos[/COLOR]', tube8 + '/newest.html',  2, logos + 'tube8.png', fanart)
	add_dir('Tubegalore [COLOR yellow] Videos[/COLOR]', tubegalore + '/new/page0/',  2, logos + 'tubegalore.png', fanart)
	add_dir('Tubepornclassic [COLOR yellow] Videos[/COLOR]', tubepornclassic + '/latest-updates/', 2, logos + 'tpc.png', fanart)
	add_dir('Txxx [COLOR yellow] Videos[/COLOR]', txxx + '/latest-updates/', 2, logos + 'txxx.png', fanart)
	add_dir('Uflash.TV [COLOR yellow] Videos[/COLOR]', uflash + '/videos?o=mr', 2, logos + 'uflash.png', fanart)
	add_dir('Upornia [COLOR yellow] Videos[/COLOR]', upornia + '/latest-updates/', 2, logos + 'upornia.png', fanart)
	add_dir('ViKiPorn [COLOR yellow] Videos[/COLOR]', vikiporn + '/latest-updates/', 2, logos + 'vikiporn.png', fanart) 
	add_dir('xHamster [COLOR yellow] Videos[/COLOR]', xhamster, 2, logos + 'xhamster.png', fanart)
	add_dir('Xvideos [COLOR yellow] Videos[/COLOR]', xvideos, 2, logos + 'xvideos.png', fanart)
	add_dir('YesPornPlease [COLOR yellow] Videos[/COLOR]', yespornplease + '/?s=date', 2, logos + 'yespornplease.png', fanart)
	add_dir('Yes XXX [COLOR yellow] Videos[/COLOR]', yesxxx + '?s=recent', 2, logos + 'yes.png', fanart)
	add_dir('YouJizz [COLOR yellow] Videos[/COLOR]', youjizz + '/newest-clips/1.html', 2, logos + 'youjizz.png', fanart)
	add_dir('YouPorn [COLOR yellow] Videos[/COLOR]', youporn + '/browse/time/', 2, logos + 'youporn.png', fanart)	
	add_dir('ZBPorn [COLOR yellow] Videos[/COLOR]', zbporn + '/latest-updates/', 2, logos + 'zbporn.png', fanart)



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
		elif 'efukt' in name:
			url = efukt + '/search/' + searchText + '/'
			start(url)	
		elif 'eporner' in name:
			url = eporner + '/search/' + searchText 
			start(url)
		elif 'gotporn' in name:
			url = gotporn + '/results?search_query=' + searchText + '&src=ipt:b'
			start(url)
		elif 'hentaigasm' in name:
			url = hentaigasm + '/?s=' + searchText
			start(url)
		elif 'heavy-r' in name:
			url = heavyr + 'free_porn/' + searchText + '.html'
			start(url)
		elif 'jav720p' in name:
			url = japanesehd + '/search/' + searchText
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
		elif '.porn.com' in name:
			url = porncom + '/videos/search?q=' + searchText  
			media_list(url)
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
			url = pornxs + '/search.php?s=' + searchText
			media_list(url)			
		elif 'redtube.com' in name:
			url = redtube + '/?search=' + searchText      	  
			start(url)
		elif 'tube8.com' in name:
			url = tube8 + '/searches.html?q=' + searchText      	  
			start(url)
		elif 'tubepornclassic' in name:
			url = tubepornclassic + '/search/' + searchText + '/'
			start(url)
		elif 'vikiporn.com' in name:
			url = vikiporn + '/search/?q=' + searchText      	  
			media_list(url)	
		elif 'xhamster.com' in name:
			url = xhamster + '/search.php?q=' + searchText +'&qcat=video'     	  
			start(url)
		elif 'xvideos.com' in name:
			url = xvideos + '/?k=' + searchText      	  
			start(url)			
		elif 'yes.xxx' in name:
			url = yesxxx + '?s=search&search=' + searchText	  
			start(url)			
		elif 'youjizz.com' in name:  
			url = youjizz + '/srch.php?q=' + searchText     	  
			start(url)			
		elif 'youporn' in name:
			url = youporn + '/search/?query=' + searchText
			start(url)			
		elif 'zbporn' in name:
			url = zbporn + '/search/?q=' + searchText	  
			start(url)	
		elif 'empflix' in name:
			url = empflix + '/search.php?what=' + searchText	  
			start(url)
		elif 'txxx' in name:
			url = txxx + '/search/?s=' + searchText	  
			start(url)	
		elif 'fantasti' in name:
			url = fantasti + '/search/' + searchText + '/videos/'
			start(url)			
		elif 'upornia' in name:
			url = upornia + '/search/?q=' + searchText
			start(url)
		elif 'yespornplease' in name:
			url = yespornplease + '/search?q=' + searchText	  
			start(url)		
		elif '.uflash.tv' in name:
			url = uflash + '/search?search_type=videos&search_query=' + searchText
			start(url)
		elif 'tubegalore' in name:
			url = tubegalore + '/search/?q='  + searchText
			start(url)
	except:
		pass

def start(url): 
	home()
	if 'ashemaletube' in url:
		add_dir('[COLOR lightgreen]ashemaletube.com     [COLOR red]Search[/COLOR]', ashemaletube, 1, logos + 'ashemaletube.png', fanart)	
		add_dir('[COLOR lime]Categories[/COLOR]', ashemaletube + '/tags/', 30, logos + 'ashemaletube.png', fanart)
		content = make_request(url)
		match = re.compile('<div class="thumb vidItem" id=".+?">.+?<a href="([^"]*)">.+?src="([^"]*)" alt="([^"]*)".+?>([:\d]+)</span>', re.DOTALL).findall(content)
		for url, thumb, name, duration in match:
			name = name.replace('&amp;', '&')
			add_link(name + ' [COLOR lime]('+ duration + ')[/COLOR]', url, 4, thumb, fanart)  
		try:
			match = re.compile('<link rel="next" href="(.+?)" />').findall(content)
			add_dir('[COLOR blue]Next  Page  >>>>[/COLOR]', ashemaletube + match[0], 2, logos + 'ashemaletube.png', fanart)
		except:
			pass

	elif 'efukt' in url:
		content = make_request(url)
		add_dir('[COLOR lightgreen]efukt.com     [COLOR red]Search[/COLOR]', efukt, 1, logos + 'efukt.png', fanart)
		match = re.compile('<a href="([^"]*)" title="([^"]*)"  class="thumb"><img src="([^"]*)"').findall(content)
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
		match = re.compile('<div id="remove(.+?)">.+?<a href="([^"]+)".+?><h2>(.+?)</h2>.+?<span class=\"duringTime\">([\d:]+)</span>.+?<img src="([^"]+)"', re.DOTALL).findall(content)
		for url, dummy, name, duration, thumb in match:
			url = 'http://player.empflix.com/video/' + url
			name = name.replace('&amp;', '&').replace('&quot;', '"').replace('&#39;', '\'')
			content2 = make_request(url)
			match = re.compile('flashvars\.config\s*=\s*escape\("([^"]*)"\);').findall(content2)
			for url in match:
				add_link(name + ' [COLOR lime]('+ duration + ')[/COLOR]', url , 4, 'http:' + thumb, fanart)
		try:
			match = re.compile('href="([^"]+)">next &gt;&gt;</a>').findall(content)
			add_dir('[COLOR blue]Next  Page  >>>>[/COLOR]', empflix + '/' + match[0], 2, logos + 'empflix.png', fanart)	
		except:
			pass	

	elif 'eporner' in url:
		content = make_request(url)
		add_dir('[COLOR lightgreen]eporner.com     [COLOR red]Search[/COLOR]', eporner, 1, logos + 'eporner.png', fanart)
		add_dir('[COLOR lime]Categories[/COLOR]', eporner + '/categories/',  21, logos + 'eporner.png', fanart)
		match = re.compile('<span>(.+?)</span></div> <a href="/.+?/([^"]*)" title="(.+?)".+?src="(.+?)".+?<div class="mbtim">(.+?)</div>', re.DOTALL).findall(content)
		for dummy, url, name, thumb, duration in match:
			add_link(name + ' [COLOR lime]('+ duration + ')[/COLOR]', eporner + '/config5/' + url, 4, thumb, fanart)	
		try:
			match = re.compile("<a href='([^']*)' title='Next page'>").findall(content)
			add_dir('[COLOR blue]Next  Page  >>>>[/COLOR]', eporner + match[0], 2, logos + 'eporner.png', fanart)
		except:
			match = re.compile('<a href="([^"]*)" title="Next page">').findall(content)
			add_dir('[COLOR blue]Next  Page  >>>>[/COLOR]', eporner +  match[0], 2, logos + 'eporner.png', fanart)
	
	elif 'fantasti' in url:
		content = make_request(url)
		add_dir('[COLOR lightgreen]Fantastic.com     [COLOR red]Search[/COLOR]', fantasti, 1, logos + 'fantasti', fanart)
		add_dir('[COLOR lime]Collection[/COLOR]', fantasti + '/videos/collections/popular/today/', 48, logos + 'fantasti.png', fanart)
		add_dir('[COLOR lime]Sorting [/COLOR]', fantasti + '/videos/popular/today/',  49, logos + 'fantasti.png', fanart)		
		if 'search' in url:
			match = re.compile('href="([^"]+)".+?<img alt="([^"]+)"   src="([^"]+)".+?<span class="v_lenght">([\d:]+)</span>', re.DOTALL).findall(content)
			for url, name, thumb, duration in match:
				name = name.replace('&amp;', '&').replace('&quot;', '"').replace('&#39;', '\'')
				url = fantasti + url
				add_dir(name, url, 4, thumb, fanart)
		else:
			match = re.compile('href="([^"]+)"><img src="([^"]+)".+?alt="([^"]+)"').findall(content)
			for url, thumb, name in match:
				name = name.replace('&amp;', '&').replace('&quot;', '"').replace('&#39;', '\'')
				url = fantasti + url
				add_link(name, url, 4, thumb, fanart)					
				
		try:
			match = re.compile('<a href="([^"]+)">next &gt;&gt').findall(content)
			add_dir('[COLOR blue]Next  Page  >>>>[/COLOR]', fantasti + match[0], 2, logos + 'fantasti.png', fanart)	
		except:
			pass	
	
	elif 'gotporn' in url:
		content = make_request(url)
		add_dir('[COLOR lightgreen]gotporn.com     [COLOR red]Search[/COLOR]', gotporn, 1, logos + 'gotporn.png', fanart)
		add_dir('[COLOR lime]Categories[/COLOR]', gotporn + '/categories?src=hm',  40, logos + 'gotporn.png', fanart)
		add_dir('[COLOR lime]Change Content[/COLOR]', gotporn ,  41, logos + 'gotporn.png', fanart)
		match = re.compile('<a class=".+?" href="([^"]+)".+?data-title="([^"]+)">.+?<span class="duration">.+?([\d:]+).+?</span>.+?<img src=\'(.+?)\'', re.DOTALL).findall(content)
		for url, name, duration, thumb in match:
			add_link(name + ' [COLOR lime]('+ duration + ')[/COLOR]', url, 4, thumb, fanart)	
		try:
			if "/shemale" in url :
				match = re.compile('<a href="([^"]+)" class="btn btn-secondary"><i class="icon icon-angle-right"></i></a>').findall(content)
				add_dir('[COLOR blue]Next  Page  >>>>[/COLOR]', gotporn + '/shemale/' + match[0], 2, logos + 'gotporn.png', fanart)
			if "gay" in url :
				match = re.compile('<a href="([^"]+)" class="btn btn-secondary"><i class="icon icon-angle-right"></i></a>').findall(content)
				add_dir('[COLOR blue]Next  Page  >>>>[/COLOR]', gotporn + '/gay/' + match[0], 2, logos + 'gotporn.png', fanart)
			else :
				match = re.compile('<a href="([^"]+)" class="btn btn-secondary"><i class="icon icon-angle-right"></i></a>').findall(content)
				add_dir('[COLOR blue]Next  Page  >>>>[/COLOR]', gotporn + match[0], 2, logos + 'gotporn.png', fanart)
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
		match = re.compile('<a href="([^"]+)" class="image">.+?<img src="([^"]+)".+?alt="([^"]+)".+?<span class="duration"><i class="fa fa-clock-o"></i> ([\d:]+)</span>', re.DOTALL).findall(content)
		for url, thumb, name, duration in match:
			add_link(name + ' [COLOR lime]('+ duration + ')[/COLOR]', heavyr + url, 4, thumb, fanart)  
		try:
			match = re.compile('<a href="([^"]*)">Next</a>').findall(content)
			add_dir('[COLOR blue]Next  Page  >>>>[/COLOR]', heavyr + match[0], 2, logos + 'heavyr.png', fanart)
		except:
			pass
			
	elif 'jav720p' in url:
		add_dir('[COLOR lightgreen]jav720p.net     [COLOR red]Search[/COLOR]', japanesehd, 1, logos + 'j720p.png', fanart)	
		add_dir('[COLOR lime]Genres[/COLOR]', japanesehd + '/categories/genres', 34, logos + 'j720p.png', fanart)
		add_dir('[COLOR lime]Models[/COLOR]', japanesehd + '/categories/models', 35, logos + 'j720p.png', fanart) 
		add_dir('[COLOR lime]Makers[/COLOR]', japanesehd + '/categories/makers', 36, logos + 'j720p.png', fanart) 
		content = make_request(url)
		match = re.compile('title=".+?"> <img src="([^"]*)" alt=".+?" title="([^"]*)"/> <div class=".+?"> </div> </a> <span class="duration">([^"]*)</span> <span class="quality">HD</span> </div> <div class="item-detail"> <h4><a href="([^"]*)"').findall(content)
		for thumb, name, duration, url in match:
			name = name.replace('&amp;', '&').replace('&quot;', '"').replace('&#39;', '\'')
			add_link(name + ' [COLOR lime]('+ duration + ')[/COLOR]', url , 4, thumb, fanart)
		try:
			match = re.compile('<a href="([^"]*)" title="Next">Next</a></li><li>').findall(content)
			add_dir('[COLOR blue]Next  Page  >>>>[/COLOR]', match[0], 2, logos + 'j720p.png', fanart)
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

	elif '.porn.com' in url:
		content = make_request(url)
		add_dir('[COLOR lightblue].porn.com     [COLOR red]Search[/COLOR]', porncom, 1, logos + 'porncom.png', fanart)	
		add_dir('[COLOR lime]Categories[/COLOR]', porncom,  14, logos + 'porncom.png', fanart)
		match = re.compile('<img src="([^"]*)".+?<a href="/videos/(.+?)" class="title">(.+?)</a><span class="added">(.+?)</span>', re.DOTALL).findall(content)
		for thumb, url, name, duration in match:
			add_link(name + ' [COLOR lime]('+ duration + ')[/COLOR]', porncom + '/videos/' + url, 4, thumb, fanart)
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
		match = re.compile('<a class="thumb" href="(.+?)" >\s*<img class="lazy"\s*alt="(.+?)"\s*src=".+?"\s*data-original="(.+?)" width=".+?" height=".+?" />\s*<div class="meta transition">\s*<time>(.+?)</time>').findall(content)
		for url, name, thumb, duration in match:
			add_link(name + ' [COLOR lime]('+ duration + ')[/COLOR]', pornhd + url, 4, thumb, fanart)  
		try:
			match = re.compile('<link rel="next" href="([^"]*)" />').findall(content)
			add_dir('[COLOR blue]Next  Page  >>>>[/COLOR]', pornhd + match[0], 2, logos + 'pornhd.png', fanart)
		except:
			pass
		
	elif 'pornhub' in url:
		content = make_request(url)
		add_dir('[COLOR lightgreen]pornhub.com     [COLOR red]Search[/COLOR]', pornhub, 1, logos + 'pornhub.png', fanart)	
		add_dir('[COLOR lime]Categories[/COLOR]', pornhub + '/categories', 25, logos + 'pornhub.png', fanart) 
		match = re.compile('<li class="videoblock.+?<a href="([^"]+)" title="([^"]+)".+?<var class="duration">([^<]+)<.*?data-mediumthumb="([^"]+)"', re.DOTALL).findall(content)
		for url, name, duration, thumb in match:
			add_link(name + ' [COLOR lime]('+ duration + ')[/COLOR]', pornhub + url, 4, thumb, fanart)
		match = re.compile('<li class="page_next"><a href="([^"]+)" class="orangeButton">Next</a></li>', re.DOTALL).findall(content) 
		add_dir('[COLOR blue]Next  Page  >>>>[/COLOR]', pornhub + match[0].replace('&amp;','&'), 2, logos + 'pornhub.png', fanart)	

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
		add_dir('[COLOR lime]Categories[/COLOR]', pornxs + '/categories.php', 39, logos + 'pornxs.png', fanart) 
		match = re.compile('<a href="([^"]+)"><div class="video-container".+?<img src="([^"]+)" alt="([^"]+)".+?</div><div class="time">([:\d]+)</div>', re.DOTALL).findall(content)
		for url, thumb, name, duration in match:
			add_link(name + ' [COLOR lime]('+ duration + ')[/COLOR]', pornxs + url, 4, thumb, fanart)
		try:
			match = re.compile('<a class="pagination-next" href="([^"]*)"><span></span></a></li> ').findall(content)
			add_dir('[COLOR blue]Next  Page  >>>>[/COLOR]', pornxs + match[0], 2, logos + 'pornxs.png', fanart)
		except:
			pass

	elif 'redtube' in url:
		content = make_request(url)
		add_dir('[COLOR lightgreen]redtube.com     [COLOR red]Search[/COLOR]', redtube, 1, logos + 'redtube.png', fanart)
		add_dir('[COLOR lime]Channels[/COLOR]', redtube + '/channel', 10, logos + 'redtube.png', fanart) 
		match = re.compile('window.location.href =\'([^"]+)\'">([:\d]+)</span>.+?<img title="([^"]+)".+?data-src="([^"]+)"', re.DOTALL).findall(content)
		for url, duration, name, thumb in match:
			name = name.replace('&#39;', ' ').replace('&amp;', '&').replace('&quot;', '"').replace('	', '')
			add_link(name + ' [COLOR lime]('+ duration + ')[/COLOR]', redtube + url, 4, thumb,  fanart)
		try:
			match = re.compile('rel="next" href="([^"]+)">').findall(content)
			add_dir('[COLOR blue]Next  Page  >>>>[/COLOR]', match[0], 2, logos + 'redtube.png', fanart)	
		except:
			pass

	elif 'tube8' in url:
		content = make_request(url)
		add_dir('[COLOR lightgreen]tube8.com     [COLOR red]Search[/COLOR]', tube8, 1, logos + 'tube8.png', fanart)
		add_dir('[COLOR lime]Categories[/COLOR]', tube8 + '/categories.html', 22, logos + 'tube8.png', fanart) 
	   	match = re.compile('class="thumb_box">.+?<a href="([^"]+)".+?src="([^"]+)" alt="([^"]+)".+?video_duration">([:\d]+)</div>', re.DOTALL).findall(content)
		for url, thumb, name, duration in match:
			name = name.replace('&#39;', ' ').replace('&amp;', '&').replace('&quot;', '"').replace('	', '')
			add_link(name + ' [COLOR lime]('+ duration + ')[/COLOR]', url, 4, thumb, fanart)
		match = re.compile('<link rel="next" href="([^"]*)">').findall(content) 
		add_dir('[COLOR blue]Next  Page  >>>>[/COLOR]', match[0], 2, logos + 'tube8.png', fanart)
	
	elif 'tubegalore' in url:
		content = make_request(url)
		add_dir('[COLOR lightgreen]tubegalore.com     [COLOR red]Search[/COLOR]', tubegalore, 1, logos + 'tubegalore.png', fanart)
		add_dir('[COLOR lime]Categories[/COLOR]', tubegalore, 53, logos + 'tubegalore.png', fanart) 
		match = re.compile('target="_blank">([^"]*)</a></span><div class="imgContainer"><a href="/out/?.+?http(.+?)" target="_blank"><img src="([^"]+)".+?.+?target="_blank">([^"]*)</a>.+?<span class="length">([:\d]+)</span>', re.DOTALL).findall(content)
		for name, url, thumb, dummy, duration in match:
			url = url.replace('%3A', ':').replace('%2F', '/').replace('%3F', '?').replace('%3D', '=').replace('%26', '&')
			dummy = dummy.replace('</a>', '')
			if 'GotPorn' in dummy :
				pass
			elif 'porn.porn' in dummy:
				pass
			elif 'PornXOom' in dummy:
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
			match = re.compile('<link rel="next" href="([^"]*)" />').findall(content) 
			add_dir('[COLOR blue]Next  Page  >>>>[/COLOR]', match[0], 2, logos + 'tubegalore.png', fanart)
		except:
			pass
	
	elif 'tubepornclassic' in url:
		content = make_request(url)
		add_dir('[COLOR lightgreen]tubepornclassic     [COLOR red]Search[/COLOR]', tubepornclassic, 1, logos + 'tubepornclassic.png', fanart)
		add_dir('[COLOR lime]Categories[/COLOR]', tubepornclassic + '/categories/',  38, logos + 'tubepornclassic.png', fanart)
		match = re.compile('<div class="item  ">.+?<a href="([^"]+)" title="([^"]+)".*?original="([^"]+)".*?duration">([^<]+)<', re.DOTALL).findall(content)
		for url, name, thumb, duration in match:
			add_link(name + ' [COLOR lime]('+ duration + ')[/COLOR]',  url,  4, thumb, fanart)
		try:
			match = re.compile('<a href="([^"]*)" data-action=".+?" data-container-id=".+?" data-block-id=".+?" data-parameters=".+?" title=\"Next Page\">Next</a>').findall(content)
			add_dir('[COLOR blue]Next  Page  >>>>[/COLOR]', tubepornclassic + match[0], 2, logos + 'tubepornclassic.png', fanart)
		except:
			pass
	
	elif 'txxx' in url:
		content = make_request(url)
		add_dir('[COLOR lightgreen]txxx   [COLOR red]Search[/COLOR]', txxx, 1, logos + 'txxx.png', fanart)
		add_dir('[COLOR lime]Categories[/COLOR]', 'http://m.txxx.com/categories/',  47, logos + 'txxx.png', fanart)
		match = re.compile('<a href="([^"]+)" class="js-thumb-pagination".+?<img src="([^"]+)" alt="([^"]+)".+?<div class="thumb__duration">([^<]+)</div>', re.DOTALL).findall(content)
		for url, thumb, name, duration in match:
			add_link(name + ' [COLOR lime]('+ duration + ')[/COLOR]',  url,  4, thumb, fanart)
		try:
			match = re.compile('<a class=" btn btn--size--l btn--next" href="([^"]+)" title="Next Page"').findall(content)
			add_dir('[COLOR blue]Next  Page  >>>>[/COLOR]', txxx + match[0], 2, logos + 'txxx.png', fanart)
		except:
			pass
	
	elif '.uflash.tv' in url:
		content = make_request(url)
		add_dir('[COLOR lightgreen].uflash.tv   [COLOR red]Search[/COLOR]', uflash, 1, logos + 'uflash.png', fanart)
		add_dir('[COLOR lime]Categories[/COLOR]', uflash + '/videos?o=mr', 54, logos + 'uflash.png', fanart)
		add_dir('[COLOR magenta]Female Exhibitionist Videos[/COLOR]', uflash + '/videos?g=female&o=mr',  2, logos + 'uflash.png', fanart)
		add_dir('[COLOR magenta]Male Exhibitionist Videos[/COLOR]', uflash + '/videos?g=male&o=mr',  2, logos + 'uflash.png', fanart)
		add_dir('[COLOR magenta]Recently Viewed - Exhibitionist Videos[/COLOR]', uflash + '/videos?o=bw',  2, logos + 'uflash.png', fanart)
		match = re.compile('<a href="(.+?)" class="vid" title="(.+?)">\s*<img src="(.+?)" alt=".+?" width=".+?" height=".+?" id=".+?" />\s*.+?\s*\s*.+?\s*<span class="info">\s*<span class="duration">([^<]+)</span>\s*<!--<span class="new">NEW</span>-->').findall(content)
		for url, name, thumb, duration in match:
			add_link(name + ' [COLOR lime]('+ duration + ')[/COLOR]',  uflash + url,  4, uflash + thumb, fanart)
		try:
			match = re.compile('<a href="([^"]+)" class="prevnext">Next&raquo;</a>', re.DOTALL).findall(content)
			add_dir('[COLOR blue]Next  Page  >>>>[/COLOR]', match[0], 2, logos + 'uflash.png', fanart)
		except:
			pass	
			
	elif 'upornia' in url:
		content = make_request(url)
		add_dir('[COLOR lightgreen]upornia   [COLOR red]Search[/COLOR]', upornia, 1, logos + 'upornia.png', fanart)
		add_dir('[COLOR lime]Categories[/COLOR]', upornia + '/categories/',  50, logos + 'upornia.png', fanart)
		add_dir('[COLOR lime]Models[/COLOR]', upornia + '/models/',  51, logos + 'upornia.png', fanart)
		match = re.compile('<a class="thumbnail thumbnail-pagination" href="([^"]*)".+?<img src="([^"]+)" alt="([^"]+)">.+?<div class="thumbnail__info__right">.+?([:\d]+).+?</div>', re.DOTALL).findall(content)
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
		match = re.compile('<a href="(.+?)">\s*<div class=".+?">\s*<img style=".+?" class=".+?"  src=".+?" data-original="(.+?)" alt="(.+?)" onmouseover=".+?" onmouseout=".+?">\s*<span class=".+?">(.+?)</span>').findall(content)
		for url, thumb, name, duration in match:
			add_link(name + ' [COLOR lime]('+ duration + ')[/COLOR]', url,  4, thumb, fanart)
		match = re.compile('<a href="([^"]*)">NEXT</a>').findall(content) 
		add_dir('[COLOR blue]Next  Page  >>>>[/COLOR]', vikiporn + match[0], 2, logos + 'vikiporn.png', fanart)	
	
	elif 'xhamster' in url:
		content = make_request(url)
		add_dir('[COLOR lightgreen]xhamster.com     [COLOR red]Search[/COLOR]', xhamster, 1, logos + 'xhamster.png', fanart)	
		add_dir('[COLOR lime]Categories[/COLOR]', xhamster + '/channels.php', 17, logos + 'xhamster.png', fanart) 
		add_dir('[COLOR lime]Rankings[/COLOR]', xhamster + '/rankings/weekly-top-viewed.html' , 42, logos + 'xhamster.png', fanart) 
		add_dir('[COLOR lime]Change Content[/COLOR]', xhamster , 24, logos + 'xhamster.png', fanart)
		match = re.compile('><a href="http://xhamster.com/movies/(.+?)".+?<img src=\'(.+?)\'.+?alt="([^"]*)".+?<b>(.+?)</b>', re.DOTALL).findall(content)
		for url, thumb, name, duration in match:
			name = name.replace('&amp;', '&').replace('&quot;', '"').replace('&#39;', '\'')
			if '?from=video_promo' in url:
				pass
			else:
				add_link(name + ' [COLOR lime]('+ duration + ')[/COLOR]', 'http://xhamster.com/movies/' + url, 4, thumb, fanart)
		match = re.compile('<div id="cType"><div class="([^"]*)"></div>').findall(content)
		if "iconL iconTrans" in match :
			match = re.compile('<link rel="next" href="([^"]*)"><link rel="dns-prefetch"').findall(content) 
			add_dir('[COLOR blue]Next  Page  >>>>[/COLOR]', match[0] + '?content=shemale', 2, logos + 'xhamster.png', fanart)	
		if "iconL iconGays" in match :
			match = re.compile('<link rel="next" href="([^"]*)"><link rel="dns-prefetch"').findall(content) 
			add_dir('[COLOR blue]Next  Page  >>>>[/COLOR]', match[0] + '?content=gay', 2, logos + 'xhamster.png', fanart)	
		else :
			match = re.compile('<link rel="next" href="([^"]*)"><link rel="dns-prefetch"').findall(content) 
			add_dir('[COLOR blue]Next  Page  >>>>[/COLOR]', match[0] , 2, logos + 'xhamster.png', fanart)	
		

	elif 'xvideos' in url:
		content = make_request(url)
		add_dir('[COLOR lightgreen]xvideos.com     [COLOR red]Search[/COLOR]', xvideos, 1, logos + 'xvideos.png', fanart)
		add_dir('[COLOR lime]Categories[/COLOR]', xvideos,  27, logos + 'xvideos.png', fanart)
		add_dir('[COLOR lime]Pornstars[/COLOR]', xvideos + '/pornstars',  32, logos + 'xvideos.png', fanart)
	   	match = re.compile('<a href="([^"]*)"><img src="([^"]*)".+? title="([^"]*)">.+?"duration">\(([^"]*)\)</span>', re.DOTALL).findall(content)
		for url, thumb, name, duration in match:
			name = name.replace('&amp;', '&').replace('&quot;', '"').replace('&#39;', '`')
			add_link(name + ' [COLOR lime]('+ duration + ')[/COLOR]', xvideos + url, 4, thumb, fanart)
		try:
			match = re.compile('<a href="([^"]*)" class=\"no-page\"').findall(content) 
			add_dir('[COLOR blue]Next  Page  >>>>[/COLOR]', xvideos + match[0], 2, logos + 'xvideos.png', fanart)
		except:
			pass		
				
	elif 'youjizz' in url:
		content = make_request(url)
		add_dir('[COLOR lightgreen]youjizz.com  [COLOR red]Search[/COLOR]', youjizz, 1, logos + 'youjizz.png', fanart)
		add_dir('[COLOR lime]Categories[/COLOR]', youjizz + '/newest-clips/1.html' , 28, logos + 'youjizz.png', fanart)
		match = re.compile('<a class="frame" href=\'([^\']+)\'.+?data-original="([^"]+)".+?<span id="title1">([^"]+)</span>.+?>([:\d]+)</span>', re.DOTALL).findall(content)
		for url, thumb, name, duration in match:
			add_link(name + ' [COLOR lime]('+ duration + ')[/COLOR]', youjizz + url, 4, thumb, fanart)
		match = re.compile("<a href='([^']+)'>Next", re.DOTALL).findall(content)
		add_dir('[COLOR blue]Next  Page  >>>>[/COLOR]', youjizz + match[0], 2, logos + 'youjizz.png', fanart)

	elif 'youporn' in url:
		add_dir('[COLOR lightgreen]youporn.com  [COLOR red]Search[/COLOR]', youporn, 1, logos + 'youporn.png', fanart)
		add_dir('[COLOR lime]Categories[/COLOR]', youporn + '/categories/', 31, logos + 'youporn.png', fanart)
		add_dir('[COLOR lime]Sorting[/COLOR]', youporn, 43, logos + 'youporn.png', fanart)
		content = make_request(url)
		match = re.compile('<a href="([^"]*)" class=\'video-box-image\' >.+?alt=\'([^"]+)\'.+?data-thumbnail="([^"]+)".+?<span class="video-box-duration">.+?([:\d]+)	</span>', re.DOTALL).findall(content)
		for url, name, thumb, duration in match:
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
			match = re.compile('<a style="text-decoration:none;" href="([^"]*)">.+?<img src="([^"]*)".+?alt="([^"]*)".+?<div class="duration">([:\d]+)</div>', re.DOTALL).findall(content)
			for url, thumb, name, duration in match:
				name = name.replace('&amp;', '&').replace('&quot;', '"').replace('&#39;', '\'').replace('	', '')
				add_link(name + '[COLOR lime] (' + duration + ')[/COLOR]', yespornplease + url,  4, thumb, fanart)		
		else:
			match = re.compile('class="video-link" href="([^"]*)">.+?<img src="([^"]*)".+?alt="([^"]*)".+?<div class="duration">([:\d]+)</div>', re.DOTALL).findall(content)
			for url, thumb, name, duration in match:
				name = name.replace('&amp;', '&').replace('&quot;', '"').replace('&#39;', '\'').replace('	', '')
				add_link(name + '[COLOR lime] (' + duration + ')[/COLOR]', yespornplease + url,  4, thumb, fanart)		
		try:
			match = re.compile('<a href="(.+?)" class="prevnext">Next &raquo;</a></li>').findall(content)
			add_dir('[COLOR blue]Next  Page  >>>>[/COLOR]', yespornplease + match[0], 2, logos + 'yespp.png', fanart)
		except:
			pass
			
	elif 'yes.xxx' in url:
		content = make_request(url)
		add_dir('[COLOR lightgreen]yes.xxx    [COLOR red]Search[/COLOR]', yesxxx, 1, logos + 'yes.png', fanart)	
		add_dir('[COLOR lime]Categories[/COLOR]', yesxxx + '?s=tags', 37, logos + 'yes.png', fanart)
		match = re.compile('href="/([^"]*)" title="([^"]*)"><img src="([^"]*)" /><br></a></div><div class="dur">([:\d]+)</div>').findall(content)
		for url, name, thumb, duration in match:
			name = name.replace('&amp;', '&').replace('&quot;', '"').replace('&#39;', '\'').replace('	', '')
			add_link(name + '[COLOR lime] (' + duration + ')[/COLOR]', yesxxx + url,  4, thumb, fanart)		
		match = re.compile('<li><a href="(.+?)">Next</a></li>').findall(content)
		add_dir('[COLOR blue]Next  Page  >>>>[/COLOR]', yesxxx + match[0], 2, logos + 'yes.png', fanart)
	
	elif 'zbporn' in url:
		content = make_request(url)
		add_dir('[COLOR lightgreen]zbporn.com    [COLOR red]Search[/COLOR]', zbporn, 1, logos + 'zbporn.png', fanart)
		add_dir('[COLOR lime]Categories[/COLOR]', zbporn + '/categories/',  23, logos + 'zbporn.png', fanart)
		match = re.compile('href="([^"]*)" data-rt=".+?"><img src="([^"]+)" alt="([^"]+)">.+?<span class="length">([:\d]+)</span>', re.DOTALL).findall(content)
		for url, thumb, name, duration in match:
			add_link(name + ' [COLOR lime]('+ duration + ')[/COLOR]', url , 4, thumb, fanart)
		try:
			match = re.compile('</li>\s*<li><a data-page=".+?" href="(.+?)">.+?</a></li>\s*<li><a').findall(content)
			add_dir('[COLOR blue]Next  Page  >>>>[/COLOR]', zbporn + match[0], 2, logos + 'zbporn.png', fanart)
		except:
			pass			

def pornhd_categories(url):
	home()
	content = make_request(url)
	match = re.compile('<a href="([^"]*)">.+?alt="([^"]*)".+?data-original="([^"]*)"', re.DOTALL).findall(content)
	for url, name, thumb in match:
		add_dir(name, pornhd + url, 2, thumb, fanart)

def pornhd_pornstars(url):
	home()
	content = make_request(url)
	match = re.compile('data-original="([^"]*)"\s*width=".+?"\s*height=".+?"\s*/>\s*</a>\s*<div class="info">\s*<a class="name" href="([^"]*)">\s*(.+?)\s*<').findall(content)
	for thumb, url, name in match:
		add_dir(name, pornhd + url, 2, thumb, fanart)
	match = re.compile('<link rel="next" href="([^"]*)" />').findall(content)
	add_dir('[COLOR blue]Next  Page  >>>>[/COLOR]', pornhd + match[0], 20, logos + 'pornhd.png', fanart)

def eporner_categories(url):
	home()
	content = make_request(url)		
	match = re.compile('href="/category/([^"]*)" title="([^"]*)"><img src="([^"]*)"').findall(content)
	for url, name, thumb in match:
		add_dir(name, eporner + '/category/' + url, 2, thumb, fanart)
		
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

def redtube_channels_list(url):
	home()
	content = make_request(url)
	match = re.compile('href="(.+?)" class="channels-list-img">\s*<img src="(.+?)" alt="(.+?)">').findall(content)
	for url, thumb, name in match:
		add_dir(name, redtube + url, 2, thumb, fanart)
	try:
		match = re.compile('rel="next" href="([^"]+)">').findall(content)
		add_dir('[COLOR blue]Next  Page  >>>>[/COLOR]', match[0], 11, logos + 'redtube.png', fanart)	
	except:
		pass

def redtube_channels_cat(url): 
	home()
	content = make_request(url)
	match = re.compile('href="/channel/(.+?)" title="(.+?)">').findall(content)
	for url, name in match:
		add_dir(name, redtube + '/channel/' + url, 11, logos + 'redtube.png', fanart)  		
		
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
	match = re.compile('href="http://xhamster.com/channels/(.+?)">(.+?)<').findall(content)
	for url, name in match:
		name = name.replace('&amp;', '&').replace('&quot;', '"').replace('&#39;', '´')
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
	match = re.compile('<a href="http://www.tube8.com/cat/([^"]*)">([^"]*)</a>\s*				</li>').findall(content)
	for url, name in match:
		add_dir(name, tube8 + '/cat/' + url, 2, logos + 'tube.png', fanart)

def zbporn_categories(url) :
	home()
	content = make_request(url)
	match = re.compile('<a href="([^"]*)"><div class="img_hold"><img src="([^"]*)" alt="([^"]*)"><span class="info"').findall(content)
	for url, thumb, name in match:
		add_dir(name, url, 2, thumb, fanart)

def pornhub_categories(url) :
	home()
	content = make_request(url)
	match = re.compile('<div class="category-wrapper">.+?<a href="(.+?)"  alt="(.+?)">.+?<img src="(.+?)"', re.DOTALL).findall(content)
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
	match = re.compile('<li><a target=\"_blank\" href="([^"]+)" >([^"]+)</a></li>').findall(content)
	for url,name in match:
		url = url.replace('High Definition', 'HighDefinition');
		add_dir(name, url, 2, logos + 'youjizz.png', fanart)	
		
def hentaigasm_categories(url) :
	home()
	content = make_request(url)
	match = re.compile("<a href='http://hentaigasm.com/tag/([^']+)'").findall(content)
	for url in match:
		name = url.replace('http://hentaigasm.com/tag/', '').replace ('/', '')
		add_dir(name, 'http://hentaigasm.com/tag/' + url, 2, logos + 'hentaigasm.png', fanart)
		
def youporn_categories(url)	:
	home()
	content = make_request(url)
	match = re.compile('<a href="([^"]+)" class=".+?" onclick=".+?">\s*<img src="([^"]+)" alt="([^"]+)">').findall(content)
	for url, thumb, name in match:
		add_dir(name, youporn + url, 2, thumb, fanart)
		
def ashemaletube_categories(url) :
	home()
	content = make_request(url)	
	match = re.compile('Galleries" src="([^"]+)".+?href="/videos/([^"]+)/best-recent/">([^>]+)</a>', re.DOTALL).findall(content)
	for thumb, url, name in match:
		add_dir(name, ashemaletube + '/videos/' + url + '/newest/', 2, thumb, fanart)
			
def	heavyr_categories(url) :
	home()
	content = make_request(url)	
	match = re.compile('<a href="([^"]+)" class="image">.+?<img src="([^"]+)" alt="([^"]+)', re.DOTALL).findall(content)
	for url, thumb, name in match:
		add_dir(name, heavyr + url, 2, heavyr + thumb, fanart)
		
def jav720p_categories(url) :
	home()
	content = make_request(url)	
	match = re.compile('<div class="col-sm-4"> <h3 class="title-category"><a href="([^"]+)" title="All JAV Genre .+?">([^"]+)</a></h3> </div>', re.DOTALL).findall(content)
	for url, name in match:
		add_dir(name, url, 2, logos + 'j720p.png', fanart)

def jav720p_models(url) :
	home()
	content = make_request(url)	
	match = re.compile('<div class="col-sm-4"> <h3 class="title-category"><a href="([^"]+)" title="All JAV Model .+?">([^"]+)</a></h3> </div>', re.DOTALL).findall(content)
	for url, name in match:
		add_dir(name, url, 2, logos + 'j720p.png', fanart)
		
def jav720p_makers(url) :
	home()
	content = make_request(url)	
	match = re.compile('<div class="col-sm-4"> <h3 class="title-category"><a href="([^"]+)" title="All JAV maker .+?">([^"]+)</a></h3> </div>', re.DOTALL).findall(content)
	for url, name in match:
		add_dir(name, url, 2, logos + 'j720p.png', fanart)	

def xvideos_categories(url) :
	home()
	content = make_request(url)	
	match = re.compile('<li><a href="(/c/\w+[-]\d+)" class="btn btn-default">([^"]+)<\/a></li>', re.DOTALL).findall(content)
	for url, name in match:
		add_dir(name, xvideos + url, 2, logos + 'xvideos.png', fanart)	

def xvideos_pornstars(url) :
	home()
	content = make_request(url)	
	match = re.compile('Url\(\'<img src="([^"]+)".+?<p class="profile-name"><a href="/pornstars-click/13/([^"]+)">([^"]+)</a></p><p', re.DOTALL).findall(content)
	for thumb, url, name in match:
		add_dir(name, xvideos + '/profiles/' + url + '/videos/', 2, thumb, fanart)	
	try:
		match = re.compile('<a class="active" href=".+?">.+?</a></li><li><a href="([^"]+)">.+?</a></li><li>', re.DOTALL).findall(content)
		add_dir('[COLOR blue]Next  Page  >>>>[/COLOR]', xvideos + match[0], 32, logos + 'xvideos.png', fanart)
	except:
		pass
		
def yesxxx_categories(url) :
	home()
	content = make_request(url)
	match = re.compile('<a href="([^"]+)" title="([^"]+)"><img src="([^"]+)"', re.DOTALL).findall(content)
	for url, name, thumb in match:
		add_dir(name, yesxxx +  url , 2, thumb, fanart)	
	try:
		match = re.compile('<li><a href="([^"]+)">Next</a></li>', re.DOTALL).findall(content)
		add_dir('[COLOR blue]Next  Page  >>>>[/COLOR]', yesxxx + match[0], 37, logos + 'yes.png', fanart)
	except:
		pass
		
def tubepornclassic_categories(url) :
	home()
	content = make_request(url)
	match = re.compile('a class="item" href="([^"]+)" title="([^"]+)">.+?<img class="thumb" src="([^"]+)".+?<div class="videos">([^"]+)</div>', re.DOTALL).findall(content)
	for url, name, thumb, duration in match:
		add_dir(name + ' [COLOR lime]('+ duration + ')[/COLOR]',  url,  2, thumb, fanart)		
		
def pornxs_categories(url) :
	home()
	content = make_request(url)
	match = re.compile('<a href="(.+?)">.+?/img/categories/(.+?).jpg.+?caption">([^"]+)</div>', re.DOTALL).findall(content)
	for url, thumb, name in match:
		name = name.replace (' ', '')
		add_dir(name, pornxs + url,  2,  pornxs + '/img/categories/' + thumb + 'pornxs.jpg', fanart)	

def gotporn_categories(url) :
	home()
	content = make_request(url)
	match = re.compile(' <a class="category-list-item" href="([^"]+)">(.+?)<span>([^"]+)</span>', re.DOTALL).findall(content)
	for url, name, duration in match:
		name = name.replace (' ', '')
		add_dir(name + ' [COLOR lime]('+ duration + ')[/COLOR]',  url,  2, logos + 'gotporn.png', fanart)
		
def gotporn_content(url) :
	home()
	content = make_request(url)
	match = re.compile('<a href="http://www.gotporn.com/browse-settings/(.+?)"').findall(content)
	for url in match:
		name = url
		name = name.replace ('store?orientation=', '')
		add_dir(name, 'http://www.gotporn.com/browse-settings/' + url,  2, logos + 'gotporn.png', fanart)
		
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
	match = re.compile('<span class="thumb2">.+?<a href="//www.empflix.com/categories/([^"]+)" class="floatLeft">.+?<img src="([^"]+)" alt="([^"]+)">', re.DOTALL).findall(content)
	for url, thumb, name in match:
		name = name.replace('&amp;', '&').replace('&quot;', '"').replace('&#39;', '\'')
		add_dir(name, 'http://www.empflix.com/categories/' + url, 2, 'http:' + thumb, fanart)
		
def emplix_sorting(url) :
	home()
	content = make_request(url)
	match = re.compile('href="([^"]*)"  >(Being Watched|Most Recent|Most Viewed|Top Rated)').findall(content)
	for url, name in match:
		add_dir(name, empflix  + url,  2, logos + 'empflix.png', fanart)

def	txxx_categories(url):
	home()
	content = make_request(url)
	match = re.compile('<a class="thumbnail" href="([^"]*)" title="([^"]*)">.+?="([^"]*)".+?<strong>(.+?)</strong> videos', re.DOTALL).findall(content)
	for url, name, thumb, duration in match:
		add_dir(name + ' [COLOR lime]('+ duration + ')[/COLOR]', txxx + url,  2, thumb, fanart)

def fantasti_collections(url):
	home()
	content = make_request(url)
	add_dir('[COLOR lime]Sorting [/COLOR]', fantasti + '/videos/collections/popular/today/',  49, logos + 'fantasti.png', fanart)
	match = re.compile('30px; "><a href="([^"]+)">([^"]+)</a>.+?src="([^"]+)"', re.DOTALL).findall(content)
	for url, name, thumb in match:
		add_dir(name, fantasti + url,  2, thumb, fanart)
	try:
		match = re.compile('<a href="([^"]+)">next &gt;&gt').findall(content)
		add_dir('[COLOR blue]Next  Page  >>>>[/COLOR]', fantasti + match[0], 48, logos + 'fantasti.png', fanart)	
	except:
		pass	
		

def fatasti_sorting(url) :
	home()
	content = make_request(url)
	if 'collections' in url:
		match = re.compile('href="/videos/collections/popular(.+?)" style=".+?">(Today|This Week|This Month|All Time)</a>').findall(content) 
		for url, name in match:
			add_dir('Popular Videos ' + name, fantasti + '/videos/collections/popular' + url,  48, logos + 'fantasti.png', fanart)		
	else:
		match = re.compile('<a href="/videos/popular/(.+?)" style=".+?">(today|this week|this month|all time)</a>').findall(content)
		for url, name in match:
			add_dir('Popular Videos ' + name, fantasti + '/videos/popular/' + url,  2, logos + 'fantasti.png', fanart)	

def	upornia_categories(url):
	home()
	content = make_request(url)
	match = re.compile('<a class="thumbnail" href="(.+?)" title="(.+?)">.+?<img src="(.+?)" alt=".+?">', re.DOTALL).findall(content)
	for url, name, thumb in match:
		add_dir(name , url,  2, thumb, fanart)

def	upornia_models(url):
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
	match = re.compile('<a href="([^"]*)" target="_blank">([^<]+)<span class="badge float-right">', re.DOTALL).findall(content)
	for url, name in match:
		name = name.replace('	', '')
		add_dir(name, tubegalore + url,  2, logos + 'tubegalore.png', fanart)
		
def	uflash_categories(url):
	home()
	content = make_request(url)
	match = re.compile('<li><a href="(.+?)">([^<]+)</a></li>', re.DOTALL).findall(content)
	for url, name in match:
		add_dir(name, uflash + url,  2, logos + 'uflash.png', fanart)
	
def resolve_url(url):
	content = make_request(url)
	if 'xvideos' in url:
		media_url = urllib.unquote(re.compile("flv_url=(.+?)&amp").findall(content)[-1]) 
	elif 'tube8' in url:
		media_url = re.compile('videoUrlJS = "(.+?)"').findall(content)[0]
	elif 'redtube' in url: 
		try:
			video_url = re.compile('<source src="(.+?)" type="video/mp4">').findall(content)[0] # 720p+480p
		except:
			video_url = re.compile('value="quality_.+?=(.+?)=').findall(content)[0]   #240p
		media_url = urllib.unquote_plus(video_url)
	elif '.porn.com' in url:
		try:
			media_url = re.compile('id:"720p",url:"(.+?)",definition:"HD"').findall(content)[0]
		except:
			media_url = re.compile('id:"240p",url:"(.+?)"},').findall(content)[0]
	elif 'vikiporn' in url:
		media_url = re.compile("video_url: '(.+?)'").findall(content)[0]
	elif 'xhamster' in url:
		media_url = re.compile("file: '(.+?)',").findall(content)[0]
	elif 'lubetube' in url: 
		media_url = re.compile('id="video-.+?" href="(.+?)"').findall(content)[0] 	
	elif 'yes.xxx' in url: 
		media_url = re.compile("video_url: '(.+?)',video_url_text:").findall(content)[0]		
	elif 'pornxs' in url: 
		media_url = re.compile('config-final-url="(.+?)"').findall(content)[0]	
	elif 'zbporn' in url: 
		media_url = re.compile('file: "(.+?)",').findall(content)[0]	
	elif 'pornhd' in url: 
		try:
			media_url = re.compile("'720p'  : '(.+?)'").findall(content)[0]	
		except:
			media_url = re.compile("'480p'  : '(.+?)'").findall(content)[0]			
	elif 'motherless' in url:		
		media_url = re.compile('__fileurl = \'(.+?)\';').findall(content)[0]
	elif 'tubepornclassic' in url:		
		media_url = re.compile("video_url: '(.+?)',").findall(content)[0]
	elif 'efukt' in url:	
		media_url = re.compile('<source src="(.+?)" type="video/mp4">').findall(content)[0]
	elif 'pornhub' in url:	
		media_url = re.compile("var player_quality_.+? = '(.+?)'").findall(content)[0]
	elif 'pornsocket' in url:	
		media_url = pornsocket + re.compile('<source src="(.+?)" type="video/mp4"/>').findall(content)[0]
	elif 'youjizz' in url:
		media_url = re.compile('<a href="(.+?)" class=".+?" >Download This Video</a>').findall(content)[0]
	elif 'hentaigasm' in url:
		media_url = re.compile('file: "(.+?)",').findall(content)[0]
	elif 'ashemaletube' in url:	
		try:
			media_url = re.compile('"(.+?).mp4", label: "High Quality"}').findall(content)[0] + '.mp4'
		except:
			media_url = re.compile('"(.+?).mp4"').findall(content)[0] + '.mp4'
	elif 'youporn' in url:	
		try:
			media_url = re.compile("720: '([^']+)").findall(content)[0]
		except:	
			media_url = re.compile("480: '([^']+)").findall(content)[0]
	elif 'heavy-r' in url:	
			media_url = re.compile("file: '([^']+)',").findall(content)[0]
	elif 'jav720p' in url:
			media_url = re.compile('file: "([^"]+)"').findall(content)[0]
	elif 'gotporn' in url:
			media_url = re.compile('<source src="([^"]+)"').findall(content)[0]
	elif 'empflix' in url:
		try:
			video_url = re.compile('<videoLink>([^<]+.mp4[^<]+)').findall(content)[-1]
		except:
			video_url = re.compile('<videoLink>([^<]+.mp4[^<]+)').findall(content)[-1]
		media_url = urllib.unquote_plus(video_url)
	elif 'txxx' in url:
		media_url = re.compile('file\': \'(.+?)\',').findall(content)[0]
		media_url = re.compile('file\': \'(.+?)\',').findall(content)[0]
	elif 'drtuber' in url:
		media_url = re.compile('<source src="(.+?)"').findall(content)[0]
	elif 'upornia' in url:
		media_url = re.compile('video_url: \'(.+?)\',').findall(content)[0]
	elif 'yespornplease' in url:
		media_url = re.compile('.*?video_url=(.+?)&.*?').findall(content)[0]
	elif 'fantasti.cc' in url:	
		url = re.compile('<div class="video-wrap" data-origin-source="([^"]+)">').findall(content)[0]
		return resolve_url(url)
	elif 'tnaflix' in url:
		media_url = re.compile('<meta itemprop="contentUrl" content="([^"]+)" />').findall(content)[0]
	elif 'uflash' in url:
		media_url = re.compile('<source src="([^"]+)" type="video/mp4">').findall(content)[0]
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
		media_url = re.compile('file: "(.+?)"').findall(content)[0]
	elif 'pornicom' in url:		
		media_url = re.compile('video_url: \'(.+?)\',').findall(content)[0]
	elif 'sheshaft' in url:		
		media_url = re.compile('video_url: \'(.+?)\',').findall(content)[0]
	elif 'ashemaletv' in url:		
		media_url = re.compile('file: "(.+?)"').findall(content)[0]
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
		media_url = re.compile('file: "(.+?)"').findall(content)[0]
	elif '3movs' in url:		
		media_url = re.compile('video_url: \'(.+?)\',').findall(content)[0]
	elif 'pornoxo' in url:		
		media_url = re.compile('file: "(.+?)"').findall(content)[0]
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
	elif 'pornyeah' in url:				
		video_url = re.compile('flashvars="settings=(.+?)').findall(content)[0]
		media_url = urllib.unquote_plus(video_url)
		#media_url = 'http://' + re.compile('flvMask:http://(.+?).mp4;').findall(video_url)[-1] + '.mp4'
	
	else:
		media_url = url
	item = xbmcgui.ListItem(name, path = media_url)
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
	ok = xbmcplugin.addDirectoryItem(handle = int(sys.argv[1]), url = u, listitem = liz, isFolder = True)
	return ok
	
def add_link(name, url, mode, iconimage, fanart):
	u = sys.argv[0] + "?url=" + urllib.quote_plus(url) + "&mode=" + str(mode) + "&name=" + urllib.quote_plus(name) + "&iconimage=" + urllib.quote_plus(iconimage)	
	liz = xbmcgui.ListItem(name, iconImage = "DefaultVideo.png", thumbnailImage = iconimage)
	liz.setProperty('IsPlayable', 'true')  
	ok = xbmcplugin.addDirectoryItem(handle = int(sys.argv[1]), url = u, listitem = liz)  

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
	start(url)
  
elif mode == 3:
	media_list(url)

elif mode == 4:
	resolve_url(url) 

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
	jav720p_categories(url)
	
elif mode == 35:	
	jav720p_models(url)

elif mode == 36:	
	jav720p_makers(url)

elif mode == 37:	
	yesxxx_categories(url)

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

elif mode == 60:	
	motherless_galeries_cat(url)
	
elif mode == 61:	
	motherless_being_watched_now(url)

elif mode == 62:	
	motherless_groups_cat(url)
	
xbmcplugin.endOfDirectory(int(sys.argv[1]))