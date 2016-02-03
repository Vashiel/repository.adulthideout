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
homemenu = xbmc.translatePath(os.path.join(home, 'resources', 'playlists', 'xxx_playlist.m3u'))


#define webpages.
redtube = 'http://www.redtube.com'
xvideos = 'http://www.xvideos.com'
xhamster = 'http://xhamster.com'
tnaflix = 'https://www.tnaflix.com/'
vikiporn = 'http://www.vikiporn.com'
tube8 = 'http://www.tube8.com'
pornxs = 'http://pornxs.com'
pornhd = 'http://www.pornhd.com'
lubetube = 'http://lubetube.com/'
porncom = 'http://www.porn.com'
flyflv = 'http://www.flyflv.com'
zbporn = 'http://zbporn.com'
yesxxx = 'http://www.yes.xxx/'
youjizz = 'http://www.youjizz.com'
motherless = 'http://motherless.com'
eporner = 'http://www.eporner.com'
tubepornclassic = 'http://www.tubepornclassic.com'
crazyshit = 'http://www.crazyshit.com'
efukt = 'http://efukt.com/'
pornhub = 'http://pornhub.com'
pornsocket = 'http://pornsocket.com'

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
		req.add_header('User-Agent', 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:19.0) Gecko/20100101 Firefox/19.0')
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
	
	add_dir('Eporner [COLOR yellow] Videos[/COLOR]', eporner + '/0/', 2, logos + 'eporner.png', fanart)
	add_dir('FlyFLV [COLOR yellow] Videos[/COLOR]', flyflv + '/1?sort=addDate', 2, logos + 'flyflv.png', fanart) 
	add_dir('LubeTube [COLOR yellow] Videos[/COLOR]', lubetube + 'view', 2, logos + 'lubetube.png', fanart) 
	add_dir('Motherless [COLOR yellow] Videos[/COLOR]', motherless + '/videos/recent?page=1', 2, logos + 'motherless.png', fanart)
	add_dir('PornCom [COLOR yellow] Videos[/COLOR]', porncom + '/videos?p=1', 2, logos + 'porncom.png', fanart)	
	add_dir('PornHD [COLOR yellow] Videos[/COLOR]', pornhd, 2, logos + 'pornhd.png', fanart)
	add_dir('PornHub [COLOR yellow] Videos[/COLOR]', pornhub +'/video?page=1', 2, logos + 'pornhub.png', fanart)
	add_dir('Pornsocket [COLOR yellow] Videos[/COLOR]', pornsocket + '/media-gallery.html?display=list&limitstart=0', 2, logos + 'pornsocket.png', fanart)	
	add_dir('PornXS [COLOR yellow] Videos[/COLOR]', pornxs + '/browse/sort-time/', 2, logos + 'pornxs.png', fanart)		
	add_dir('RedTube [COLOR yellow] Videos[/COLOR]', redtube + '/?page=1', 2, logos + 'redtube.png', fanart)
	add_dir('TnAFlix [COLOR yellow] Videos[/COLOR]', tnaflix + 'new/1/', 2, logos + 'tnaflix.png', fanart) 	
	add_dir('Tube8 [COLOR yellow] Videos[/COLOR]', tube8 + '/newest.html',  2, logos + 'tube8.png', fanart)
	add_dir('Tubepornclassic [COLOR yellow] Videos[/COLOR]', tubepornclassic + '/latest-updates/', 2, logos + 'tpc.png', fanart)
	add_dir('ViKiPorn [COLOR yellow] Videos[/COLOR]', vikiporn + '/latest-updates/', 2, logos + 'vikiporn.png', fanart) 
	add_dir('xHamster [COLOR yellow] Videos[/COLOR]', xhamster, 2, logos + 'xhamster.png', fanart)
	add_dir('Xvideos [COLOR yellow] Videos[/COLOR]', xvideos, 2, logos + 'xvideos.png', fanart)
	add_dir('Yes XXX [COLOR yellow] Videos[/COLOR]', yesxxx + '?s=recent', 2, logos + 'yes.png', fanart)
	add_dir('YouJizz [COLOR yellow] Videos[/COLOR]', youjizz + '/newest-clips/1.html', 2, logos + 'youjizz.png', fanart)	
	add_dir('ZBPorn [COLOR yellow] Videos[/COLOR]', zbporn + '/latest-updates/', 2, logos + 'zbporn.png', fanart)
	add_dir('CrazyShit [COLOR yellow] Videos[/COLOR]', crazyshit + '/videos/', 2, logos + 'crazyshit.png', fanart)
	add_dir('Efukt [COLOR yellow] Videos[/COLOR]', efukt, 2, logos + 'efukt.png', fanart)


#Search part. Add url + search expression + searchtext	
def search():
	try:
		keyb = xbmc.Keyboard('', '[COLOR yellow]Enter search text[/COLOR]')
		keyb.doModal()
		if (keyb.isConfirmed()):
			searchText = urllib.quote_plus(keyb.getText())
		if 'redtube.com' in name:
			url = redtube + '/?search=' + searchText      	  
			media_list(url) 
		elif 'youjizz.com' in name:  
			url = youjizz + '/srch.php?q=' + searchText     	  
			media_list(url)			
		elif 'tube8.com' in name:
			url = tube8 + '/searches.html?q=' + searchText      	  
			start(url)
		elif '.porn.com' in name:
			url = porncom + '/videos/search?q=' + searchText  
			media_list(url) 
		elif 'flyflv.com' in name:
			url = flyflv + '/?q=' + searchText      	  
			media_list(url)
		elif 'vikiporn.com' in name:
			url = vikiporn + '/search/?q=' + searchText      	  
			media_list(url)	
		elif 'xhamster.com' in name:
			url = xhamster + '/search.php?q=' + searchText +'&qcat=video'     	  
			start(url)	
		elif 'tnaflix.com' in name:
			url = tnaflix + 'search.php?what=' + searchText  	  
			media_list(url)	
		elif 'lubetube.com' in name:
			url = lubetube + 'search/title/' + searchText.replace('+', '_') + '/'	  
			media_list(url)	
		elif 'yes.xxx' in name:
			url = yesxxx + '?s=search&search=' + searchText	  
			start(url)			
		elif 'pornxs' in name:
			url = pornxs + '/search.php?s=' + searchText
			media_list(url)
		elif 'zbporn' in name:
			url = zbporn + '/search/?q=' + searchText	  
			start(url)	
		elif 'pornhd.com' in name:
			url = pornhd + '/search?search=' + searchText 
			start(url)				
		elif 'xvideos.com' in name:
			url = xvideos + '/?k=' + searchText      	  
			media_list(url)
		elif 'motherless' in name:
			if 'Groups' in name:
				url = motherless + '/search/groups?term=' + searchText + '&member=&sort=date&range=0&size=0'
				motherless_groups_cat(url)
			if 'Galleries' in name:
				url = motherless + '/search/Galleries?term=' + searchText + '&member=&sort=date&range=0&size=0'	  
				motherless_galeries_cat(url)
			else:
				url = motherless + '/term/videos/' + searchText	  
				media_list(url)	
		elif 'eporner' in name:
			url = eporner + '/search/' + searchText 
			start(url)	
		elif 'tubepornclassic' in name:
			url = tubepornclassic + '/search/' + searchText + '/'
			start(url)
		elif 'crazyshit' in name:
			url = crazyshit + '/search/result.php?type=all&search=' + searchText 
			start(url)
		elif 'efukt' in name:
			url = efukt + '/search/' + searchText 
			start(url)
		elif 'pornhub' in name:
			url = pornhub + '/video/search?search=' + searchText 
			start(url)
		elif 'pornsocket' in name:
			url = pornsocket + '/media-gallery.html?filter_search=&amp;filter_tag=' + searchText 
			start(url)
			
			
	except:
		pass

def start(url): 
	home()
	if 'youjizz' in url:
		content = make_request(url)
		add_dir('[COLOR yellow]youjizz.com  [COLOR red]Search[/COLOR]', youjizz, 1, logos + 'youjizz.png', fanart)
		add_dir('[COLOR lime]HD[/COLOR]', youjizz + '/search/highdefinition-1.html', 3, logos + 'youjizz.png', fanart)
		match = re.compile("<a href=\"(.+?)\" ><span>(.+?)<\/span><\/a>").findall(content)
		for url, name in match:
			add_dir(name, youjizz + url, 3, logos + 'youjizz.png', fanart)  
		match = re.compile("<a href=\"([^\"]*)\"><span>(.+?)<\/span><\/a>").findall(content)[1:-1]
		for url, name in match:
			add_dir(name, youjizz + url, 3, logos + 'youjizz.png', fanart)
		match = re.compile("<a class=\".+?\" href='(.+?)' target='_self' style='text-decoration: none;'></a>\s*<img class=\".+?\" src=\".+?\" data-original=\"(.+?)\">\s*</span>\s*<span id=\".+?\">(.+?)</span>").findall(content) [1:-1]
		for url, thumb, name in match:
			add_link(name, youjizz + url, 4, thumb, logos + 'youjizz.png')
	
	elif 'pornhd' in url:
		add_dir('[COLOR lime]pornhd.com     [COLOR red]Search[/COLOR]', pornhd, 1, logos + 'pornhd.png', fanart)	
		add_dir('[COLOR magenta]Categories[/COLOR]', pornhd + '/category', 19, logos + 'pornhd.png', fanart)
		add_dir('[COLOR magenta]Pornstars[/COLOR]', pornhd + '/pornstars?order=video_count&gender=female', 20, logos + 'pornhd.png', fanart) 
		content = make_request(url)
		match = re.compile('<a class="thumb" href="(.+?)" >\s*<img class="lazy"\s*alt="(.+?)"\s*src=".+?"\s*data-original="(.+?)" width=".+?" height=".+?" />\s*<div class="meta transition">\s*<time>(.+?)</time>').findall(content)
		for url, name, thumb, duration in match:
			add_link(name + ' [COLOR lime]('+ duration + ')[/COLOR]', pornhd + url, 4, thumb, fanart)  
		try:
			match = re.compile('<link rel="next" href="([^"]*)" />').findall(content)
			add_dir('[COLOR blue]Next  Page  >>>>[/COLOR]', pornhd + match[0], 2, logos + 'pornhd.png', fanart)
		except:
			pass

	elif 'tnaflix' in url:
		content = make_request(url)
		add_dir('[COLOR green]tnaflix.com     [COLOR red]Search[/COLOR]', tnaflix, 1, logos + 'tnaflix.png', fanart)	
		add_dir('[COLOR magenta]Categories[/COLOR]', tnaflix, 18, logos + 'tanflix.png', fanart) 
		match = re.compile('a  href="(.+?)" class="videoThumb" title="">\s*<span class="nHover"><h2>(.+?)</h2>\s*<span class="duringTime">(.+?)</span>\s*</span>\s*<img src="(.+?)"').findall(content)
		for url, name, duration, thumb  in match:
			add_link(name + ' [COLOR lime]('+ duration + ')[/COLOR]', tnaflix + url,  4, 'http:' + thumb, fanart)
		match = re.compile('class="navLink" href="([^"]*)">next &raquo;</a>').findall(content) 
		add_dir('[COLOR blue]Next  Page  >>>>[/COLOR]', tnaflix + match[0], 2, logos + 'tnaflix.png', fanart)	
		
	elif 'xhamster' in url:
		content = make_request(url)
		add_dir('[COLOR blue]xhamster.com     [COLOR red]Search[/COLOR]', xhamster, 1, logos + 'xhamster.png', fanart)	
		add_dir('[COLOR magenta]Categories[/COLOR]', xhamster + '/channels.php', 17, logos + 'xhamster.png', fanart) 
		add_dir('[COLOR magenta]Change Content[/COLOR]', xhamster , 24, logos + 'xhamster.png', fanart)
		match = re.compile('href="([^"]*)" class=".+?"><img src=\'(.+?)\' class=\'.+?\' alt="(.+?)"/>.+?<b>(.+?)</b>').findall(content)
		for url, thumb, name, duration in match:
			add_link(name + ' [COLOR lime]('+ duration + ')[/COLOR]', url, 4, thumb, fanart)
		match = re.compile('<link rel="next" href="([^"]*)"><link rel="dns-prefetch"').findall(content) 
		add_dir('[COLOR blue]Next  Page  >>>>[/COLOR]', match[0], 2, logos + 'xhamster.png', fanart)	
	
	elif 'pornhub' in url:
		content = make_request(url)
		add_dir('[COLOR blue]pornhub.com     [COLOR red]Search[/COLOR]', pornhub, 1, logos + 'pornhub.png', fanart)	
		add_dir('[COLOR magenta]Categories[/COLOR]', pornhub + '/categories', 25, logos + 'pornhub.png', fanart) 
		#add_dir('[COLOR magenta]Change Content[/COLOR]', pornhub , 24, logos + 'pornhub.png', fanart)
		match = re.compile('<li class="videoblock.+?<a href="([^"]+)" title="([^"]+)".+?<var class="duration">([^<]+)<.*?data-mediumthumb="([^"]+)"', re.DOTALL).findall(content)
		for url, name, duration, thumb in match:
			name = cleantext(name)
			add_link(name + ' [COLOR lime]('+ duration + ')[/COLOR]', pornhub + url, 4, thumb, fanart)
		match = re.compile('<li class="page_next"><a href="([^"]+)" class="orangeButton">Next</a></li>', re.DOTALL).findall(content) 
		add_dir('[COLOR blue]Next  Page  >>>>[/COLOR]', pornhub + match[0].replace('&amp;','&'), 2, logos + 'pornhub.png', fanart)	

	elif 'pornsocket' in url:
		content = make_request(url)
		add_dir('[COLOR blue]pornsocket.com     [COLOR red]Search[/COLOR]', pornsocket, 1, logos + 'pornsocket.png', fanart)	
		add_dir('[COLOR magenta]Categories[/COLOR]', pornsocket + '/categories-media.html', 26, logos + 'pornsocket.png', fanart) 
		match = re.compile('<div class="media-duration">\s*([^<]+)</div>\s*<a href="([^"]+)"> <img src="([^"]+)" border="0" alt="([^"]+)"').findall(content)
		for duration, url, thumb, name in match:
			add_link(name + ' [COLOR lime]('+ duration + ')[/COLOR]', pornsocket + url, 4, pornsocket + thumb, fanart)	
		match = re.compile('><a title="Next" href="([^"]+)" class="pagenav">Next</a>', re.DOTALL).findall(content) 
		add_dir('[COLOR blue]Next  Page  >>>>[/COLOR]', pornsocket + match[0].replace('&amp;','&'), 2, logos + 'pornsocket.png', fanart)			

	elif 'vikiporn' in url:
		content = make_request(url)
		add_dir('[COLOR silver]vikiporn.com     [COLOR red]Search[/COLOR]', vikiporn, 1, logos + 'vikiporn.png', fanart)
		add_dir('[COLOR magenta]Categories[/COLOR]', vikiporn + '/categories/', 16, logos + 'vikiporn.png', fanart) 
		match = re.compile('<a href="(.+?)">\s*<div class=".+?">\s*<img style=".+?" class=".+?"  src=".+?" data-original="(.+?)" alt="(.+?)" onmouseover=".+?" onmouseout=".+?">\s*<span class=".+?">(.+?)</span>').findall(content)
		for url, thumb, name, duration in match:
			add_link(name + ' [COLOR lime]('+ duration + ')[/COLOR]', url,  4, thumb, fanart)
		match = re.compile('<a href="([^"]*)">NEXT</a>').findall(content) 
		add_dir('[COLOR blue]Next  Page  >>>>[/COLOR]', vikiporn + match[0], 2, logos + 'vikiporn.png', fanart)	
	
	elif 'tube8' in url:
		content = make_request(url)
		add_dir('[COLOR lime]tube8.com     [COLOR red]Search[/COLOR]', tube8, 1, logos + 'tube8.png', fanart)
		add_dir('[COLOR magenta]Categories[/COLOR]', tube8 + '/categories.html', 22, logos + 'tube8.png', fanart) 
	   	match = re.compile('href="(.+?)"\s*.+?\s*data-action=\'.+?\'\s*data-ajaxlink=\'.+?\'\s*data-value=\'.+?\'>.+?\s*src="(.+?)" alt="(.+?)"\s*title=".+?" />\s*</a>\s*<div class="video_duration">(.+?)</div>').findall(content)
		for url, thumb, name, duration in match:
			add_link(name + ' [COLOR lime]('+ duration + ')[/COLOR]', url, 4, thumb, fanart)
		match = re.compile('<link rel="next" href="([^"]*)">').findall(content) 
		add_dir('[COLOR blue]Next  Page  >>>>[/COLOR]', match[0], 2, logos + 'tube8.png', fanart)	

	elif 'redtube' in url:
		content = make_request(url)
		add_dir('[COLOR lime]redtube.com     [COLOR red]Search[/COLOR]', redtube, 1, logos + 'redtube.png', fanart)
		add_dir('[COLOR magenta]Channels[/COLOR]', redtube + '/channel', 10, logos + 'redtube.png', fanart) 
		content = make_request(redtube)
		
		match = re.compile('onclick="window.location.href =\'(.+?)\'">(.+?)</span>\s*			<img title="(.+?)" id=".+?" class=".+?" data-src="(.+?)" ').findall(content)
		for url, duration, name, thumb in match:
			add_link(name + ' [COLOR lime]('+ duration + ')[/COLOR]', redtube + url, 4, thumb,  fanart)
			
		match = re.compile('link rel="next" href="(.+?)">\s*	<meta name="description"').findall(content) 
		add_dir('[COLOR blue]Next  Page  >>>>[/COLOR]', match[0], 2, logos + 'redtube.png', fanart)	

	elif 'pornxs' in url:
		content = make_request(url)
		add_dir('[COLOR blue]pornxs.com     [COLOR red]Search[/COLOR]', pornxs, 1, logos + 'pornxs.png', fanart)
		match = re.compile('<a href="(.+?)"><div class=".+?"><div class=".+?">\s*<div class="video"><img src="(.+?)" alt="(.+?)"').findall(content)
		for url, thumb, name in match:
			add_link(name, pornxs + url, 4, thumb, fanart)
		match = re.compile('<a class="pagination-next" href="([^"]*)"><span></span></a></li> ').findall(content)
		add_dir('[COLOR blue]Next  Page  >>>>[/COLOR]', pornxs + match[0], 2, logos + 'pornxs.png', fanart)
			

	elif 'lubetube' in url:
		content = make_request(url)
		add_dir('[COLOR white]lubetube.com     [COLOR red]Search[/COLOR]', lubetube, 1, logos + 'lubetube.png', fanart)	
		add_dir('[COLOR lime]Categories[/COLOR]', lubetube + 'categories', 15, logos + 'lubetube.png', fanart)
		
		match = re.compile('href="(.+?)" title="(.+?)"><img src="(.+?)".+?Length: (.+?)<').findall(content)
		for url, name, thumb, duration in match:
			add_link(name + '[COLOR lime] (' + duration + ')[/COLOR]', url, 4, thumb, fanart)
		match = re.compile('<a class="next" href="([^"]*)">Next</a></div>').findall(content)
		add_dir('[COLOR blue]Next  Page  >>>>[/COLOR]', lubetube + match[0], 2, logos + 'lubetube.png', fanart)

		
	elif 'yes.xxx' in url:
		content = make_request(url)
		add_dir('yes.xxx    [COLOR red]Search[/COLOR]', yesxxx, 1, logos + 'yes.png', fanart)	
		match = re.compile('href="/(.+?)" title="(.+?)"><img src="(.+?)" />').findall(content)
		for url, name, thumb in match:
			add_link(name, yesxxx + url,  4, thumb, fanart)		
		match = re.compile('<li><a href="(.+?)">Next</a></li>').findall(content)
		add_dir('[COLOR blue]Next  Page  >>>>[/COLOR]', yesxxx + match[0], 2, logos + 'yes.png', fanart)

		
	elif 'motherless' in url:
		content = make_request(url)
		###Search in def search(): and media_list(url)
		add_dir('[COLOR lightgreen]motherless.com     [COLOR red]Search[/COLOR]', motherless, 1, logos + 'motherless.png', fanart)
		####Subfolders
		add_dir('[COLOR lime]Being watched now[/COLOR]', motherless +  '/live/videos',  61, logos + 'motherless.png', fanart)
		add_dir('[COLOR lime]Popular Videos[/COLOR]', motherless +  '/videos/popular',  3, logos + 'motherless.png', fanart)
		add_dir('[COLOR lime]Most Viewed Videos[/COLOR]', motherless +  '/videos/viewed',  3, logos + 'motherless.png', fanart)
		add_dir('[COLOR lime]Most Favorited Videos[/COLOR]', motherless +  '/videos/favorited',  3, logos + 'motherless.png', fanart)
		add_dir('[COLOR lime]Most Commented Videos[/COLOR]', motherless +  '/videos/commented',  3, logos + 'motherless.png', fanart)
		add_dir('[COLOR magenta]Galleries[/COLOR]', motherless + '/galleries/updated?page=1', 60, logos + 'motherless.png', fanart) 
		add_dir('[COLOR magenta]Groups[/COLOR]', motherless + '/groups?page=1&s=u', 62, logos + 'motherless.png', fanart) 
		###sending video URL to resolve_url(url) 		
		match = re.compile('es=\"12\">\s*<a href="(.+?)" class=".+?" target=".+?">\s*<img class=".+?" src="(.+?)" data-strip-src=".+?" alt="(.+?)" />\s*</a>\s*<div class=".+?">\s*<h2 class=".+?">.+?</h2>\s*<div class=".+?">(.+?)</div>').findall(content)
		for url, thumb, name, duration in match:
			add_link(name + ' [COLOR lime]('+ duration + ')[/COLOR]', url , 4, thumb, fanart)	
		###Next Button
		match = re.compile('<a href="([^"]*)" class="pop" rel="[1-9999]">NEXT &raquo;</a></div>').findall(content)
		add_dir('[COLOR blue]Next  Page  >>>>[/COLOR]', motherless + match[0], 2, logos + 'motherless.png', fanart)

		
		
	elif 'eporner' in url:
		content = make_request(url)
		add_dir('[COLOR lightgreen]eporner.com     [COLOR red]Search[/COLOR]', eporner, 1, logos + 'eporner.png', fanart)
		add_dir('[COLOR lime]Categories[/COLOR]', eporner + '/categories/',  21, logos + 'eporner.png', fanart)
		match = re.compile('</div> <a href="/.+?/([^"]*)" title="(.+?)" id=".+?"> <div id=".+?"> <img id=".+?" src="(.+?)".+?<div class="mbtim">(.+?)</div>').findall(content)
		for url, name, thumb, duration in match:
			add_link(name + ' [COLOR lime]('+ duration + ')[/COLOR]', eporner + '/config5/' + url, 4, thumb, fanart)	
		try:
			match = re.compile("<a href='([^']*)' title='Next page'>").findall(content)
			add_dir('[COLOR blue]Next  Page  >>>>[/COLOR]', eporner + match[0], 2, logos + 'eporner.png', fanart)
		except:
			match = re.compile('<a href="([^"]*)" title="Next page">').findall(content)
			add_dir('[COLOR blue]Next  Page  >>>>[/COLOR]', eporner +  match[0], 2, logos + 'eporner.png', fanart)

		
	elif 'zbporn' in url:
		content = make_request(url)
		add_dir('[COLOR lightgreen]zbporn.com    [COLOR red]Search[/COLOR]', zbporn, 1, logos + 'zbporn.png', fanart)
		add_dir('[COLOR lime]Categories[/COLOR]', zbporn + '/categories/',  23, logos + 'zbporn.png', fanart)
		match = re.compile('<a href="([^"]*)" rotator_params=".+?"><img src="([^"]*)" alt="(.+?)" onmouseover=".+?" onmouseout=".+?"><span class="length">(.+?)</span').findall(content)
		for url, thumb, name, duration in match:
			add_link(name + ' [COLOR lime]('+ duration + ')[/COLOR]', url , 4, thumb, fanart)
		match = re.compile('</li>\s*<li><a data-page=".+?" href="(.+?)">.+?</a></li>\s*<li><a').findall(content)
		add_dir('[COLOR blue]Next  Page  >>>>[/COLOR]', zbporn + match[0], 2, logos + 'zbporn.png', fanart)			
		
	elif 'crazyshit' in url:
		content = make_request(url)
		add_dir('[COLOR lightgreen]crazyshit.com    [COLOR red]Search[/COLOR]', crazyshit, 1, logos + 'crazyshit.png', fanart)
		match = re.compile('<a href="(.+?)" target=".+?"><div style=".+?"><img\s*src="(.+?)" width=".+?" height=".+?" border=".+?" alt="(.+?)"').findall(content)
		for url, thumb, name in match:
			add_link(name, crazyshit + url , 4, thumb, fanart)
		match = re.compile('<a href="([^"]*)" class="pagenavBig"><b>Next &gt;').findall(content)
		add_dir('[COLOR blue]Next  Page  >>>>[/COLOR]', crazyshit + match[0], 2, logos + 'crazyshit.png', fanart)		
	
	elif 'efukt' in url:
		content = make_request(url)
		add_dir('[COLOR lightgreen]Efukt.com    [COLOR red]Search[/COLOR]', efukt, 1, logos + 'efukt.png', fanart)
		match = re.compile('<div class="thumb"><a href="([^"]+)"><img src="([^"]+)" width=".+?" height=".+?" /></a></div>\s*<div class=".+?">\s*<p class=".+?"><a href=".+?">(.+?)</a></p>').findall(content)
		for url, thumb, name in match:
			add_link(name, efukt + url , 4, thumb, fanart)
		match = re.compile('<a href=".+?" style="color:#bf4616;">.+?</a><a href="([^"]+)">.+?</a>').findall(content)
		add_dir('[COLOR blue]Next  Page  >>>>[/COLOR]', efukt + match[0], 2, logos + 'efukt.png', fanart)			
	
	elif 'tubepornclassic' in url:
		content = make_request(url)
		add_dir('[COLOR lightgreen]tubepornclassic     [COLOR red]Search[/COLOR]', tubepornclassic, 1, logos + 'tubepornclassic.png', fanart)
		match = re.compile('<a href="([^"]+)" title="([^"]+)".*?original="([^"]+)".*?duration">([^<]+)<', re.DOTALL | re.IGNORECASE).findall(content)
		for url, name, thumb, duration in match:
			add_link(name + ' [COLOR lime]('+ duration + ')[/COLOR]',  url,  4, thumb, fanart)
		match = re.compile('<a href="([^"]*)" data-action=".+?" data-container-id=".+?" data-block-id=".+?" data-parameters=".+?" title=\"Next Page\">Next</a>').findall(content)
		add_dir('[COLOR blue]Next  Page  >>>>[/COLOR]', tubepornclassic + match[0], 2, logos + 'tubepornclassic.png', fanart)
	
	elif 'xvideos' in url:
		content = make_request(url)
		add_dir('[COLOR lightgreen]xvideos.com     [COLOR red]Search[/COLOR]', xvideos, 1, logos + 'xvideos.png', fanart) 
	   	match = re.compile('<a href="(.+?)"><img src="(.+?)".+? title="(.+?)">.+?"duration">\((.+?)\)</span>').findall(content)
		for url, thumb, name, duration in match:
			add_link(name + ' [COLOR lime]('+ duration + ')[/COLOR]', xvideos + url, 4, thumb, fanart)
		match = re.compile('<a href="([^"]*)" class=\"no-page\"').findall(content) 
		add_dir('[COLOR blue]Next  Page  >>>>[/COLOR]', xvideos + match[0], 2, logos + 'xvideos.png', fanart)
	elif 'flyflv' in url:
		content = make_request(url)
		add_dir('[COLOR orange]flyflv.com     [COLOR red]Search[/COLOR]', flyflv, 1, logos + 'flyflv.png', fanart)	
		add_dir('[COLOR lime]Categories[/COLOR]', flyflv,  13, logos + 'flyflv.png', fanart)
		match = re.compile('class="imageLink" href="(.+?)"><img.+?bestThumb.+?src="(.+?)" alt="(.+?)"').findall(content)
		for url, thumb, name in match:
			add_link(name, flyflv + url, 4, thumb, fanart)
		match = re.compile('<li class="next"><a class="button small blue" href="([^"]*)">></a></li>').findall(content)
		add_dir('[COLOR blue]Next  Page  >>>>[/COLOR]', flyflv + match[0], 2, logos + 'flyflv.png', fanart)
	elif '.porn.com' in url:
		content = make_request(url)
		add_dir('[COLOR lightblue].porn.com     [COLOR red]Search[/COLOR]', porncom, 1, logos + 'porncom.png', fanart)	
		add_dir('[COLOR lime]Categories[/COLOR]', porncom,  14, logos + 'porncom.png', fanart)
		match = re.compile('<a href="(.+?)" class=".+?"><img src="(.+?)" /><span class=".+?">.+?class="duration">(.+?)</.+?class="title">(.+?)</a>').findall(content)
		for url, thumb, duration, name in match:	
			add_link(name + ' [COLOR lime]('+ duration + ')[/COLOR]', porncom + url, 4, thumb, fanart)
			
		match = re.compile('</span><a href="([^"]*)" class="btn nav">Next').findall(content)
		add_dir('[COLOR blue]Next  Page  >>>>[/COLOR]', porncom + match[0], 2, logos + 'porncom.png', fanart)

def tnaflix_categories(url):
	home()
	content = make_request(url)
	match = re.compile('href="/([^"]*)" title=".+?">(?!Sign In)(.+?)<').findall(content)
	for url, name in match:
		name = name.replace('&amp;', '&')
		add_dir(name, tnaflix + url,  3, logos + 'tnaflix.png', fanart)

def pornhd_categories(url):
	home()
	content = make_request(url)
	match = re.compile('data-original="([^"]*)"\s*/>\s*</a>\s*<a class="name" href="([^"]*)">\s*(.+?)\s*<').findall(content)
	for thumb, url, name in match:
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
	match = re.compile('href="([^"]*)" title="([^"]*)"><img src="([^"]*)"').findall(content)
	for url, name, thumb in match:
		add_dir(name, eporner + url, 2, thumb, fanart)
		
def lubtetube_pornstars(url):
	home()
	content = make_request(url)
	match = re.compile('class="frame" href="/(.+?)"><img src="(.+?)" alt="(.+?)"').findall(content)
	for url, thumb, name in match:
		add_dir(name, lubetube + url,  3, thumb, fanart)
	match = re.compile('href="/pornstars/(.+?)">(\d+)<').findall(content)
	for url, name in match:
		add_dir('[COLOR yellow]Page ' + name + '[/COLOR]', lubetube + 'pornstars/' + url,  12, logos + 'lubetube.png', fanart)		
		
def lubetube_categories(url):
	home()
	content = make_request(url)		
	match = re.compile('href="http://lubetube.com/search/adddate/cat/([^"]*)"><img src="(.+?)" alt="(.+?)"').findall(content)
	for url, thumb, name in match:
		add_dir(name, lubetube + 'search/adddate/cat/' + url,  3, logos + 'lubetube.png', fanart)
			
def porncom_channels_list(url):		
	home()
	content = make_request(url)
	match = re.compile('href="/videos/(.+?)" title="(.+?)"').findall(content)[31:200]
	for url, name in match:
		add_dir(name, porncom + '/videos/' + url,  3, logos + 'porncom.png', fanart)

def flv_channels_list(url):
	home()
	content = make_request(url)
	match = re.compile('href="/category/(.+?)">(.+?)<').findall(content)[:23]
	for url, name in match:
		add_dir(name, flyflv + '/category/' + url,  3, logos + 'flyflv.png', fanart)


def redtube_channels_cat(url): 
	home()
	content = make_request(url)
	match = re.compile('href="/channel/(.+?)" title="(.+?)">').findall(content)
	for url, name in match:
		add_dir('[COLOR orange]' + name + '[/COLOR]', redtube + '/channel/' + url, 11, logos + 'redtube.png', fanart)  
	
	match = re.compile('href="(.+?)">([A-Z])<').findall(content)
	for url, name in match:
		add_dir('[COLOR violet]' + name + '[/COLOR]', redtube + url, 11, logos + 'redtube.png', fanart)

def motherless_galeries_cat(url):
	home()
	add_dir('[COLOR lightgreen]motherless.com Galleries    [COLOR red]Search[/COLOR]', motherless + '/search/Galleries', 1, logos + 'motherless.png', fanart)
	content = make_request(url)
	match = re.compile('href="/G(.+?)" class=".+?" target=".+?">\s*<img class=".+?" src="(.+?)" data-strip-src=".+?" alt="(.+?)"').findall(content)
	for url, thumb, name in match:
		add_dir(name, motherless + '/GV' + url, 3, thumb, fanart)
	match = re.compile('<a href="([^"]*)" class=".+?" rel="[1-9999]">NEXT &raquo;</a></div>').findall(content)
	add_dir('[COLOR blue]Next  Page  >>>>[/COLOR]', motherless + match[0], 60, logos + 'motherless.png', fanart)
		
def motherless_groups_cat(url): #62
	home()
	add_dir('[COLOR lightgreen]motherless.com Groups    [COLOR red]Search[/COLOR]', motherless + '/search/groups?term=', 1, logos + 'motherless.png', fanart)
	content = make_request(url)
	match = re.compile('<a href="/g/(.+?)">\s*<div class="avatar-wrap avatar-size-medium">\s*<img\s*src="(.+?)"').findall(content)
	for url, thumb in match:
		name = url.replace('/g/', 'http://motherless.com/gv/')
		add_dir('[COLOR orange]' + name + '[/COLOR]', motherless + '/gv/' + url, 3, thumb, fanart)
	match = re.compile('<a href="([^"]*)" class="pop" rel="[1-9999]">NEXT &raquo;</a></div>').findall(content)
	add_dir('[COLOR blue]Next  Page  >>>>[/COLOR]', motherless + match[0], 62, logos + 'motherless.png', fanart)
	
	
def motherless_being_watched_now(url):
	home()
	content = make_request(url)
	if 'motherless' in url:		
		match = re.compile("<a href=\"(.+?)\" title=\"All Media\">").findall(content)
		add_dir('[COLOR lime]REFRESH[COLOR orange]  Page[COLOR red]  >>>>[/COLOR]', motherless + match[0], 31, logos + 'motherless.png', fanart)
		match = re.compile('href="(.+?)" class=".+?" target=".+?">\s*<img class=".+?" src="(.+?)" data-strip-src=".+?" alt="(.+?)"').findall(content)
		for url, thumb, name in match:
			add_link('[COLOR yellow]' + name + '[/COLOR]', url, 4, thumb, fanart)

def redtube_channels_list(url):
	home()
	content = make_request(url)
	match = re.compile('href="(.+?)" class="channels-list-img">\s*<img src="(.+?)" alt="(.+?)">').findall(content)
	for url, thumb, name in match:
		add_dir('[COLOR lightgreen]' + name + '[/COLOR]', redtube + url, 3, thumb, fanart)
	match = re.compile('<a  href	= "(.+?)" title	= ".+?" ><b>(\d+)</b></a>').findall(content)
	for url, name in match:
		add_dir('[COLOR yellow]Page ' + name + '[/COLOR]', redtube + url, 11, logos + 'redtube.png', fanart)			

def vikiporn_categories(url):
	home()
	content = make_request(url)
	match = re.compile('href="(.+?)">(.+?)<span>(\(\d+\))<').findall(content)[42:]
	for url, name, inum in match:
		inum = inum.replace(')', ' videos)')
		add_dir(name + '[COLOR lime] ' + inum + '[/COLOR]', url,  3, logos + 'vikiporn.png', fanart)	
		
def xhamster_categories(url):
	home()
	content = make_request(url)
	match = re.compile('href="http://xhamster.com/channels/(.+?)">(.+?)<').findall(content)
	for url, name in match:
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
	match = re.compile('<a href="([^"]*)"><img src="([^"]*)" alt="([^"]*)"><span class="info">').findall(content)
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
		add_dir(name, pornsocket + url, 2, pornsocket + thumb, fanart)
		
def media_list(url):
	home()
	content = make_request(url)
	if 'youjizz' in url:	  
		if 'random' in url or 'srch.php' in url:
			match = re.compile("<a class=\"frame\" href='(.+?)'.+?><\/a>\s*<img class.+?data-original=\"(.+?)\"").findall(content)		
			for url, thumb in match:
				name = url.replace('/videos/', '').replace('-', ' ').replace('.html', '') 
				name = re.sub('\s\d+$', '', name) # Get rid of numbers at the end of string 
				add_link('[COLOR yellow][UPPERCASE]' + name + '[/UPPERCASE][/COLOR]', youjizz + url, 4, thumb, fanart)
		elif 'highdefinition' in url:
			match = re.compile("href='([^']*)'.+?\s*\s*<img class=.+?data-original=\"([^\"]*)\">\s*<\/span>\s*<span id=\"title1\">\s*(.+?)<\/span>").findall(content)
			for url, thumb, name in match: # SD contents '-640-480-' in thumbnail
				if '-1280-720-' in thumb:  
					add_link('[COLOR yellow]' + name + ' [COLOR lime][HD - 720][/COLOR] ', youjizz + url, 4, thumb, fanart)	
				elif '-1280-960-' in thumb or '-1920-1080-' in thumb:
					add_link('[COLOR yellow]' + name + ' [HD - 1080][/COLOR] ', youjizz + url, 4, thumb, fanart)	
			match = re.compile("href=\"\/search(.+?)\">(\d+)<").findall(content) 
			for url, name in match:  
				add_dir('[COLOR lime]Page ' + name + '[COLOR orange] >>>>[/COLOR]', youjizz + '/search' + url, 3, logos + 'hdadult.png', fanart) 
			match = re.compile('href=\'\/search(.+?)\'>(\d+)<').findall(content) 
			for url, name in match:  
				add_dir('[COLOR red]Page ' + name + '[COLOR yellow] >>>>[/COLOR]', youjizz + '/search' + url, 3, logos + 'hdadult.png', fanart) 
		else:
			match = re.compile("<a class=\"frame\" href='(.+?)'.+?><\/a>\s*<img class.+?data-original=\"(.+?)\">\s*<\/span>\s*<span id=\"title1\">(.+?)<\/span>\s*<span id=\"title2\">\s*<span class='thumbtime'><span>(.+?)<\/span>").findall(content)		
			for url, thumb, name, duration in match:
				add_link('[COLOR yellow]' + name + ' [COLOR lime](' + duration + ')[/COLOR]', youjizz + url, 4, thumb, fanart)
			match = re.compile("<a href=\"(.+?).html\">(\d+)<\/a>").findall(content)
			for url, name in match:	
				add_dir('[COLOR orange]Page ' + name + '  >>>>[/COLOR]', youjizz + url + '.html', 3, logos + 'youjizz.png', fanart)
			match = re.compile("<a href='([^>]*)'>(\d+)<\/a>").findall(content)
			for url, name in match:	
				add_dir('[COLOR red]Page ' + name + '[COLOR magenta]  >>>>[/COLOR]', youjizz + url, 3, logos + 'youjizz.png', fanart)
	
	elif '.porn.com' in url:
		match = re.compile('<a href="(.+?)" class=".+?"><img src="(.+?)" /><span class=".+?">.+?class="duration">(.+?)</.+?class="title">(.+?)</a>').findall(content)
		for url, thumb, duration, name in match:	
			add_link(name + ' [COLOR lime]('+ duration + ')[/COLOR]', porncom + url, 4, thumb, fanart)
		match = re.compile('href="([^"]*)">(\d+)</a>&nbsp;').findall(content)
		for url, name in match:
			add_dir('[COLOR yellow]Page ' + name + '[/COLOR]', porncom + url.replace('&amp;', '&') , 3, logos + 'porncom.png', fanart)		
	
	elif 'yespleaseporn' in url:
		match = re.compile(".+?video_url=(.+?)&quality_480p.+?").findall(content)
		for url in match:
			add_link(name, yespleaseporn + url, 4, thumb, fanart)
	
	elif 'motherless' in url:		
		match = re.compile('href="(.+?)" class=".+?" target=".+?">\s*<img class=".+?" src="(.+?)" data-strip-src=".+?" alt="(.+?)" />\s*</a>\s*<div class=".+?">\s*<h2 class=".+?">.+?</h2>\s*<div class=".+?">(.+?)</div>').findall(content)
		for url, thumb, name, duration in match:
			if 'motherless.com' in url:  
				add_link(name + ' [COLOR lime]('+ duration + ')[/COLOR]', url, 4, thumb, fanart)
			else:
				add_link(name + ' [COLOR lime]('+ duration + ')[/COLOR]', motherless + url, 4, thumb, fanart)
		match = re.compile('<a href="([^"]+)" class="pop" rel="[1-9999]">NEXT').findall(content)
		for url in match:
			if '/' in url:  
				add_dir('[COLOR blue]Next  Page  >>>>[/COLOR]', motherless + match[0], 3, logos + 'motherless.png', fanart)
			else:
				pass

	elif 'redtube' in url:
		match = re.compile('href="([^"]*)" title="(.+?)" class.+?>\s*<span.+?>([^>]*)</span>\s*<img.+?data-src="([^"]+)"').findall(content)
		for url, name, duration, thumb in match:
			name = name.replace('&#039;', '\'').replace('&amp;', '&')
			add_link('' + name + ' [COLOR orange][' + duration + '][/COLOR]', redtube + url, 4, thumb, fanart)
		match = re.compile('<a  href	= "(.+?)" title	= ".+?" onclick	= ".+?" ><b>(\d+)</b>').findall(content)
		for url, name in match:
			add_dir('[COLOR lime]Page ' + name + '[/COLOR]', redtube + url, 3, logos + 'redtube.png', fanart)
	
	elif 'flyflv' in url:
		match = re.compile('class="imageLink" href="(.+?)"><img.+?bestThumb.+?src="(.+?)" alt="(.+?)"').findall(content)
		for url, thumb, name in match:
			add_link(name, flyflv + url, 4, thumb, fanart)
		match = re.compile('href="(.+?)">(\d+)<').findall(content)
		for url, name in match:
			add_dir('[COLOR yellow]Page ' + name + '[/COLOR]', flyflv + url, 3, logos + 'flyflv.png', fanart)			
	
	elif 'vikiporn' in url:
		match = re.compile('href="(.+?)">\s*.+\s*<img.+?original="(.+?)" alt="(.+?)".+?\(this\)">\s*.+"time-info">(.+?)<').findall(content)
		for url, thumb, name, duration in match:
			add_link(name + '[COLOR lime] (' + duration + ')[/COLOR]', url, 4, thumb, fanart)
		match = re.compile('href="(.+?)" title="Page (\d+)"').findall(content)
		for url, name in match:
			add_dir('[COLOR yellow]Page ' + name + '[/COLOR]', vikiporn + url, 3, logos + 'vikiporn.png', fanart)			
	
	elif 'tnaflix' in url:
		match = re.compile('href="/(.+?)" class.+?title="">\s*.+><h2>(.+?)</h2>\s*.+"duringTime">(.+?)</span>\s*.+\s*<img src="(.+?)"').findall(content)
		for url, name, duration, thumb in match:
			add_link(name + '[COLOR lime] (' + duration + ')[/COLOR]', tnaflix + url, 4, 'http:' + thumb, fanart)
		match = re.compile('href="([^"]*)">(\d+)<').findall(content)
		for url, name in match:
			url = url.replace('search.php', tnaflix + 'search.php')
			add_dir('[COLOR yellow]Page ' + name + '[/COLOR]', url, 3, logos + 'tnaflix.png', fanart)	

	elif 'lubetube' in url:
		match = re.compile('href="(.+?)" title="(.+?)"><img src="(.+?)".+?Length: (.+?)<').findall(content)
		for url, name, thumb, duration in match:
			add_link(name + '[COLOR lime] (' + duration + ')[/COLOR]', url, 4, thumb, fanart)
		match = re.compile('href="/([^"]*)">(\d+)<').findall(content)
		for url, name in match:
			add_dir('[COLOR yellow]Page ' + name + '[/COLOR]', lubetube + url, 3, logos + 'lubetube.png', fanart)
		
	elif 'pornxs' in url:
		match = re.compile('href="/(.+?)">\s*<div class.+?>\s*<div class.+?>\s*<div class.+?>\s*<img src="(.+?)" alt="(.+?)"').findall(content)
		for url, thumb, name in match:
			add_link(name, pornxs + url, 4, thumb, fanart)			
		match = re.compile('<a class="pagination-next" href="([^"]*)"><span></span></a></li> ').findall(content)
		add_dir('[COLOR blue]Next  Page  >>>>[/COLOR]', match[0], 3, logos + 'pornxs.png', fanart)


def resolve_url(url):
	content = make_request(url)
	if 'youjizz' in url:
		media_url = re.compile("<a href=\"(.+?)\" style=\".+?\" >Download This Video<\/a>").findall(content)[0]
	elif 'xvideos' in url:
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
	elif 'flyflv' in url:
		media_url = re.compile('fileUrl="(.+?)"').findall(content)[0]	
	elif 'vikiporn' in url:
		media_url = re.compile("video_url: '(.+?)'").findall(content)[0]
	elif 'xhamster' in url:
		media_url = re.compile("file: '(.+?)',").findall(content)[0]
	elif 'tnaflix' in url:
		media_url = 'http:' + re.compile('href="([^"]*)" class="downloadButton">MP4 Format</a>').findall(content)[0]	
	elif 'lubetube' in url: 
		media_url = re.compile('id="video-.+?" href="(.+?)"').findall(content)[0] 	
	elif 'yes.xxx' in url: 
		media_url = re.compile("video_url: '(.+?)',video_url_text:").findall(content)[0]		
	elif 'pornxs' in url: 
		media_url = re.compile('config-final-url="(.+?)"').findall(content)[0]	
	elif 'zbporn' in url: 
		media_url = re.compile("video_url: '(.+?)'").findall(content)[0]	
	elif 'pornhd' in url: 
		try:
			media_url = re.compile("'480p'  : '(.+?)'").findall(content)[0]	
		except:
			media_url = re.compile("'240p'  : '(.+?)'").findall(content)[0]			
	elif 'motherless' in url:		
		media_url = re.compile('__fileurl = \'(.+?)\';').findall(content)[0]
	elif 'eporner' in url:		
		media_url = re.compile('file: "(.+?)"').findall(content)[0]
	elif 'tubepornclassic' in url:		
		media_url = re.compile("video_url: '(.+?)',").findall(content)[0]
	elif 'crazyshit' in url:
		media_url = re.compile('<source src="(.+?)" type="video/mp4" />').findall(content)[0]
	elif 'efukt' in url:	
		media_url = re.compile('file: "(.+?)",').findall(content)[0]
	elif 'pornhub' in url:	
		media_url = re.compile("var player_quality_.+? = '(.+?)'").findall(content)[0]
	elif 'pornsocket' in url:	
		media_url = pornsocket + re.compile('<source src="(.+?)" type="video/mp4"/>').findall(content)[0]
	else:
		media_url = url
	item = xbmcgui.ListItem(name, path = media_url)
	xbmcplugin.setResolvedUrl(int(sys.argv[1]), True, item)	  
	return

def cleantext(text):
    text = text.replace('&#8211;','-')
    text = text.replace('&#038;','&')
    text = text.replace('&#8217;','\'')
    text = text.replace('&#8230;','...')
    text = text.replace('&quot;','"')
    text = text.replace('&#039;','`')
    text = text.replace('&amp;','&')
    text = text.replace('&ntilde;','ñ')
    return text
	
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
	liz.setInfo( type = "Video", infoLabels = { "Title": name } )
	liz.setProperty('fanart_image', fanart)
	ok = xbmcplugin.addDirectoryItem(handle = int(sys.argv[1]), url = u, listitem = liz, isFolder = True)
	return ok

def add_link(name, url, mode, iconimage, fanart):
	u = sys.argv[0] + "?url=" + urllib.quote_plus(url) + "&mode=" + str(mode) + "&name=" + urllib.quote_plus(name) + "&iconimage=" + urllib.quote_plus(iconimage)	
	liz = xbmcgui.ListItem(name, iconImage = "DefaultVideo.png", thumbnailImage = iconimage)
	liz.setInfo( type = "Video", infoLabels = { "Title": name } )
	liz.setProperty('fanart_image', fanart)
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

elif mode == 18:		
	tnaflix_categories(url)

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

elif mode == 60:	
	motherless_galeries_cat(url)
	
elif mode == 61:	
	motherless_being_watched_now(url)

elif mode == 62:	
	motherless_groups_cat(url)
	

	
xbmcplugin.endOfDirectory(int(sys.argv[1]))