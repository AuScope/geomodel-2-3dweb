#!/usr/bin/env python3
#
# I am writing this because the current library (LaGrit) used to read  GOCAD *.ts
# is buggy (seg faults a lot) and does not read the 'ZPOSITIVE', so some parts of models are displayed
# upside down.
#
# This accepts most types of GOCAD files and support colours and 'ZPOSITIVE' flag etc.
# 
#  Dependencies: owslib, pyproj, pycollada, pyassimp
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
from makeBoreholes import get_boreholes
import exports.collada2gltf
from file_processing import find, create_json_config, read_json_file, update_json_config, reduce_extents, add_info2popup

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




def find_and_process(src_dir, ext_list):
    ''' Searches for files in local directory and processes them

    :param src_dir: source directory where there are 3rd party model files
    :param ext_list: list of supported file extensions
    :returns: a list of model dicts
        (model dict list format: [ { model_attr: { object_name: { 'attr_name': attr_val, ... } } } ] )
        and a list of geographical extents [ [min_x, max_x, min_y, max_y], ... ]
        both can be used to create a config file
    '''
    logger.debug("find_and_process(%s)", src_dir)
    ret_list = []
    extent_list = []
    for ext_str in ext_list:
        wildcard_str = os.path.join(src_dir, "*."+ext_str.lower())
        file_list = glob.glob(wildcard_str)
        for filename_str in file_list:
            success, model_dict_list, extent = process(filename_str)
            if success:
                ret_list += model_dict_list
                extent_list.append(extent)

    # Convert all files from COLLADA to GLTF v2
    if CONVERT_COLLADA:
        exports.collada2gltf.convert_dir(src_dir)
    return ret_list, reduce_extents(extent_list)


def process(filename_str):
    ''' Processes a GOCAD file. This one GOCAD file can contain many parts and produce many output files

    :param filename_str: filename of GOCAD file, including path
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
    fileName, fileExt = os.path.splitext(filename_str)
    ext_str = fileExt.lstrip('.').upper()
    src_dir = os.path.dirname(filename_str)
    ck = COLLADA_KIT(DEBUG_LVL)
    pk = PNG_KIT(DEBUG_LVL)
    # Open GOCAD file an read all its contents, assume it fits in memory
    try:
        fp = open(filename_str,'r')
        whole_file_lines = fp.readlines()
    except Exception as e:
        logger.error("ERROR - Can't open or read - skipping file %s %s", filename_str, e)
        return False, [], []
    has_result = False

    # VS and VO files usually have lots of data points and thus one COLLADA file for each GOCAD file
    if ext_str in ['VS', 'VO']:
        file_lines_list = de_concat(whole_file_lines)
        mask_idx = 0  
        out_filename = fileName
        for file_lines in file_lines_list:
            if len(file_lines_list)>1:
                out_filename = "{0}_{1:d}".format(fileName, mask_idx)
            gv = GOCAD_VESSEL(DEBUG_LVL, base_xyz=base_xyz, nondefault_coords=NONDEF_COORDS, ct_file_dict=CtFileDict)

            # Check that conversion worked
            is_ok, gsm_list = gv.process_gocad(src_dir, filename_str, file_lines)
            if not is_ok:
                logger.warning("WARNING - could not process %s", filename_str) 
                continue

            # Write out files
            if ext_str == 'VS':
                # Loop around when several properties in one GOCAD VSET object
                prop_idx = 0
                for geom_obj, style_obj, meta_obj in gsm_list:
                     prop_filename = "{0}_{1:d}".format(out_filename, prop_idx)
                     prop_idx += 1
                     popup_dict = ck.write_collada(geom_obj, style_obj, meta_obj, prop_filename)
                     has_result = True
                     model_dict_list.append(add_info2popup(meta_obj.name, popup_dict, prop_filename))

            elif ext_str == 'VO':
                idx = 0
                if not gv.is_single_layer_vo():
                    for geom_obj, style_obj, meta_obj in gsm_list:
                        # Produce a GLTF from voxel file
                        popup_list = ck.write_vol_collada(geom_obj, style_obj, meta_obj, out_filename+"_"+str(idx))
                        idx += 1
                        for popup_dict_key, popup_dict, out_filename in popup_list:
                            model_dict_list.append(add_info2popup(popup_dict_key, popup_dict, out_filename+"_"+str(idx)))
                else:
                    for geom_obj, style_obj, meta_obj in gsm_list:
                        # *.VO files will produce a PNG file, not GLTF
                        popup_list = pk.write_vol_png(geom_obj, src_dir, out_filename+"_"+str(idx))
                        file_idx=1
                        for popup_obj in popup_list:
                            model_dict_list.append(add_info2popup("{0}_{1}".format(meta_obj.name, file_idx), popup_obj, out_filename+"_{1}_{0}".format(file_idx, idx), file_ext='.PNG', position=geom_obj.vol_origin))
                            file_idx+=1
                has_result = True
            mask_idx+=1
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
                if ext_str == 'TS' and len(geom_obj.vrtx_arr) > 0 and len(geom_obj.trgl_arr) > 0:
                    popup_dict.update(ck.add_geom_to_collada(geom_obj, style_obj, meta_obj))
                    extent_list.append(geom_obj.get_extent())
                    has_result = True

                elif (ext_str in ['PL','WL']) and len(geom_obj.vrtx_arr) > 0 and len(geom_obj.seg_arr) > 0:
                    popup_dict.update(ck.add_geom_to_collada(geom_obj, style_obj, meta_obj))
                    extent_list.append(geom_obj.get_extent())
                    has_result = True

        if has_result:
            model_dict_list.append(add_info2popup(os.path.basename(fileName), popup_dict, fileName))
            ck.end_collada(fileName)
        

    # Process group files, depending on the number of GOCAD objects inside
    elif ext_str == 'GP':
        gsm_list=extract_from_grp(src_dir, filename_str, whole_file_lines, base_xyz, DEBUG_LVL, NONDEF_COORDS, CtFileDict)

        # If there are too many entries in the GP file, then place everything in one COLLADA file
        if len(gsm_list) > GROUP_LIMIT:
            ck.start_collada()
            popup_dict = {}
            for geom_obj, style_obj, meta_obj in gsm_list:
                popup_dict.update(ck.add_geom_to_collada(geom_obj, style_obj, meta_obj))
                extent_list.append(geom_obj.get_extent())
                has_result = True
            if has_result:
                model_dict_list.append(add_info2popup(os.path.basename(fileName), popup_dict, fileName))
                ck.end_collada(fileName)
 
        # Else place each GOCAD object in a separate file
        else:
            file_idx = 0
            for geom_obj, style_obj, meta_obj in gsm_list:
                out_filename = "{0}_{1:d}".format(fileName, file_idx)
                p_dict = ck.write_collada(geom_obj, style_obj, meta_obj, out_filename)
                model_dict_list.append(add_info2popup(meta_obj.name, p_dict, out_filename))
                file_idx += 1
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
        logger.error("ERROR - Cannot find 'ModelProperties' key in JSON file %s", param_file)
        sys.exit(1)
    # Mandatory parameters
    for field_name in ['crs', 'name', 'init_cam_dist']:
        if field_name not in param_dict['ModelProperties']:
            logger.error('ERROR - field "%s" not in "ModelProperties" in JSON input parameter file %s', field_name, param_file)
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
    parser.add_argument('src', help='GOCAD source directory or source file', metavar='GOCAD source dir or file')
    parser.add_argument('param_file', help='Input parameters in JSON format', metavar='JSON input param file')
    parser.add_argument('--config_in', '-i', action='store', help='Input JSON config file', metavar='input config file')
    parser.add_argument('--config_out', '-o', action='store', help='Output JSON config file', metavar='output config file')
    parser.add_argument('--create', '-c', action='store_true', help='Create a JSON config file, must be used with -o option')
    parser.add_argument('--bores', '-b', action='store_true', help='Add WFS boreholes to model')
    parser.add_argument('--recursive', '-r', action='store_true', help='Recursively search directories for files')
    parser.add_argument('--debug', '-d', action='store_true', help='Print debug statements during execution')
    parser.add_argument('--nondefault_coord', '-x', action='store_true', help='Tolerate non-default GOCAD coordinate system')
    args = parser.parse_args()

    model_dict_list = {}
    is_dir = False
    gocad_src = args.src
    geo_extent = [0.0, 0.0, 0.0, 0.0]

    initialise_params(args.param_file)

    # Set debug level
    if args.debug:
        DEBUG_LVL = logging.DEBUG
    else:
        DEBUG_LVL = logging.INFO

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
            model_dict_list, geo_extent = find(gocad_src, GOCAD_VESSEL.SUPPORTED_EXTS, find_and_process)

        # Only search local directory
        else: 
            model_dict_list, geo_extent = find_and_process(gocad_src, GOCAD_VESSEL.SUPPORTED_EXTS)

    # Process a single file
    elif os.path.isfile(gocad_src):
        success, model_dict_list, extent = process(gocad_src)

        # Convert all files from collada to GLTF v2
        if success and CONVERT_COLLADA:
            file_name, file_ext = os.path.splitext(gocad_src)
            exports.collada2gltf.convert_file(file_name+".dae")

        if not success:
            logger.error("Could not convert file %s", gocad_src)
            sys.exit(1)

    else:
        logger.error("ERROR - %s does not exist", gocad_src)
        sys.exit(1)
       
    # Update a config file
    if args.config_in!=None and args.config_out!=None:
        json_template = args.config_in
        json_output = args.config_out
        if os.path.isfile(json_template):
            if is_dir and args.bores:
                update_json_config(model_dict_list, json_template, json_output, gocad_src)
            else:
                update_json_config(model_dict_list, json_template, json_output)
        else:
            logger.error("ERROR - %s does not exist", json_template)
            sys.exit(1)

    # Create a config file
    elif args.create and args.config_out!=None:
        json_output = args.config_out
        create_json_config(model_dict_list, json_output, geo_extent, Params)

    elif args.config_in!=None or args.config_out!=None or args.create:
        logger.error("You must specify either input and output files or create flag and output file")
        sys.exit(1)
