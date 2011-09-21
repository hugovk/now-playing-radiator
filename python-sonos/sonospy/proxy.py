#
# proxy
#
# Copyright (c) 2009 Mark Henkelis
# Portions Copyright Brisa Team <brisa-develop@garage.maemo.org>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# Author: Mark Henkelis <mark.henkelis@tesco.net>

import os
import re
import ConfigParser

from xml.etree.ElementTree import _ElementInterface
from xml.etree import cElementTree as ElementTree

from brisa.core import webserver

from brisa.upnp.device import Device
from brisa.upnp.device.service import Service
from brisa.upnp.device.service import StateVariable
from brisa.upnp.soap import HTTPProxy, HTTPRedirect
from brisa.core.network import parse_url, get_ip_address, parse_xml


class Proxy(object):
    
    def __init__(self, proxyname, proxytype, proxytrans, udn, controlpoint, mediaserver, config, port):
        self.root_device = None
        self.upnp_urn = 'urn:schemas-upnp-org:device:MediaServer:1'
        self.proxyname = proxyname
        self.proxytype = proxytype
        self.proxytrans = proxytrans
        self.udn = udn
        self.controlpoint = controlpoint
        self.mediaserver = mediaserver
        self.destaddress = mediaserver.address
        self.destmusicaddress = None
        self.config = config
        self.port = port

    def _add_root_device(self):
        """ Creates the root device object which will represent the device
        description.
        """
        project_page = 'http://brisa.garage.maemo.org'
#        ip = get_ip_address('')
        ip, port = self.controlpoint._event_listener.host()
        listen_url = "http://" + ip + ':' + str(self.port)
        if self.proxytype == 'WMP':
            model_name='Windows Media Player Sharing'
        else:
            model_name='Rhapsody'

        self.root_device = Device(self.upnp_urn,
                                  self.proxyname,
                                  udn=self.udn,
                                  manufacturer='Henkelis',
                                  manufacturer_url=project_page,
                                  model_description='Media Server',
                                  model_name=model_name,
                                  model_number='3.0',
                                  model_url=project_page,
                                  udp_listener=self.controlpoint._ssdp_server.udp_listener,
                                  force_listen_url=listen_url)
        self.root_device.webserver.get_render = self.get_render

    def _add_services(self):
        # TODO: investigate why an error in creating the ContentDirectory
        #       causes the controlpoint to receive a duplicate _new_device_event_impl
        #       for the device being proxied
        cdservice = ContentDirectory(self.controlpoint, self.mediaserver, self.root_device.location, self)
        self.root_device.add_service(cdservice)
        cmservice = ConnectionManager(self.controlpoint, self.mediaserver)
        self.root_device.add_service(cmservice)
        mrservice = X_MS_MediaReceiverRegistrar()
        self.root_device.add_service(mrservice)

    def _load(self):
        self._add_root_device()
        self._add_services()

    def start(self):
        self.stop()
        self._load()
        self.root_device.start()

    def stop(self):
        if self.root_device:
            self.root_device.stop()
            self.root_device = None

    def get_render(self, uri, params):
        return self

    def render(self, env, start_response):
        if self.destmusicaddress is not None:
            address = self.destmusicaddress
        else:
            address = self.destaddress
#        respbody = HTTPProxy().call(address, env, start_response)
        respbody = HTTPRedirect().call(address, env, start_response)
        return respbody


class ContentDirectory(Service):

    service_name = 'ContentDirectory'
    service_type = 'urn:schemas-upnp-org:service:ContentDirectory:1'
    scpd_xml_path = os.path.join(os.getcwd(), 'content-directory-scpd.xml')

    searchArtists = {}
    searchContributing = {}
    searchAlbums = {}
    searchComposers = {}
    searchGenres = {}
    searchTracks = {}
    searchPlaylists = {}

    dictmapping = {'Artist'                 : searchArtists,
                   'Contributing Artists'   : searchContributing,
                   'Album'                  : searchAlbums,
                   'Composer'               : searchComposers,
                   'Genre'                  : searchGenres,
                   'Tracks'                 : searchTracks,
                   'Playlists'              : searchPlaylists }

    decaches = {'microsoft:artistAlbumArtist'   : searchArtists,
# should not be needed as replace is performed later                'upnp:artist'     : searchArtists,  # TODO: create this automatically from mapping
                'microsoft:artistPerformer'     : searchContributing,
                'upnp:album'                    : searchAlbums,
                'microsoft:authorComposer'      : searchComposers,
# should not be needed as replace is performed later                'upnp:author'      : searchComposers,  # TODO: create this automatically from mapping
                'upnp:genre'                    : searchGenres,
                'NOT_NEEDED'                    : searchTracks,
                'ug'                            : searchPlaylists }

    # TODO: fix playlists

    defaultcaches = {'107' + ' - ' + 'upnp:class = "object.container.person.musicArtist"' : searchArtists,
                     '100' + ' - ' + 'upnp:class = "object.container.person.musicArtist"' : searchContributing,
                     '0'   + ' - ' + 'upnp:class = "object.container.album.musicAlbum"'   : searchAlbums,
                     '108' + ' - ' + 'upnp:class = "object.container.person.musicArtist"' : searchComposers,
                     '0'   + ' - ' + 'upnp:class = "object.container.genre.musicGenre"'   : searchGenres,
                     '0'   + ' - ' + 'upnp:class derivedfrom "object.item.audioItem"'     : searchTracks,
                     '0'   + ' - ' + 'upnp:class = "object.container.playlistContainer"'  : searchPlaylists }
    defaultop = '='

    def __init__(self, controlpoint, mediaserver, proxyaddress, proxy):
        self.controlpoint = controlpoint
        self.mediaserver = mediaserver
        self.destscheme = mediaserver.scheme
        self.destip = mediaserver.ip
        self.proxyaddress = proxyaddress
        self.destmusicaddress = None
        self.proxy = proxy
        self.translate = 0
        self.subtranslate = ''
        self.caches = {}
        self.sonos_containers = {}
        self.sonos_decache = {}
        self.proxy_decache = {}
        self.containers = {}
        self.container_mappings = {}
        self.attribute_mappings = {}
        self.operators = [self.defaultop]

        Service.__init__(self, self.service_name, self.service_type, url_base='', scpd_xml_filepath=self.scpd_xml_path)

        # TODO: add error processing for ini file entries

        if self.proxy.proxytrans != '':
            try:        
                self.translate = self.proxy.config.get('WMP Translators', self.proxy.proxytrans)
                if ',' in self.translate:
                    valuestring = self.translate.split(',')
                    self.translate = valuestring[0]
                    self.subtranslate = valuestring[1]
            except ConfigParser.NoSectionError:
                self.translate = '0'
            except ConfigParser.NoOptionError:
                self.translate = '0'

            if self.translate != '0':
                # set defaults
                self.caches = self.defaultcaches.copy()
                # load Sonos container mapping
                try:        
                    self.conts = self.proxy.config.items('Sonos Containers')
                    self.sonos_containers = fixcolonequals(self.conts)
                    for k, v in self.sonos_containers.iteritems():
                        if v == '': continue    # ignore empty keys
                        valuestring = v.split(',')
                        if len(valuestring) == 1:
                            cachestring = valuestring[0]
                        elif len(valuestring) == 2:
                            cachestring = valuestring[0] + ' - ' + 'upnp:class = "' + valuestring[1] + '"'
                        else:
                            cachestring = valuestring[0] + ' - ' + 'upnp:class ' + valuestring[2] + ' "' + valuestring[1] + '"'
                            if valuestring[2] not in self.operators:                             
                                    self.operators.append(valuestring[2])
                        self.caches[cachestring] = self.dictmapping[k]
#                        self.sonos_decache[valuestring[0] + ',' + valuestring[1]] = k
                        self.sonos_decache[v] = k
                except ConfigParser.NoSectionError:
                    pass

                # load mappings for selected proxy            
                try:        
                    self.conts = self.proxy.config.items(self.proxy.proxytrans + ' Containers')
                    self.containers = fixcolonequals(self.conts)
#                    print self.containers

                    '''
                    for k, v in self.containers.iteritems():
                    
# Composer=1$16,object.container.person.author
                    
                        if v == '': continue    # ignore empty keys
                        valuestring = v.split(',')
                        if len(valuestring) == 1:
                            cachestring = valuestring[0]
                        elif len(valuestring) == 2:
                            cachestring = valuestring[0] + ' - ' + 'upnp:class = "' + valuestring[1] + '"'
                        else:
                            cachestring = valuestring[0] + ' - ' + 'upnp:class ' + valuestring[2] + ' "' + valuestring[1] + '"'
                            if valuestring[2] not in self.operators:                             
                                    self.operators.append(valuestring[2])
                        self.caches[cachestring] = self.dictmapping[k]
                        self.proxy_decache[v] = k
                    '''
                except ConfigParser.NoSectionError:
                    pass

                try:        
                    self.cont_maps = self.proxy.config.items(self.proxy.proxytrans + ' Container Mapping')
                    self.container_mappings = fixcolonequals(self.cont_maps)
                except ConfigParser.NoSectionError:
                    pass

                try:        
                    self.attr_maps = self.proxy.config.items(self.proxy.proxytrans + ' Attribute Mapping')
                    self.attribute_mappings = fixcolonequals(self.attr_maps)
#                    print self.attribute_mappings
                except ConfigParser.NoSectionError:
                    pass

#            print "##############################"
#            print self.proxy.proxytrans
#            print self.translate
#            print self.caches
#            print self.sonos_containers
#            print self.sonos_decache
#            print self.containers
#            print self.container_mappings
#            print self.attribute_mappings
#            print "##############################"


    def soap_Browse(self, *args, **kwargs):
#        for key in kwargs:
#            print "another keyword arg: %s: %s" % (key, kwargs[key])

        result = self.controlpoint.proxyBrowse(kwargs['ObjectID'], kwargs['BrowseFlag'], kwargs['Filter'], kwargs['StartingIndex'], kwargs['RequestedCount'], kwargs['SortCriteria'], self.mediaserver)
        if 'Result' in result:

            # if we are browsing the root, filter out 2 (video) and 3 (pictures)
            res = result['Result']

            c = 0
            cont1 = re.search('<container id="1" parentID="0".*?/container>', res)
            if cont1 != None:
                # root entry
                cont2 = re.search('<container id="2" parentID="0".*?/container>', res)
                if cont2 != None:
                    c -= 1
                    res = re.sub('<container id="2" parentID="0".*?/container>', '', res)
                cont3 = re.search('<container id="3" parentID="0".*?/container>', res)
                if cont3 != None:
                    c -= 1
                    res = re.sub('<container id="3" parentID="0".*?/container>', '', res)
            # correct the counts
            if 'NumberReturned' in result:
                nr = int(result['NumberReturned'])
                nr += c
                result['NumberReturned'] = str(nr)
            if 'TotalMatches' in result:
                tm = int(result['TotalMatches'])
                tm += c
                result['TotalMatches'] = str(tm)

            # if result contains destination addresses in XML, need to transform them to proxy addresses
            # (otherwise the Sonos kicks up a fuss)
            # for WMP at least, the port of the dest track address may not be the port of the dest webserver
            #    so we need to save the dest track address
            address = re.search(self.destip + ':[0-9]*', res)
            if address != None:
                self.destmusicaddress = self.destscheme + '://' + address.group()
                # save this address so proxy can use it
                self.proxy.destmusicaddress = self.destmusicaddress
                res = re.sub(self.destmusicaddress, self.proxyaddress, res)

#            print "@@@@@@@@@ res after: " + str(res)

            result['Result'] = res
        return result

    def soap_Search(self, *args, **kwargs):

        containerID = kwargs['ContainerID']
        mscontainerID = containerID
        searchCriteria = kwargs['SearchCriteria']

#        print "@@@@@@@@@@@@@@@@@@"
#        print 'containerID: ' + str(containerID)
#        print 'searchCriteria: ' + str(searchCriteria)
#        print 'translate: ' + str(self.translate)

        if self.translate == 'Through':

            result = self.controlpoint.proxySearch(containerID, searchCriteria, kwargs['Filter'], kwargs['StartingIndex'], kwargs['RequestedCount'], kwargs['SortCriteria'], self.mediaserver)
#            print result['Result']

        elif self.translate == 'Translate':

            # perform any container and attribute mappings
            if containerID in self.container_mappings:
                containerID = self.container_mappings[containerID]
            for k, v in self.attribute_mappings.iteritems():
                searchCriteria = re.sub(k, v, searchCriteria)

            if containerID == '':
                # server does not support search type
                result = {'NumberReturned': '0', 'UpdateID': '1', 'Result': '', 'TotalMatches': '0'}
                return result
            else:
                result = self.controlpoint.proxySearch(containerID, searchCriteria, kwargs['Filter'], kwargs['StartingIndex'], kwargs['RequestedCount'], kwargs['SortCriteria'], self.mediaserver)
            
        elif self.translate == 'Cache':

#            if kwargs['Filter'] == 'dc:title,res':
#                kwargs['Filter'] = 'dc:title,res,upnp:albumArtURI'
#            print "%%%%%%%%%%%%%%%%%%%%%%%%"
#            print kwargs['Filter']
#            print "%%%%%%%%%%%%%%%%%%%%%%%%"
                        

            # TODO: look into sort criteria
#<SortCriteria>+dc:title,+microsoft:artistAlbumArtist</SortCriteria>
               
#            print "map: " + str(self.attribute_mappings)         

            # split search string into components
            # TODO: check if there is ever an 'or'
            searchelements = searchCriteria.split(' and ')
            
            # TODO: add error processing if dict items not found

#            print "len: " + str(len(searchelements))
            
            if len(searchelements) == 2:
                # first time through, just class and refID
                # get search type from containerID and class combination
                for op in self.operators:
                    if op in searchelements[0]:
                        thisop = op
                        break
                upnpclass = searchelements[0].split(' ' + thisop + ' ')[1][1:-1]

#                print "Class: " + str(upnpclass)

                searchkey = containerID + ',' + upnpclass
                if thisop != self.defaultop:
                    searchkey += ',' + thisop

#                print "searchkey: " + str(searchkey)

                searchtype = self.sonos_decache[searchkey]

#                print "searchtype: " + str(searchtype)

                # get containerID from map
                containerID = self.containers[searchtype]

                # check for translation
                criteriatrans = False
                if ',' in containerID:
                    valuestring = containerID.split(',')
                    containerID = valuestring[0]
                    newclass = valuestring[1]
                    if newclass != '':
                        criteriatrans = True

#                print "containerID: " + str(containerID)

                # just use container for search
                if self.subtranslate == 'Discrete':
                    searchCriteria = ''
                else:               
                    searchCriteria = searchelements[0]

                # apply translation
                if criteriatrans == True:
                    searchCriteria = re.sub(upnpclass, newclass, searchCriteria)

#                print "searchCriteria: " + str(searchCriteria)

                if containerID == '':
                    # server does not support search type
                    result = {'NumberReturned': '0', 'UpdateID': '1', 'Result': '', 'TotalMatches': '0'}
                    return result
                else:
                    result = self.controlpoint.proxySearch(containerID, searchCriteria, kwargs['Filter'], kwargs['StartingIndex'], kwargs['RequestedCount'], kwargs['SortCriteria'], self.mediaserver)
                # cache results

                if 'Result' in result:
                    # at this level there should be at least one container in the result (Asset returns items for playlists if not registered),
                    # unless we are searching tracks

#                    print result['Result']

                    if not '<container id' in result['Result'] and searchtype != 'Tracks':
                        result = {'NumberReturned': '0', 'UpdateID': '1', 'Result': '', 'TotalMatches': '0'}
                        return result

                    if searchtype != 'Tracks':
                        # get cache to hold results in
                        cache = self.caches[mscontainerID + ' - ' + searchelements[0]]
                        # save results in cache
                        self.update_cache(result['Result'], cache)

            elif len(searchelements) >= 3:
                # not first time through, use cache to get container id

                check_for_containers = False
                if searchelements[0] == 'upnp:class derivedfrom "object.item.audioItem"':
                    # In this search Sonos is expecting items rather than containers, need to check
                    # what we get in the result and may need to make another search
                    check_for_containers = True

                # get cache
                classstring = searchelements[2].split(' = ')
                upnpclass = classstring[0]
                dctitle = classstring[1][1:-1]
                cache = self.decaches[upnpclass]

                # add on any subelements to cache item name
                numelements = len(searchelements)
                if numelements > 3:
                    for i in range(3, numelements):
                        substring = searchelements[i].split(' = ')
                        subtype = substring[0]
                        subtitle = substring[1][1:-1]
                        dctitle += ' - ' + subtitle  
                
                containerID = cache[dctitle]

#                print "containerID: " + str(containerID)

                if self.subtranslate == 'Discrete':
                    searchCriteria = ''
                else:               
                    searchCriteria = searchelements[0]
                    if numelements >= 3:
                        for i in range(2, numelements):
                            additionalCriteria = searchelements[i]
                            # perform any attribute translations
                            for k, v in self.attribute_mappings.iteritems():
                                additionalCriteria = re.sub(k, v, additionalCriteria)
#                            print "@@@@ add: " + str(additionalCriteria)
                            # 3 hacks for Twonky follow TODO: add to ini
                            if not 'upnp:genre' in additionalCriteria:
                                searchCriteria += ' and ' + additionalCriteria
                            if 'upnp:genre' in additionalCriteria and check_for_containers == True:
                                searchCriteria += ' and ' + additionalCriteria
                        if 'upnp:author' in searchCriteria:
                            searchCriteria = '*'
                        if 'upnp:albumArtist' in searchCriteria:
                            searchCriteria = '*'

#                print "searchCriteria: " + str(searchCriteria)

                result = self.controlpoint.proxySearch(containerID, searchCriteria, kwargs['Filter'], kwargs['StartingIndex'], kwargs['RequestedCount'], kwargs['SortCriteria'], self.mediaserver)

#                print result['Result']

                if 'Result' in result:

                    # save in cache with prefix of search class
                    container_found, item_found, container_list = self.update_cache(result['Result'], cache, dctitle)

                    if check_for_containers == True and container_found == True and self.subtranslate == 'Discrete':
                        # In this search Sonos is expecting items rather than containers, but we found containers
                        # We need to search the containers too
#                        print container_list
                        new_result = {}
                        numberReturned = totalMatches = 0
                        items = ''
                        if 'UpdateID' in result:
                            new_result['UpdateID'] = result['UpdateID']
                        
                        for childID in container_list:
                            child_result = self.controlpoint.proxySearch(childID, searchCriteria, kwargs['Filter'], kwargs['StartingIndex'], kwargs['RequestedCount'], kwargs['SortCriteria'], self.mediaserver)
                            if 'Result' in child_result:
                                numberReturned += int(child_result['NumberReturned'])
                                totalMatches += int(child_result['TotalMatches'])

                                # split out items and containers                                
                                item, containers = self.process_result(child_result['Result'])
                                # for containers, append to list we are processing
                                if containers != []:
                                    container_list += containers
                                # for items, add to found items
                                if item != '':
                                    items += item
                        result_xml  = '<DIDL-Lite xmlns="urn:schemas-upnp-org:metadata-1-0/DIDL-Lite/" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:upnp="urn:schemas-upnp-org:metadata-1-0/upnp/" xmlns:dlna="urn:schemas-dlna-org:metadata-1-0/">'
                        result_xml += items
                        result_xml += '</DIDL-Lite>'

                        new_result['NumberReturned'] = str(numberReturned)
                        new_result['TotalMatches'] = str(totalMatches)
                        new_result['Result'] = result_xml
#                        print 'new_result: ' + str(new_result)

                        # save our result
                        result = new_result

                    if check_for_containers == False and item_found == True and self.subtranslate != 'Discrete':
                        # In this search Sonos is expecting containers rather than items, but we found items too
                        # We need to remove the items (assume they may not be consecutive)
                        new_result = result['Result']
                        numberReturned = int(result['NumberReturned'])
                        totalMatches = int(result['TotalMatches'])
                        num_items = new_result.count('</item>')
                        numberReturned -= num_items
                        totalMatches -= num_items
                        while '<item ' in new_result:
                            new_result = re.sub('<item.*?</item>' , '', new_result)
                        result['Result'] = new_result
                        result['NumberReturned'] = str(numberReturned)
                        result['TotalMatches'] = str(totalMatches)

#                    print result['Result']

                    '''
                    test of album art

                    if '<upnp:albumArtURI dlna:profileID="JPEG_TN">http://192.168.0.10:26125/albumart/Art--1859633031.jpg/cover.jpg</upnp:albumArtURI>' in result['Result']:
                    
                        print "------------------------------------------------------"
                        print "UDN: " + str(self.proxy.udn)
                        udn = self.proxy.udn.replace('uuid:', '')
                        print ">>>>>>>>>>>"

#                        aart  = '<upnp:albumArtURI>/getaa?m=1&u=http://'
                        aart  = '<upnp:albumArtURI>/getaa?u=http://'
                        aart += udn
                        aart += '.x-udn/'
#                        aart += '192.168.0.2:10243/
                        aart += 'albumart/Art--1859633031.jpg/cover.jpg'
#                        aart += 'content/c2/b16/f44100/7782.mp3'
#                        aart += '?albumArt=true</upnp:albumArtURI>'
                        aart += '</upnp:albumArtURI>'

#                        aart = '<upnp:albumArtURI>http://192.168.0.2:10243/albumart/Art--1859633031.jpg/cover.jpg</upnp:albumArtURI>'
#                        aart = '<upnp:albumArtURI>/getaa?m=1&u=http://192.168.0.2:10243/content/c2/b16/f44100/7782.mp3?albumArt=true</upnp:albumArtURI>'

#http://192.168.0.2:10243/albumart/Art--1859633031.jpg/cover.jpg
                        
                        result['Result'] = result['Result'].replace('<upnp:albumArtURI dlna:profileID="JPEG_TN">http://192.168.0.10:26125/albumart/Art--1859633031.jpg/cover.jpg</upnp:albumArtURI>', aart)

                        print result['Result']

                        print "------------------------------------------------------"

#<upnp:albumArtURI dlna:profileID="JPEG_TN">http://192.168.0.10:26125/albumart/Art--1859633031.jpg/cover.jpg</upnp:albumArtURI>

#/getaa?m=1&u=http://02286246-a968-4b5b-9a9a-defd5e9237e0.x-udn/WMPNSSv3/4206383637/1_e0JBNDM5NENDLUJENjgtNDQ0Ny05NTdFLTMxNTQ5QTAxRDI2Qn0uMC40.mp3?albumArt=true

#/getaa?m=1&u=http://b68dd228-957b-4cfe-abcd-123456789abc.x-udn/content/c2/b16/f44100/7782.mp3?albumArt=true

                    '''
                
        elif self.translate == 'Browse':
            pass

#            if containerID in self.container_mappings:
#                containerID = self.container_mappings[containerID]

#            result = self.soap_Browse(ObjectID=containerID, BrowseFlag='BrowseDirectChildren', Filter='*', StartingIndex=kwargs['StartingIndex'], RequestedCount=kwargs['RequestedCount'], SortCriteria='')
#            REMEMBER TO ADJUST THE XML SURROUNDING THE RESULT SO IT LOOKS LIKE A SEARCH RESPONSE!
#            result = self.controlpoint.proxySearch(containerID, searchCriteria, kwargs['Filter'], kwargs['StartingIndex'], kwargs['RequestedCount'], kwargs['SortCriteria'], self.mediaserver)
#            print result['Result']

        else:
            print 'Unsupported Translation type "' + self.translate + '" in pycpoint.ini file'
            result = {'NumberReturned': '0', 'UpdateID': '1', 'Result': '', 'TotalMatches': '0'}
            return result

        # post process result
        if 'Result' in result:
            # if result contains destination addresses in XML, need to transform them to proxy addresses
            # (otherwise the Sonos kicks up a fuss)
            # for WMP at least, the port of the dest track address may not be the port of the dest webserver
            #    so we need to save the dest track address
            res = result['Result']
            address = re.search(self.destip + ':[0-9]*', res)
            if address != None:
                self.destmusicaddress = self.destscheme + '://' + address.group()
                # save this address so proxy can use it
                self.proxy.destmusicaddress = self.destmusicaddress
                res = re.sub(self.destmusicaddress, self.proxyaddress, res)

#            # remove all but first res - assumes res are consecutive
#            firstres = re.search('<res[^<]*</res>', res)
#            if firstres != None:
#                res = re.sub('<res.*</res>' , firstres.group(), res)
    
            # if proxied server returns flac, spoof it as something else that is supported
            # on WMP, otherwise Sonos will not offer to play it as in individual track
            res = res.replace(':audio/x-flac:', ':audio/x-ms-wma:')

            result['Result'] = res
#            print "@@@@@@@@@ res after: " + str(res)

        return result

    def update_cache(self, result, cache, prefix=''):
        # get containers returned
        container_found = False
        item_found = False
        container_list = []
        elt = parse_xml(result)
        elt = elt.getroot()
        for item in elt.getchildren():
            # only save containers, not individual items
            if item.tag == '{urn:schemas-upnp-org:metadata-1-0/DIDL-Lite/}container':
                containerid = item.attrib.get('id')
                dctitle = item.find('{%s}%s' % ('http://purl.org/dc/elements/1.1/', 'title')).text
#                upnpclass = item.find('{%s}%s' % ('urn:schemas-upnp-org:metadata-1-0/upnp/', 'class'))
                if prefix != '':
                    dctitle = prefix + ' - ' + dctitle
                cache[dctitle] = containerid
                container_list.append(containerid)
                container_found = True
            elif item.tag == '{urn:schemas-upnp-org:metadata-1-0/DIDL-Lite/}item':
                item_found = True
        return container_found, item_found, container_list
#        print "~~~~~~~~~~~~~~~~~~~~~~~"                            
#        print cache
#        print "~~~~~~~~~~~~~~~~~~~~~~~"                            

    def process_result(self, result):
        container_list = []
        items = ''
        elt = parse_xml(result)
        elt = elt.getroot()
        for item in elt.getchildren():
            if item.tag == '{urn:schemas-upnp-org:metadata-1-0/DIDL-Lite/}container':
                containerid = item.attrib.get('id')
                container_list.append(containerid)
            elif item.tag == '{urn:schemas-upnp-org:metadata-1-0/DIDL-Lite/}item':
                items += ElementTree.tostring(item)
        return items, container_list

    def soap_GetSearchCapabilities(self, *args, **kwargs):
        result = self.controlpoint.proxyGetSearchCapabilities(self.mediaserver)
        return result
    def soap_GetSortCapabilities(self, *args, **kwargs):
        result = self.controlpoint.proxyGetSortCapabilities(self.mediaserver)
        return result
    def soap_GetSystemUpdateID(self, *args, **kwargs):
        result = self.controlpoint.proxyGetSystemUpdateID(self.mediaserver)
        return result


class ConnectionManager(Service):

    service_name = 'ConnectionManager'
    service_type = 'urn:schemas-upnp-org:service:ConnectionManager:1'
    scpd_xml_path = os.path.join(os.getcwd(), 'connection-manager-scpd.xml')

    def __init__(self, controlpoint, mediaserver):
        self.controlpoint = controlpoint
        self.mediaserver = mediaserver
        Service.__init__(self, self.service_name, self.service_type, url_base='', scpd_xml_filepath=self.scpd_xml_path)
    def soap_GetCurrentConnectionInfo(self, *args, **kwargs):
        result = self.controlpoint.proxyGetCurrentConnectionInfo(kwargs['ConnectionID'], self.mediaserver)
        return result
    def soap_GetProtocolInfo(self, *args, **kwargs):
        result = self.controlpoint.proxyGetProtocolInfo(self.mediaserver)
        return result
    def soap_GetCurrentConnectionIDs(self, *args, **kwargs):
        result = self.controlpoint.proxyGetCurrentConnectionIDs(self.mediaserver)
        return result


class X_MS_MediaReceiverRegistrar(Service):

    service_name = 'X_MS_MediaReceiverRegistrar'
    service_type = 'urn:microsoft.com:service:X_MS_MediaReceiverRegistrar:1'
    scpd_xml_path = os.path.join(os.getcwd(), 'media-receiver-registrar-scpd.xml')

    def __init__(self):
        Service.__init__(self, self.service_name, self.service_type, url_base='', scpd_xml_filepath=self.scpd_xml_path)
    def soap_IsAuthorized(self, *args, **kwargs):
#        print "IsAuthorised"
#        for arg in args:
#            print "another arg: " + str(arg)
#        for key in kwargs:
#            print "another keyword arg: " + str(key) + " : " + str(kwargs[key])
        ret = {'Result': '1'}
        return ret
    def soap_IsValidated(self, *args, **kwargs):
#        print "IsValidated"
#        for arg in args:
#            print "another arg: " + str(arg)
#        for key in kwargs:
#            print "another keyword arg: " + str(key) + " : " + str(kwargs[key])
        ret = {'Result': '1'}
        return ret
    def soap_RegisterDevice(self, *args, **kwargs):
#        print "RegisterDevice"
#        for arg in args:
#            print "another arg: " + str(arg)
#        for key in kwargs:
#            print "another keyword arg: " + str(key) + " : " + str(kwargs[key])
        ret = {'RegistrationRespMsg': '1'}
        return ret

def fixcolonequals(clist):
    cdict = {}
    for n,v in clist:
        if v.find('=') != -1:
            cat = n + ':' + v
            scat = cat.split('=')
            n = scat[0]
            v = scat[1] 
        n = n.replace('__colon__', ':')
        n = n.replace('__equals__', '=')
        v = v.replace('__colon__', ':')
        v = v.replace('__equals__', '=')
        cdict[n] = v
    return cdict
    
