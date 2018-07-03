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

from owslib.wfs import WebFeatureService
import http.client, urllib

import collada2gltf
from types import SimpleNamespace


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
    p_in = Proj(init=input_crs)
    p_out = Proj(init=output_crs)
    return transform(p_in, p_out, xy[0], xy[1])


def write_collada_borehole(bv, dest_dir, file_name, borehole_name):
    ''' Write out a COLLADA file
        file_name - filename of COLLADA file, without extension
        bv - base vertex, position of the object within the model [x,y,z]
    '''
    mesh = Collada.Collada()
    BH_WIDTH = 75
    BH_HEIGHT = 10000
    BH_DEPTH = 20000
    node_list = []

    # Convert bv to an equilateral triangle of floats
    angl_rad = math.radians(30.0)
    cos_flt = math.cos(angl_rad)
    sin_flt = math.sin(angl_rad)
    #print(cos_flt, sin_flt)
    ptA_high = [bv[0], bv[1]+BH_WIDTH*cos_flt, bv[2]+BH_HEIGHT]
    ptB_high = [bv[0]+BH_WIDTH*cos_flt, bv[1]-BH_WIDTH*sin_flt, bv[2]+BH_HEIGHT]
    ptC_high = [bv[0]-BH_WIDTH*cos_flt, bv[1]-BH_WIDTH*sin_flt, bv[2]+BH_HEIGHT]
    ptA_low = [bv[0], bv[1]+BH_WIDTH*cos_flt, bv[2]-BH_DEPTH]
    ptB_low = [bv[0]+BH_WIDTH*cos_flt, bv[1]-BH_WIDTH*sin_flt, bv[2]-BH_DEPTH]
    ptC_low = [bv[0]-BH_WIDTH*cos_flt, bv[1]-BH_WIDTH*sin_flt, bv[2]-BH_DEPTH]

    diffuse_colour = (0.7, 0.55, 0.35, 1)
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


def get_scanned_borehole_hrefs(wfs):
    ''' This gets a list of URLs of NVCL boreholes which have been scanned
        wfs - handle of WFS object
    '''
    response = wfs.getfeature(typename='nvcl:ScannedBoreholeCollection')
    response_str = bytes(response.read(), 'ascii')
    #print("scannedborehole response=", response_str)
    href_list = []

    root = ET.fromstring(response_str)
    for child in root.iter('{http://www.auscope.org/nvcl}scannedBorehole'):
        # print("child", child.tag, child.attrib)
        href_list.append(child.attrib['{http://www.w3.org/1999/xlink}href'])

    return href_list


def get_borehole_data(wfs, nvcl_href_list, max_boreholes):
    ''' Returns a list of borehole data
        wfs - handle of borehole's WFS service
        nvcl_href_list - list of links to NVCL boreholes
        max_boreholes - maximum number of boreholes to retrieve

        NOTA BENE: I know that 'nvcl' href list is input, and it is not used
        that is because there are no NVCL cores within the BBOX
        Usually I would like to have it read in the NVCL hrefs and use them to find
        the borehole data (to be done in the near future)
    '''
    #print('get_borehole_data() wfs.contents =', list(wfs.contents))
    response = wfs.getfeature(typename='gsml:Borehole', bbox=Param.BBOX, srsname=Param.BOREHOLE_CRS)
    response_str = bytes(response.read(), 'ascii')
    href_list = []
    borehole_list = []
    #print('get_borehole_data() resp=', response_str)
    borehole_cnt=0
    root = ET.fromstring(response_str)
    for child in root.findall('./*/*/{http://www.opengis.net/gml}name'):
        #print("2 2 child", child.tag, child.attrib, child.text)
        if child.attrib['codeSpace']=='http://www.ietf.org/rfc/rfc2616':
            href_list.append(child.text)
            #print("borehole href=", child.text)
    root = ET.fromstring(response_str)

    for child in root.findall('./*/gsml:Borehole', NS):
        #print("borehole child", child.tag, child.attrib, child.text)
        borehole_dict = {}

        # Finds name and URL for borehole
        for namenode in child.findall('./gml:name', NS):
            #print("namenode", namenode.tag, namenode.attrib, namenode.text)
            if namenode.attrib['codeSpace']=='http://www.ietf.org/rfc/rfc2616':
                borehole_dict['href'] = namenode.text
            if namenode.attrib['codeSpace']==Param.BOREHOLE_CODESPACE:
                borehole_dict['id'] = namenode.text

        # Finds borehole collar x,y assumes units are degrees
        for posnode in child.findall('./gsml:collarLocation/gsml:BoreholeCollar/gsml:location/gml:Point/gml:pos', NS):
            #print("posnode", posnode.tag, posnode.attrib, posnode.text)
            xy = posnode.text.split(' ')
            try:
                borehole_dict['x'] = float(xy[0])
                borehole_dict['y'] = float(xy[1])
            except:
                borehole_dict['x'] = 0.0
                borehole_dict['y'] = 0.0

        # Finds most of the borehole details
        for infonode in child.findall('./gsml:indexData/gsml:BoreholeDetails', NS):
            #print("infonode", infonode.tag, infonode.attrib, infonode.text)
            for infonode_ch in infonode:
                #print("infonode_ch", infonode_ch.tag, infonode_ch.attrib, infonode_ch.text)
                borehole_dict[infonode_ch.tag.split('}')[1]] = infonode_ch.text

        # Finds elevation, assumes units are metres
        for elevnode in child.findall('./gsml:collarLocation/gsml:BoreholeCollar/gsml:elevation', NS):
            #print("elevnode", elevnode.tag, elevnode.attrib, elevnode.text)
            try:
                borehole_dict['z'] = float(elevnode.text)
            except:
                borehole_dict['z'] = 0.0

        if 'id' in borehole_dict:
            borehole_cnt+=1
            borehole_list.append(borehole_dict)
        if borehole_cnt > max_boreholes:
            break
    #print('get_borehole_data() returns ', borehole_list)
    return borehole_list


def get_json_popupinfo(borehole_dict):
    ''' Returns some JSON for displaying in a popup box when user clicks on
        a borehole in the model
        borehole_dict - borehole information used to make JSON

    '''
    json_obj = {}
    json_obj['title'] = borehole_dict['id']
    for key in ['drillingMethod','dateOfDrilling','driller', 'startPoint',
                'coreCustodian', 'inclinationType','coredInterval']:
        json_obj[key] = borehole_dict[key]
    json_obj['href'] = [ { 'label': 'WFS URL', 'URL': borehole_dict['href'] },
                         { 'label': 'AuScope URL', 'URL': Param.EXTERNAL_LINK['URL'] } ]
    json_obj['elevation'] = "{0:6.3f}".format(borehole_dict['z'])
    json_obj['location'] = "{0:6.3f} {1:6.3f}".format(borehole_dict['x'], borehole_dict['y'])
    return json_obj


def get_config_borehole(borehole_list):
    ''' Creates a config object of borehole GLTF objects to display in 3D
        borehole_list - list of boreholes
    '''
    config_obj = []
    for borehole_dict in borehole_list:
        j_dict = {}
        j_dict['popup_info'] = get_json_popupinfo(borehole_dict)
        j_dict['type'] = 'GLTFObject'
        x_m, y_m = convert_coords(Param.BOREHOLE_CRS, Param.MODEL_CRS, [borehole_dict['x'], borehole_dict['y']])
        j_dict['position'] = [x_m, y_m, borehole_dict['z']]
        j_dict['model_url'] = make_borehole_filename(borehole_dict['id'])+".gltf"
        j_dict['display_name'] = borehole_dict['id']
        j_dict['3dobject_label'] = make_borehole_label(borehole_dict['id'])
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
    return borehole_name.replace(' ','_').replace('/','_')


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
    for field_name in ['BBOX', 'EXTERNAL_LINK', 'MODEL_CRS', 'WFS_URL', 'BOREHOLE_TYPE', 'BOREHOLE_CRS', 'WFS_VERSION', 'BOREHOLE_CODESPACE']:
        if field_name not in param_dict['BoreholeData']:
            print("ERROR - Cannot find '"+field_name+"' key in input file", input_file);
            sys.exit(1)
        setattr(Param, field_name, param_dict['BoreholeData'][field_name])

    if 'west' not in Param.BBOX or 'south' not in Param.BBOX or 'east' not in Param.BBOX or 'north' not in Param.BBOX:
        print("ERROR - Cannot find 'west', 'south', 'east', 'north' keys in 'BBOX' in input file", input_file)
        sys.exit(1)
    Param.BBOX = [ Param.BBOX['west'], Param.BBOX['south'], Param.BBOX['east'], Param.BBOX['north'] ]
    

def get_boreholes(dest_dir, input_file):
    ''' Retrieves borehole data and writes 3D model files to a directory
        dest_dir - directory where 3D model files are written
        input_file - file of input parameters
    '''
    get_json_input_param(input_file)
    wfs = WebFeatureService(Param.WFS_URL, version=Param.WFS_VERSION, timeout=WFS_TIMEOUT)
    #print('wfs=', wfs)
    nvcl_href_list = get_scanned_borehole_hrefs(wfs)
    #print("nvcl_href_list=", nvcl_href_list)
    borehole_list = get_borehole_data(wfs, nvcl_href_list, MAX_BOREHOLES)

    # Parse response for all boreholes, make COLLADA files
    for borehole_dict in borehole_list:
        #print(borehole_dict)
        if 'id' in borehole_dict and 'x' in borehole_dict and 'y' in borehole_dict and 'z' in borehole_dict:
            file_name = make_borehole_filename(borehole_dict['id'])
            x_m, y_m = convert_coords(Param.BOREHOLE_CRS, Param.MODEL_CRS, [borehole_dict['x'], borehole_dict['y']])
            base_xyz = (x_m, y_m, borehole_dict['z'])
            write_collada_borehole(base_xyz, dest_dir, file_name, borehole_dict['id'])
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
            print(get_boreholes(dest_dir, input_file))
    else:
        print("Command line parameters are: \n 1. a destination dir to place the output files\n 2. input config file\n\n")
