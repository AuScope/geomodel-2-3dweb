'''
  A very general collection of functions used for finding files, JSON file creation, JSON file reading, updating dictionaries, detecting small geometric objects etc.
'''
import os
import json
import sys
from json import JSONDecodeError
import logging
from collections import defaultdict

# Set up debugging
logger = logging.getLogger("file_processing")

# Create console handler
local_handler = logging.StreamHandler(sys.stdout)

# Create formatter
local_formatter = logging.Formatter('%(asctime)s -- %(name)s -- %(levelname)s - %(message)s')

# Add formatter to ch
local_handler.setFormatter(local_formatter)

# Add handler to logger
logger.addHandler(local_handler)

#logger.setLevel(logging.DEBUG)


def find(src_dir, dest_dir, ext_list, find_and_process):
    ''' Searches for 3rd party model files in all the subdirectories

    :param src_dir: directory in which to begin the search
    :param dest_dir: directory to store output
    :param ext_list: list of supported file extensions
    :param find_and_process: calls this when found something, fn(src_dir, dest_dir, ext_list)
    :returns: a list of model dict
        (model dict list format: [ { model_attr: { object_name: { 'attr_name': attr_val, ... } } } ] )
        and a list of geographical extents ( [ [min_x, max_x, min_y, max_y], ... ] )
        both can be used to create a config file
    '''
    logger.debug("find(%s, %s, %s)", src_dir, dest_dir, repr(ext_list))
    model_dict_list = []
    geoext_list = []
    walk_obj = os.walk(src_dir)
    for root, subfolders, files in walk_obj:
        done = False
        for file in files:
            name_str, ext_str = os.path.splitext(file)
            for target_ext_str in ext_list:
                if ext_str.lstrip('.').upper() == target_ext_str:
                    p_list, g_list = find_and_process(root, dest_dir, ext_list)
                    model_dict_list += p_list
                    geoext_list.append(g_list)
                    done = True
                    break
            if done:
                break

    reduced_geoext_list = reduce_extents(geoext_list)
    return model_dict_list, reduced_geoext_list


def create_json_config(model_dict_list, output_filename, dest_dir, geo_extent, params):
    ''' Creates a JSON file of GLTF objects to display in 3D

    :param model_dict_list: list of model dicts to write to JSON file
    :param output_filename: name of file containing created config file
    :param dest_dir: destination directory for output file
    :param geo_extent: list of coords defining boundaries of model [min_x, max_x, min_y, max_y]
    :param params: model input parameters, SimpleNamespace() object, keys are: 'name' 'crs' 'init_cam_dist'
                                                                    and optional 'proj4_defn'
    '''
    logger.debug("create_json_config(%s, %s, %s)", repr(model_dict_list), output_filename, repr(geo_extent))
    try:
        fp = open(os.path.join(dest_dir, os.path.basename(output_filename)), "w")
    except Exception as e:
        logger.error("Cannot open file %s %s", output_filename, e)
        return
    # Sort by display name before saving to file, sort by display name, then model URL
    sorted_model_dict_list = sorted(model_dict_list, key=lambda x: (x['display_name'], x['model_url']))
    config_dict = { "properties": { "crs": params.crs, "extent": geo_extent,
                                    "name": params.name,
                                    "init_cam_dist": params.init_cam_dist
                                  },
                    "type": "GeologicalModel",
                    "version": 1.0
                   }
    # Are there any sidebar group labels that we can use?
    # If not, then put them in "Not Grouped"
    if hasattr(params, 'grp_struct_dict'):
        config_dict['groups'] = defaultdict(list)
        for model in sorted_model_dict_list:
            model_file = model['model_url']
            if model_file in params.grp_struct_dict:
                group_name = params.grp_struct_dict[model_file][0]
                config_dict["groups"][group_name].append(model)
            else:
                config_dict["groups"]["Not Grouped"].append(model)

    # Is there a proj4 definition?
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
        logger.error("Cannot open JSON file %s %s", file_name, e)
        sys.exit(1)
    try:
        json_dict = json.load(fp)
    except JSONDecodeError as e:
        json_dict = {}
        logger.error("Cannot read JSON file %s %s", file_name, e)
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
        logger.error("Cannot open file %s %s", output_filename, e)
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
        from makeBoreholes import get_boreholes
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


def add_config2popup(gs_dict, label_str, popup_dict, file_name, file_ext='.gltf', position=[0.0, 0.0, 0.0]):
    ''' Adds more config information to popup dictionary

    :param gs_dict: group structure dictionary (group struct dict format:
        { filename: ( group_name, { insert_key1: val, insert_key2: val } } )
    :param label_str: string to use as a display name for this part of the
        model, if none available in group struct dict
    :param popup_dict: information to display in popup window
        ( popup dict format: { object_name: { 'attr_name': attr_val, ... } } )
    :param file_name:  file and path (without extension) of model part source file
    :param file_ext: optional file extension of 'file_name', defaults to '.gltf'
    :param position: optional [x,y,z] position of model part
    :returns: a dict of model configuration info, which includes the popup dict
    '''
    logger.debug("add_config2popup(%s, %s, %s)", label_str, file_name, file_ext)
    np_filename = os.path.basename(file_name)
    modelconf_dict = {}
    modelconf_dict['popups'] = popup_dict
    if file_ext.upper()==".PNG":
        modelconf_dict['type'] = 'ImagePlane'
        modelconf_dict['position'] = position;
    else:
        modelconf_dict['type'] = 'GLTFObject'
    model_url = np_filename + file_ext
    modelconf_dict['model_url'] = model_url

    add_inserts(gs_dict, model_url, modelconf_dict, label_str.replace('_', ' '))

    modelconf_dict['include'] = True
    modelconf_dict['displayed'] = True
    return modelconf_dict


def add_inserts(gs_dict, model_part_key, modelconf_dict, alt_name):
    ''' Sets the 'display_name' and other inserts from the group structure dictionary

    :param gs_dict: group structure dictionary (group struct dict format: \
    { filename: ( group_name, { insert_key1: val, insert_key2: val } } ))
    :param model_part_key: model part key in 'gs_dict'
    :param modelconf_dict: dictionary of model information
    :param alt_name: alternative 'display_name' when not supplied in 'gs_dict'
    '''
    # Include inserts from group struct dict
    if model_part_key in gs_dict and len(gs_dict[model_part_key]) > 1:
        for ins_k, ins_v in gs_dict[model_part_key][1].items():
            modelconf_dict[ins_k] = ins_v
                 
    # If display name not in group structure dict, use alt name string
    if 'display_name' not in modelconf_dict:
        modelconf_dict['display_name'] = alt_name


def add_vol_config(gs_dict, geom_obj, style_obj, meta_obj):
    ''' Create a dictionary containing volume configuration data 

    :param gs_dict: group structure dictionary (group struct dict format: \
    { filename: ( group_name, { insert_key1: val, insert_key2: val } } ))
    :param geom_obj: MODEL_GEOMETRIES object
    :param style_obj: STYLE object
    :param meta_obj: METADATA object
    :returns: a dict of volume config data
    '''
    model_url = os.path.basename(meta_obj.src_filename)+'.gz'
    modelconf_dict = { 'model_url': model_url, 'type': '3DVolume', 'include': True, 'displayed': False }
    add_inserts(gs_dict, model_url, modelconf_dict, meta_obj.name)
    modelconf_dict['volumeData'] = { 'dataType': geom_obj.vol_data_type, 'dataDims': geom_obj.vol_sz,
                              'origin': geom_obj.vol_origin, 'size': geom_obj.get_vol_side_lengths(),
                              'maxVal': geom_obj.get_max_data(), 'minVal': geom_obj.get_min_data(),
                              'rotation': geom_obj.get_rotation()  }
    if len(style_obj.get_colour_table()) > 0:
        modelconf_dict['volumeData']['colourLookup'] = style_obj.get_colour_table()
    if len(style_obj.get_label_table()) > 0:
        modelconf_dict['volumeData']['labelLookup'] = style_obj.get_label_table()
    return modelconf_dict
    
     
def is_only_small(gsm_list):
    ''' Returns True if this list of geometries contains only lines and points
    :param gsm_list: list of (MODEL_GEOMETRIES, STYLE, METADATA) objects
    :returns: True if we think this is a small model that can fit in one collada file
    '''
    small = True
    for geom_obj, style_obj, meta_obj in gsm_list:
        if not geom_obj.is_point() and not geom_obj.is_line():
            small = False
            break
    return small



