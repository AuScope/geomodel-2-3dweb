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
import requests

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


def get_input_conv_param_bh(input_file):
    ''' Reads the parameters from conversion input file and stores them in global 'Param' object
    Used for processing borehole data.

    :param input_file: filename of conversion input parameter file
    :return: dictionary object of input parameter file
    '''
    LOGGER.info(f"Opening {input_file}")
    with open(input_file, "r") as file_p:
        try:
            param_dict = json.load(file_p)
        except JSONDecodeError as exc:
            LOGGER.error(f"Cannot read JSON file {input_file}: {str(exc)}")
            sys.exit(1)

    # Check for missing fields
    if 'BoreholeData' not in param_dict:
        LOGGER.error(f"Cannot find 'BoreholeData' key in input file {input_file}")
        sys.exit(1)
    if 'PROVIDER' not in param_dict['BoreholeData']:
        LOGGER.error(f"Cannot find 'PROVIDER' in 'BoreholeData' in input file {input_file}")
        sys.exit(1)
    if 'ModelProperties' not in param_dict:
        LOGGER.error(f"Cannot find 'ModelProperties' key in input file {input_file}")
        sys.exit(1)

    # Check for model's CRS
    param_obj = SimpleNamespace()
    param_obj.MODEL_CRS = param_dict['ModelProperties'].get('crs', None)
    if param_obj.MODEL_CRS is None:
        LOGGER.error(f"Cannot find 'crs' under 'ModelProperties' in input file {input_file}")
        sys.exit(1)
    # If 'MODEL_CRS' is in 'BoreholeData', this overrides the one in 'ModelProperties'
    if 'MODEL_CRS' in param_dict['BoreholeData']:
        param_obj.MODEL_CRS = param_dict['BoreholeData']['MODEL_CRS']

    # Check for model's URL path
    param_obj.modelUrlPath = param_dict['ModelProperties'].get('modelUrlPath', None)
    if param_obj.modelUrlPath is None:
        LOGGER.error(f"'modelUrlPath' not in input file {input_file}")
        sys.exit(1)
    param_obj.MAX_BOREHOLES = MAX_BOREHOLES

    # Check and setup other fields
    for field_name in ['PROVIDER', 'BBOX', 'EXTERNAL_LINK', 'WFS_URL', 'BOREHOLE_CRS', 'WFS_VERSION', 'NVCL_URL']:
        if field_name in param_dict['BoreholeData']:
            setattr(param_obj, field_name, param_dict['BoreholeData'][field_name])

    # Check for missing bounding box fields
    if 'BBOX' in param_dict['BoreholeData'] and ('west' not in param_obj.BBOX or 'south' not in param_obj.BBOX or \
       'east' not in param_obj.BBOX or 'north' not in param_obj.BBOX):
        LOGGER.error(f"Cannot find 'west','south','east','north' in 'BBOX' in {input_file}")
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
    # Open up and parse 'ProviderModelInfo.json' from geomodelportal repo
    result = requests.get("https://raw.githubusercontent.com/AuScope/geomodelportal/dev/ui/src/assets/geomodels/ProviderModelInfo.json")
    if result.status_code != '200':
        LOGGER.error("Cannot read ProviderModelInfo.json file")
        sys.exit(1)
    conf_dict = result.json()
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
        LOGGER.error(f"Cannot open JSON file {file_name}: {oe_exc}")
        sys.exit(1)
    except JSONDecodeError as jd_exc:
        LOGGER.error(f"Cannot parse JSON file {file_name}: {jd_exc}")
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
