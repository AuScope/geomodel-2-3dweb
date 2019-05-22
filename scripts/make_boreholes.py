#!/usr/bin/env python3
"""
# This code creates a set of COLLADA (.dae) or GLTF files and a sqlite database
# which can be used to embed NVCL boreholes in a geological model
"""

import sys
import os

import xml.etree.ElementTree as ET
import json
from json import JSONDecodeError
from collections import OrderedDict
from types import SimpleNamespace
import itertools
import logging
import argparse

from urllib.error import URLError
import urllib
import urllib.parse
import urllib.request
from requests.exceptions import HTTPError, ReadTimeout


from pyproj import Proj, transform

from owslib.wfs import WebFeatureService
from owslib.fes import PropertyIsLike, etree
from owslib.util import ServiceException

from lib.exports.bh_utils import make_borehole_filename, make_borehole_label
from lib.exports.assimp_kit import AssimpKit
from lib.exports.geometry_gen import colour_borehole_gen
from lib.db.db_tables import QueryDB


DEBUG_LVL = logging.ERROR
''' Initialise debug level to minimal debugging
'''

# Set up debugging
LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(DEBUG_LVL)

if not LOGGER.hasHandlers():

    # Create logging console handler
    HANDLER = logging.StreamHandler(sys.stdout)

    # Create logging formatter
    FORMATTER = logging.Formatter('%(name)s -- %(levelname)s - %(message)s')

    # Add formatter to ch
    HANDLER.setFormatter(FORMATTER)

    # Add handler to LOGGER and set level
    LOGGER.addHandler(HANDLER)

# We are exporting using AssimpKit, could also use ColladaKit
EXPORT_KIT = AssimpKit(DEBUG_LVL)

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


# Maximum number of boreholes processed
MAX_BOREHOLES = 9999

# Timeout for querying WFS and NVCL services (seconds)
TIMEOUT = 6000



def get_json_input_param(input_file):
    ''' Reads the parameters from input JSON file and stores them in global 'Param' object

    :param input_file: filename of input parameter file
    '''
    LOGGER.info("Opening: %s", input_file)
    with open(input_file, "r") as file_p:
        try:
            param_dict = json.load(file_p)
        except JSONDecodeError as exc:
            LOGGER.error("Cannot read JSON file %s: %s", input_file, str(exc))
            sys.exit(1)
    if 'BoreholeData' not in param_dict:
        LOGGER.error('Cannot find "BoreholeData" key in input file %s', input_file)
        sys.exit(1)
    if 'ModelProperties' not in param_dict:
        LOGGER.error('Cannot find "ModelProperties" key in input file %s', input_file)
        sys.exit(1)

    param_obj = SimpleNamespace()
    if 'modelUrlPath' not in param_dict['ModelProperties']:
        LOGGER.error("'modelUrlPath' not in input file %s", input_file)
        sys.exit(1)
    setattr(param_obj, 'modelUrlPath', param_dict['ModelProperties']['modelUrlPath'])
    for field_name in ['BBOX', 'EXTERNAL_LINK', 'MODEL_CRS', 'WFS_URL', 'BOREHOLE_CRS',
                       'WFS_VERSION', 'NVCL_URL']:
        if field_name not in param_dict['BoreholeData']:
            LOGGER.error("Cannot find '%s' key in input file %s", field_name, input_file)
            sys.exit(1)
        setattr(param_obj, field_name, param_dict['BoreholeData'][field_name])

    if 'west' not in param_obj.BBOX or 'south' not in param_obj.BBOX or \
       'east' not in param_obj.BBOX or 'north' not in param_obj.BBOX:
        LOGGER.error("Cannot find 'west','south','east','north' in 'BBOX' in input file %s",
                     input_file)
        sys.exit(1)
    return param_obj


def convert_coords(input_crs, output_crs, x_y):
    ''' Converts coordinate systems

    :param input_crs: coordinate reference system of input coordinates
    :param output_crs: coordinate reference system of output coordinates
    :param x_y: input coordinates in [x,y] format
    :returns: converted coordinates [x,y]
    '''
    p_in = Proj(init=__clean_crs(input_crs))
    p_out = Proj(init=__clean_crs(output_crs))
    return transform(p_in, p_out, x_y[0], x_y[1])

def __clean_crs(crs):
    ''' Removes namespace prefixes from a CRS:
          e.g. 'urn:x-ogc:def:crs:EPSG:4326' becomes 'EPSG:4326'

    :param crs: crs string to be cleaned
    :returns: cleaned crs string
    '''
    pair = crs.split(':')[-2:]
    return pair[0]+':'+pair[1]


def bgr2rgba(bgr):
    ''' Converts BGR colour integer into an RGB tuple

    :param bgr: BGR colour integer
    :returns: RGB float tuple
    '''
    return ((bgr & 255)/255.0, ((bgr & 65280) >> 8)/255.0, (bgr >> 16)/255.0, 1.0)


def get_borehole_data(url, log_id, height_resol, class_name):
    ''' Retrieves borehole mineral data for a borehole

    :param url: URL of the NVCL Data Service
    :param log_id: borehole log identifier, string e.g. 'ce2df1aa-d3e7-4c37-97d5-5115fc3c33d'
    :param height_resol: height resolution, float
    :param class_name: name of mineral class
    :returns: a dict: key - depth, float; value - { 'colour': RGB colour string,
                                                    'classText': mineral name }
    '''
    LOGGER.debug(" get_borehole_data(%s, %s)", url, log_id)
    # Send HTTP request, get response
    params = {'logid' : log_id, 'outputformat': 'json', 'startdepth': 0.0,
              'enddepth': 10000.0, 'interval': height_resol}
    enc_params = urllib.parse.urlencode(params).encode('ascii')
    req = urllib.request.Request(url, enc_params)
    json_data = b''
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as response:
            json_data = response.read()
    except URLError as ue_exc:
        LOGGER.warning('URLError: %s', ue_exc)
        return OrderedDict()
    except ConnectionResetError as cre_exc:
        LOGGER.warning('ConnectionResetError: %s', cre_exc)
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


def get_borehole_logids(url, nvcl_id):
    ''' Retrieves a set of log ids for a particular borehole

    :param url: URL for the NVCL 'getDataSetCollection' service
    :param nvcl_id: NVCL 'holeidentifier' parameter
    :returns: a list of [log id, log type, log name]
    '''
    params = {'holeidentifier' : nvcl_id}
    enc_params = urllib.parse.urlencode(params).encode('ascii')
    req = urllib.request.Request(url, enc_params)
    response_str = b''
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as response:
            response_str = response.read()
    except URLError as ue_exc:
        LOGGER.warning('URLError: %s', ue_exc)
        return []
    except ConnectionResetError as cre_exc:
        LOGGER.warning('ConnectionResetError: %s', cre_exc)
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


def get_boreholes_list(wfs, max_boreholes, param_obj):
    ''' Returns a list of borehole data within bounding box, whether they are NVCL or not
        and a flag to say whether there are NVCL boreholes in there or not

    :param wfs: handle of borehole's WFS service
    :param max_boreholes: maximum number of boreholes to retrieve
    :param param_obj: object containing command line parameters
    '''
    LOGGER.debug("get_boreholes_list(%s, %d, %s)", str(wfs), max_boreholes, str(param_obj))
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
        response = wfs.getfeature(typename='gsmlp:BoreholeView', filter=filterxml)
        response_str = bytes(response.read(), 'ascii')
    except (HTTPError, ServiceException, ReadTimeout) as exc:
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
                if param_obj.BOREHOLE_CRS != 'EPSG:4283':
                    borehole_dict['y'] = float(x_y[0]) # lat
                    borehole_dict['x'] = float(x_y[1]) # lon
                else:
                    borehole_dict['x'] = float(x_y[0]) # lon
                    borehole_dict['y'] = float(x_y[1]) # lat
            except OSError as os_exc:
                LOGGER.warning("Cannot parse collar coordinates %s", str(os_exc))
                continue

            borehole_dict['href'] = child.findtext('./gsmlp:identifier', default="", namespaces=NS)

            # Finds most of the borehole details
            for tag in GSMLP_IDS:
                if tag != 'identifier':
                    borehole_dict[tag] = child.findtext('./gsmlp:'+tag, default="", namespaces=NS)

            elevation = child.findtext('./gsmlp:elevation_m', default="0.0", namespaces=NS)
            try:
                borehole_dict['z'] = float(elevation)
            except ValueError:
                borehole_dict['z'] = 0.0

            # Only accept if within bounding box
            if param_obj.BBOX['west'] < borehole_dict['x'] and \
               param_obj.BBOX['east'] > borehole_dict['x'] and \
               param_obj.BBOX['north'] > borehole_dict['y'] and \
               param_obj.BBOX['south'] < borehole_dict['y']:
                borehole_cnt += 1
                borehole_list.append(borehole_dict)
            if borehole_cnt > max_boreholes:
                break
    LOGGER.debug('get_boreholes_list() returns %s', str(borehole_list))
    return borehole_list


def get_bh_info_dict(borehole_dict, param_obj):
    ''' Returns a dict of borehole info for displaying in a popup box
        when user clicks on a borehole in the model

    :param borehole_dict: dict of borehole information
        expected keys are: 'x', 'y', 'z', 'href' and GSMLP_IDS
    :param param_obj: object containing command line parameters
    :return: dict of borehole information
    '''
    info_obj = {}
    info_obj['title'] = borehole_dict['name']
    for key in GSMLP_IDS:
        if key not in ['name', 'identifier', 'metadata_uri'] and borehole_dict[key]:
            info_obj[key] = borehole_dict[key]
    info_obj['href'] = [{'label': 'WFS URL', 'URL': borehole_dict['href']},
                        {'label': 'AuScope URL', 'URL': param_obj.EXTERNAL_LINK['URL']}]
    if borehole_dict['metadata_uri']:
        info_obj['href'].append({'label': 'Metadata URI', 'URL': borehole_dict['metadata_uri']})
    return info_obj


def get_loadconfig_dict(borehole_dict, param_obj):
    ''' Creates a config dictionary, used to load a static GLTF file
    :param borehole_dict: dictionary of borehole data
    :param param_obj: object containing command line parameters
    :return: config dictionary
    '''
    j_dict = {}
    j_dict['type'] = 'GLTFObject'
    x_m, y_m = convert_coords(param_obj.BOREHOLE_CRS, param_obj.MODEL_CRS,
                              [borehole_dict['x'], borehole_dict['y']])
    j_dict['position'] = [x_m, y_m, borehole_dict['z']]
    j_dict['model_url'] = make_borehole_filename(borehole_dict['name'])+".gltf"
    j_dict['display_name'] = borehole_dict['name']
    j_dict['include'] = True
    j_dict['displayed'] = True
    return j_dict


def get_loadconfig(borehole_list, param_obj):
    ''' Creates a config object of borehole GLTF objects to display in 3D
    It prefers to create a list of NVCL boreholes

    :param borehole_list: list of boreholes
    '''
    loadconfig_obj = []
    for borehole_dict in borehole_list:
        j_dict = get_loadconfig_dict(borehole_dict, param_obj)
        loadconfig_obj.append(j_dict)
    return loadconfig_obj


def get_blob_boreholes(borehole_dict, param_obj):
    ''' Retrieves borehole data and writes 3D model files to a blob

    :param borehole_dict:
    :param param_obj: input parameters
    :returns: GLTF blob object
    '''
    LOGGER.debug("get_blob_boreholes(%s)", str(borehole_dict))
    height_res = 10.0
    if 'name' in borehole_dict and 'x' in borehole_dict and \
                                   'y' in borehole_dict and \
                                   'z' in borehole_dict:
        x_m, y_m = convert_coords(param_obj.BOREHOLE_CRS, param_obj.MODEL_CRS,
                                  [borehole_dict['x'], borehole_dict['y']])
        base_xyz = (x_m, y_m, borehole_dict['z'])
        log_ids = get_borehole_logids(param_obj.NVCL_URL + '/getDatasetCollection.html',
                                      borehole_dict['nvcl_id'])
        url = param_obj.NVCL_URL + '/getDownsampledData.html'
        bh_data_dict = []
        for log_id, log_type, log_name in log_ids:
            # For the moment, only process log type '1' and 'Grp1 uTSAS'
            # Min1,2,3 = 1st, 2nd, 3rd most common mineral
            # Grp1,2,3 = 1st, 2nd, 3rd most common group of minerals
            # uTSAV = visible light, uTSAS = shortwave IR, uTSAT = thermal IR
            if log_type == '1' and log_name in ['Grp1 uTSAS', 'Grp1 uTSAV', 'Grp1 uTSAT']:
                bh_data_dict = get_borehole_data(url, log_id, height_res, log_name)
                LOGGER.debug('got bh_data_dict= %s', str(bh_data_dict))
                break

        # If there's data, then create the borehole
        if bh_data_dict:
            blob_obj = EXPORT_KIT.write_borehole(base_xyz, borehole_dict['name'],
                                                 bh_data_dict, height_res, '')
            LOGGER.debug("Returning: blob_obj = %s", str(blob_obj))
            return blob_obj

        LOGGER.debug("No borehole data len=%d", len(log_ids))

    return None


def get_boreholes(wfs, qdb, param_obj, output_mode='GLTF', dest_dir=''):
    ''' Retrieves borehole data and writes 3D model files to a directory or a blob
        If 'dest_dir' is supplied, then files are written
        If output_mode != 'GLTF' then 'dest_dir' must not be ''

    :param wfs: OWSLib WebFeatureService object
    :param qdb: opened query database 'QueryDB' object
    :param param_obj: input parameters
    :param output_mode: optional flag, when set to 'GLTF' outputs GLTF to file/blob,
                        else outputs COLLADA (.dae) to file
    :param dest_dir: optional directory where 3D model files are written
    :returns: config object and optional GLTF blob object
    '''
    LOGGER.debug("get_boreholes(%s, %s, %s)", str(param_obj), output_mode, dest_dir)

    # Get all NVCL scanned boreholes within BBOX
    borehole_list = get_boreholes_list(wfs, MAX_BOREHOLES, param_obj)
    if borehole_list:
        LOGGER.warning("No boreholes found for %s using %s", param_obj.modelUrlPath,
                       param_obj.WFS_URL)
    height_res = 10.0
    LOGGER.debug("borehole_list = %s", str(borehole_list))
    blob_obj = None
    # Parse response for all boreholes, make COLLADA files
    bh_cnt = 0
    for borehole_dict in borehole_list:

        # Get borehole information dictionary, and add to query db
        bh_info_dict = get_bh_info_dict(borehole_dict, param_obj)
        is_ok, p_obj = qdb.add_part(json.dumps(bh_info_dict))
        if not is_ok:
            LOGGER.warning("Cannot add part to db: %s", p_obj)
            continue

        if 'name' in borehole_dict and 'x' in borehole_dict and \
                                       'y' in borehole_dict and \
                                       'z' in borehole_dict:
            file_name = make_borehole_filename(borehole_dict['name'])
            x_m, y_m = convert_coords(param_obj.BOREHOLE_CRS, param_obj.MODEL_CRS,
                                      [borehole_dict['x'], borehole_dict['y']])
            base_xyz = (x_m, y_m, borehole_dict['z'])

            # Look for NVCL mineral data
            log_ids = get_borehole_logids(param_obj.NVCL_URL + '/getDatasetCollection.html',
                                          borehole_dict['nvcl_id'])
            LOGGER.debug('log_ids = %s', str(log_ids))
            url = param_obj.NVCL_URL + '/getDownsampledData.html'
            bh_data_dict = []
            for log_id, log_type, log_name in log_ids:
                # For the moment, only process log type '1' and 'Grp1 uTSAS'
                # Min1,2,3 = 1st, 2nd, 3rd most common mineral
                # Grp1,2,3 = 1st, 2nd, 3rd most common group of minerals
                # uTSAV = visible light, uTSAS = shortwave IR, uTSAT = thermal IR
                if log_type == '1' and log_name == 'Grp1 uTSAS':
                    bh_data_dict = get_borehole_data(url, log_id, height_res, 'Grp1 uTSAS')
                    break
            # If there's NVCL data, then create the borehole
            if bh_data_dict:
                first_depth = -1
                for vert_list, indices, colour_idx, depth, colour_info, mesh_name in \
                    colour_borehole_gen(base_xyz, borehole_dict['name'], bh_data_dict, height_res):
                    if first_depth < 0:
                        first_depth = int(depth)
                    popup_info = colour_info.copy()
                    del popup_info['colour']
                    is_ok, s_obj = qdb.add_segment(json.dumps(popup_info))
                    if not is_ok:
                        LOGGER.warning("Cannot add segment to db: %s", s_obj)
                        continue
                    # Using 'make_borehole_label()' ensures that name is the same
                    # in both db and GLTF file
                    bh_label = make_borehole_label(borehole_dict['name'], first_depth)
                    bh_str = "{0}_{1}".format(bh_label.decode('utf-8'), colour_idx)
                    is_ok, r_obj = qdb.add_query(bh_str, param_obj.modelUrlPath,
                                                 s_obj, p_obj, None, None)
                    if not is_ok:
                        LOGGER.warning("Cannot add query to db: %s", r_obj)
                        continue
                    LOGGER.debug("ADD_QUERY(%s, %s)", mesh_name, param_obj.modelUrlPath)

                if output_mode == 'GLTF':
                    blob_obj = EXPORT_KIT.write_borehole(base_xyz, borehole_dict['name'],
                                                         bh_data_dict, height_res,
                                                         os.path.join(dest_dir, file_name))

                elif dest_dir != '':
                    import exports.collada2gltf
                    from exports.collada_kit import ColladaKit
                    export_kit = ColladaKit(DEBUG_LVL)
                    export_kit.write_borehole(base_xyz, borehole_dict['name'], bh_data_dict,
                                              height_res, os.path.join(dest_dir, file_name))
                    blob_obj = None
                else:
                    LOGGER.warning("ColladaKit cannot write blobs")
                    sys.exit(1)
                bh_cnt += 1

    LOGGER.info("Found NVCL data for %d/%d boreholes", bh_cnt, len(borehole_list))
    if output_mode != 'GLTF':
        # Convert COLLADA files to GLTF
        exports.collada2gltf.convert_dir(dest_dir, "Borehole*.dae")
        # Return borehole objects
    loadconfig = get_loadconfig(borehole_list, param_obj)

    LOGGER.debug("Returning: loadconfig, blobobj = %s, %s", str(loadconfig), str(blob_obj))
    return loadconfig, blob_obj


def process_single(dest_dir, input_file, db_name, create_db=True):
    ''' Process a single model's boreholes

    :param dest_dir: directory to output database and files
    :param input_file: conversion parameter file
    :param db_name: name of database
    :param create_db: optional (default True) create new database or append to existing one

    '''
    LOGGER.info("Processing %s", input_file)
    out_filename = os.path.join(dest_dir, 'borehole_'+os.path.basename(input_file))
    LOGGER.info("Writing to: %s", out_filename)
    with open(out_filename, 'w') as file_p:
        param_obj = get_json_input_param(input_file)
        try:
            wfs = WebFeatureService(param_obj.WFS_URL, version=param_obj.WFS_VERSION,
                                    xml=None, timeout=TIMEOUT)
        except ServiceException as se_exc:
            LOGGER.warning("WFS error, cannot process %s : %s", input_file, str(se_exc))
            return
        except ReadTimeout as rt_exc:
            LOGGER.warning("Timeout error, cannot process %s : %s", input_file, str(rt_exc))
            return
        except HTTPError as he_exc:
            LOGGER.warning("HTTP error code returned, cannot process %s : %s",
                           input_file, str(he_exc))
            return

        qdb = QueryDB(create=create_db, db_name=db_name)
        err_str = qdb.get_error()
        if err_str != '':
            LOGGER.error("Cannot open/create database: %s", err_str)
            sys.exit(1)
        borehole_loadconfig, none_obj = get_boreholes(wfs, qdb, param_obj, output_mode='GLTF',
                                                      dest_dir=dest_dir)
        json.dump(borehole_loadconfig, file_p, indent=4, sort_keys=True)


if __name__ == "__main__":
    PARSER = argparse.ArgumentParser(description='Create borehole data: GLTF, JSON and database.')
    PARSER.add_argument('dest_dir', help='directory to hold output files',
                        metavar='Output directory')
    PARSER.add_argument('-i', '--input', help='single input file')
    PARSER.add_argument('-b', '--batch',
                        help='filename of a text file containing paths of many input files,' \
                             ' one input file per line')
    PARSER.add_argument('-d', '--database', help='filename of output database file',
                        default='query.db')
    PARSER.add_argument('--debug', help='turn on debug statements', action='store_true')
    ARGS = PARSER.parse_args()

    # Set debug level
    if ARGS.debug:
        DEBUG_LVL = logging.DEBUG
    else:
        DEBUG_LVL = logging.INFO

    LOGGER.setLevel(DEBUG_LVL)

    # Check and create output directory, if necessary
    if not os.path.isdir(ARGS.dest_dir):
        LOGGER.warning("Output directory %s does not exist", ARGS.dest_dir)
        try:
            LOGGER.info("Creating %s", ARGS.dest_dir)
            os.mkdir(ARGS.dest_dir)
        except OSError as os_exc:
            LOGGER.error("Cannot create dir %s: %s", ARGS.dest_dir, str(os_exc))
            sys.exit(1)

    # Check input file
    if getattr(ARGS, 'input', None) is not None:
        if not os.path.isfile(ARGS.input):
            LOGGER.error("Input file does not exist: %s", ARGS.input)
            sys.exit(1)
        process_single(ARGS.dest_dir, ARGS.input, os.path.join(ARGS.dest_dir, ARGS.database))

    # Check batch file
    elif getattr(ARGS, 'batch', None) is not None:
        if not os.path.isfile(ARGS.batch):
            LOGGER.error("Batch file does not exist: %s", ARGS.batch)
            sys.exit(1)
        CREATE_DB = True
        with open(ARGS.batch, 'r') as fp:
            for line in fp:
                # Skip lines starting with '#'
                if line[0] != '#':
                    process_single(ARGS.dest_dir, line.rstrip('\n'),
                                   os.path.join(ARGS.dest_dir, ARGS.database), CREATE_DB)
                    CREATE_DB = False
    else:
        print("No input specified")
        PARSER.print_help()
