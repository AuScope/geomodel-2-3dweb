#!/usr/bin/env python3
#
# This code creates a set of COLLADA (.dae) or GLTF files which represent BoreHoles in a 3D model
#
import collada as Collada
import numpy
import sys
import os
import glob
from pyproj import Proj, transform
import xml.etree.ElementTree as ET
import json
from json import JSONDecodeError
from collections import OrderedDict
from types import SimpleNamespace
import itertools
import logging



from owslib.wfs import WebFeatureService
from owslib.fes import *
import http.client, urllib
import urllib.parse
import urllib.request
import urllib.parse

from exports.bh_utils import make_borehole_label, make_borehole_filename
from exports.assimp_kit import ASSIMP_KIT
from exports.geometry_gen import colour_borehole_gen
from db.db_tables import QueryDB


DEBUG_LVL = logging.CRITICAL
''' Initialise debug level to minimal debugging
'''

EXPORT_KIT = ASSIMP_KIT(DEBUG_LVL)

# Namespaces for WFS Borehole response
NS = { 'wfs':"http://www.opengis.net/wfs",
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
        'xsi':"http://www.w3.org/2001/XMLSchema-instance" }


# From GeoSciML BoreholeView 4.1
GSMLP_IDS = [ 'identifier', 'name', 'description', 'purpose', 'status', 'drillingMethod', 'operator', 'driller',
 'drillStartDate', 'drillEndDate', 'startPoint', 'inclinationType', 'boreholeMaterialCustodian',
 'boreholeLength_m', 'elevation_m', 'elevation_srs', 'positionalAccuracy', 'source', 'parentBorehole_uri',
 'metadata_uri', 'genericSymbolizer']


# Maximum number of boreholes processed
MAX_BOREHOLES = 9999

# Timeout for querying WFS services (seconds)
WFS_TIMEOUT = 6000



def get_json_input_param(input_file):
    ''' Reads the parameters from input JSON file and stores them in global 'Param' object

    :param input_file: filename of input parameter file
    '''
    print("Opening: ", input_file)
    fp = open(input_file, "r")
    try:
        param_dict = json.load(fp)
    except JSONDecodeError as exc:
        print("Cannot read JSON file\n", input_file, "\n", exc)
        fp.close()
        sys.exit(1)
    fp.close()
    if 'BoreholeData' not in param_dict:
        print('Cannot find "BoreholeData" key in input file', input_file);
        sys.exit(1)

    Param = SimpleNamespace()
    for field_name in ['BBOX', 'EXTERNAL_LINK', 'MODEL_CRS', 'WFS_URL', 'BOREHOLE_CRS', 'WFS_VERSION', 'NVCL_URL']:
        if field_name not in param_dict['BoreholeData']:
            print("Cannot find '"+field_name+"' key in input file", input_file);
            sys.exit(1)
        setattr(Param, field_name, param_dict['BoreholeData'][field_name])

    if 'west' not in Param.BBOX or 'south' not in Param.BBOX or 'east' not in Param.BBOX or 'north' not in Param.BBOX:
        print("Cannot find 'west', 'south', 'east', 'north' keys in 'BBOX' in input file", input_file)
        sys.exit(1)
    print("Closed: ", input_file)
    return Param


def convert_coords(input_crs, output_crs, xy):
    ''' Converts coordinate systems

    :param input_crs: coordinate reference system of input coordinates
    :param output_crs: coordinate reference system of output coordinates
    :param xy: input coordinates in [x,y] format
    :returns: converted coordinates [x,y]
    '''
    p_in = Proj(init=__clean_crs(input_crs))
    p_out = Proj(init=__clean_crs(output_crs))
    return transform(p_in, p_out, xy[0], xy[1])

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


def get_borehole_data(url, log_id, height_resol):
    ''' Retrieves borehole mineral data for a borehole

    :param url: URL of the NVCL Data Service 
    :param log_id: borehole log identifier, string e.g. 'ce2df1aa-d3e7-4c37-97d5-5115fc3c33d'
    :param height_resol: height resolution, float
    :returns: a dict: key - depth, float; value - { 'colour': RGB colour string, 'classText': mineral name }
    '''
    print(" get_borehole_data(", url, log_id, ")")
    # Send HTTP request, get response
    params = {'logid' : log_id, 'outputformat': 'json', 'startdepth': 0.0, 'enddepth': 10000.0, 'interval': height_resol }
    enc_params = urllib.parse.urlencode(params).encode('ascii')
    req = urllib.request.Request(url, enc_params)
    with urllib.request.urlopen(req, timeout=60) as response:
        json_data = response.read()
    #print('json_data = ', json_data)
    meas_list = []
    depth_dict = OrderedDict()
    try:
        meas_list = json.loads(json_data.decode('utf-8'))
    except json.decoder.JSONDecodeError:
        print("Logid not known")
    else:
        # Sort then group by depth
        depth_dict = OrderedDict()
        sorted_meas_list = sorted(meas_list, key=lambda x: x['roundedDepth'])
        for depth, group in itertools.groupby(sorted_meas_list, lambda x: x['roundedDepth']):
            # Filter out invalid values
            filtered_group = itertools.filterfalse(lambda x: x['classText'] == 'INVALID', group)
            # Make a dict keyed on depth, value is element with largest count
            try:
                max_elem = max(filtered_group, key = lambda x: x['classCount'])
            except ValueError:
                # Sometimes 'filtered_group' is empty
                continue
            col = bgr2rgba(max_elem['colour'])
            depth_dict[depth] = { **max_elem, 'colour': col}
            del depth_dict[depth]['roundedDepth']
            del depth_dict[depth]['classCount']
            
    return depth_dict 


def get_borehole_logids(url, nvcl_id):
    ''' Retrieves a set of log ids for a particular borehole

    :param url: URL for the NVCL 'getDataSetCollection' service
    :param nvcl_id: NVCL 'holeidentifier' parameter
    :returns: a list of [log id, log type, log name]
    '''
    params = {'holeidentifier' : nvcl_id }
    enc_params = urllib.parse.urlencode(params).encode('ascii')
    req = urllib.request.Request(url, enc_params)
    with urllib.request.urlopen(req, timeout=60) as response:
        response_str = response.read()
    root = ET.fromstring(response_str)
    logid_list = []
    for child in root.findall('./*/Logs/Log'):
        is_public = child.findtext('./ispublic', default='false')
        log_name =  child.findtext('./logName', default='')
        log_type = child.findtext('./logType', default='')
        log_id = child.findtext('./LogID', default='')
        if is_public == 'true' and log_name != '' and log_type != '' and log_id != '':
            logid_list.append([log_id, log_type, log_name])
    return logid_list
      

def get_boreholes_list(wfs, max_boreholes, Param):
    ''' Returns a list of borehole data within bounding box, whether they are NVCL or not
        and a flag to say whether there are NVCL boreholes in there or not

    :param wfs: handle of borehole's WFS service
    :param max_boreholes: maximum number of boreholes to retrieve
    '''
    print("get_boreholes_list(", wfs, max_boreholes, Param, ")")
    # Can't filter for BBOX and nvclCollection==true at the same time [owslib's BBox uses 'ows:BoundingBox', not supported in WFS]
    # so is best to do the BBOX manually
    filter_ = PropertyIsLike(propertyname='gsmlp:nvclCollection', literal='true', wildCard='*')
    # filter_2 = BBox([Param.BBOX['west'], Param.BBOX['south'], Param.BBOX['east'], Param.BBOX['north']], crs=Param.BOREHOLE_CRS)
    # filter_3 = And([filter_, filter_2])
    filterxml = etree.tostring(filter_.toXML()).decode("utf-8")
    response = wfs.getfeature(typename='gsmlp:BoreholeView', filter=filterxml)
    response_str = bytes(response.read(), 'ascii')
    borehole_list = []
    print('get_boreholes_list() resp=', response_str)
    borehole_cnt=0
    root = ET.fromstring(response_str)

    for child in root.findall('./*/gsmlp:BoreholeView', NS):
        nvcl_id = child.attrib.get('{'+NS['gml']+'}id', '').split('.')[-1:][0]
        is_nvcl = child.findtext('./gsmlp:nvclCollection', default="false", namespaces=NS)
        if is_nvcl == "true" and nvcl_id.isdigit():
            borehole_dict = { 'nvcl_id': nvcl_id }

            # Finds borehole collar x,y assumes units are degrees
            xy = child.findtext('./gsmlp:shape/gml:Point/gml:pos', default="? ?", namespaces=NS).split(' ')
            try:
                if Param.BOREHOLE_CRS != 'EPSG:4283':
                    borehole_dict['y'] = float(xy[0]) # lat
                    borehole_dict['x'] = float(xy[1]) # lon
                else:
                    borehole_dict['x'] = float(xy[0]) # lon
                    borehole_dict['y'] = float(xy[1]) # lat
            except:
                continue
        
            borehole_dict['href'] = child.findtext('./gsmlp:identifier', default="", namespaces=NS)

            # Finds most of the borehole details
            for tag in GSMLP_IDS:
                if tag != 'identifier':
                    borehole_dict[tag] = child.findtext('./gsmlp:'+tag, default="", namespaces=NS)

            elevation = child.findtext('./gsmlp:elevation_m', default="0.0", namespaces=NS)
            try:
                borehole_dict['z'] = float(elevation)
            except:
                borehole_dict['z'] = 0.0

            # Only accept if within bounding box
            if Param.BBOX['west'] < borehole_dict['x'] and  Param.BBOX['east'] > borehole_dict['x'] and \
               Param.BBOX['north'] > borehole_dict['y'] and Param.BBOX['south'] < borehole_dict['y']:
                borehole_cnt+=1
                borehole_list.append(borehole_dict)
            if borehole_cnt > max_boreholes:
                break
    print('get_boreholes_list() returns ', borehole_list)
    return borehole_list


def get_bh_info_dict(borehole_dict, Param):
    ''' Returns a dict of borehole info for displaying in a popup box when user clicks on a borehole in the model

    :param borehole_dict: dict of borehole information 
        expected keys are: 'x', 'y', 'z', 'href' and GSMLP_IDS
    '''
    info_obj = {}
    info_obj['title'] = borehole_dict['name']
    for key in GSMLP_IDS:
        if key not in ['name', 'identifier', 'metadata_uri'] and len(borehole_dict[key])>0:
            info_obj[key] = borehole_dict[key]
    info_obj['href'] = [ { 'label': 'WFS URL', 'URL': borehole_dict['href'] },
                         { 'label': 'AuScope URL', 'URL': Param.EXTERNAL_LINK['URL'] } ]
    if len(borehole_dict['metadata_uri']) > 0:
        info_obj['href'].append({'label': 'Metadata URI', 'URL': borehole_dict['metadata_uri']})
    return info_obj

    
def get_loadconfig_dict(borehole_dict, Param):
    j_dict = {}
    j_dict['type'] = 'GLTFObject'
    x_m, y_m = convert_coords(Param.BOREHOLE_CRS, Param.MODEL_CRS, [borehole_dict['x'], borehole_dict['y']])
    j_dict['position'] = [x_m, y_m, borehole_dict['z']]
    j_dict['model_url'] = make_borehole_filename(borehole_dict['name'])+".gltf"
    j_dict['display_name'] = borehole_dict['name']
    j_dict['include'] = True
    j_dict['displayed'] = True
    return j_dict


def get_loadconfig(borehole_list, Param):
    ''' Creates a config object of borehole GLTF objects to display in 3D
    It prefers to create a list of NVCL boreholes

    :param borehole_list: list of boreholes
    '''
    loadconfig_obj = []
    for borehole_dict in borehole_list:
        j_dict = get_loadconfig_dict(borehole_dict, Param)
        loadconfig_obj.append(j_dict)
    return loadconfig_obj
    
    
def get_boreholes_fast(input_file, dest_dir=''):
    import pickle
    fp = open(os.path.join('C:', os.sep, 'users', 'vjf', 'Desktop', 'bh_params.pck'), 'rb')
    base_xyz, borehole_name, bh_data_dict, HEIGHT_RES, dest_dir, file_name = pickle.load(fp)
    fp.close()
    blob_obj = EXPORT_KIT.write_borehole(base_xyz, borehole_name, bh_data_dict, HEIGHT_RES, dest_dir, file_name)
    fp = open(os.path.join('C:', os.sep, 'users', 'vjf', 'Desktop', 'bh_config.pck'), 'rb')
    config = pickle.load(fp)
    fp.close()
    return config, blob_obj
    
    
def get_blob_boreholes(borehole_dict, Param):
    ''' Retrieves borehole data and writes 3D model files to a blob

    :param borehole_dict: 
    :returns: GLTF blob object
    '''
    print("get_blob_boreholes(", borehole_dict, ")")
    HEIGHT_RES = 10.0
    if 'name' in borehole_dict and 'x' in borehole_dict and 'y' in borehole_dict and 'z' in borehole_dict:
        file_name = make_borehole_filename(borehole_dict['name'])
        x_m, y_m = convert_coords(Param.BOREHOLE_CRS, Param.MODEL_CRS, [borehole_dict['x'], borehole_dict['y']])
        base_xyz = (x_m, y_m, borehole_dict['z'])
        log_ids = get_borehole_logids(Param.NVCL_URL + '/getDatasetCollection.html', borehole_dict['nvcl_id'])
        print('got log_ids = ', log_ids)
        url = Param.NVCL_URL + '/getDownsampledData.html'
        bh_data_dict = [] 
        for log_id, log_type, log_name in log_ids:
            # For the moment, only process log type '1' and 'Grp1 uTSAS'
            # Min1,2,3 = 1st, 2nd, 3rd most common mineral
            # Grp1,2,3 = 1st, 2nd, 3rd most common group of minerals
            # uTSAV = visible light, uTSAS = shortwave IR, uTSAT = thermal IR
            if log_type == '1' and log_name == 'Grp1 uTSAS':
                bh_data_dict = get_borehole_data(url, log_id, HEIGHT_RES)
                print('got bh_data_dict=', bh_data_dict)
                break

        # If there's data, then create the borehole
        if len(bh_data_dict) > 0:
            #import pickle
            #fp = open(os.path.join('C:', os.sep, 'users', 'vjf', 'Desktop', 'bh_params.pck'), 'wb')
            #pickle.dump((base_xyz, borehole_dict['name'], bh_data_dict, HEIGHT_RES, dest_dir, file_name), fp)
            #fp.close()
            blob_obj = EXPORT_KIT.write_borehole(base_xyz, borehole_dict['name'], bh_data_dict, HEIGHT_RES, '', file_name)
            print("Returning: blob_obj = ", blob_obj)
            return blob_obj
                
    return None


def get_boreholes(wfs, qdb, Param, output_mode='GLTF', dest_dir=''):
    ''' Retrieves borehole data and writes 3D model files to a directory or a blob
        If 'dest_dir' is supplied, then files are written
        If output_mode != 'GLTF' then 'dest_dir' must not be ''

    :param Param: input parameters
    :param output_mode: optional flag, when set to 'GLTF' outputs GLTF to file/blob, else outputs COLLADA (.dae) to file
    :param dest_dir: optional directory where 3D model files are written :returns: config object and optional GLTF blob object '''
    print("get_boreholes(", Param, output_mode, dest_dir, ")")


    # Get all NVCL scanned boreholes within BBOX
    borehole_list = get_boreholes_list(wfs, MAX_BOREHOLES, Param)
    HEIGHT_RES = 10.0
    print("borehole_list = ", borehole_list)
    # Parse response for all boreholes, make COLLADA files
    for borehole_dict in borehole_list:
        #print(borehole_dict)

        # Get borehole information dictionary, and add to query db
        bh_info_dict = get_bh_info_dict(borehole_dict, Param)
        p = qdb.add_part(json.dumps(bh_info_dict))

        if 'name' in borehole_dict and 'x' in borehole_dict and 'y' in borehole_dict and 'z' in borehole_dict:
            file_name = make_borehole_filename(borehole_dict['name'])
            x_m, y_m = convert_coords(Param.BOREHOLE_CRS, Param.MODEL_CRS, [borehole_dict['x'], borehole_dict['y']])
            base_xyz = (x_m, y_m, borehole_dict['z'])
            log_ids = get_borehole_logids(Param.NVCL_URL + '/getDatasetCollection.html', borehole_dict['nvcl_id'])
            # print('log_ids = ', log_ids)
            url = Param.NVCL_URL + '/getDownsampledData.html'
            bh_data_dict = [] 
            for log_id, log_type, log_name in log_ids:
                # For the moment, only process log type '1' and 'Grp1 uTSAS'
                # Min1,2,3 = 1st, 2nd, 3rd most common mineral
                # Grp1,2,3 = 1st, 2nd, 3rd most common group of minerals
                # uTSAV = visible light, uTSAS = shortwave IR, uTSAT = thermal IR
                if log_type == '1' and log_name == 'Grp1 uTSAS':
                    bh_data_dict = get_borehole_data(url, log_id, HEIGHT_RES)
                    break
            # If there's data, then create the borehole
            if len(bh_data_dict) > 0:
                first_depth = -1
                for vert_list, indices, colour_idx, depth, colour_info, mesh_name in colour_borehole_gen(base_xyz, borehole_dict['name'], bh_data_dict, HEIGHT_RES):
                    if first_depth < 0:
                        first_depth = int(depth)
                    popup_info = colour_info.copy()
                    del popup_info['colour']
                    s = qdb.add_segment(json.dumps(popup_info))
                    # This is the format that the label takes when a part of the GLTF file is clicked on. NB: Implementation dependent.
                    qdb.add_query("{0}_{1}_{2}".format(borehole_dict['name'], first_depth, colour_idx), 'model_name', s, p, None, None)
                    print("ADD_QUERY(", mesh_name, 'model_name')
                if output_mode == 'GLTF':
                    blob_obj = EXPORT_KIT.write_borehole(base_xyz, borehole_dict['name'], bh_data_dict, HEIGHT_RES, dest_dir, file_name)
                    
                elif dest_dir != '':
                    import exports.collada2gltf
                    from exports.collada_kit import COLLADA_KIT
                    export_kit = COLLADA_KIT(DEBUG_LVL)
                    export_kit.write_borehole(base_xyz, borehole_dict['name'], bh_data_dict, HEIGHT_RES, dest_dir, file_name)
                    blob_obj = None
                else:
                    print("WARNING - COLLADA_KIT cannot write blobs")
                    sys.exit(1)
                   
    if output_mode != 'GLTF':
        # Convert COLLADA files to GLTF
        exports.collada2gltf.convert_dir(dest_dir, "Borehole*.dae")
        # Return borehole objects
    loadconfig = get_loadconfig(borehole_list, Param)

    print("Returning: loadconfig = ", loadconfig, "blob_obj = ", blob_obj)
    return loadconfig, blob_obj


if __name__ == "__main__":
    if len(sys.argv) == 3:
        dest_dir = sys.argv[1]
        input_file = sys.argv[2]
        if not os.path.isdir(dest_dir):
            print("Dir "+dest_dir+" does not exist")
        elif not os.path.isfile(input_file):
            print("Input file does not exist: "+input_file)
        else:
            out_filename = os.path.join(dest_dir, 'borehole_'+os.path.basename(input_file))
            print("Writing to: ", out_filename)
            fp = open(out_filename, 'w')
            Param = get_json_input_param(input_file)
            wfs = WebFeatureService(Param.WFS_URL, version=Param.WFS_VERSION, xml=None, timeout=WFS_TIMEOUT)
            qdb = QueryDB()
            qdb.open_db(create=True)
            borehole_loadconfig, none_obj = get_boreholes(wfs, qdb, Param, output_mode='GLTF', dest_dir=dest_dir)
            json.dump(borehole_loadconfig, fp, indent=4, sort_keys=True)
            fp.close()
            print(qdb.query('GRANITE DOWNS DH 3_5', 'model_name'))
    else:
        print("Command line parameters are: \n 1. a destination dir to place the output files\n 2. input config file\n\n")
