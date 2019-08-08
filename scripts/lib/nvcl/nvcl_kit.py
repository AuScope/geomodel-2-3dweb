"""
# This module is used to extract NVCL borehole data
"""

import sys

import xml.etree.ElementTree as ET
import json
from collections import OrderedDict
import itertools
import logging

import urllib
import urllib.parse
import urllib.request
from requests.exceptions import RequestException

from owslib.wfs import WebFeatureService
from owslib.fes import PropertyIsLike, etree
from owslib.util import ServiceException

from http.client import HTTPException


LOG_LVL = logging.INFO
''' Initialise debug level to minimal debugging
'''

# Set up debugging
LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(LOG_LVL)

if not LOGGER.hasHandlers():

    # Create logging console handler
    HANDLER = logging.StreamHandler(sys.stdout)

    # Create logging formatter
    FORMATTER = logging.Formatter('%(name)s -- %(levelname)s - %(message)s')

    # Add formatter to ch
    HANDLER.setFormatter(FORMATTER)

    # Add handler to LOGGER and set level
    LOGGER.addHandler(HANDLER)

# Namespaces for WFS Borehole response
NS = {'wfs':"http://www.opengis.net/wfs",
      'xs':"http://www.w3.org/2001/XMLSchema",
      'it.geosolutions':"http://www.geo-solutions.it",
      'mo':"http://xmlns.geoscience.gov.au/minoccml/1.0",
      'topp':"http://www.openplans.org/topp",
      'mt':"http://xmlns.geoscience.gov.au/mineraltenementml/1.0",
      'nvcl':"http://www.auscope.org/nvcl",
      'gsml':"urn:cgi:xmlns:CGI:GeoSciML:2.0",
      'ogc':"http://www.opengis.net/ogc",
      'gsmlp':"http://xmlns.geosciml.org/geosciml-portrayal/4.0",
      'sa':"http://www.opengis.net/sampling/1.0",
      'ows':"http://www.opengis.net/ows",
      'om':"http://www.opengis.net/om/1.0",
      'xlink':"http://www.w3.org/1999/xlink",
      'gml':"http://www.opengis.net/gml",
      'er':"urn:cgi:xmlns:GGIC:EarthResource:1.1",
      'xsi':"http://www.w3.org/2001/XMLSchema-instance"}


# From GeoSciML BoreholeView 4.1
GSMLP_IDS = ['identifier', 'name', 'description', 'purpose', 'status', 'drillingMethod',
             'operator', 'driller', 'drillStartDate', 'drillEndDate', 'startPoint',
             'inclinationType', 'boreholeMaterialCustodian', 'boreholeLength_m',
             'elevation_m', 'elevation_srs', 'positionalAccuracy', 'source', 'parentBorehole_uri',
             'metadata_uri', 'genericSymbolizer']



TIMEOUT = 6000
''' Timeout for querying WFS and NVCL services (seconds)
'''


def bgr2rgba(bgr):
    ''' Converts BGR colour integer into an RGB tuple

    :param bgr: BGR colour integer
    :returns: RGB float tuple
    '''
    return ((bgr & 255)/255.0, ((bgr & 65280) >> 8)/255.0, (bgr >> 16)/255.0, 1.0)


class NVCLKit:
    ''' A class to extract NVCL borehole data:
    (1) Instantiate class
    (2) Call get_boreholes_list() to get list of NVCL boreholes
    (3) Call get_borehole_logids() to get logids
    (4) Call get_borehole_data() to get borehole data
    '''

    def __init__(self, param_obj, wfs=None):
        '''
        :param param_obj: dictionary of parameters, fields are: NVCL_URL, WFS_URL, WFS_VERSION,
                                                                BOREHOLE_CRS, BBOX
        e.g.
        {
            "BBOX": { "west": 132.76, "south": -28.44, "east": 134.39, "north": -26.87 },
            "MODEL_CRS": "EPSG:28352",
            "WFS_URL": "http://blah.blah.blah/nvcl/geoserver/wfs",
            "BOREHOLE_CRS": "EPSG:4283",
            "WFS_VERSION": "1.1.0",
            "NVCL_URL": "https://blah.blah.blah/nvcl/NVCLDataServices"
        }
        :param wfs: optional owslib 'WebFeatureService' object

        NOTE: Check if 'wfs' is not 'None' to see if this instance initialised properly

        '''
        self.param_obj = param_obj
        self.wfs = None
        if wfs is None:
            try:
                self.wfs = WebFeatureService(self.param_obj.WFS_URL,
                                             version=self.param_obj.WFS_VERSION,
                                             xml=None, timeout=TIMEOUT)
            except ServiceException as se_exc:
                LOGGER.warning("WFS error: %s", str(se_exc))
            except RequestException as re_exc:
                LOGGER.warning("Request error: %s", str(re_exc))
            except HTTPException as he_exc:
                LOGGER.warning("HTTP error code returned: %s", str(he_exc))
            except OSError as os_exc:
                LOGGER.warning("OS error: %s", str(os_exc))
        else:
            self.wfs = wfs



    def get_borehole_data(self, log_id, height_resol, class_name):
        ''' Retrieves borehole mineral data for a borehole

        :param log_id: borehole log identifier, string e.g. 'ce2df1aa-d3e7-4c37-97d5-5115fc3c33d'
                       This is the first id from the list of triplets [log id, log type, log name]
                       fetched from 'get_borehole_logids()'
        :param height_resol: height resolution, float
        :param class_name: name of mineral class
        :returns: a dict: key - depth, float; value - { 'colour': RGB colour string,
                                                    'className': class name,
                                                    'classText': mineral name }
        '''
        LOGGER.debug(" get_borehole_data(%s, %d, %s)", log_id, height_resol, class_name)
        # Send HTTP request, get response
        url = self.param_obj.NVCL_URL + '/getDownsampledData.html'
        params = {'logid' : log_id, 'outputformat': 'json', 'startdepth': 0.0,
                  'enddepth': 10000.0, 'interval': height_resol}
        enc_params = urllib.parse.urlencode(params).encode('ascii')
        req = urllib.request.Request(url, enc_params)
        json_data = b''
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as response:
                json_data = response.read()
        except HTTPException as he_exc:
            LOGGER.warning('HTTP Error: %s', he_exc)
            return OrderedDict()
        except OSError as os_exc:
            LOGGER.warning("OS error: %s", str(os_exc))
            return OrderedDict()
        LOGGER.debug('json_data = %s', json_data)
        meas_list = []
        depth_dict = OrderedDict()
        try:
            meas_list = json.loads(json_data.decode('utf-8'))
        except json.decoder.JSONDecodeError:
            LOGGER.warning("Logid not known")
        else:
            # Sort then group by depth
            depth_dict = OrderedDict()
            sorted_meas_list = sorted(meas_list, key=lambda x: x['roundedDepth'])
            for depth, group in itertools.groupby(sorted_meas_list, lambda x: x['roundedDepth']):
                # Filter out invalid values
                filtered_group = itertools.filterfalse(lambda x: x['classText'].upper() == 'INVALID',
                                                       group)
                # Make a dict keyed on depth, value is element with largest count
                try:
                    max_elem = max(filtered_group, key=lambda x: x['classCount'])
                except ValueError:
                    # Sometimes 'filtered_group' is empty
                    LOGGER.warning("No valid values at depth %s", str(depth))
                    continue
                col = bgr2rgba(max_elem['colour'])
                depth_dict[depth] = {'className': class_name, **max_elem, 'colour': col}
                del depth_dict[depth]['roundedDepth']
                del depth_dict[depth]['classCount']

        return depth_dict


    def get_borehole_logids(self, nvcl_id):
        ''' Retrieves a set of log ids for a particular borehole

        :param nvcl_id: NVCL 'holeidentifier' parameter,
                        the 'nvcl_id' from each dict item retrieved from 'get_boreholes_list()'
        :returns: a list of [log id, log type, log name]
        '''
        url = self.param_obj.NVCL_URL + '/getDatasetCollection.html'
        params = {'holeidentifier' : nvcl_id}
        enc_params = urllib.parse.urlencode(params).encode('ascii')
        req = urllib.request.Request(url, enc_params)
        response_str = b''
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as response:
                response_str = response.read()
        except HTTPException as he_exc:
            LOGGER.warning('HTTP Error: %s', str(he_exc))
            return []
        except OSError as os_exc:
            LOGGER.warning('OS error: %s', str(os_exc))
            return []
        root = ET.fromstring(response_str)
        logid_list = []
        for child in root.findall('./*/Logs/Log'):
            is_public = child.findtext('./ispublic', default='false')
            log_name = child.findtext('./logName', default='')
            log_type = child.findtext('./logType', default='')
            log_id = child.findtext('./LogID', default='')
            if is_public == 'true' and log_name != '' and log_type != '' and log_id != '':
                logid_list.append([log_id, log_type, log_name])
        return logid_list


    def get_boreholes_list(self, max_boreholes):
        ''' Returns a list of WFS borehole data within bounding box, but only NVCL boreholes
            [ { 'nvcl_id': XXX, 'x': XXX, 'y': XXX, 'href': XXX, ... }, { ... } ]

        :param max_boreholes: maximum number of boreholes to retrieve
        '''
        LOGGER.debug("get_boreholes_list(%d)", max_boreholes)
        # Can't filter for BBOX and nvclCollection==true at the same time
        # [owslib's BBox uses 'ows:BoundingBox', not supported in WFS]
        # so is best to do the BBOX manually
        filter_ = PropertyIsLike(propertyname='gsmlp:nvclCollection', literal='true', wildCard='*')
        # filter_2 = BBox([Param.BBOX['west'], Param.BBOX['south'], Param.BBOX['east'],
        #                  Param.BBOX['north']], crs=Param.BOREHOLE_CRS)
        # filter_3 = And([filter_, filter_2])
        filterxml = etree.tostring(filter_.toXML()).decode("utf-8")
        response_str = ''
        try:
            response = self.wfs.getfeature(typename='gsmlp:BoreholeView', filter=filterxml)
            response_str = bytes(response.read(), 'ascii')
        except (RequestException, HTTPException, ServiceException, OSError) as exc:
            LOGGER.warning("WFS GetFeature failed, filter=%s: %s", filterxml, str(exc))
            return []
        borehole_list = []
        LOGGER.debug('get_boreholes_list() resp= %s', response_str)
        borehole_cnt = 0
        root = ET.fromstring(response_str)

        for child in root.findall('./*/gsmlp:BoreholeView', NS):
            nvcl_id = child.attrib.get('{'+NS['gml']+'}id', '').split('.')[-1:][0]
            is_nvcl = child.findtext('./gsmlp:nvclCollection', default="false", namespaces=NS)
            if is_nvcl == "true" and nvcl_id.isdigit():
                borehole_dict = {'nvcl_id': nvcl_id}

                # Finds borehole collar x,y assumes units are degrees
                x_y = child.findtext('./gsmlp:shape/gml:Point/gml:pos', default="? ?",
                                     namespaces=NS).split(' ')
                try:
                    if self.param_obj.BOREHOLE_CRS != 'EPSG:4283':
                        borehole_dict['y'] = float(x_y[0]) # lat
                        borehole_dict['x'] = float(x_y[1]) # lon
                    else:
                        borehole_dict['x'] = float(x_y[0]) # lon
                        borehole_dict['y'] = float(x_y[1]) # lat
                except (OSError, ValueError) as os_exc:
                    LOGGER.warning("Cannot parse collar coordinates %s", str(os_exc))
                    continue

                borehole_dict['href'] = child.findtext('./gsmlp:identifier',
                                                       default="", namespaces=NS)

                # Finds most of the borehole details
                for tag in GSMLP_IDS:
                    if tag != 'identifier':
                        borehole_dict[tag] = child.findtext('./gsmlp:'+tag, default="",
                                                            namespaces=NS)

                elevation = child.findtext('./gsmlp:elevation_m', default="0.0", namespaces=NS)
                try:
                    borehole_dict['z'] = float(elevation)
                except ValueError:
                    borehole_dict['z'] = 0.0

                # Only accept if within bounding box
                if self.param_obj.BBOX['west'] < borehole_dict['x'] and \
                   self.param_obj.BBOX['east'] > borehole_dict['x'] and \
                   self.param_obj.BBOX['north'] > borehole_dict['y'] and \
                   self.param_obj.BBOX['south'] < borehole_dict['y']:
                    borehole_cnt += 1
                    borehole_list.append(borehole_dict)
                if borehole_cnt > max_boreholes:
                    break
        LOGGER.debug('get_boreholes_list() returns %s', str(borehole_list))
        return borehole_list
