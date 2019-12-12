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

# Set up debugging
LOGGER = logging.getLogger("file_processing")

# Create console handler
LOCAL_HANDLER = logging.StreamHandler(sys.stdout)

# Create formatter
LOCAL_FORMATTER = logging.Formatter('%(asctime)s -- %(name)s -- %(levelname)s - %(message)s')

# Add formatter to ch
LOCAL_HANDLER.setFormatter(LOCAL_FORMATTER)

# Add handler to LOGGER
LOGGER.addHandler(LOCAL_HANDLER)

#LOGGER.setLevel(logging.DEBUG)


def find(src_dir, dest_dir, fileext_list, find_and_process, config_build_obj):
    ''' Searches for 3rd party model files in all the subdirectories

    :param src_dir: directory in which to begin the search
    :param dest_dir: directory to store output
    :param fileext_list: list of supported file extensions
    :param find_and_process: calls this when found something, fn(src_dir, dest_dir, ext_list)
    :param config_build_obj: ConfigBuilder object
    '''
    LOGGER.debug("find(%s, %s, %s)", src_dir, dest_dir, repr(fileext_list))
    model_dict_list = []
    geoext_list = []
    walk_obj = os.walk(src_dir)
    for root, subfolders, files in walk_obj:
        done = False
        for file in files:
            name_str, fileext_str = os.path.splitext(file)
            for target_fileext_str in fileext_list:
                if fileext_str.lstrip('.').upper() == target_fileext_str:
                    find_and_process(root, dest_dir, fileext_list)
                    done = True
                    break
            if done:
                break


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
