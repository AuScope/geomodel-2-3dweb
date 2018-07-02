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
import math

from owslib.wfs import WebFeatureService
import http.client, urllib

import collada2gltf

MODEL = 'Tas'

if MODEL=='NorthGawler':

    # Bounding box of the area where boreholes are retrieved
    BBOX = (132.7052603, -28.3847194, 134.4664228, -26.9293133)

    AUSCOPE_PORTAL_URL = 'http://portal.auscope.org/portal/gmap.html?s=XQAAAQDvv4IBAAAAAAAAAD3vvojvvonvvqI3LO+/vzc7CwN/aO++rO+/kndiBe+/pCbvvoBgTu+/te++qk/vv73vvpDvvq9SEu+/pO++h++/uu+/uDIILSAM77+u776qIu+/oe++sg/vvqLvv6/vv6cWERE5Be+/se++sD1877+Qbn3vvrfvvqXvvpEyAmUy776DX2Xvv7Tvv4Am77+iV0jvvrt077+k776B77+TS0fvvqDvvqXvv5Yy77++776l77+/NTkZawHvv7Tvv7Tvv6/vvol0SUwH776iG++/g+++lTLvvojvv5rvvoVVOu+/tRBA77+Ff3RL77+nAGlRck9VQe++qW/vvrhhFe+/gkhQYWXvvqIj776NR+++j++/uEkYPH8f776ndxIb776dOShCPnlxQw4CaO++u0/vv7vvvrLvv598A++/kO++g3BtPWrvv5Pvv6M2776AZGvvvrgudHoC77+tbxzvvqt/Lw1hKgLvvqjvv5Lvv4rvvoRECH9kbGs/77+NcRoQfe++rO+/o+++rO++lu+/pe+/ikMT776CGe++gnvvv43vvqp/PGnvv6jvv6LvvqMz776577+k776I776ZZEnvv6M577+o776SVCzvvo/vvrEjN+++lmrvvrYAVgMj77+IEEQL776OBBV/77+0T++/lSbvvp9Hfe+/qu+/pVXvv6g2UBBp77+y77+rW++/gO+/jBLvv6Hvv53vv5/vvqEt77+o77+rNTMaNBnvv5Ai776777+DKjtC77+y77+w77++77+5776wEA==&v=4' 

    # Geo model's CRS, all output is converted to this CRS
    MODEL_CRS = "epsg:28352"

    WFS_URL = 'http://sarigdata.pir.sa.gov.au/nvcl/geoserver/wfs'

    # CRS of the coordinates in the WFS response
    BOREHOLE_TYPE='gsml:Borehole'
    BOREHOLE_CRS = "epsg:4326"
    WFS_VERSION='1.1.0'
    BOREHOLE_CODESPACE='http://www.pir.sa.gov.au'

elif MODEL == 'Tas':

    BBOX = (144.5, -43.7, 148.5, -40.5)
    AUSCOPE_PORTAL_URL = 'http://au-portal-2.it.csiro.au/portal/index.htm?state=XQAAAAJJCgAAAAAAAAA9776I776J77+H776j776DJO+/gT4/776VUi/vv4oW7761776j77+Q77+n776kCi3vv5Lvv4w1776KfO+/gWVT77+lPu++ku+/u+++mHlx776DKid577+/77+O776WCe++vO+/ihZGMO++ohTvv6oUbEY2fHnvvrnvv6oX77+rfO+/gO+/jF0ID1BXOO+/lxHvvoNX776L776xGu++oO++tO+/r1Em77+5He+/lO+/h+++lDdd77+1776reDLvvpAzRO++o++/tzTvvqTvv5B6T+++qQTvv4YbK3vvv6AdeAxk77+VG1bvvrrvv4QG776fLDlQ776V7768776gX+++qe+/kGtldncA776c77+5bVAd77+v776DJ1Q5KFliMBwf77+177+GeiTvvqTvvqjvv7/vv4lb776b77+Y7761776gRe+/qu++khzvvprvv4dq77+JS0ko776+77+W776I77+2C+++lQPvv4Uh776o77+DUzEj77+nAQVtPO++mm/vvoPvv77vvqrvv4Pvv7zvv6rvvrI1776hC0sjejbvvp5/776gTgLvv4J3aO+/hu++mu+/kCzvv7nvv4M077+d776h776377+W776qEO+/le+/g++/gBg/776eXjbvv5MZQTHvv7NRMUDvvpfvvqdnHnIt77+wP2nvvq7vv6Rj77+E77+N776sZ+++i++/te+/tO++ve++pu++lu++mO++nO++ve+/oO++re+/lDfvv4nvvrtb776e77+w77+dDu++tO++rO++sRAp7764f+++hxXvv5Pvv5BV776dBO+/nO++vilz77+o77+fbe++o0M7776d776bPu+/tO++je++jR4c776877+a77+PH+++su++mu++pAnvv6kwbO++mW5mOG1O77+q77+8M3DvvrhyD+++t3bvv6N1ce+/lO+/v+++ru++oe++onLvv6Pvv4s2776HSu+/ru+/h+++ge+/re++tWDvvpAJ776WIkfvv5Xvv4fvv5Pvvorvv54E776We2jvv4Xvv6Fv77+YKTQGIe++lO+/hzPvvpbvvppcP++/qm3vvqMoW++/nVzvv4Pvv6Ff776K776277+8YX0FfF/vvrvvvq7vv6EF776CCGU7Qy84776e77+h77+H77+FL17vvqzvvpM5Me+/t+++iRNE776xbu++j+++sXNZ7762776D77+577+v77+c77+X77+K776h776cQ++/ve+/kBJL77+J77+L77+qIe++i1Xvv5c2776hSFsN77+HckEx77+u776y776E7764X++/iO++jRUc776I776w77+jPXnvv5FnQSnvvrtFbkLvvqJI77+u77+JaO+/tl4t77+XTO+/h++/le++tu+/ryMjR+++iynvv5zvv7xB77+Z77+M77+JShDvvosm77+fRO+/t1Xvv7w6BnZDKO+/ve++sDERGUtN776X77+S77+iAe+/glPvv5J9776277+BOWciTljvv5ZD77+FIXDvvrVy776RR0tbYDNF77+p77+A77+u776M776P77+O7766Oe++ge++sV3vv40I77+577+0b++/rDfvvpvvv7Tvv5crB17vv7RYF+++ge++ie+/nR3vvo88aO+/je++oO++t1p0J+++hlfvvoDvv5FD77+x776cC+++vC3vvoNVSmAlDe++sGjvvrDvv4rvvqvvvqDvv7bvvpI2fQTvvroJ776Q776V77+3776ZDSQR77+377+/77+d77+xAnl/77+oZO+/k+++he+/pwZ3B++/q3FE77+BJ3vvvrbvv4k6O1p1776USu++pe+/khB777+k77+p776+e++/ou+/pkjvvrrvvpIqY+++tO++uu++gzbvv6Z0P++/mSXvvo/vvrMg77+L776M77+qaO+/nu+/tu++s1Lvv5zvvoMF776MJ++/gu+/pu++qjHvvqZtJ+++iFoFVVfvvrnvvqTvvpRXBO++iO++kVbvv5Lvv5wI77+ucu+/i08JF+++hXgL77+v77+A77+A77+w7769VEYx776DY++/v++/uBUB776G'

    MODEL_CRS = 'epsg:3857'

    WFS_URL = 'http://www.mrt.tas.gov.au:80/web-services/wfs'

    # CRS of the coordinates in the WFS response
    BOREHOLE_CRS = "epsg:4283"
    BOREHOLE_TYPE = "nvcl:ScannedBoreholeCollection"
    WFS_VERSION='1.1.0'
    BOREHOLE_CODESPACE='http://www.mrt.tas.gov.au'

elif MODEL == 'NorthQueensland':
    pass

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
    response = wfs.getfeature(typename='gsml:Borehole', bbox=BBOX, srsname=BOREHOLE_CRS)
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
            if namenode.attrib['codeSpace']==BOREHOLE_CODESPACE:
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
                         { 'label': 'AuScope URL', 'URL': AUSCOPE_PORTAL_URL } ]
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
        x_m, y_m = convert_coords(BOREHOLE_CRS, MODEL_CRS, [borehole_dict['x'], borehole_dict['y']])
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


def get_boreholes(dest_dir):
    ''' Retrieves borehole data and writes 3D model files to a directory
        dest_dir - directory where 3D model files are written
    '''
    wfs = WebFeatureService(WFS_URL, version=WFS_VERSION, timeout=6000)
    #print('wfs=', wfs)
    nvcl_href_list = get_scanned_borehole_hrefs(wfs)
    #print("nvcl_href_list=", nvcl_href_list)
    borehole_list = get_borehole_data(wfs, nvcl_href_list, MAX_BOREHOLES)

    # Parse response for all boreholes, make COLLADA files
    for borehole_dict in borehole_list:
        #print(borehole_dict)
        if 'id' in borehole_dict and 'x' in borehole_dict and 'y' in borehole_dict and 'z' in borehole_dict:
            file_name = make_borehole_filename(borehole_dict['id'])
            x_m, y_m = convert_coords(BOREHOLE_CRS, MODEL_CRS, [borehole_dict['x'], borehole_dict['y']])
            base_xyz = (x_m, y_m, borehole_dict['z'])
            write_collada_borehole(base_xyz, dest_dir, file_name, borehole_dict['id'])
    # Convert COLLADA files to GLTF
    collada2gltf.convert_dir(dest_dir, "Borehole*.dae")
    # Return borehole objects
    return get_config_borehole(borehole_list)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        dest_dir = sys.argv[1]
        if os.path.isdir(dest_dir):
            print(get_boreholes(dest_dir))
        else:
            print("Dir "+dest_dir+" does not exist")
    else:
        print("Command line parameter is a destination dir to place the output files")
