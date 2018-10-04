import os
import json
import sys
from json import JSONDecodeError
import logging

# Set up debugging
logger = logging.getLogger(__name__)




def find(src_dir, ext_list, find_and_process):
    ''' Searches for 3rd party model files in all the subdirectories

    :param src_dir: directory in which to begin the search
    :param ext_list: list of supported file extensions
    :param find_and_process: calls this when found something, fn(src_dir, ext_list)
    :returns: a list of model dict
        (model dict list format: [ { model_attr: { object_name: { 'attr_name': attr_val, ... } } } ] )
        and a list of geographical extents ( [ [min_x, max_x, min_y, max_y], ... ] )
        both can be used to create a config file
    '''
    logger.debug("find(%s, %s)", src_dir, repr(ext_list))
    model_dict_list = []
    geoext_list = []
    walk_obj = os.walk(src_dir)
    for root, subfolders, files in walk_obj:
        done = False
        for file in files:
            name_str, ext_str = os.path.splitext(file)
            for target_ext_str in ext_list:
                if ext_str.lstrip('.').upper() == target_ext_str:
                    p_list, g_list = find_and_process(root, ext_list)
                    model_dict_list += p_list
                    geoext_list.append(g_list)
                    done = True
                    break
            if done:
                break

    reduced_geoext_list = reduce_extents(geoext_list)
    return model_dict_list, reduced_geoext_list


def create_json_config(model_dict_list, output_filename, geo_extent, params):
    ''' Creates a JSON file of GLTF objects to display in 3D

    :param model_dict_list: list of model dicts to write to JSON file
    :param output_filename: name of file containing created config file
    :param geo_extent: list of coords defining boundaries of model [min_x, max_x, min_y, max_y]
    :param params: model input parameters, SimpleNamespace() object, keys are: 'name' 'crs' 'init_cam_dist'
                                                                    and optional 'proj4_defn'
    '''
    logger.debug("create_json_config(%s, %s)",  output_filename, repr(geo_extent))
    try:
        fp = open(output_filename, "w")
    except Exception as e:
        logger.error("ERROR - cannot open file %s %s", output_filename, e)
        return
    # Sort by display name before saving to file
    sorted_model_dict_list = sorted(model_dict_list, key=lambda x: x['display_name'])
    config_dict = { "properties": { "crs": params.crs, "extent": geo_extent,
                                    "name": params.name,
                                    "init_cam_dist": params.init_cam_dist
                                  },
                    "type": "GeologicalModel",
                    "version": 1.0,
                    "groups": {"Group Name": sorted_model_dict_list }
                   }
    if hasattr(params, 'proj4_defn'):
        config_dict["properties"]["proj4_defn"] = params.proj4_defn
    json.dump(config_dict, fp, indent=4, sort_keys=True)
    fp.close()

def read_json_file(file_name):
    ''' Reads a JSON file and returns the contents

    :param file_name: file name of JSON file
    '''
    try:
        fp = open(file_name, "r")
    except Exception as e:
        logger.error("ERROR - Cannot open JSON file %s %s", file_name, e)
        sys.exit(1)
    try:
        json_dict = json.load(fp)
    except JSONDecodeError as e:
        json_dict = {}
        logger.error("ERROR - cannot read JSON file %s %s", file_name, e)
        sys.exit(1)
    fp.close()
    return json_dict


def update_json_config(model_dict_list, template_filename, output_filename, borehole_outdir=""):
    ''' Updates a JSON file of GLTF objects to display in 3D

    :param model_dict_list: list of model dicts to write to JSON file
    :param template_filename: name of file which will be used as input for the update
    :param output_filename: name of updated config file
    :param borehole_outdir: optional name of diectory in which to save borehole GLTF files
    '''
    logger.debug("update_json_config(%s, %s, %s)", template_filename, output_filename, borehole_outdir)
    try:
        fp = open(output_filename, "w")
    except Exception as e:
        logger.error("ERROR - cannot open file %s %s", output_filename, e)
        return
    config_dict = read_json_file(template_filename)
    if config_dict=={}:
        config_dict['groups'] = {}
    groups_obj = config_dict['groups']
    for group_name, part_list in groups_obj.items():
        for part in part_list:
            for model_dict in model_dict_list:
                if part['model_url'] == model_dict['model_url']:
                    part['popups'] = model_dict['popups']
                    for label, p_dict in part['popups'].items():
                        p_dict['title'] = group_name + '-' + part['display_name']
                    break
    if borehole_outdir != "":
        config_dict['groups']['Boreholes'], flag = get_boreholes(borehole_outdir)
    json.dump(config_dict, fp, indent=4, sort_keys=True)
    fp.close()


def reduce_extents(extent_list):
    ''' Reduces a list of extents to just one extent

    :param extent_list: list of geographical extents [ [min_x, max_x, min_y, max_y], ... ]
    '''
    logger.debug("reduce_extents()")
    # If only a single extent and not in a list, then return
    if len(extent_list)==0 or type(extent_list[0]) is float:
        return extent_list

    out_extent = [sys.float_info.max, -sys.float_info.max, sys.float_info.max, -sys.float_info.max]
    for extent in extent_list:
        if len(extent) < 4:
            continue
        if extent[0] < out_extent[0]:
            out_extent[0] = extent[0]
        if extent[1] > out_extent[1]:
            out_extent[1] = extent[1]
        if extent[2] < out_extent[2]:
            out_extent[2] = extent[2]
        if extent[3] > out_extent[3]:
            out_extent[3] = extent[3]
    return out_extent


def add_info2popup(label_str, popup_dict, fileName, file_ext='.gltf', position=[0.0, 0.0, 0.0]):
    ''' Adds more information to popup dictionary

    :param label_str: string to use as a display name for this part of the model
    :param popup_dict: information to display in popup window
            ( popup dict format: { object_name: { 'attr_name': attr_val, ... } } )
    :param fileName:  file and path without extension of source file
    :returns: a dict of model info, which includes the popup dict
    '''
    logger.debug("add_info2popup(%s, %s, %s)", label_str, fileName, file_ext)
    np_filename = os.path.basename(fileName)
    j_dict = {}
    j_dict['popups'] = popup_dict
    if file_ext.upper()==".PNG":
        j_dict['type'] = 'ImagePlane'
        j_dict['position'] = position;
    else:
        j_dict['type'] = 'GLTFObject'
    j_dict['model_url'] = np_filename + file_ext
    j_dict['display_name'] = label_str.replace('_',' ')
    j_dict['include'] = True
    j_dict['displayed'] = True
    return j_dict


