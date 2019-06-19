'''
A rough implementation of a subset of the 3DPS standard V1.0
 (http://docs.opengeospatial.org/is/15-001r4/15-001r4.html)
 and WFS v2.0 standard (http://www.opengeospatial.org/standards/wfs)

 Currently this is used to display boreholes in the geomodels website.
 In future, it will be expanded to other objects

 To get information upon double click on object:
 http://localhost:4200/api/NorthGawler?service=3DPS&version=1.0&request=GetFeatureInfoByObjectId&objectId=EWHDDH01_185_0&layers=boreholes&format=application%2Fjson

 To get list of borehole ids:
 http://localhost:4200/api/NorthGawler?service=WFS&version=2.0&request=GetPropertyValue&exceptions=application%2Fjson&outputFormat=application%2Fjson&typeName=boreholes&valueReference=borehole:id

 To get borehole object after scene is loaded:
 http://localhost:4200/api/NorthGawler?service=3DPS&version=1.0&request=GetResourceById&resourceId=228563&outputFormat=model%2Fgltf%2Bjson%3Bcharset%3DUTF-8
'''

import sys
import os
import ctypes
import json
from json import JSONDecodeError
import urllib
import logging
from owslib.feature.wfs110 import WebFeatureService_1_1_0
from diskcache import Cache, Timeout

from make_boreholes import get_json_input_param, get_blob_boreholes
from lib.imports.gocad.gocad_importer import GocadImporter
from lib.file_processing import read_json_file
from lib.db.db_tables import QueryDB, QUERY_DB_FILE
from lib.exports.assimp_kit import AssimpKit

from lib.nvcl.nvcl_kit import NVCLKit

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


LOCAL_DIR = os.path.dirname(__file__)
DATA_DIR = os.path.join(LOCAL_DIR, 'data')


INPUT_DIR = os.path.join(LOCAL_DIR, 'input')
''' Directory where conversion parameter files are stored, one for each model
'''

CACHE_DIR = os.path.join(DATA_DIR, 'cache')
''' Directory where WFS service information is kept
'''

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



def create_borehole_dict_list(model_name, param_dict, wfs_dict):
    '''
    Call upon network services to create dictionary and a list of boreholes for a model

    :param model_name: name of model, string
    :param param_dict: parameter dictionary
    :param wfs_dict: dictionary of WFS services
    :returns: borehole_dict, response_list
    '''
    # Concatenate response
    response_list = []
    if model_name not in wfs_dict or model_name not in param_dict:
        LOGGER.warning("model_name %s not in wfs_dict or param_dict", model_name)
        return {}, []
    nvcl_kit = NVCLKit(param_dict[model_name], wfs=wfs_dict[model_name])
    borehole_list = nvcl_kit.get_boreholes_list(MAX_BOREHOLES)
    result_dict = {}
    for borehole_dict in borehole_list:
        borehole_id = borehole_dict['nvcl_id']
        response_list.append({'borehole:id': borehole_id})
        result_dict[borehole_id] = borehole_dict
    return result_dict, response_list



def get_cached_dict_list(model_name, param_dict, wfs_dict):
    '''
    Fetches borehole dictionary and response list from cache or creates them if necessary

    :param model_name: name of model, string
    :param param_dict: parameter dictionary
    :param wfs_dict: dictionary of WFS services
    :returns: borehole_dict, response_list
    '''
    try:
        with Cache(CACHE_DIR) as cache_obj:
            bhd_key = 'bh_dict|' + model_name
            bhl_key = 'bh_list|' + model_name
            bh_dict = cache_obj.get(bhd_key)
            bh_list = cache_obj.get(bhl_key)
            if bh_dict is None or bh_list is None:
                bh_dict, bh_list = create_borehole_dict_list(model_name, param_dict, wfs_dict)
                cache_obj.add(bhd_key, bh_dict)
                cache_obj.add(bhl_key, bh_list)
            return bh_dict, bh_list
    except OSError as os_exc:
        LOGGER.error("Cannot get cached dict list: %s", str(os_exc))
        return (None, 0)
    except Timeout as t_exc:
        LOGGER.error("DB Timeout, cannot get cached dict list: %s", str(t_exc))
        return (None, 0)



def cache_blob(model_name, blob_id, blob, blob_sz, exp_timeout=None):
    '''
    Cache a GLTF blob and its size
    :param model_name: name of model, string
    :param blob_id: blob id string, must be unique within each model
    :param blob: binary string
    :param size of blob
    :param exp_timeout cache expiry timeout, float, in seconds
    :returns: True if blob was added to cache, false if it wasn't added
    '''
    try:
        with Cache(CACHE_DIR) as cache_obj:
            blob_key = 'blob|' + model_name + '|' + blob_id
            return cache_obj.set(blob_key, (blob, blob_sz), expire=exp_timeout)

    except OSError as os_exc:
        LOGGER.error("Cannot cache blob %s", str(os_exc))
        return False
    except Timeout as t_exc:
        LOGGER.error("DB Timeout, cannot get cached dict list: %s", str(t_exc))
        return False



def get_cached_blob(model_name, blob_id):
    '''
    Get blob from cache

    :param model_name: name of model, string
    :param blob_id: blob id string, must be unique within each model
    :returns: a GLTF blob (binary string) and its size
    '''
    try:
        with Cache(CACHE_DIR) as cache_obj:
            blob_key = 'blob|' + model_name + '|' + blob_id
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
            model_name = model_obj['modelUrlPath']
            file_prefix = model_obj['configFile'][:-5]
            # Open up model's conversion input parameter file
            input_file = os.path.join(INPUT_DIR, file_prefix + 'ConvParam.json')
            if not os.path.exists(input_file):
                continue
            # Create params and WFS service
            param_dict[model_name] = get_json_input_param(os.path.join(INPUT_DIR, input_file))
            wfs_dict[model_name] = MyWebFeatureService(param_dict[model_name].WFS_URL,
                                                       version=param_dict[model_name].WFS_VERSION,
                                                       xml=None, timeout=WFS_TIMEOUT)
    return param_dict, wfs_dict



def make_str_response(start_response, message):
    '''
    Create and initialise an HTTP response with a string message

    :param start_response :callback function for initialising HTTP response
    :param message:  string message
    :returns: byte array HTTP response
    '''
    msg_bytes = bytes(message, 'utf-8')
    response_headers = [('Content-type', 'text/plain'), ('Content-Length', str(len(msg_bytes))),
                        ('Connection', 'keep-alive')]
    start_response('200 OK', response_headers)
    return [msg_bytes]



def make_json_exception_response(start_response, version, code, message, locator='noLocator'):
    '''
    Write out a json error response

    :param start_response: callback function for initialising HTTP response
    :param version: version string
    :param code: error code string, can be 'OperationNotSupported', 'MissingParameterValue',
                                           'OperationProcessingFailed'
    :param message: text message explaining error in more detail
    :param locator:  optional string indicating what part of input caused the problem.
                     This must be checked for XSS or SQL injection exploits
    :returns: byte array HTTP response
    '''
    msg_json = {"version": version, "exceptions": [{"code": code, "locator": locator,
                                                    "text": message}]}
    msg_str = json.dumps(msg_json)
    msg_bytes = bytes(msg_str, 'utf-8')
    response_headers = [('Content-type', 'application/json'),
                        ('Content-Length', str(len(msg_bytes))), ('Connection', 'keep-alive')]
    start_response('200 OK', response_headers)
    return [msg_bytes]



def get_val(key, arr_dict, none_val=''):
    '''
    Try to find a value in a dict using a key

    :param key: the key to look for
    :param arr_dict: dictionary to search in, must have format { 'key' : [val] ... }
    :param none_val: optional value used when key is not found, default is ''
    :returns: string value from dict or none_val (if not found)
    '''
    return arr_dict.get(key, [none_val])[0]



def make_getcap_response(start_response, model_name, param_dict):
    '''
    Create and initialise the 3DPS 'GetCapabilities' response

    :param start_response: callback function for initialising HTTP response
    :returns: byte array HTTP response
    '''
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
  <Contents>""".format(model_name)
    response += """       <Layer>
      <ows:Identifier>{0}</ows:Identifier>
      <AvailableCRS>{1}</AvailableCRS>
    </Layer>""".format(LAYER_NAME, param_dict[model_name].MODEL_CRS)

    response += "</Contents>\n</Capabilities>"

    msg_bytes = bytes(response, 'utf-8')
    response_headers = [('Content-type', 'text/xml'), ('Content-Length', str(len(msg_bytes))),
                        ('Connection', 'keep-alive')]
    start_response('200 OK', response_headers)
    return [msg_bytes]



def make_getfeatinfobyid_response(start_response, url_kvp, model_name):
    '''
    Create and initialise the 3DPS 'GetFeatureInfoByObjectId' response

    :param start_response: callback function for initialising HTTP response
    :param url_kvp: key-value pair dictionary of URL parameters, format: 'key':['val1', 'val2' .. ]
    :returns: byte array HTTP response in JSON format
    '''
    LOGGER.debug('make_getfeatinfobyid_response() url_kvp = %s', repr(url_kvp))
    # Parse id from query string
    obj_id = get_val('objectid', url_kvp)
    if obj_id == '':
        return make_json_exception_response(start_response, get_val('version', url_kvp),
                                            'MissingParameterValue', 'missing objectId parameter')

    # Parse format from query string
    query_format = get_val('format', url_kvp)
    if query_format == '':
        return make_json_exception_response(start_response, get_val('version', url_kvp),
                                            'MissingParameterValue', 'missing format parameter')
    if query_format != 'application/json':
        return make_json_exception_response(start_response, get_val('version', url_kvp),
                                            'InvalidParameterValue',
                                            'incorrect format, try "application/json"')

    # Parse layers from query string
    layer_names = get_val('layers', url_kvp)
    if layer_names == '':
        return make_json_exception_response(start_response, get_val('version', url_kvp),
                                            'MissingParameterValue', 'missing format parameter')
    if layer_names != LAYER_NAME:
        return make_json_exception_response(start_response, get_val('version', url_kvp),
                                            'InvalidParameterValue',
                                            'incorrect layers, try "'+ LAYER_NAME + '"')

    if obj_id != '':
        # Query database
        # Open up query database
        db_path = os.path.join(DATA_DIR, QUERY_DB_FILE)
        qdb = QueryDB(create=False, db_name=db_path)
        err_msg = qdb.get_error()
        if err_msg != '':
            LOGGER.error('Could not open query db %s: %s', db_path, err_msg)
            return make_str_response(start_response, ' ')
        LOGGER.debug('querying db: %s %s', obj_id, model_name)
        o_k, result = qdb.query(obj_id, model_name)
        if o_k:
            # pylint: disable=W0612
            label, out_model_name, segment_str, part_str, model_str, user_str = result
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
            resp_str = json.dumps(resp_dict)
            resp_bytes = bytes(resp_str, 'utf-8')
        else:
            LOGGER.error('Could not query db: %s', str(result))
            return make_str_response(start_response, ' ')

    response_headers = [('Content-type', 'application/json'),
                        ('Content-Length', str(len(resp_bytes))), ('Connection', 'keep-alive')]
    start_response('200 OK', response_headers)
    return [resp_bytes]




def make_getresourcebyid_response(start_response, url_kvp, model_name, param_dict, wfs_dict):
    '''
    Create and initialise the 3DPS 'GetResourceById' response

    :param start_response: callback function for initialising HTTP response
    :param url_kvp: key-value pair dictionary of URL parameters, format: 'key':['val1', 'val2' ..]
    :param model_name: name of model (string)
    :param param_dict: parameter dictionary
    :param wfs_dict: dictionary of WFS services
    :returns: byte array HTTP response
    '''
    # This sends back the first part of the GLTF object - the GLTF file for the
    # resource id specified
    LOGGER.debug('make_getresourcebyid_response(model_name = %s)', model_name)

    # Parse outputFormat from query string
    output_format = get_val('outputformat', url_kvp)
    LOGGER.debug('output_format = %s', output_format)
    if output_format == '':
        return make_json_exception_response(start_response, get_val('version', url_kvp),
                                            'MissingParameterValue',
                                            'missing outputFormat parameter')
    if output_format != 'model/gltf+json;charset=UTF-8':
        resp_msg = 'incorrect outputFormat, try "model/gltf+json;charset=UTF-8"'
        return make_json_exception_response(start_response, get_val('version', url_kvp),
                                            'InvalidParameterValue', resp_msg)

    # Parse resourceId from query string
    res_id = get_val('resourceid', url_kvp)
    LOGGER.debug('resourceid = %s', res_id)
    if res_id == '':
        return make_json_exception_response(start_response, get_val('version', url_kvp),
                                            'MissingParameterValue',
                                            'missing resourceId parameter')

    # Get borehole dictionary for this model
    # pylint: disable=W0612
    model_bh_dict, model_bh_list = get_cached_dict_list(model_name, param_dict, wfs_dict)
    LOGGER.debug('model_bh_dict = %s', repr(model_bh_dict))
    borehole_dict = model_bh_dict.get(res_id, None)
    if borehole_dict is not None:
        borehole_id = borehole_dict['nvcl_id']

        # Get blob from cache
        blob = get_blob_boreholes(borehole_dict, param_dict[model_name])
        # Some boreholes do not have the requested metric
        if blob is not None:
            return send_blob(start_response, model_name, res_id, blob)
        LOGGER.debug('Empty GLTF blob')
    else:
        LOGGER.debug('Resource not found in borehole dict')

    return make_str_response(start_response, '{}')



def send_blob(start_response, model_name, blob_id, blob, exp_timeout=None):
    ''' Returns a blob in response

    :param start_response: callback function for initialising HTTP response
    :param model_name: name of model (string)
    :param blob_id: unique id string for blob, used for caching
    :param blob: blob object
    :param exp_timeout: cache expiry timeout, float, in seconds
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
                    gltf_json["buffers"][0]["uri"] = model_name + '/' + \
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
            cache_blob(model_name, blob_id, bcd_bytes, blob.contents.size, exp_timeout)


        blob = blob.contents.next
    if gltf_bytes == b'':
        LOGGER.debug('GLTF not found in blob')
    else:
        response_headers = [('Content-type', 'model/gltf+json;charset=UTF-8'),
                            ('Content-Length', str(len(gltf_bytes))),
                            ('Connection', 'keep-alive')]
        start_response('200 OK', response_headers)
        return [gltf_bytes]

    return make_str_response(start_response, '{}')


def make_getpropvalue_response(start_response, url_kvp, model_name, param_dict, wfs_dict):
    '''
    Returns a response to a WFS getPropertyValue request, example:
      https://demo.geo-solutions.it/geoserver/wfs?version=2.0&request=GetPropertyValue&
        outputFormat=json&exceptions=application/json&typeName=test:Linea_costa&valueReference=id

    :param start_response: callback function for initialising HTTP response
    :param url_kvp key-value pair dictionary of URL parameters, format: 'key': ['val1','val2' ..]
    :returns: byte array HTTP response
    '''

    # Parse outputFormat from query string
    output_format = get_val('outputformat', url_kvp)
    if output_format == '':
        return make_json_exception_response(start_response, get_val('version', url_kvp),
                                            'MissingParameterValue',
                                            'missing outputFormat parameter')
    if output_format != 'application/json':
        return make_json_exception_response(start_response, get_val('version', url_kvp),
                                            'OperationProcessingFailed',
                                            'incorrect outputFormat, try "application/json"')

    # Parse typeName from query string
    type_name = get_val('typename', url_kvp)
    if type_name == '':
        return make_json_exception_response(start_response, get_val('version', url_kvp),
                                            'MissingParameterValue',
                                            'missing typeName parameter')
    if type_name != 'boreholes':
        return make_json_exception_response(start_response, get_val('version', url_kvp),
                                            'OperationProcessingFailed',
                                            'incorrect typeName, try "boreholes"')

    # Parse valueReference from query string
    value_ref = get_val('valuereference', url_kvp)
    if value_ref == '':
        return make_json_exception_response(start_response, get_val('version', url_kvp),
                                            'MissingParameterValue',
                                            'missing valueReference parameter')
    if value_ref != 'borehole:id':
        return make_json_exception_response(start_response, get_val('version', url_kvp),
                                            'OperationProcessingFailed',
                                            'incorrect valueReference, try "borehole:id"')

    # Fetch list of borehole ids
    # pylint: disable=W0612
    model_bh_dict, response_list = get_cached_dict_list(model_name, param_dict, wfs_dict)
    response_str = json.dumps({'type': 'ValueCollection', 'totalValues': len(response_list),
                               'values': response_list})
    response_bytes = bytes(response_str, 'utf-8')
    response_headers = [('Content-type', 'application/json'),
                        ('Content-Length', str(len(response_bytes))),
                        ('Connection', 'keep-alive')]
    start_response('200 OK', response_headers)
    return [response_bytes]


def convert(start_response, model_name, id_str, gocad_list):
    '''
    Call the conversion code to convert a GOCAD string to GLTF

    :param gocad_list: GOCAD file lines as a list of strings
    '''
    base_xyz = (0.0, 0.0, 0.0)
    gocad_obj = GocadImporter(DEBUG_LVL, base_xyz=base_xyz,
                              nondefault_coords=NONDEF_COORDS)
    # First convert GOCAD to GSM
    is_ok, gsm_list = gocad_obj.process_gocad('drag_and_drop', 'drag_and_drop.ts', gocad_list)
    # LOGGER.error("gsm_list = %s", repr(gsm_list))
    if is_ok and gsm_list:
        # Then, output GSM as GLTF ...
        gsm_obj = gsm_list[0]
        #LOGGER.error("gsm_obj = %s", repr(gsm_obj))
        geom_obj, style_obj, metadata_obj = gsm_obj
        assimp_obj = AssimpKit(DEBUG_LVL)
        assimp_obj.start_scene()
        assimp_obj.add_geom(geom_obj, style_obj, metadata_obj)
        blob_obj = assimp_obj.end_scene("")
        return send_blob(start_response, model_name, 'drag_and_drop_'+id_str, blob_obj, 60.0)
    return make_str_response(start_response, ' ')


'''
' INITIALISATION - Executed upon startup only.
' Loads all the model parameters and WFS services from cache or creates them
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


def application(environ, start_response):
    '''
    MAIN - This is called whenever an HTTP request arrives
    '''
    doc_root = os.path.normcase(environ['DOCUMENT_ROOT'])
    sys.path.append(os.path.join(doc_root, 'lib'))
    path_bits = environ['PATH_INFO'].split('/')

    # Exit if path is not correct
    if len(path_bits) < 2 or path_bits[0] != '':
        return make_str_response(start_response, ' ')

    # Remove '' from path
    path_bits.pop(0)

    # If there is 'api' remove it, so to deal with both '/api/<model_name>?service=blah'
    # and '/<model_name?service=blah'
    if path_bits[0] == 'api':
        path_bits.pop(0)

    # Model names are always alphabetic
    if not path_bits or not path_bits[0].isalpha():
        return make_str_response(start_response, ' ')
    model_name = path_bits[0]

    # Expecting a path '/<model_name>?service=<service_name>&param1=val1'
    if len(path_bits) == 1:
        url_params = urllib.parse.parse_qs(environ['QUERY_STRING'])
        # Convert all the URL parameter names to lower case with merging
        url_kvp = {}
        for key, val in url_params.items():
            url_kvp.setdefault(key.lower(), [])
            url_kvp[key.lower()] += val
        service_name = get_val('service', url_kvp)
        request = get_val('request', url_kvp)

        LOGGER.debug('service_name = %s', repr(service_name))
        LOGGER.debug('request = %s', repr(request))

        # Roughly trying to conform to 3DPS standard
        if service_name.lower() == '3dps':
            if request.lower() == 'getcapabilities':
                return make_getcap_response(start_response, model_name, G_PARAM_DICT)

            # Check for version
            version = get_val('version', url_kvp)
            if version == '':
                return make_json_exception_response(start_response, 'Unknown',
                                                    'MissingParameterValue',
                                                    'missing version parameter')
            if version != '1.0':
                return make_json_exception_response(start_response, 'Unknown',
                                                    'OperationProcessingFailed',
                                                    'Incorrect version, try "1.0"')

            # Check request type
            if request.lower() in ['getscene', 'getview', 'getfeatureinfobyray',
                                   'getfeatureinfobyposition']:
                return make_json_exception_response(start_response,
                                                    get_val('version', url_kvp),
                                                    'OperationNotSupported',
                                                    'Request type is not implemented',
                                                    request.lower())

            if request.lower() == 'getfeatureinfobyobjectid':
                return make_getfeatinfobyid_response(start_response, url_kvp, model_name)

            if request.lower() == 'getresourcebyid':
                return make_getresourcebyid_response(start_response, url_kvp, model_name,
                                                     G_PARAM_DICT, G_WFS_DICT)

            # Unknown request
            if request != '':
                return make_json_exception_response(start_response,
                                                    get_val('version', url_kvp),
                                                    'OperationNotSupported',
                                                    'Unknown request type')

            # Missing request
            return make_json_exception_response(start_response,
                                                get_val('version', url_kvp),
                                                'MissingParameterValue',
                                                'Missing request parameter')

        # WFS request
        if service_name.lower() == 'wfs':
            # Check for version 2.0
            version = get_val('version', url_kvp)
            LOGGER.debug('version = %s', version)
            if version == '':
                return make_json_exception_response(start_response, 'Unknown',
                                                    'MissingParameterValue',
                                                    'Missing version parameter')
            if version != '2.0':
                return make_json_exception_response(start_response, 'Unknown',
                                                    'OperationProcessingFailed',
                                                    'Incorrect version, try "2.0"')

            # GetFeature
            if request.lower() == 'getpropertyvalue':
                return make_getpropvalue_response(start_response, url_kvp, model_name,
                                                  G_PARAM_DICT, G_WFS_DICT)
            return make_json_exception_response(start_response, get_val('version', url_kvp),
                                                'OperationNotSupported', 'Unknown request name')

        # Expecting a path '/<model_name>?service=CONVERT&&id=HEX_STRING'
        if service_name.lower() == 'convert':
            id_str = get_val('id', url_kvp)
            resp_lines = environ['wsgi.input'].readlines()
            resp_list = []
            for resp_str in resp_lines:
                resp_list.append(resp_str.decode())
            return convert(start_response, model_name, id_str, resp_list)

        if service_name != '':
            return make_json_exception_response(start_response, get_val('version', url_kvp),
                                                'OperationNotSupported', 'Unknown service name')

        return make_json_exception_response(start_response, get_val('version', url_kvp),
                                            'MissingParameterValue', 'Missing service parameter')


    # This sends back the second part of the GLTF object - the .bin file
    # Format '/<model_name>/$blobfile.bin?id=12345'
    # or '/<model_name>/$blobfile.bin?id=drag_and_drop_01234567890abcde'
    if len(path_bits) == 2 and path_bits[1] == GLTF_REQ_NAME:

        # Get the GLTF binary file associated with each GLTF file
        res_id_arr = urllib.parse.parse_qs(environ['QUERY_STRING']).get('id', [])
        if res_id_arr:
            id_val = res_id_arr[0]
            # Check that the id format is correct
            if (id_val[:14] == 'drag_and_drop_' and id_val[14:].isalnum() and len(id_val) == 30) \
                                                                        or id_val.isnumeric():
                # Get blob from cache
                blob, blob_sz = get_cached_blob(model_name, id_val)
                if blob is not None:
                    response_headers = [('Content-type', 'application/octet-stream'),
                                        ('Content-Length', str(blob_sz)),
                                        ('Connection', 'keep-alive')]
                    start_response('200 OK', response_headers)
                    return [blob]
            LOGGER.warning("Cannot locate blob in cache")
        else:
            LOGGER.warning("Cannot locate id in borehole_dict")

    else:
        LOGGER.debug('Bad URL')

    # Catch-all sends empty response
    return make_str_response(start_response, ' ')
