'''
A very general collection of functions used for finding files, JSON file creation,
JSON file reading, updating dictionaries, detecting small geometric objects etc.
'''
import os
import sys
import logging
from collections import defaultdict
import json
from json import JSONDecodeError
from types import SimpleNamespace

# Set up debugging
LOGGER = logging.getLogger(__name__)

# Create console handler
LOCAL_HANDLER = logging.StreamHandler(sys.stdout)

# Create formatter
LOCAL_FORMATTER = logging.Formatter('%(asctime)s -- %(name)s -- %(levelname)s - %(message)s')

# Add formatter to ch
LOCAL_HANDLER.setFormatter(LOCAL_FORMATTER)

# Add handler to LOGGER
LOGGER.addHandler(LOCAL_HANDLER)

#LOGGER.setLevel(logging.DEBUG)

MAX_BOREHOLES = 9999
''' Maximum number of boreholes processed
'''


def get_input_conv_param(input_file):
    ''' Reads the parameters from conversion input file and stores them in global 'Param' object

    :param input_file: filename of input parameter file
    :return: dictionary object of input parameter file
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
    param_obj.modelUrlPath = param_dict['ModelProperties']['modelUrlPath']
    param_obj.MAX_BOREHOLES = MAX_BOREHOLES
    for field_name in ['BBOX', 'EXTERNAL_LINK', 'MODEL_CRS', 'WFS_URL', 'BOREHOLE_CRS',
                       'WFS_VERSION', 'NVCL_URL']:
        # Check for compulsory fields
        if field_name not in param_dict['BoreholeData']:
            if field_name not in ['BBOX', 'EXTERNAL_LINK', 'BOREHOLE_CRS']:
                LOGGER.error("Cannot find '%s' key in input file %s", field_name, input_file)
                sys.exit(1)
        else:
            setattr(param_obj, field_name, param_dict['BoreholeData'][field_name])

    if 'BBOX' in param_dict['BoreholeData'] and ('west' not in param_obj.BBOX or 'south' not in param_obj.BBOX or \
       'east' not in param_obj.BBOX or 'north' not in param_obj.BBOX):
        LOGGER.error("Cannot find 'west','south','east','north' in 'BBOX' in input file %s",
                     input_file)
        sys.exit(1)
    return param_obj

def find_gltf(geomodels_dir, input_dir, target_model_name, gltf_file):
    '''
    Searches for the model's file path in the model's config file

    :param geomodels_dir: dir path where geomodels files are kept
    :param input_dir: dir path where website input config files are kept
    :param target_model_name: name of model we're searching for
    :param gltf_file: GLTF filename
    :returns: model file full path                                                                                               '''
    # Open up and parse 'input/ProviderModelInfo.json'
    config_file = os.path.join(input_dir, 'ProviderModelInfo.json')
    conf_dict = read_json_file(config_file)
    # pylint: disable=W0612
    for prov_name, model_dict in conf_dict.items():
        model_list = model_dict['models']
        # For each model within a provider
        for model_obj in model_list:
            model_name = model_obj['modelUrlPath']
            if model_name == target_model_name:
                model_filepath = os.path.join(geomodels_dir, model_obj['modelDir'], gltf_file)
                if os.path.exists(model_filepath):
                    return model_filepath
    return ''

def read_json_file(file_name):
    ''' Reads a JSON file and returns the contents

    :param file_name: file name of JSON file
    '''
    try:
        with open(file_name, "r") as file_p:
            json_dict = json.load(file_p)
    except OSError as oe_exc:
        LOGGER.error("Cannot open JSON file %s %s", file_name, oe_exc)
        sys.exit(1)
    except JSONDecodeError as jd_exc:
        json_dict = {}
        LOGGER.error("Cannot read JSON file %s %s", file_name, jd_exc)
        sys.exit(1)
    return json_dict

def is_only_small(gsm_list):
    ''' Returns True if this list of geometries contains only lines and points
    :param gsm_list: list of (ModelGeometries, STYLE, METADATA) objects
    :returns: True if we think this is a small model that can fit in one collada file
    '''
    small = True
    for geom_obj, style_obj, meta_obj in gsm_list:
        if not geom_obj.is_point() and not geom_obj.is_line():
            small = False
            break
    return small
