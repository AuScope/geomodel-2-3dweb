#!/usr/bin/env python3
#
# This converts GOCAD to COLLADA and GLTF 
# It accepts many types of GOCAD files (TS, GP, VS, PL, VO) and support colours and 'ZPOSITIVE' flag etc.
# 
#
import sys
import os
import glob
import argparse
import random
import logging
from types import SimpleNamespace

# Add in path to local library files
sys.path.append(os.path.join('..','lib'))

from exports.png_kit import PNG_KIT
from exports.collada_kit import COLLADA_KIT
from imports.gocad.gocad_vessel import GOCAD_VESSEL, extract_from_grp, de_concat
import exports.collada2gltf
from file_processing import find, create_json_config, read_json_file, reduce_extents, add_info2popup

DEBUG_LVL = logging.CRITICAL
''' Initialise debug level to minimal debugging
'''

CONVERT_COLLADA = True
''' Runs the collada2gltf program after creating COLLADA files
'''

GROUP_LIMIT = 8
''' If there are more than GROUP_LIMIT number of GOCAD objects in a group file then use one COLLADA file 
    else put use separate COLLADA files for each object
'''

NONDEF_COORDS = False
''' Will tolerate non default coordinates
'''

# Set up debugging 
logger = logging.getLogger(__name__)

# Input parameters are stored here
Params = SimpleNamespace()

# Coordinate Offsets are stored here, key is filename, value is (x,y,z)
CoordOffset = {}

# Colour table files: key is GOCAD filename, value is CSV colour table filename (without path)
CtFileDict = {}




def find_and_process(src_dir, dest_dir, ext_list):
    ''' Searches for files in local directory and processes them

    :param src_dir: source directory where there are 3rd party model files
    :param dest_dir: destination directory where output is written to
    :param ext_list: list of supported file extensions
    :returns: a list of model dicts
        (model dict list format: [ { model_attr: { object_name: { 'attr_name': attr_val, ... } } } ] )
        and a list of geographical extents [ [min_x, max_x, min_y, max_y], ... ]
        both can be used to create a config file
    '''
    logger.debug("find_and_process(%s, %s )", src_dir, dest_dir)
    ret_list = []
    extent_list = []
    for ext_str in ext_list:
        wildcard_str = os.path.join(src_dir, "*."+ext_str.lower())
        file_list = glob.glob(wildcard_str)
        for filename_str in file_list:
            success, model_dict_list, extent = process(filename_str, dest_dir)
            if success:
                ret_list += model_dict_list
                extent_list.append(extent)

    # Convert all files from COLLADA to GLTF v2
    if CONVERT_COLLADA:
        exports.collada2gltf.convert_dir(dest_dir)
    return ret_list, reduce_extents(extent_list)


def process(filename_str, dest_dir):
    ''' Processes a GOCAD file. This one GOCAD file can contain many parts and produce many output files

    :param filename_str: filename of GOCAD file, including path
    :param dest_dir: destination directory
    :returns: success/failure flag, model dictionary list,
        (model dict list format: [ { model_attr:  { object_name: { 'attr_name': attr_val, ... } } } ] )
        and geographical extent [min_x, max_x, min_y, max_y]
    '''
    global CoordOffset
    global CtFileDict
    logger.info("\nProcessing %s", filename_str)
    # If there is an offset from the input parameter file, then apply it
    base_xyz = (0.0, 0.0, 0.0)
    basefile = os.path.basename(filename_str)
    if basefile in CoordOffset:
        base_xyz = CoordOffset[basefile]
    model_dict_list = []
    popup_dict = {}
    extent_list = []
    file_name, fileExt = os.path.splitext(filename_str)
    out_filename = os.path.join(dest_dir, os.path.basename(file_name))
    ext_str = fileExt.lstrip('.').upper()
    src_dir = os.path.dirname(filename_str)
    ck = COLLADA_KIT(DEBUG_LVL)
    pk = PNG_KIT(DEBUG_LVL)
    # Open GOCAD file and read all its contents, assume it fits in memory
    try:
        fp = open(filename_str,'r')
        whole_file_lines = fp.readlines()
    except Exception as e:
        logger.error("Can't open or read - skipping file %s %s", filename_str, e)
        return False, [], []
    has_result = False

    # VS and VO files usually have lots of data points and thus one COLLADA file for each GOCAD file
    if ext_str in ['VS', 'VO']:
        file_lines_list = de_concat(whole_file_lines)
        for mask_idx, file_lines in enumerate(file_lines_list):
            if len(file_lines_list)>1:
                out_filename = "{0}_{1:d}".format(os.path.join(dest_dir, os.path.basename(file_name)), mask_idx)
            gv = GOCAD_VESSEL(DEBUG_LVL, base_xyz=base_xyz, nondefault_coords=NONDEF_COORDS, ct_file_dict=CtFileDict)

            # Check that conversion worked
            is_ok, gsm_list = gv.process_gocad(src_dir, filename_str, file_lines)
            if not is_ok:
                logger.warning("Could not process %s", filename_str) 
                continue

            # Write out files
            prop_filename = out_filename
            if len(gsm_list) > 1:
               prop_filename += "_0"
            # Loop around when several properties in one GOCAD object
            for prop_idx, (geom_obj, style_obj, meta_obj) in enumerate(gsm_list):
                if prop_idx > 0:
                    prop_filename = "{0}_{1:d}".format(out_filename, prop_idx)
                if ext_str == 'VS':
                    popup_dict = ck.write_collada(geom_obj, style_obj, meta_obj, prop_filename)
                    model_dict_list.append(add_info2popup(meta_obj.name, popup_dict, prop_filename))

                elif ext_str == 'VO':
                    md_list = write_single_volume(ck, pk, geom_obj, style_obj, meta_obj, src_dir, prop_filename, prop_idx)
                    model_dict_list += md_list
                has_result = True
                extent_list.append(geom_obj.get_extent())

    # For triangles, wells and lines, place multiple GOCAD objects in one COLLADA file
    elif ext_str in ['TS','PL', 'WL']:
        file_lines_list = de_concat(whole_file_lines)
        ck.start_collada()
        popup_dict = {}
        for file_lines in file_lines_list:
            gv = GOCAD_VESSEL(DEBUG_LVL, base_xyz=base_xyz, nondefault_coords=NONDEF_COORDS)
            is_ok, gsm_list = gv.process_gocad(src_dir, filename_str, file_lines)
            if not is_ok:
                logger.warning("WARNING - could not process %s", filename_str) 
                continue
            for geom_obj, style_obj, meta_obj in gsm_list:

                # Check that conversion worked and write out files
                if ext_str == 'TS' and len(geom_obj.vrtx_arr) > 0 and len(geom_obj.trgl_arr) > 0 \
                           or (ext_str in ['PL','WL']) and len(geom_obj.vrtx_arr) > 0 and len(geom_obj.seg_arr) > 0:
                    popup_dict.update(ck.add_geom_to_collada(geom_obj, style_obj, meta_obj))
                    extent_list.append(geom_obj.get_extent())
                    has_result = True

        if has_result:
            model_dict_list.append(add_info2popup(os.path.basename(file_name), popup_dict, file_name))
            ck.end_collada(out_filename)
        

    # Process group files, depending on the number of GOCAD objects inside
    elif ext_str == 'GP':
        gsm_list=extract_from_grp(src_dir, filename_str, whole_file_lines, base_xyz, DEBUG_LVL, NONDEF_COORDS, CtFileDict)

        # If there are too many entries in the GP file, then place everything in one COLLADA file
        if len(gsm_list) > GROUP_LIMIT:
            logger.debug("All group objects in one COLLADA file")
            ck.start_collada()
            popup_dict = {}
            for geom_obj, style_obj, meta_obj in gsm_list:
                popup_dict.update(ck.add_geom_to_collada(geom_obj, style_obj, meta_obj))
                extent_list.append(geom_obj.get_extent())
                has_result = True
            if has_result:
                model_dict_list.append(add_info2popup(os.path.basename(file_name), popup_dict, file_name))
                ck.end_collada(out_filename)
 
        # Else place each GOCAD object in its own COLLADA file
        else:
            for file_idx, (geom_obj, style_obj, meta_obj) in enumerate(gsm_list):
                prop_filename = "{0}_{1:d}".format(out_filename, file_idx)
                if geom_obj.is_volume():
                    md_list = write_single_volume(ck, pk, geom_obj, style_obj, meta_obj, src_dir, prop_filename, file_idx)
                    model_dict_list += md_list
                else:
                    p_dict = ck.write_collada(geom_obj, style_obj, meta_obj, prop_filename)
                    model_dict_list.append(add_info2popup(meta_obj.name, p_dict, prop_filename))
                extent_list.append(geom_obj.get_extent())
                has_result = True

    fp.close()
    if has_result:
        logger.debug("process() returns True")
        reduced_extent_list =  reduce_extents(extent_list)
        return True, model_dict_list, reduce_extents(extent_list)
    else:
        logger.debug("process() returns False, no result")
        return False, [], []


def write_single_volume(ck, pk, geom_obj, style_obj, meta_obj, src_dir, out_filename, prop_idx):
    # Produce a GLTF from voxet file
    model_dict_list = []
    if not geom_obj.vol_data is None: 
        if not geom_obj.is_single_layer_vo():
            popup_list = ck.write_vol_collada(geom_obj, style_obj, meta_obj, out_filename)
            for popup_dict_key, popup_dict, out_filename in popup_list:
                model_dict_list.append(add_info2popup(popup_dict_key, popup_dict, out_filename))

        # Produce a PNG file from voxet file
        else:
            popup_dict = pk.write_single_voxel_png(geom_obj, style_obj, meta_obj, out_filename, prop_idx)
            model_dict_list.append(add_info2popup("{0}_{1}".format(meta_obj.name, prop_idx+1), popup_dict, "{1}_{0}".format(prop_idx+1, out_filename), file_ext='.PNG', position=geom_obj.vol_origin))
    return model_dict_list


def initialise_params(param_file):
    ''' Initialise the global 'Params' object from input parameter file

    :param param_file: file name of input parameter file
    '''
    global Params
    global CoordOffset
    global CtFileDict
    Params = SimpleNamespace()
    param_dict = read_json_file(param_file)
    if 'ModelProperties' not in param_dict:
        logger.error("Cannot find 'ModelProperties' key in JSON file %s", param_file)
        sys.exit(1)
    # Mandatory parameters
    for field_name in ['crs', 'name', 'init_cam_dist']:
        if field_name not in param_dict['ModelProperties']:
            logger.error('Field "%s" not in "ModelProperties" in JSON input parameter file %s', field_name, param_file)
            sys.exit(1)
        setattr(Params, field_name, param_dict['ModelProperties'][field_name])
    # Optional parameter
    if 'proj4_defn' in param_dict['ModelProperties']:
        setattr(Params, 'proj4_defn', param_dict['ModelProperties']['proj4_defn'])
    # Optional Coordinate Offsets
    if 'CoordOffsets' in param_dict:
        for coordOffsetObj in param_dict['CoordOffsets']:
            CoordOffset[coordOffsetObj['filename']] = tuple(coordOffsetObj['offset'])
    # Optional colour table files for VOXET file
    if 'VoxetColourTables' in param_dict:
        for ctObj in param_dict['VoxetColourTables']:
            colour_table = ctObj['colour_table']
            filename = ctObj['filename']
            CtFileDict[filename] = colour_table
        

# MAIN PART OF PROGRAMME
if __name__ == "__main__":

    # Parse the arguments
    parser = argparse.ArgumentParser(description='Convert GOCAD files into files used to display a geological model')
    parser.add_argument('src', help='GOCAD source directory or source file', metavar='GOCAD source dir/file')
    parser.add_argument('param_file', help='Input parameters in JSON format', metavar='JSON input param file')
    parser.add_argument('--output_config', '-o', action='store', help='Output JSON config file', default='output_config.json')
    parser.add_argument('--recursive', '-r', action='store_true', help='Recursively search directories for files')
    parser.add_argument('--debug', '-d', action='store_true', help='Print debug statements during execution')
    parser.add_argument('--nondefault_coord', '-x', action='store_true', help='Tolerate non-default GOCAD coordinate system')
    parser.add_argument('--output_folder', '-f', action='store', help='Output folder for graphics files')
    parser.add_argument('--no_gltf', '-g', action='store_true', help='Create COLLADA files, but do not convert to GLTF')
    args = parser.parse_args()

    # If just want to create COLLADA files without converting them to GLTF
    if args.no_gltf:
        CONVERT_COLLADA = False

    model_dict_list = {}
    is_dir = False
    gocad_src = args.src
    geo_extent = [0.0, 0.0, 0.0, 0.0]

    initialise_params(args.param_file)

    # Initialise output directory, default is source directory
    dest_dir = os.path.dirname(args.src)
    if args.output_folder != None:
        if not os.path.exists(args.output_folder) or not os.path.exists(args.output_folder):
            logger.error("Output folder %s does not exist, or is not a directory", args.output_folder)
            sys.exit(1)
        dest_dir = args.output_folder

    # Set debug level
    if args.debug:
        DEBUG_LVL = logging.DEBUG
    else:
        DEBUG_LVL = logging.INFO

    # Will tolerate non default coords
    if args.nondefault_coord:
        NONDEF_COORDS = True

    # Create logging console handler
    handler = logging.StreamHandler(sys.stdout)

    # Create logging formatter
    formatter = logging.Formatter('%(asctime)s -- %(name)s -- %(levelname)s - %(message)s')

    # Add formatter to ch
    handler.setFormatter(formatter)

    # Add handler to logger and set level
    logger.addHandler(handler)
    logger.setLevel(DEBUG_LVL)

    # Process a directory of files
    if os.path.isdir(gocad_src):
        is_dir = True

        # Recursively search subdirectories
        if args.recursive:
            model_dict_list, geo_extent = find(gocad_src, dest_dir, GOCAD_VESSEL.SUPPORTED_EXTS, find_and_process)

        # Only search local directory
        else: 
            model_dict_list, geo_extent = find_and_process(gocad_src, dest_dir, GOCAD_VESSEL.SUPPORTED_EXTS)

    # Process a single file
    elif os.path.isfile(gocad_src):
        success, model_dict_list, geo_extent = process(gocad_src, dest_dir)

        # Convert all files from collada to GLTF v2
        if success and CONVERT_COLLADA:
            file_name, file_ext = os.path.splitext(gocad_src)
            exports.collada2gltf.convert_file(os.path.join(dest_dir, os.path.basename(file_name)+".dae"))

        if not success:
            logger.error("Could not convert file %s", gocad_src)
            sys.exit(1)

    else:
        logger.error("%s does not exist", gocad_src)
        sys.exit(1)
       
    # Always create a config file
    create_json_config(model_dict_list, args.output_config, geo_extent, Params)

