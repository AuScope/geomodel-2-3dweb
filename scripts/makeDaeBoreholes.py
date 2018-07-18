#!/usr/bin/env python3
#
# This code creates a set of DAE (COLLADA) files which represent BoreHoles in a 3D model
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
import math
from types import SimpleNamespace

from owslib.wfs import WebFeatureService
from owslib.fes import *
import http.client, urllib

import collada2gltf


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
GSMLP_IDS = [ 'identifier', 'name', 'description', 'purpose', 'status', 'drillingMethod', 'operator', 'driller', 'drillStartDate',
          'drillEndDate', 'startPoint', 'inclinationType', 'boreholeMaterialCustodian', 'boreholeLength_m', 'elevation_m',
          'elevation_srs', 'positionalAccuracy', 'source', 'parentBorehole_uri', 'metadata_uri', 'genericSymbolizer']


# Maximum number of boreholes processed
MAX_BOREHOLES = 9999

WFS_TIMEOUT = 6000

Param = SimpleNamespace()

def convert_coords(input_crs, output_crs, xy):
    ''' Converts coordinate systems
        input_crs - coordinate reference system of input coordinates
        output_crs - coordinate reference system of output coordinates
        xy - input coordinates in [x,y] format
    '''
    p_in = Proj(init=__clean_crs(input_crs))
    p_out = Proj(init=__clean_crs(output_crs))
    return transform(p_in, p_out, xy[0], xy[1])

def __clean_crs(crs):
    ''' Removes namespace prefixes from a CRS:
          e.g. 'urn:x-ogc:def:crs:EPSG:4326' becomes 'EPSG:4326'
    '''
    pair = crs.split(':')[-2:]
    return pair[0]+':'+pair[1]


def write_collada_borehole(bv, dest_dir, file_name, borehole_name):
    ''' Write out a COLLADA file
        file_name - filename of COLLADA file, without extension
        bv - base vertex, position of the object within the model [x,y,z]
    '''
    mesh = Collada.Collada()
    BH_WIDTH_UPPER = 75
    BH_WIDTH_LOWER = 10
    BH_HEIGHT = 15000
    BH_DEPTH = 2000
    node_list = []

    # Convert bv to an equilateral triangle of floats
    angl_rad = math.radians(30.0)
    cos_flt = math.cos(angl_rad)
    sin_flt = math.sin(angl_rad)
    #print(cos_flt, sin_flt)
    ptA_high = [bv[0], bv[1]+BH_WIDTH_UPPER*cos_flt, bv[2]+BH_HEIGHT]
    ptB_high = [bv[0]+BH_WIDTH_UPPER*cos_flt, bv[1]-BH_WIDTH_UPPER*sin_flt, bv[2]+BH_HEIGHT]
    ptC_high = [bv[0]-BH_WIDTH_UPPER*cos_flt, bv[1]-BH_WIDTH_UPPER*sin_flt, bv[2]+BH_HEIGHT]
    ptA_low = [bv[0], bv[1]+BH_WIDTH_LOWER*cos_flt, bv[2]-BH_DEPTH]
    ptB_low = [bv[0]+BH_WIDTH_LOWER*cos_flt, bv[1]-BH_WIDTH_LOWER*sin_flt, bv[2]-BH_DEPTH]
    ptC_low = [bv[0]-BH_WIDTH_LOWER*cos_flt, bv[1]-BH_WIDTH_LOWER*sin_flt, bv[2]-BH_DEPTH]

    diffuse_colour = (1.0, 0.0, 0.0, 1)
    effect = Collada.material.Effect("effect0", [], "phong", emission=(0,0,0,1), ambient=(0,0,0,1), diffuse=diffuse_colour, specular=(0.7, 0.7, 0.7, 1), shininess=50.0)
    mat = Collada.material.Material("material0", "mymaterial0", effect)
    mesh.effects.append(effect)
    mesh.materials.append(mat)

    vert_list = ptA_high + ptB_high + ptC_high + ptA_low + ptC_low + ptB_low
    vert_src = Collada.source.FloatSource("pointverts-array-0", numpy.array(vert_list), ('X', 'Y', 'Z'))
    geom = Collada.geometry.Geometry(mesh, "geometry0", make_borehole_label(borehole_name), [vert_src])
    input_list = Collada.source.InputList()
    input_list.addInput(0, 'VERTEX', "#pointverts-array-0")

    indices = [0, 2, 1,
               3, 5, 4,
               1, 2, 5,
               2, 4, 5,
               0, 4, 2,
               0, 3, 4,
               0, 1, 3,
               1, 5, 3]

    triset = geom.createTriangleSet(numpy.array(indices), input_list, "materialref-0")

    geom.primitives.append(triset)
    mesh.geometries.append(geom)

    matnode = Collada.scene.MaterialNode("materialref-0", mat, inputs=[])
    geomnode_list = [Collada.scene.GeometryNode(geom, [matnode])]

    node = Collada.scene.Node("node0", children=geomnode_list)
    node_list.append(node)

    #print("Creating a scene")
    myscene = Collada.scene.Scene("myscene", node_list)
    mesh.scenes.append(myscene)
    mesh.scene = myscene

    #print("Writing mesh")
    mesh.write(os.path.join(dest_dir,file_name+'.dae'))



def get_borehole_data(wfs, max_boreholes):
    ''' Returns a list of borehole data within bounding box, whether they are NVCL or not
        and a flag to say whether there are NVCL boreholes in there or not
        wfs - handle of borehole's WFS service
        max_boreholes - maximum number of boreholes to retrieve
    '''
    # Can't filter for BBOX and nvclCollection==true at the same time [owslib's BBox uses 'ows:BoundingBox', not supported in WFS]
    # so is best to do the BBOX manually
    filter_ = PropertyIsLike(propertyname='gsmlp:nvclCollection', literal='true', wildCard='*')
    # filter_2 = BBox([Param.BBOX['west'], Param.BBOX['south'], Param.BBOX['east'], Param.BBOX['north']], crs=Param.BOREHOLE_CRS)
    # filter_3 = And([filter_, filter_2])
    filterxml = etree.tostring(filter_.toXML()).decode("utf-8")
    response = wfs.getfeature(typename='gsmlp:BoreholeView', filter=filterxml)
    response_str = bytes(response.read(), 'ascii')
    borehole_list = []
    print('get_borehole_data() resp=', response_str)
    borehole_cnt=0
    root = ET.fromstring(response_str)

    for child in root.findall('./*/gsmlp:BoreholeView', NS):
        is_nvcl = child.findtext('./gsmlp:nvclCollection', default="false", namespaces=NS)
        if is_nvcl == "true":
            borehole_dict = {}
            print("boreholeview: ", "tag:", child.tag, "attrib:", child.attrib, "text:", child.text)

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
            print(Param.BBOX['west'], '<', borehole_dict['x'], 'and', Param.BBOX['east'], '>', borehole_dict['x'], 'and')
            print(Param.BBOX['north'], '>', borehole_dict['y'], 'and', Param.BBOX['south'], '<', borehole_dict['y'])
            if Param.BBOX['west'] < borehole_dict['x'] and  Param.BBOX['east'] > borehole_dict['x'] and \
               Param.BBOX['north'] > borehole_dict['y'] and Param.BBOX['south'] < borehole_dict['y']:
                borehole_cnt+=1
                borehole_list.append(borehole_dict)
                print('borehole_dict = ', borehole_dict)
                print('ACCEPTED')
            else:
                print('REJECTED')
            if borehole_cnt > max_boreholes:
                break
    #print('get_borehole_data() returns ', borehole_list)
    return borehole_list


def get_json_popupinfo(borehole_dict):
    ''' Returns some JSON for displaying in a popup box when user clicks on
        a borehole in the model
        borehole_dict - dict of borehole information used to make JSON
                        expected keys are: 'x', 'y', 'z', 'href' and GSMLP_IDS
,
    '''
    json_obj = {}
    json_obj['title'] = borehole_dict['name']
    for key in GSMLP_IDS:
        if key not in ['name', 'identifier', 'metadata_uri'] and len(borehole_dict[key])>0:
            json_obj[key] = borehole_dict[key]
    json_obj['href'] = [ { 'label': 'WFS URL', 'URL': borehole_dict['href'] },
                         { 'label': 'AuScope URL', 'URL': Param.EXTERNAL_LINK['URL'] } ]
    if len(borehole_dict['metadata_uri']) > 0:
        json_obj['href'].append({'label': 'Metadata URI', 'URL': borehole_dict['metadata_uri']})
    return json_obj


def get_config_borehole(borehole_list):
    ''' Creates a config object of borehole GLTF objects to display in 3D
        It prefers to create a list of NVCL boreholes, but will create ordinary boreholes if NVCL ones are not
        available
        borehole_list - list of boreholes
    '''
    config_obj = []
    for borehole_dict in borehole_list:
        j_dict = {}
        j_dict['popup_info'] = get_json_popupinfo(borehole_dict)
        j_dict['type'] = 'GLTFObject'
        x_m, y_m = convert_coords(Param.BOREHOLE_CRS, Param.MODEL_CRS, [borehole_dict['x'], borehole_dict['y']])
        j_dict['position'] = [x_m, y_m, borehole_dict['z']]
        j_dict['model_url'] = make_borehole_filename(borehole_dict['name'])+".gltf"
        j_dict['display_name'] = borehole_dict['name']
        j_dict['3dobject_label'] = make_borehole_label(borehole_dict['name'])
        j_dict['include'] = True
        j_dict['displayed'] = True
        config_obj.append(j_dict)
    return config_obj


def make_borehole_filename(borehole_name):
    ''' Returns a string, formatted borehole file name with no filename extension
        borehole_name - borehole identifier used to make file name
    '''
    return "Borehole_"+clean_borehole_name(borehole_name)


def clean_borehole_name(borehole_name):
    ''' Returns a clean version of the borehole name or id
        borehole_name - borehole identifier
    '''
    return borehole_name.replace(' ','_').replace('/','_').replace(':','_')


def make_borehole_label(borehole_name):
    ''' Returns a label version of the borehole name or id
        borehole_name - borehole name or identifier
    '''
    return "borehole-{0}".format(clean_borehole_name(borehole_name))


def get_json_input_param(input_file):
    ''' Reads the parameters from input JSON file and stores them in global 'Param' object
        input_file - filename of input parameter file
    '''
    global Param
    fp = open(input_file, "r")
    try:
        param_dict = json.load(fp)
    except JSONDecodeError as exc:
        print("ERROR - cannot read JSON file\n", input_file, "\n", exc)
        fp.close()
        sys.exit(1)
    fp.close()
    if 'BoreholeData' not in param_dict:
        print('ERROR - Cannot find "BoreholeData" key in input file', input_file);
        sys.exit(1)

    Param = SimpleNamespace()
    for field_name in ['BBOX', 'EXTERNAL_LINK', 'MODEL_CRS', 'WFS_URL', 'BOREHOLE_CRS', 'WFS_VERSION']:
        if field_name not in param_dict['BoreholeData']:
            print("ERROR - Cannot find '"+field_name+"' key in input file", input_file);
            sys.exit(1)
        setattr(Param, field_name, param_dict['BoreholeData'][field_name])

    if 'west' not in Param.BBOX or 'south' not in Param.BBOX or 'east' not in Param.BBOX or 'north' not in Param.BBOX:
        print("ERROR - Cannot find 'west', 'south', 'east', 'north' keys in 'BBOX' in input file", input_file)
        sys.exit(1)
    

def get_boreholes(dest_dir, input_file):
    ''' Retrieves borehole data and writes 3D model files to a directory
        dest_dir - directory where 3D model files are written
        input_file - file of input parameters
    '''
    # Set up input parameters from input file
    get_json_input_param(input_file)
    wfs = WebFeatureService(Param.WFS_URL, version=Param.WFS_VERSION, timeout=WFS_TIMEOUT)
    #print('wfs=', wfs)
    # Get all NVCL scanned boreholes within BBOX
    borehole_list = get_borehole_data(wfs, MAX_BOREHOLES)

    # Parse response for all boreholes, make COLLADA files
    for borehole_dict in borehole_list:
        #print(borehole_dict)
        if 'name' in borehole_dict and 'x' in borehole_dict and 'y' in borehole_dict and 'z' in borehole_dict:
            file_name = make_borehole_filename(borehole_dict['name'])
            x_m, y_m = convert_coords(Param.BOREHOLE_CRS, Param.MODEL_CRS, [borehole_dict['x'], borehole_dict['y']])
            base_xyz = (x_m, y_m, borehole_dict['z'])
            write_collada_borehole(base_xyz, dest_dir, file_name, borehole_dict['name'])
    # Convert COLLADA files to GLTF
    collada2gltf.convert_dir(dest_dir, "Borehole*.dae")
    # Return borehole objects
    return get_config_borehole(borehole_list)


### USED FOR TESTING ###
if __name__ == "__main__":
    if len(sys.argv) == 3:
        dest_dir = sys.argv[1]
        input_file = sys.argv[2]
        if not os.path.isdir(dest_dir):
            print("Dir "+dest_dir+" does not exist")
        elif not os.path.isfile(input_file):
            print("Input file does not exist: "+input_file)
        else:
            print(json.dumps(get_boreholes(dest_dir, input_file), indent=4, sort_keys=True))
    else:
        print("Command line parameters are: \n 1. a destination dir to place the output files\n 2. input config file\n\n")
