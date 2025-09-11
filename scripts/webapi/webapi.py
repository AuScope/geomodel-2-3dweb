''' A rough implementation of a subset of the 3DPS standard V1.0
 (http://docs.opengeospatial.org/is/15-001r4/15-001r4.html)
 and WFS v2.0 standard (http://www.opengeospatial.org/standards/wfs)

 Currently this is used to display boreholes in the geomodels website, and display imported GOCAD TSURF files.
 In future, it will be expanded to other functions, and put in a more structured and secure framework

 Examples of functions:

 1. To get information upon double click on object:
 
 http://localhost:4200/api/NorthGawler?service=3DPS&version=1.0&request=GetFeatureInfoByObjectId&objectId=EWHDDH01_5_0&layers=boreholes&format=application%2Fjson

 In practice, this uses the local sqlite3 database to fetch the NVCL borehole WFS metadata and uTSAS_Grp1 mineralogy for a borehole local to the 'NorthGawler' model.
 Sections of boreholes are distinguishable because the borehole id, depth and depth index are included in the 'name' field within the GLTF file's meshes and consequently
 the ThreeJS object in the scene inherits these

 2. To get list of borehole ids:
 
 http://localhost:4200/api/NorthGawler?service=WFS&version=2.0&request=GetPropertyValue&exceptions=application%2Fjson&outputFormat=application%2Fjson&typeName=boreholes&valueReference=borehole:id

 This uses the local sqlite3 database to fetch the nvcl ids of NVCL boreholes local to the 'NorthGawler' model


 3. To get borehole object after scene is loaded:
 
 http://localhost:4200/api/NorthGawler?service=3DPS&version=1.0&request=GetResourceById&resourceId=228563&outputFormat=model%2Fgltf%2Bjson%3Bcharset%3DUTF-8

 This retrieves and sends back pre-built GLTF borehole files which are included in the docker build process
 

 4. Import a TSURF file onto the 3D scene of the 'BurraMine' model via drag and drop:

 http://localhost:4200/api/burramine/import/bff191b0dd95dd35

 This uses converter code to convert the TSURF file to a GLTF borehole 

'''

"""
Implementation NOTES

A disk cache is used to improve response speed. (Uses 'diskcache' package)

This stores:

1. dict of OWSLib WFS service objects, cached to improve response time
2. dict of model parameters
3. dicts and lists of NVCL borehole metadata gleaned from nvcl_kit

A small sqlite DB contains all the 3DPS and WFS feature info (e.g. NVCL borehole mineralogy)

"""

import sys, os
import ctypes, tempfile
import json
from json import JSONDecodeError
import requests
import logging
from owslib.feature.wfs110 import WebFeatureService_1_1_0
from owslib.util import ServiceException
from diskcache import Cache, Timeout

# If assimp (https://github.com/assimp/assimp) shared library is in the path, then multi format export will be supported
try:
    import pyassimp
    HAS_ASSIMP = True
except ImportError:
    HAS_ASSIMP = False

from types import SimpleNamespace
import copyreg
from lxml import etree

from lib.file_processing import get_input_conv_param_bh
from lib.file_processing import read_json_file, find_gltf
from lib.exports.bh_make import get_blob_boreholes
from lib.imports.gocad.gocad_importer import GocadImporter
from lib.db.db_tables import QueryDB, QUERY_DB_FILE
from lib.exports.gltf_kit import GltfKit
from lib.picklers import element_unpickler, element_pickler, elementtree_unpickler, elementtree_pickler


from nvcl_kit.reader import NVCLReader
from nvcl_kit.param_builder import param_builder

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel



app = FastAPI()
''' Set up web FastAPI interface
'''

DEBUG_LVL = logging.INFO
''' Initialise debug level to minimal debugging
'''

NONDEF_COORDS = True
''' Will tolerate non default coordinates
'''

# Set up debugging
LOGGER = logging.getLogger(__name__)

if not LOGGER.hasHandlers():
    # Create logging console handler
    HANDLER = logging.StreamHandler(sys.stdout)

    # Create logging FORMATTER
    FORMATTER = logging.Formatter('%(name)s -- %(levelname)s - %(message)s')

    # Add FORMATTER to ch
    HANDLER.setFormatter(FORMATTER)

    # Add HANDLER to LOGGER and set level
    LOGGER.addHandler(HANDLER)

LOGGER.setLevel(DEBUG_LVL)


LOCAL_DIR = os.path.dirname(os.path.realpath(__file__))
''' This file's absolute path
'''

DATA_DIR = os.path.join(LOCAL_DIR, 'data')
''' Directory where web cache data files are stored
'''

INPUT_DIR = os.path.join(LOCAL_DIR, 'input')
''' Directory where conversion parameter files are stored, one for each model
'''

CACHE_DIR = os.path.join(DATA_DIR, 'cache')
''' Directory where WFS service information is kept
'''

GEOMODELS_DIR = os.path.join(LOCAL_DIR, os.pardir, 'assets', 'geomodels')

MAX_BOREHOLES = 20
''' Maximum number of boreholes requested from nvcl_kit, set low for fast response
'''

WFS_TIMEOUT = 6000
''' Timeout for querying WFS services (seconds)
'''

LAYER_NAME = 'boreholes'
''' Name of our 3DPS layer
'''

G_PARAM_DICT = {}
''' Stores the models' conversion parameters, key: model name
'''

G_WFS_DICT = {}
''' Stores owslib WebFeatureService objects, key: model name
'''

class PickleableWebFeatureService(WebFeatureService_1_1_0):
    '''
    Override OWSLib 'WebFeatureService' so that it can initialise the class when unpickling
    '''
    def __getnewargs__(self):
        return ('', '', None)


def create_borehole_dict_list_old(model, param_dict, wfs_dict):
    '''
    Call upon nvcl_kit's network services to create dictionary and a list of boreholes for a model

    :param model: name of model, string
    :param param_dict: parameter dictionary
    :param wfs_dict: dictionary of WFS services
    :returns: borehole_dict, response_list
    '''
    # Concatenate response
    response_list = []
    if model not in wfs_dict or model not in param_dict:
        LOGGER.warning(f"Model '{model}' not in both wfs_dict and param_dict")
        LOGGER.debug(f"Exiting {wfs_dict=} {param_dict=}")
        return {}, []
    param = param_builder(param_dict[model].PROVIDER)
    # Limit the number of boreholes so that they do not take too long to load
    param.MAX_BOREHOLES = MAX_BOREHOLES
    if hasattr(param_dict[model], 'BOREHOLE_CRS'):
        param.BOREHOLE_CRS = param_dict[model].BOREHOLE_CRS
    # Use model's extent to limit borehole search area
    if hasattr(param_dict[model], 'BBOX'):
        param.BBOX = param_dict[model].BBOX
    LOGGER.debug(f"Creating NVCLReader {param_dict[model]=} {param=} {wfs_dict[model]=}")
    reader = NVCLReader(param, wfs=wfs_dict[model])
    borehole_list = reader.get_boreholes_list()
    LOGGER.debug(f"{borehole_list=}")
    result_dict = {}
    for borehole_obj in borehole_list:
        borehole_id = borehole_obj.nvcl_id
        response_list.append({'borehole:id': borehole_id})
        result_dict[borehole_id] = borehole_obj
    return result_dict, response_list


def create_borehole_dict_list(model, param_dict, wfs_dict):
    '''
    Call upon nvcl_kit's network services to create dictionary and a list of boreholes for a model

    :param model: name of model, string
    :param param_dict: parameter dictionary
    :param wfs_dict: dictionary of WFS services
    :returns: borehole_dict, response_list
    '''
    # Concatenate response
    if model not in wfs_dict or model not in param_dict:
        LOGGER.warning(f"Model '{model}' not in both wfs_dict and param_dict")
        LOGGER.debug(f"Exiting {wfs_dict=} {param_dict=}")
        return {}, []
    # Query database
    # Open up query database to get object information (e.g. NVCL borehole metadata)
    db_path = os.path.join(DATA_DIR, QUERY_DB_FILE)
    qdb = QueryDB(overwrite=False, db_name=db_path)
    err_msg = qdb.get_error()
    if err_msg != '':
        LOGGER.error(f"Could not open query db {db_path}: {err_msg}")
        return {}, []
    LOGGER.debug(f"Querying borehole feature info db: {model}")
    # Get borehole feature data from 'PartsInfo' table in db
    result_dict = {}
    result_list = []
    o_k, parts_list = qdb.get_json_from_parts(model)
    if o_k:
        for parts_str in parts_list:
            try:
                parts = json.loads(parts_str)
            except json.JSONDecodeError as e:
                # Skip if can't parse JSON
                continue
            p = SimpleNamespace()
            for key in parts:
                setattr(p, key, parts[key])
            borehole_id = parts['nvcl_id']
            setattr(p, 'borehole:id', borehole_id)
            setattr(p, 'name', borehole_id)
            result_dict[borehole_id] = p
            result_list.append({'borehole:id': borehole_id})
        return result_dict, result_list
    LOGGER.debug(f"No borehole feature data found for {model} in db: {results}")
    return {}, []


def get_cached_bhdict_list(model, param_dict, wfs_dict):
    '''
    Fetches borehole dictionary and response list from cache or creates them if necessary

    :param model: name of model, string
    :param param_dict: parameter dictionary
    :param wfs_dict: dictionary of WFS services
    :returns: borehole_dict, response_list
    '''
    try:
        with Cache(CACHE_DIR) as cache_obj:
            bhd_key = 'bh_dict|' + model
            bhl_key = 'bh_list|' + model
            bh_dict = cache_obj.get(bhd_key)
            bh_list = cache_obj.get(bhl_key)
            LOGGER.debug(f"Fetched from cache {bh_dict=} {bh_list=}")
            # If there in nothing in the cache try the network
            if bh_dict in (None,{}) or bh_list in (None,[]):
                LOGGER.debug("Empty bh_dict / bh_list")
                # Use nvcl_kit's network services to create a lists of boreholes in the vicinity of the model
                bh_dict, bh_list = create_borehole_dict_list(model, param_dict, wfs_dict)
                LOGGER.debug(f"Created from network {bh_dict=} {bh_list=}")
                cache_obj.add(bhd_key, bh_dict)
                cache_obj.add(bhl_key, bh_list)
            return bh_dict, bh_list
    except OSError as os_exc:
        LOGGER.error(f"Cannot get cached dict list: {os_exc}")
        return (None, 0)
    except Timeout as t_exc:
        LOGGER.error(f"DB Timeout, cannot get cached dict list: {t_exc}")
        return (None, 0)



def create_cacheable_parameters():
    '''
    Creates dictionaries to store model parameters and WFS services

    :returns: model parameter dict, WFS dict; both keyed on model name string
    '''
    LOGGER.debug("create_cacheable_parameters()")
    if not os.path.exists(INPUT_DIR):
        LOGGER.error(f"Input dir {INPUT_DIR} does not exist")
        sys.exit(1)

    # Get all the model names and details from 'ProviderModelInfo.json'
    config_file = os.path.join(INPUT_DIR, 'ProviderModelInfo.json')
    if not os.path.exists(config_file):
        LOGGER.error(f"config file does not exist {config_file}")
        sys.exit(1)
    conf_dict = read_json_file(config_file)
    LOGGER.debug(f"Parsed 'ProviderModelInfo.json': {conf_dict=}")
    # For each provider
    param_dict = {}
    wfs_dict = {}
    # pylint: disable=W0612
    for prov_name, model_dict in conf_dict.items():
        model_list = model_dict['models']
        LOGGER.debug(f"For {prov_name}, {model_list=}")
        # For each model within a provider
        for model_obj in model_list:
            model = model_obj['modelUrlPath']
            file_prefix = model_obj['configFile'][:-5]
            # Open up model's conversion input parameter file
            input_file = os.path.join(INPUT_DIR, file_prefix + 'ConvParam.json')
            if not os.path.exists(input_file):
                LOGGER.warning(f"Cannot find {input_file}")
                continue
            # Load params and connect to WFS service
            param_dict[model] = get_input_conv_param_bh(input_file)
            LOGGER.debug(f"For {model=}, {param_dict[model]=}")
            # If input conversion file does not have a bounding box, use the one calculated from the model
            # conversion process
            if not hasattr(param_dict[model], 'BOREHOLE_CRS') or not hasattr(param_dict[model], 'BBOX'):
                webasset_file = os.path.join(GEOMODELS_DIR, file_prefix + '.json')
                if os.path.exists(input_file):
                    webasset_dict = read_json_file(webasset_file)
                    param_dict[model].BOREHOLE_CRS = webasset_dict['properties']['crs']
                    extent =  webasset_dict['properties']['extent']
                    param_dict[model].BBOX = {'north': extent[3], 'south': extent[2], 'east': extent[1], 'west': extent[0]}
            if not hasattr(param_dict[model], 'PROVIDER'):
                LOGGER.error(f"Cannot find provider for {model}, check param conversion file")
                sys.exit(1)
            # Use nvcl_kit to get WFS_URL and WFS_VERSION parameters
            try:
                param_obj = param_builder(param_dict[model].PROVIDER)
                # Open up connection to WFS service
                wfs_dict[model] = PickleableWebFeatureService(url=param_obj.WFS_URL, xml=None, timeout=WFS_TIMEOUT, version="1.1.0")
            except Exception as e:
                LOGGER.error(f"Cannot reach service {param_obj.WFS_URL}: {e}")
    LOGGER.debug(f"Returning {param_dict=}")
    LOGGER.debug(f"Returning {wfs_dict=}")
    return param_dict, wfs_dict



def make_json_exception_response(version, code, message, locator='noLocator'):
    '''
    Make a JSON error response

    :param version: version string
    :param code: error code string, can be 'OperationNotSupported', 'MissingParameterValue', \
                                           'OperationProcessingFailed'
    :param message: text message explaining error in more detail
    :param locator:  optional string indicating what part of input caused the problem. \
                     This must be checked for XSS or SQL injection exploits
    :returns: byte array HTTP response
    '''
    msg_json = {"version": version, "exceptions": [{"code": code, "locator": locator,
                                                    "text": message}]}
    return msg_json


def make_str_response(msg):
    '''
    Make a generic string response

    :param message: text message explaining error in more detail
    :returns: byte array HTTP response
    '''
    return str(msg)



def make_getcap_response(model, param_dict):
    '''
    Create and initialise the 3DPS 'GetCapabilities' response

    :param model: Model name
    :param param_dict: model param
    :returns: byte array HTTP response
    '''
    if model not in param_dict:
        return make_json_exception_response("1.0", "OperationNotSupported", "Unknown model name")

    response = """<?xml version="1.0" encoding="UTF-8"?>
<Capabilities xmlns="http://www.opengis.net/3dps/1.0/core"
 xmlns:core="http://www.opengis.net/3dps/1.0/core"
 xmlns:ows="http://www.opengis.net/ows/2.0"
 xmlns:xlink="http://www.w3.org/1999/xlink"
 xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
 xsi:schemaLocation="http://www.opengis.net/3dps/1.0 ../../../schema/3dpResp.xsd" version="1.0">
  <ows:ServiceIdentification>
    <ows:Title>Auscope Geomodels</ows:Title>
    <ows:Abstract>Website displaying geological models</ows:Abstract>
    <ows:Keywords>
      <ows:Keyword>3D</ows:Keyword>
      <ows:Keyword>Portrayal</ows:Keyword>
    </ows:Keywords>
    <ows:ServiceType codeSpace="OGC">3DPS</ows:ServiceType>
    <ows:ServiceTypeVersion>1.0</ows:ServiceTypeVersion>
    <ows:Profile>http://www.opengis.net/spec/3DPS/1.0/extension/scene/1.0</ows:Profile>
    <ows:Fees>none</ows:Fees>
    <ows:AccessConstraints>none</ows:AccessConstraints>
  </ows:ServiceIdentification>
  <ows:ServiceProvider>
    <ows:ProviderName>AuScope</ows:ProviderName>
    <ows:ServiceContact>
      <ows:PositionName>AuScope Geomodels Support</ows:PositionName>
      <ows:ContactInfo>
        <ows:Address>
          <ows:ElectronicMailAddress>cg-admin@csiro.au</ows:ElectronicMailAddress>
        </ows:Address>
      </ows:ContactInfo>
    </ows:ServiceContact>
  </ows:ServiceProvider>
  <ows:OperationsMetadata>
    <ows:Operation name="GetCapabilities">
      <ows:DCP>
        <ows:HTTP>
          <ows:Get xlink:href="http://localhost:4200/api/{0}?"/>
        </ows:HTTP>
      </ows:DCP>
      <ows:Parameter name="AcceptFormats">
          <ows:AllowedValues>
              <ows:Value>text/xml</ows:Value>
          </ows:AllowedValues>
          <ows:DefaultValue>text/xml</ows:DefaultValue>
      </ows:Parameter>
      <ows:Parameter name="AcceptVersions">
          <ows:AllowedValues>
              <ows:Value>1.0</ows:Value>
          </ows:AllowedValues>
          <ows:DefaultValue>1.0</ows:DefaultValue>
      </ows:Parameter>
    </ows:Operation>
    <ows:Operation name="GetFeatureInfoByObjectId">
      <ows:DCP>
        <ows:HTTP>
          <ows:Get xlink:href="http://localhost:4200/api/{0}?" />
        </ows:HTTP>
      </ows:DCP>
      <ows:Parameter name="Exceptions">
        <ows:AllowedValues>
          <ows:Value>application/json</ows:Value>
        </ows:AllowedValues>
        <ows:DefaultValue>application/json</ows:DefaultValue>
      </ows:Parameter>
      <ows:Parameter name="Format">
        <ows:AllowedValues>
          <ows:Value>application/json</ows:Value>
        </ows:AllowedValues>
        <ows:DefaultValue>application/json</ows:DefaultValue>
      </ows:Parameter>
    </ows:Operation>
    <ows:Operation name="GetResourceById">
      <ows:DCP>
        <ows:HTTP>
          <ows:Get xlink:href="http://localhost:4200/api/{0}?" />
        </ows:HTTP>
      </ows:DCP>
      <ows:Parameter name="OutputFormat">
        <ows:AllowedValues>
          <ows:Value>model/gltf+json;charset=UTF-8</ows:Value>
        </ows:AllowedValues>
        <ows:DefaultValue>application/json</ows:DefaultValue>
      </ows:Parameter>
      <ows:Parameter name="ExceptionFormat">
        <ows:AllowedValues>
          <ows:Value>application/json</ows:Value>
        </ows:AllowedValues>
        <ows:DefaultValue>application/json</ows:DefaultValue>
      </ows:Parameter>
    </ows:Operation>
  </ows:OperationsMetadata>
  <Contents>""".format(model)
    response += """       <Layer>
      <ows:Identifier>{0}</ows:Identifier>
      <AvailableCRS>{1}</AvailableCRS>
    </Layer>""".format(LAYER_NAME, param_dict[model].MODEL_CRS)

    response += "</Contents>\n</Capabilities>"

    return response



def make_getfeatinfobyid_response(model, version, query_format, layer_names, obj_id):
    '''
    Create and initialise the 3DPS 'GetFeatureInfoByObjectId' response

    :param model: model name
    :param version: 3DPS version parameter
    :param query_format: response format
    :param layer_names: names of layers requested in query
    :param obj_id: object id
    :returns: byte array HTTP response in JSON format
    '''
    LOGGER.debug('make_getfeatinfobyid_response() obj_id = %s', repr(obj_id))
    # Parse id from query string
    if not obj_id:
        return make_json_exception_response(version, 'MissingParameterValue', 'missing objectId parameter')

    # Parse format from query string
    if not query_format:
        return make_json_exception_response(version, 'MissingParameterValue', 'missing format parameter')
    if query_format != 'application/json':
        return make_json_exception_response(version, 'InvalidParameterValue', 'incorrect format, try "application/json"')

    # Parse layers from query string
    if not layer_names:
        return make_json_exception_response(version, 'MissingParameterValue', 'missing layers parameter')
    if layer_names != LAYER_NAME:
        return make_json_exception_response(version, 'InvalidParameterValue', 'incorrect layers, try "'+ LAYER_NAME + '"')

    # Query database
    # Open up query database to get object information (e.g. NVCL borehole mineralogy)
    db_path = os.path.join(DATA_DIR, QUERY_DB_FILE)
    qdb = QueryDB(overwrite=False, db_name=db_path)
    err_msg = qdb.get_error()
    if err_msg != '':
        LOGGER.error(f"Could not open query db {db_path}: {err_msg}")
        return make_str_response(' ')
    LOGGER.debug(f"Querying db: {obj_id} {model}")
    o_k, result = qdb.query(obj_id, model)
    if o_k:
        # pylint: disable=W0612
        label, out_model, segment_str, part_str, model_str, user_str = result
        resp_dict = {'type': 'FeatureInfoList', 'totalFeatureInfo': 1,
                     'featureInfos': [{'type': 'FeatureInfo', 'objectId': obj_id,
                                       'featureId': obj_id, 'featureAttributeList': []}]}
        query_dict = {}
        if segment_str is not None:
            segment_info = json.loads(segment_str)
            query_dict.update(segment_info)
        if part_str is not None:
            part_info = json.loads(part_str)
            query_dict.update(part_info)
        if model_str is not None:
            model_info = json.loads(model_str)
            query_dict.update(model_info)
        if user_str is not None:
            user_info = json.loads(user_str)
            query_dict.update(user_info)
        for key, val in query_dict.items():
            feat_dict = {'type': 'FeatureAttribute', 'name': key, 'value': val}
            resp_dict['featureInfos'][0]['featureAttributeList'].append(feat_dict)
        return resp_dict

    LOGGER.error('Could not query db: %s', str(result))
    return make_str_response(' ')



def make_getresourcebyid_response(model, version, output_format, res_id, param_dict, wfs_dict):
    '''
    Create and initialise the 3DPS 'GetResourceById' response

    *** Used to retrieve GLTF for 3D boreholes ***

    :param model: name of model (string)
    :param version: 3DPS request version
    :param output_format: 3DPS response format
    :param res_id: requested resource id
    :param param_dict: parameter dictionary
    :param wfs_dict: dictionary of WFS services
    :returns: byte array HTTP response
    '''
    # This sends back the first part of the GLTF object - the GLTF file for the
    # resource id specified
    LOGGER.debug(f"make_getresourcebyid_response({model=})")

    # Parse outputFormat from query string
    LOGGER.debug(f"{output_format=}")
    if not output_format:
        return make_json_exception_response(version, 'MissingParameterValue', 'missing outputFormat parameter')
    if output_format != 'model/gltf+json;charset=UTF-8':
        resp_msg = 'incorrect outputFormat, try "model/gltf+json;charset=UTF-8"'
        return make_json_exception_response(version, 'InvalidParameterValue', resp_msg)

    # Parse resourceId from query string
    LOGGER.debug(f"{res_id=}")
    if not res_id:
        return make_json_exception_response(version, 'MissingParameterValue', 'missing resourceId parameter')

    # Read borehole file from filesystem
    file_name = f"Borehole_{res_id}.gltf"
    file_path = os.path.join(os.pardir, "assets", "geomodels", "boreholes", file_name)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")

    return FileResponse(
        path=file_path,
        media_type="model/gltf+json;charset=UTF-8",
        filename=file_name
    )


def send_blob(gltf_str):
    ''' Generic routine that returns a blob in response

    *** Used to send either a GLTF 3D borehole or a GLTF representation of an imported GOCAD file ***

    :param gltf_str: GLTF as a blob object
    :returns: a binary file response
    '''
    LOGGER.debug(f"send_blob(): Got GLTF bytes {gltf_str}")
    with tempfile.NamedTemporaryFile(mode="w", suffix=".gltf", delete=False) as fp:
        fp.write(gltf_str)
    LOGGER.debug("send_blob(): Created temp file, returning it")
    return FileResponse(fp.name, media_type="model/gltf+json;charset=UTF-8")


def make_getpropvalue_response(model, version, output_format, type_name, value_ref, param_dict, wfs_dict):
    '''
    Returns a response to a WFS getPropertyValue request, example: \
      https://demo.geo-solutions.it/geoserver/wfs?version=2.0&request=GetPropertyValue& \
        outputFormat=json&exceptions=application/json&typeName=test:Linea_costa&valueReference=id

    *** This is used to fetch the IDs for boreholes using the disk cache ***

    :param model: name of model (string)
    :param version: 3DPS request version
    :param output_format: 3DPS response format
    :param type_name: type name
    :param value_ref: value reference
    :param param_dict: parameter dictionary
    :param wfs_dict: dictionary of WFS services
    :returns: byte array HTTP response
    '''

    # Parse outputFormat from query string
    if not output_format:
        return make_json_exception_response(version, 'MissingParameterValue', 'missing outputFormat parameter')
    if output_format != 'application/json':
        return make_json_exception_response(version, 'OperationProcessingFailed',
                                            'incorrect outputFormat, try "application/json"')

    # Parse typeName from query string
    if not type_name:
        return make_json_exception_response(version, 'MissingParameterValue', 'missing typeName parameter')
    if type_name != 'boreholes':
        return make_json_exception_response(version, 'OperationProcessingFailed', 'incorrect typeName, try "boreholes"')

    # Parse valueReference from query string
    if not value_ref:
        return make_json_exception_response(version, 'MissingParameterValue', 'missing valueReference parameter')
    if value_ref != 'borehole:id':
        return make_json_exception_response(version, 'OperationProcessingFailed',
                                                     'incorrect valueReference, try "borehole:id"')

    # Fetch list of borehole ids
    # pylint: disable=W0612
    model_bh_dict, response_list = get_cached_bhdict_list(model, param_dict, wfs_dict)
    response_json = {'type': 'ValueCollection', 'totalValues': len(response_list), 'values': response_list}
    return response_json


def convert_gocad2gltf(model, id_str, gocad_list):
    '''
    Call the conversion code to convert a GOCAD string to GLTF

    *** Used when the user drags and drops a GOCAD .TS file into the 3D scene ***

    :param model: name of model
    :param id_str: sequence number string
    :param gocad_list: GOCAD file lines as a list of strings
    :returns: a JSON response
    '''
    base_xyz = (0.0, 0.0, 0.0)
    gocad_obj = GocadImporter(DEBUG_LVL, base_xyz=base_xyz,
                              nondefault_coords=NONDEF_COORDS)
    # First convert GOCAD to GSM (geometry, style, metadata)
    is_ok, gsm_list = gocad_obj.process_gocad('drag_and_drop', 'drag_and_drop.ts', gocad_list)
    if is_ok and gsm_list:
        # Then, output GSM as GLTF ...
        gsm_obj = gsm_list[0]
        geom_obj, style_obj, metadata_obj = gsm_obj
        gltf_kit = GltfKit(DEBUG_LVL)
        gltf_kit.start_scene()
        gltf_kit.add_geom(geom_obj, style_obj, metadata_obj)
        gltf_bytes = gltf_kit.end_scene("")
        return send_blob(gltf_bytes)
    return make_str_response(' ')


def convert_gltf2xxx(model, filename, fmt):
    '''
    Call the assimp conversion code to convert GLTF string to a certain format

    *** Used in the experimental EXPORT function ***

    :param model: name of model
    :param filename: filename of GLTF file to be converted
    :param fmt: string indicating what format to convert to, e.g. 'DXF'
    :returns: a file response
    '''
    # Exit if assimp library not available
    if not HAS_ASSIMP:
        LOGGER.warning(f"Assimp package not available or shared library not in LD_LIBRARY_PATH. Cannot convert {filename} to {fmt} and export")
        return make_str_reponse("Multi-format export not supported. Please contact website administrator.")

    # Use model name and file name to get full GLTF file path
    gltf_path = find_gltf(GEOMODELS_DIR, INPUT_DIR, model, filename)
    if not gltf_path:
        LOGGER.error(f"Cannot find {gltf_path}")
        return make_str_response(' ')

    gltf_path = os.path.abspath(gltf_path)

    # Load GLTF file into assimp
    try:
        assimp_obj = pyassimp.load(gltf_path, 'gltf2')
    except pyassimp.AssimpError as ae:
        LOGGER.error(f"Cannot load {gltf_path}: {ae}")
        return make_str_response(' ')

    # Export as whatever format desired
    try:
        blob_obj = pyassimp.export_blob(assimp_obj, fmt, processing=None)
    except pyassimp.AssimpError as ae:
        LOGGER.error(f"Cannot export {gltf_path}: {ae}")
        return make_str_response(' ')

    # Assume it is a text file
    with tempfile.NamedTemporaryFile(mode="w+b", suffix="."+fmt, delete=False) as fp:
            fp.write(blob_obj)
    return FileResponse(fp.name, media_type="text/plain;charset=UTF-8")


def process3DPS(model, version, request, format, outputFormat, layers, objectId, resourceId):
    '''
    Process an OCG 3PS request. Roughly trying to conform to 3DPS standard

    *** 'getresourcebyid' is used to retrieve GLTF version of NVCL borehole ***

    *** 'getfeatureinfobyobjectid' is used to get information about a GLTF borehole ***

    :param model: name of model
    :param version: WFS version parameter
    :param request: string, 3DPS request type string
    :param format: requested response output format in 'getfeatureinfobyobjectid' request
    :param outputFormat: requested response output format in 'getresourcebyid' request
    :param layers: list of layers
    :param objectId: objectId parameter in 'getfeatureinfobyobjectid' request
    :param resourceId: resourceId parameter in 'getresourcebyid' request
    :returns: a JSON response
    '''
    if request.lower() == 'getcapabilities':
        return make_getcap_response(model, G_PARAM_DICT)

    # Check for version
    if version != '1.0':
        return make_json_exception_response('Unknown', 'OperationProcessingFailed',
                                                'Incorrect version, try "1.0"')

    # Check request type
    if request.lower() in ['getscene', 'getview', 'getfeatureinfobyray',
                           'getfeatureinfobyposition']:
        return make_json_exception_response(version, 'OperationNotSupported',
                                            'Request type is not implemented',
                                            request.lower())

    # Retrieve information about a resource
    if request.lower() == 'getfeatureinfobyobjectid':
        return make_getfeatinfobyid_response(model, version, format, layers, objectId)

    # Retrieve a resource (i.e. GLTF)
    if request.lower() == 'getresourcebyid':
        return make_getresourcebyid_response(model, version, outputFormat, resourceId, G_PARAM_DICT, G_WFS_DICT)

    # Unknown request
    return make_json_exception_response(version, 'OperationNotSupported', 'Unknown request type')


def processWFS(model, version, request, outputFormat, exceptions, typeName, valueReference):
    '''
    Process an OCG WFS request

    :param model: name of model
    :param version: WFS version parameter
    :param request: string, WFS request type string
    :param outputFormat: WFS outputformat parameter
    :param exceptions: WFS exceptions parameter
    :param typeName: WFS typename parameter
    :param value_ref: WFS valuereference parameter
    :returns: a JSON response
    '''

    # Check for version 2.0
    LOGGER.debug('version = %s', version)
    if version != '2.0':
        return make_json_exception_response('Unknown', 'OperationProcessingFailed',
                                            'Incorrect version, try "2.0"')

    # WFS GetFeature request
    if request.lower() == 'getpropertyvalue':
        return make_getpropvalue_response(model, version, outputFormat, typeName, valueReference, G_PARAM_DICT, G_WFS_DICT)

    return make_json_exception_response(version, 'OperationNotSupported', 'Unknown request name')


def processEXPORT(model, filename, fmt):
    '''
    Export a model part to DXF etc.

    :param environ: WSGI 'environ' variable
    :param url_kvp: dict of parameters extracted from the incoming URL
    :param model: name of model
    :returns: a response that can be returned from the 'application()' function
    '''
    return convert_gltf2xxx(model, filename, fmt)

def processIMPORT(model, id_str, import_file):
    '''
    Process a GOCAD to GLTF conversion request

    :param model: name of model
    :param id_str: identity string
    :param import_file: content of file to be imported, bytes
    :returns: a JSON response
    '''
    file_str = import_file.content.decode()
    file_str_list = file_str.split('\n')
    return convert_gocad2gltf(model, id_str, file_str_list)


def processWMS(model, style, wms_url, **params):
    '''
    Processes an OCG WMS request by proxying

    :param model: name of model
    :param style: name of style
    :param wms_url: WMS URL of service to proxy
    :returns: a WMS response
    '''

    # Check params
    for key,val in params.items():
        if key not in ['service', 'wmsurl']:
            if not checkWMS(key, val):

                return make_str_response('{}')

    # Make the WMS request
    url = wms_url.split('?')[0]
    params['SERVICE']='WMS'

    resp = requests.get(url, params)
    with tempfile.NamedTemporaryFile(mode="w+b", suffix=".png", delete=False) as fp:
        fp.write(resp.content)
    return FileResponse(fp.name, media_type="image/png")


def checkWMS(key, val):
    '''
    Checks that a WMS URL parameter is legitimate \
    NB: Does not accept any style other than empty or 'default'

    :param key: key string
    :param val: value string
    :returns: True if this is a legitimate WMS URL parameter
    '''
    lkey = key.lower()
    lval = val.lower()
    if lkey == 'wmsurl':
        if (lval[:7] == 'http://' or lval[:8] == 'https://') and \
           lval[-12:] == '?service=wms' and lval.count('?') == 1:
            return any(c in 'abcdefghijklmnopqrstuvwxyz_-?:/.=' for c in lval)
    if lkey == 'service':
        return (lval == 'wms')
    if lkey == 'layers':
        return all(c in '1234567890abcdefghijklmnopqrstuvwxyz_-' for c in lval)
    if lkey == 'request' and lval.isalpha():
        return True
    if lkey == 'version':
        return all(c in '1234567890.' for c in lval)
    if lkey == 'styles' and lval in ['default', '']:
        return True
    if lkey == 'format' and lval in ['image/png', 'image/jpeg']:
        return True
    if lkey in ['transparent', 'displayoutsidemaxextent'] and lval in ['true','false']:
        return True
    if lkey == 'bbox':
        return all(c in '1234567890,.-' for c in lval)
    if lkey == 'crs' and lval[:5] == 'epsg:' and lval[5:].isnumeric():
        return True
    if lkey in ['height','width'] and lval.isnumeric():
        return True
    return False


# Web API starts here

# WFS and 3DPS
@app.get("/api/{model}")
async def processRequest(model: str, service: str, version: str, request: str,
                         resourceId: str = None, layers: str = None, objectId: str = None, format: str = None, # 3DPS
                         exceptions: str = None,  typeName = None, valueReference = None, outputFormat: str = None # WFS
                        ): 
    if service == 'WFS':
        return processWFS(model, version, request, outputFormat, exceptions, typeName, valueReference)
    elif service == '3DPS':
        return process3DPS(model, version, request, format, outputFormat, layers, objectId, resourceId)

    return "Unknown service name, should be one of: 'WFS', '3DPS'"


# WMS PROXY
@app.get("/api/{model}/wmsproxy/{styles}")
async def wmsProxy(model: str, styles: str, wmsUrl: str, REQUEST: str, LAYERS: str, VERSION: str, STYLES: str, FORMAT:str, BBOX:str, CRS: str, WIDTH: str, HEIGHT:str):

    return processWMS(model, styles, wmsUrl, request=REQUEST, layers=LAYERS, version=VERSION, styles=STYLES,
                                             format=FORMAT, bbox=BBOX, crs=CRS, width=WIDTH, height=HEIGHT)


# Used in API signature below
class ImportFile(BaseModel):
    crs: str
    content: bytes

# Import GOCAD file
@app.post("/api/{model}/import/{id}")
async def importFile(model: str, id: str, import_file: ImportFile):
    return processIMPORT(model, id, import_file)


# Export DXF file (experimental)
@app.get("/api/{model}/export/{filename}/{fmt}")
async def exportFile(model: str, filename: str, fmt: str):
    return processEXPORT(model, filename, fmt)


'''
INITIALISATION - Executed upon startup only.
Loads all the model parameters and WFS services from cache or creates them
'''
PARAM_CACHE_KEY = 'model_parameters'
WFS_CACHE_KEY = 'wfs_dict'

# Register functions to manage pickling/unpickling of objects from 'lxml' package
# that are contained in the 'WebFeatureService_1_1_0' class
copyreg.pickle(etree._Element, element_pickler, element_unpickler)
copyreg.pickle(etree._ElementTree, elementtree_pickler, elementtree_unpickler)

# Load cached config and 'WebFeatureService_1_1_0' classes
try:
    with Cache(CACHE_DIR) as cache:
        G_PARAM_DICT = cache.get(PARAM_CACHE_KEY)
        G_WFS_DICT = cache.get(WFS_CACHE_KEY)
        LOGGER.debug(f"Fetched {G_PARAM_DICT=} {G_WFS_DICT=}")
        if G_PARAM_DICT is None or G_WFS_DICT is None:
            LOGGER.debug("Cached PARAMS/WFS empty, trying to recreate")
            G_PARAM_DICT, G_WFS_DICT = create_cacheable_parameters()
            cache.add(PARAM_CACHE_KEY, G_PARAM_DICT)
            cache.add(WFS_CACHE_KEY, G_WFS_DICT)
except OSError as os_exc:
    LOGGER.error(f"Cannot fetch parameters & wfs from cache: {os_exc}")
    G_PARAM_DICT = {}
    G_WFS_DICT = {}
