''' A rough implementation of a subset of the 3DPS standard V1.0
 (http://docs.opengeospatial.org/is/15-001r4/15-001r4.html)
 and WFS v2.0 standard (http://www.opengeospatial.org/standards/wfs)

 Currently this is used to display boreholes in the geomodels website.
 In future, it will be expanded to other objects, add in a database
 and put in a more structured and secure framework

 To get information upon double click on object:
 http://localhost:4200/api/NorthGawler?service=3DPS&version=1.0&request=GetFeatureInfoByObjectId&objectId=EWHDDH01_185_0&layers=boreholes&format=application%2Fjson

 To get list of borehole ids:
 http://localhost:4200/api/NorthGawler?service=WFS&version=2.0&request=GetPropertyValue&exceptions=application%2Fjson&outputFormat=application%2Fjson&typeName=boreholes&valueReference=borehole:id

 To get borehole object after scene is loaded:
 http://localhost:4200/api/NorthGawler?service=3DPS&version=1.0&request=GetResourceById&resourceId=228563&outputFormat=model%2Fgltf%2Bjson%3Bcharset%3DUTF-8
'''

import sys, os
import ctypes
import json
from json import JSONDecodeError
import urllib
import logging
from owslib.feature.wfs110 import WebFeatureService_1_1_0
from owslib.util import ServiceException
from diskcache import Cache, Timeout
import pyassimp
from types import SimpleNamespace
import inspect
from urllib.parse import urlparse

from lib.file_processing import get_json_input_param
from lib.exports.bh_make import get_blob_boreholes
from lib.imports.gocad.gocad_importer import GocadImporter
from lib.file_processing import read_json_file, find_gltf
from lib.db.db_tables import QueryDB, QUERY_DB_FILE
from lib.exports.assimp_kit import AssimpKit

from nvcl_kit.reader import NVCLReader

from typing import Optional
from fastapi import FastAPI


app = FastAPI()
''' Set up web FastAPI interface
'''

DEBUG_LVL = logging.ERROR
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

MAX_BOREHOLES = 9999
''' Maximum number of boreholes processed
'''

WFS_TIMEOUT = 6000
''' Timeout for querying WFS services (seconds)
'''

LAYER_NAME = 'boreholes'
''' Name of our 3DPS layer
'''

GLTF_REQ_NAME = '$blobfile.bin'
''' Name of the binary file holding GLTF data
'''

G_PARAM_DICT = {}
''' Stores the models' conversion parameters, key: model name
'''

G_WFS_DICT = {}
''' Stores owslib WebFeatureService objects, key: model name
'''



def create_borehole_dict_list(model, param_dict, wfs_dict):
    '''
    Call upon network services to create dictionary and a list of boreholes for a model

    :param model: name of model, string
    :param param_dict: parameter dictionary
    :param wfs_dict: dictionary of WFS services
    :returns: borehole_dict, response_list
    '''
    # Concatenate response
    response_list = []
    if model not in wfs_dict or model not in param_dict:
        LOGGER.warning("model %s not in wfs_dict or param_dict", model)
        return {}, []
    param = SimpleNamespace()
    param.MAX_BOREHOLES = MAX_BOREHOLES
    param.NVCL_URL = param_dict[model].NVCL_URL
    param.WFS_URL = param_dict[model].WFS_URL
    if hasattr(param_dict[model], 'BOREHOLE_CRS'):
        param.BOREHOLE_CRS = param_dict[model].BOREHOLE_CRS
    if hasattr(param_dict[model], 'BBOX'):
        param.BOREHOLE_CRS = param_dict[model].BBOX
    reader = NVCLReader(param_dict[model], wfs=wfs_dict[model])
    borehole_list = reader.get_boreholes_list()
    result_dict = {}
    for borehole_dict in borehole_list:
        borehole_id = borehole_dict['nvcl_id']
        response_list.append({'borehole:id': borehole_id})
        result_dict[borehole_id] = borehole_dict
    return result_dict, response_list



def get_cached_dict_list(model, param_dict, wfs_dict):
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
            if bh_dict is None or bh_list is None:
                bh_dict, bh_list = create_borehole_dict_list(model, param_dict, wfs_dict)
                cache_obj.add(bhd_key, bh_dict)
                cache_obj.add(bhl_key, bh_list)
            return bh_dict, bh_list
    except OSError as os_exc:
        LOGGER.error("Cannot get cached dict list: %s", str(os_exc))
        return (None, 0)
    except Timeout as t_exc:
        LOGGER.error("DB Timeout, cannot get cached dict list: %s", str(t_exc))
        return (None, 0)



def cache_blob(model, blob_id, blob, blob_sz, exp_timeout=None):
    '''
    Cache a GLTF blob and its size

    :param model: name of model, string
    :param blob_id: blob id string, must be unique within each model
    :param blob: binary string
    :param size of blob
    :param exp_timeout cache expiry timeout, float, in seconds
    :returns: True if blob was added to cache, false if it wasn't added
    '''
    try:
        with Cache(CACHE_DIR) as cache_obj:
            blob_key = 'blob|' + model + '|' + blob_id
            return cache_obj.set(blob_key, (blob, blob_sz), expire=exp_timeout)

    except OSError as os_exc:
        LOGGER.error("Cannot cache blob %s", str(os_exc))
        return False
    except Timeout as t_exc:
        LOGGER.error("DB Timeout, cannot get cached dict list: %s", str(t_exc))
        return False



def get_cached_blob(model, blob_id):
    '''
    Get blob from cache

    :param model: name of model, string
    :param blob_id: blob id string, must be unique within each model
    :returns: a GLTF blob (binary string) and its size
    '''
    try:
        with Cache(CACHE_DIR) as cache_obj:
            blob_key = 'blob|' + model + '|' + blob_id
            blob, blob_sz = cache_obj.get(blob_key, (None, 0))
            return blob, blob_sz

    except OSError as os_exc:
        LOGGER.error("Cannot get cached blob %s", str(os_exc))
        return (None, 0)



class MyWebFeatureService(WebFeatureService_1_1_0):
    '''
    I have to override 'WebFeatureService' because a bug in owslib makes 'pickle' unusable
    I have created a pull request https://github.com/geopython/OWSLib/pull/548 to fix bug
    '''
    # pylint: disable=W0613,R0913
    def __new__(cls, url, version, xml, parse_remote_metadata=False, timeout=30, username=None,
                password=None):
        obj = object.__new__(cls)
        return obj

    def __getnewargs__(self):
        return ('', '', None)


def get_cached_parameters():
    '''
    Creates dictionaries to store model parameters and WFS services

    :returns: parameter dict, WFS dict; both keyed on model name string
    '''
    if not os.path.exists(INPUT_DIR):
        LOGGER.error("input dir %s does not exist", INPUT_DIR)
        sys.exit(1)

    # Get all the model names and details from 'ProviderModelInfo.json'
    config_file = os.path.join(INPUT_DIR, 'ProviderModelInfo.json')
    if not os.path.exists(config_file):
        LOGGER.error("config file does not exist %s", config_file)
        sys.exit(1)
    conf_dict = read_json_file(config_file)
    # For each provider
    param_dict = {}
    wfs_dict = {}
    # pylint: disable=W0612
    for prov_name, model_dict in conf_dict.items():
        model_list = model_dict['models']
        # For each model within a provider
        for model_obj in model_list:
            model = model_obj['modelUrlPath']
            file_prefix = model_obj['configFile'][:-5]
            # Open up model's conversion input parameter file
            input_file = os.path.join(INPUT_DIR, file_prefix + 'ConvParam.json')
            if not os.path.exists(input_file):
                continue
            # Create params and WFS service
            param_dict[model] = get_json_input_param(input_file)
            try:
                wfs_dict[model] = MyWebFeatureService(param_dict[model].WFS_URL,
                                                           version=param_dict[model].WFS_VERSION,
                                                           xml=None, timeout=WFS_TIMEOUT)
            except ServiceException as e:
                LOGGER.error("Cannot reach service %s: %s", param_dict[model].WFS_URL, str(e))
    return param_dict, wfs_dict



def make_json_exception_response(version, code, message, locator='noLocator'):
    '''
    Write out a json error response

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
    # Open up query database
    db_path = os.path.join(DATA_DIR, QUERY_DB_FILE)
    qdb = QueryDB(create=False, db_name=db_path)
    err_msg = qdb.get_error()
    if err_msg != '':
        LOGGER.error('Could not open query db %s: %s', db_path, err_msg)
        return make_str_response(start_response, ' ')
    LOGGER.debug('querying db: %s %s', obj_id, model)
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
    LOGGER.debug('make_getresourcebyid_response(model = %s)', model)

    # Parse outputFormat from query string
    LOGGER.debug('output_format = %s', output_format)
    if not output_format:
        return make_json_exception_response(version, 'MissingParameterValue', 'missing outputFormat parameter')
    if output_format != 'model/gltf+json;charset=UTF-8':
        resp_msg = 'incorrect outputFormat, try "model/gltf+json;charset=UTF-8"'
        return make_json_exception_response(get_val('version', url_kvp),
                                            'InvalidParameterValue', resp_msg)

    # Parse resourceId from query string
    LOGGER.debug('resourceid = %s', res_id)
    if not res_id:
        return make_json_exception_response(version, 'MissingParameterValue', 'missing resourceId parameter')

    # Get borehole dictionary for this model
    # pylint: disable=W0612
    model_bh_dict, model_bh_list = get_cached_dict_list(model, param_dict, wfs_dict)
    LOGGER.debug('model_bh_dict = %s', repr(model_bh_dict))
    borehole_dict = model_bh_dict.get(res_id, None)
    if borehole_dict is not None:
        borehole_id = borehole_dict['nvcl_id']

        # Get blob from cache
        blob = get_blob_boreholes(borehole_dict, param_dict[model])
        # Some boreholes do not have the requested metric
        if blob is not None:
            return send_blob(model, res_id, blob)
        LOGGER.debug('Empty GLTF blob')
    else:
        LOGGER.debug('Resource not found in borehole dict')

    return make_str_response('{}')



def send_blob(model, blob_id, blob, exp_timeout=None):
    ''' Returns a blob in response

    :param model: name of model (string)
    :param blob_id: unique id string for blob, used for caching
    :param blob: blob object
    :param exp_timeout: cache expiry timeout, float, in seconds
    :returns: a binary file response
    '''
    LOGGER.debug('got blob %s', str(blob))
    gltf_bytes = b''
    # There are 2 files in the blob, a GLTF file and a .bin file
    # pylint: disable=W0612
    for idx in range(2):
        LOGGER.debug('blob.contents.name.data = %s', repr(blob.contents.name.data))
        LOGGER.debug('blob.contents.size = %s', repr(blob.contents.size))
        LOGGER.debug('blob.contents.data = %s', repr(blob.contents.data))
        # Look for the GLTF file
        if not blob.contents.name.data:
            # Convert to byte array
            bcd = ctypes.cast(blob.contents.data, ctypes.POINTER(blob.contents.size \
                                                                 * ctypes.c_char))
            bcd_bytes = b''
            for bitt in bcd.contents:
                bcd_bytes += bitt
            bcd_str = bcd_bytes.decode('utf-8', 'ignore')
            LOGGER.debug('bcd_str = %s', bcd_str[:80])
            try:
                # Convert to json
                gltf_json = json.loads(bcd_str)
                LOGGER.debug('gltf_json = %s', str(gltf_json)[:80])
            except JSONDecodeError as jde_exc:
                LOGGER.debug('JSONDecodeError loads(): %s', str(jde_exc))
            else:
                try:
                    # This modifies the URL of the .bin file associated with the GLTF file
                    # Inserting model name and resource id as a parameter so we can tell
                    # the .bin files apart
                    gltf_json["buffers"][0]["uri"] = model + '/' + \
                        gltf_json["buffers"][0]["uri"] + "?id=" + blob_id

                    # Convert back to bytes and send
                    gltf_str = json.dumps(gltf_json)
                    gltf_bytes = bytes(gltf_str, 'utf-8')
                except JSONDecodeError as jde_exc:
                    LOGGER.debug('JSONDecodeError dumps(): %s', str(jde_exc))

        # Binary file (.bin)
        elif blob.contents.name.data == b'bin':
            # Convert to byte array
            bcd = ctypes.cast(blob.contents.data,
                              ctypes.POINTER(blob.contents.size * ctypes.c_char))
            bcd_bytes = b''
            for bitt in bcd.contents:
                bcd_bytes += bitt
            cache_blob(model, blob_id, bcd_bytes, blob.contents.size, exp_timeout)


        blob = blob.contents.next
    if gltf_bytes == b'':
        LOGGER.debug('GLTF not found in blob')
    else:
        with tempfile.NamedTemporaryFile(mode="w+b", suffix=".gltf", delete=False) as fp:
            fp.write(gltf_bytes)
        return FileResponse(fp.name, media_type="model/gltf+json;charset=UTF-8")

    return make_str_response('{}')


def make_getpropvalue_response(model, version, output_format, type_name, value_ref, param_dict, wfs_dict):
    '''
    Returns a response to a WFS getPropertyValue request, example: \
      https://demo.geo-solutions.it/geoserver/wfs?version=2.0&request=GetPropertyValue& \
        outputFormat=json&exceptions=application/json&typeName=test:Linea_costa&valueReference=id

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
    model_bh_dict, response_list = get_cached_dict_list(model, param_dict, wfs_dict)
    response_json = {'type': 'ValueCollection', 'totalValues': len(response_list), 'values': response_list}
    return response_json


def convert_gocad2gltf(model, id_str, gocad_list):
    '''
    Call the conversion code to convert a GOCAD string to GLTF

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
        assimp_obj = AssimpKit(DEBUG_LVL)
        assimp_obj.start_scene()
        assimp_obj.add_geom(geom_obj, style_obj, metadata_obj)
        blob_obj = assimp_obj.end_scene("")
        return send_blob(model, 'drag_and_drop_'+id_str, blob_obj, 60.0)
    return make_str_response(' ')


def convert_gltf2xxx(start_response, model, filename, format):
    '''
    Call the conversion code to convert GLTF string to a certain format

    :param start_response: function call required to create a response
    :param model: name of model
    :param filename: filename of GLTF file to be converted
    :param format: string indicating what format to convert to, e.g. 'DXF'
    :returns: a JSON response
    '''
    # Use model name and file name to get full GLTF file path
    gltf_path = find_gltf(model, filename)
    if not gltf_path:
        LOGGER.error("Cannot find %s", gltf_path)
        return make_str_response(' ')

    # Load GLTF file
    try:
        assimp_obj = pyassimp.load(gltf_path, 'gltf2')
    except AssimpError as ae:
        LOGGER.error("Cannot load %s:%s", gltf_path, str(ae))
        return make_str_response(' ')

    # Export as whatever format desired
    try:
        blob_obj = pyassimp.export_blob(assimp_obj, format, processing=None)
    except AssimpError as ae:
        LOGGER.error("Cannot export %s:%s", gltf_path, str(ae))
        return make_str_response(start_response, ' ')

    return send_blob(model, 'export_{0}_{1}'.format(model, filename), blob_obj, 60.0)



def process3DPS(model, version, request, format, outputFormat, layers, objectId, resourceId):
    '''
    Process an OCG 3PS request. Roughly trying to conform to 3DPS standard

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

    if request.lower() == 'getfeatureinfobyobjectid':
        return make_getfeatinfobyid_response(model, version, format, layers, objectId)

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

    # GetFeature
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


def processIMPORT(model, id_str):
    '''
    Process a GOCAD to GLTF conversion request

    :param environ: WSGI 'environ' variable
    :param url_kvp: dict of parameters extracted from the incoming URL
    :param model: name of model
    :returns: a JSON response
    '''
    # FIXME: Not sure how to do this in FastAPI
    #resp_lines = environ['wsgi.input'].readlines()
    resp_list = []
    for resp_str in resp_lines:
        resp_list.append(resp_str.decode())
    return convert_gocad2gltf(model, id_str, resp_list)


def processWMS(model, styles, wmsurl):
    '''
    Processes an OCG WMS request by proxying

    :param environ: WSGI 'environ' variable
    :param url_kvp: dict of parameters extracted from the incoming URL
    :returns: a response that can be returned from the 'application()' function
    '''

    wms_dict = urlparse(wmsurl)
    if not checkWMS('wmsurl', wms_url):
        return make_str_response(' ')

    # Only add in WMS parameters if they are legitimate
    for key in wms_dict.keys():
        val = url_kvp[key][0]
        if key not in ['service', 'wmsurl'] and not checkWMS(key, val):
            return make_str_response('{}')

    # Make the WMS request
    req = urllib.request.Request(wms_url)
    with urllib.request.urlopen(req) as resp:
        blob = resp.read()
    blob_sz = len(blob)

    # FIXME: Not sure if this works
    return blob


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
    if lkey == 'layers':
        return any(c in 'abcdefghijklmnopqrstuvwxyz_-' for c in lval)
    if lkey == 'request' and lval.isalpha():
        return True
    if lkey == 'version':
        return any(c in '1234567890.' for c in lval)
    if lkey == 'styles' and lval in ['default', '']:
        return True
    if lkey == 'format' and lval in ['image/png', 'image/jpeg']:
        return True
    if lkey in ['transparent', 'displayoutsidemaxextent'] and lval in ['true','false']:
        return True
    if lkey == 'bbox':
        return any(c in '1234567890,.-' for c in lval)
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
    print("model, service, version, request, outputFormat, format, resourceId, layers, objectId, exceptions,  typeName, valueReference")
    print(model, service, version, request, outputFormat, format, resourceId, layers, objectId, exceptions,  typeName, valueReference)
    if service == 'WFS':
        return processWFS(model, version, request, outputFormat, exceptions, typeName, valueReference)
    elif service == '3DPS':
        return process3DPS(model, version, request, format, outputFormat, layers, objectId, resourceId)

    return "Unknown service name, should be one of: 'WFS', '3DPS'"


# WMSPROXY
@app.get("/api/{model}/wmsproxy/{styles}")
async def wmsProxy(model: str, styles: str, wmsUrl: str):
    return processWMS(model, styles, wmsUrl)


# Import GOCAD file
@app.get("/api/{model}/import/{id}")
async def importFile(model: str, id: str):
    return processIMPORT(model, id)


# Export DXF file
@app.get("/api/{model}/export/{filename}/{fileformat}")
async def importFile(model: str, filename: str, fmt: str):
    return processEXPORT(model, filename, fmt)


# Request blobfile, second part of 3DPS request
@app.get("/api/{model}/$blobfile.bin/{id}")
async def downloadBlobFile(model: str, id: str):
    return processBLOB(model, id)


'''
INITIALISATION - Executed upon startup only.
Loads all the model parameters and WFS services from cache or creates them
'''
PARAM_CACHE_KEY = 'model_parameters'
WFS_CACHE_KEY = 'wfs_dict'
try:
    with Cache(CACHE_DIR) as cache:
        G_PARAM_DICT = cache.get(PARAM_CACHE_KEY)
        G_WFS_DICT = cache.get(WFS_CACHE_KEY)
        if G_PARAM_DICT is None or G_WFS_DICT is None:
            G_PARAM_DICT, G_WFS_DICT = get_cached_parameters()
            cache.add(PARAM_CACHE_KEY, G_PARAM_DICT)
            cache.add(WFS_CACHE_KEY, G_WFS_DICT)
except OSError as os_exc:
    LOGGER.error("Cannot fetch parameters & wfs from cache: %s", str(os_exc))
