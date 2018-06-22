#!/usr/bin/env python3
#
# I am writing this because the current library (LaGrit) used to read  GOCAD *.ts
# is buggy (seg faults a lot) and does not read the 'ZPOSITIVE', so some parts of models are displayed
# upside down.
#
# This accepts all types of GOCAD files and support colours and 'ZPOSITIVE' flag etc.
#
import sys
import os
import glob
import json
from json import JSONDecodeError
import argparse
import random
import logging

from gocad_kit import GOCAD_KIT
from gocad_vessel import GOCAD_VESSEL
from makeDaeBoreholes import get_boreholes
import collada2gltf

DEBUG_LVL = logging.NOTSET
''' Initialise debug level to no debugging
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

OUTPUT_VOXEL_GLTF = False
''' Will output voxel files as GLTF, use only for small voxel files
'''

# Set up debugging 
logger = logging.getLogger(__name__)


def de_concat(filename_lines):
    ''' Separates joined GOCAD entries within a file 
        filename_lines - lines from concatenated GOCAD file
    '''
    file_lines_list = []
    part_list = []
    in_file = False
    for line in filename_lines:
        line_str = line.rstrip(' \n\r').upper()
        if not in_file:
            for marker in GOCAD_VESSEL.GOCAD_HEADERS.values():
                if line_str == marker[0]:
                    in_file = True
                    part_list.append(line)
                    break
        elif in_file:
            part_list.append(line) 
            if line_str == 'END':
                in_file = False
                part_list.append(line)
                file_lines_list.append(part_list)
                part_list = []
    return file_lines_list


def extract_gocad(src_dir, filename_str, file_lines, base_xyz):
    ''' Extracts GOCAD files from a GOCAD group file
        filename_str - filename of GOCAD file
        file_lines - lines extracted from GOCAD group file
        Returns a list of GOCAD_VESSEL objects
    '''
    logger.debug("extract_gocad(%s,%s)", src_dir, filename_str)
    gv_list = []
    firstLine = True
    inMember = False
    inGoCAD = False
    gocad_lines = []
    fileName, fileExt = os.path.splitext(filename_str)
    for line in file_lines:

        line_str = line.rstrip(' \n\r').upper()
        splitstr_arr = line_str.split(' ')
        if firstLine:
            firstLine = False
            if fileExt.upper() != '.GP' or line_str not in GOCAD_VESSEL.GOCAD_HEADERS['GP']:
                print("SORRY - not a GOCAD GP file", repr(line_str))
                print("    filename_str = ", filename_str)
                sys.exit(1)
        if line_str == "BEGIN_MEMBERS":
            inMember = True
        elif line_str == "END_MEMBERS":
            inMember = False
        elif inMember and splitstr_arr[0]=="GOCAD":
            inGoCAD = True
        elif inMember and line_str == "END":
            inGoCAD = False
            gv = GOCAD_VESSEL(DEBUG_LVL, base_xyz=base_xyz, group_name=os.path.basename(fileName).upper(), nondefault_coords=NONDEF_COORDS)
            if gv.process_gocad(src_dir, filename_str, gocad_lines):
                gv_list.append(gv)
            gocad_lines = []
        if inMember and inGoCAD:
            gocad_lines.append(line)

    logger.debug("extract_gocad() returning len(gv_list)=%d", len(gv_list))
    return gv_list


def find(gocad_src_dir):
    ''' Searches for GOCAD files in all the subdirectories
        gocad_src_dir - directory in which to begin the search
        Returns a list of model dict
            (model dict list format: [ { model_attr: { object_name: { 'attr_name': attr_val, ... } } } ] )
        and a list of geographical extents ( [ [min_x, max_x, min_y, max_y], ... ] )
        both can be used to create a config file
    '''
    logger.debug("find(%s)", gocad_src_dir)
    model_dict_list = []
    geoext_list = []
    walk_obj = os.walk(gocad_src_dir)
    for root, subfolders, files in walk_obj:
        done = False
        for file in files:
            name_str, ext_str = os.path.splitext(file)
            for gocad_ext_str in GOCAD_VESSEL.SUPPORTED_EXTS:
                if ext_str.lstrip('.').upper() == gocad_ext_str:
                    p_list, g_list = find_and_process(root)
                    model_dict_list += p_list
                    geoext_list.append(g_list)
                    done = True
                    break
            if done:
                break

    reduced_geoext_list = reduce_extents(geoext_list)
    return model_dict_list, reduced_geoext_list
 


def find_and_process(gocad_src_dir, base_x=0.0, base_y=0.0, base_z=0.0):
    ''' Searches for GOCAD files in local directory and processes them
        gocad_src_dir - source directory where there are GOCAD files
        base_x, base_y, base_z - optional 3D coordinate offset. This is added to all coordinates
        Returns a list of model dicts
            (model dict list format: [ { model_attr: { object_name: { 'attr_name': attr_val, ... } } } ] )
        and a list of geographical extents [ [min_x, max_x, min_y, max_y], ... ]
        both can be used to create a config file
    '''
    logger.debug("find_and_process(%s)", gocad_src_dir)
    ret_list = []
    extent_list = []
    for ext_str in GOCAD_VESSEL.SUPPORTED_EXTS:
        wildcard_str = os.path.join(gocad_src_dir, "*."+ext_str.lower())
        file_list = glob.glob(wildcard_str)
        for filename_str in file_list:
            success, model_dict_list, extent = process(filename_str, base_x, base_y, base_z)
            if success:
                ret_list += model_dict_list
                extent_list.append(extent)

    # Convert all files from COLLADA to GLTF v2
    if CONVERT_COLLADA:
        collada2gltf.convert_dir(gocad_src_dir)
    return ret_list, reduce_extents(extent_list)


def process(filename_str, base_x=0.0, base_y=0.0, base_z=0.0):
    ''' Processes a GOCAD file
        This one GOCAD file can contain many parts and produce many output files
        filename_str - filename of GOCAD file
        base_x, base_y, base_z - 3D coordinate offset, this is added to all coordinates
        Returns success/failure flag, model dictionary list,
            (model dict list format: [ { model_attr:  { object_name: { 'attr_name': attr_val, ... } } } ] )
        and geographical extent [min_x, max_x, min_y, max_y]
    '''
    print("\nProcessing ", filename_str)
    logger.debug("process(%s)", filename_str)
    model_dict_list = []
    popup_dict = {}
    extent_list = []
    fileName, fileExt = os.path.splitext(filename_str)
    ext_str = fileExt.lstrip('.').upper()
    gocad_src_dir = os.path.dirname(filename_str)
    gs = GOCAD_KIT(DEBUG_LVL)
    # Open GOCAD file an read all its contents, assume it fits in memory
    try:
        fp = open(filename_str,'r')
        whole_file_lines = fp.readlines()
    except(Exception):
        print("ERROR - Can't open or read - skipping file", filename_str)
        return False, [], []
    has_result = False

    # VS and VO files have lots of data points and thus one COLLADA file for each GOCAD file
    if ext_str in ['VS', 'VO']:
        file_lines_list = de_concat(whole_file_lines)
        mask_idx = 0  
        out_filename = fileName
        for file_lines in file_lines_list:
            if len(file_lines_list)>1:
                out_filename = "{0}_{1:d}".format(fileName, mask_idx)
            gv = GOCAD_VESSEL(DEBUG_LVL, base_xyz=(base_x, base_y, base_z), nondefault_coords=NONDEF_COORDS)
            # Check that conversion worked and write out files
            if not gv.process_gocad(gocad_src_dir, filename_str, file_lines):
                continue
            if ext_str == 'VS' and len(gv.get_vrtx_arr()) > 0:
                popup_dict = gs.write_collada(gv, out_filename)
                has_result = True
                model_dict_list.append(add_info2popup(popup_dict, out_filename))

            elif ext_str == 'VO':
                # By default must convert upper layer to PNG because some voxel files are too large
                #gs.write_OBJ(gv, out_filename, filename_str)
                if OUTPUT_VOXEL_GLTF:
                    # Produce a GLTF from voxel file
                    popup_list = gs.write_vo_collada(gv, out_filename)
                    for popup_dict, out_filename in popup_list:
                        model_dict_list.append(add_info2popup(popup_dict, out_filename))
                else:
                    # *.VO files will produce a PNG file, not GLTF
                    popup_list = gs.write_voxel_png(gv, gocad_src_dir, out_filename)
                    file_idx=1
                    for popup_obj in popup_list:
                        model_dict_list.append(add_info2popup(popup_obj, out_filename+"_{0}".format(file_idx), file_ext='.PNG', position=gv.axis_origin))
                        file_idx+=1
                has_result = True
            mask_idx+=1
            extent_list.append(gv.get_extent())

    # For triangles and lines, place multiple GOCAD objects in one COLLADA file
    elif ext_str in ['TS','PL']:
        file_lines_list = de_concat(whole_file_lines)
        gs.start_collada()
        popup_dict = {}
        for file_lines in file_lines_list:
            gv = GOCAD_VESSEL(DEBUG_LVL, base_xyz=(base_x, base_y, base_z), nondefault_coords=NONDEF_COORDS)
            if not gv.process_gocad(gocad_src_dir, filename_str, file_lines):
                continue
            has_result = True

            # Check that conversion worked and write out files
            if ext_str == 'TS' and len(gv.get_vrtx_arr()) > 0 and len(gv.get_trgl_arr()) > 0:
                popup_dict.update(gs.add_v_to_collada(gv))

            elif ext_str == 'PL' and len(gv.get_vrtx_arr()) > 0 and len(gv.get_seg_arr()) > 0:
                popup_dict.update(gs.add_v_to_collada(gv))
            extent_list.append(gv.get_extent())

        if has_result:
            model_dict_list.append(add_info2popup(popup_dict, fileName))
            gs.end_collada(fileName)
        

    # Process group files, depending on the number of GOCAD objects inside
    elif ext_str == 'GP':
        gv_list=extract_gocad(gocad_src_dir, filename_str, whole_file_lines, (base_x, base_y, base_z))

        # If there are too many entries in the GP file, then place everything in one COLLADA file
        if len(gv_list) > GROUP_LIMIT:
            gs.start_collada()
            popup_dict = {}
            for gv in gv_list:
                popup_dict.update(gs.add_v_to_collada(gv))
                extent_list.append(gv.get_extent())
                has_result = True
            if has_result:
                model_dict_list.append(add_info2popup(popup_dict, fileName))
                gs.end_collada(fileName)
 
        # Else place each GOCAD object in a separate file
        else:
            file_idx = 0
            for gv in gv_list:
                out_filename = "{0}_{1:d}".format(fileName, file_idx)
                p_dict = gs.write_collada(gv, out_filename)
                model_dict_list.append(add_info2popup(p_dict, out_filename))
                file_idx += 1
                extent_list.append(gv.get_extent())
                has_result = True

    fp.close()
    if has_result:
        reduced_extent_list =  reduce_extents(extent_list)
        return True, model_dict_list, reduce_extents(extent_list)
    else:
        return False, [], []


def reduce_extents(extent_list):
    ''' Reduces a list of extents to just one extent
        extent_list - list of geographical extents [ [min_x, max_x, min_y, max_y], ... ]
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


def add_info2popup(popup_dict, fileName, file_ext='.gltf', position=[0.0, 0.0, 0.0]):
    ''' Adds more information to popup dictionary
        popup_dict - information to display in popup window
            ( popup dict format: { object_name: { 'attr_name': attr_val, ... } } )
        fileName - file and path without extension of source file
        Returns a dict of model info, which includes the popup dict
    '''
    logger.debug("add_info2popup(%s, %s)", fileName, file_ext)
    np_filename = os.path.basename(fileName)
    j_dict = {}
    j_dict['popups'] = popup_dict
    if file_ext.upper()==".PNG":
        j_dict['type'] = 'ImagePlane'
        j_dict['position'] = position;
    else: 
        j_dict['type'] = 'GLTFObject'
    j_dict['model_url'] = np_filename + file_ext
    j_dict['display_name'] = np_filename.replace('_',' ')
    j_dict['include'] = True
    j_dict['displayed'] = True 
    return j_dict


def update_json_config(model_dict_list, template_filename, output_filename, borehole_outdir=""):
    ''' Updates a JSON file of GLTF objects to display in 3D
        model_dict_list - list of model dicts to write to JSON file
        template_filename - name of file which will be used as input for the update
        output_filename - name of updated config file
        borehole_outdir - optional name of diectory in which to save borehole GLTF files
    '''
    logger.debug("update_json_config(%s, %s, %s)", template_filename, output_filename, borehole_outdir) 
    try:
        fp = open(output_filename, "w")
    except:
        print("ERROR - cannot open file", output_filename)
        return
    config_dict = read_json_config(template_filename)
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
        config_dict['groups']['Boreholes'] = get_boreholes(borehole_outdir)
    json.dump(config_dict, fp, indent=4, sort_keys=True)
    fp.close()


def create_json_config(model_dict_list, output_filename, geo_extent):
    ''' Creates a JSON file of GLTF objects to display in 3D
        model_dict_list - list of model dicts to write to JSON file
        output_filename - name of file containing created config file
        geo_extent - list of coords defining boundaries of model [min_x, max_x, min_y, max_y]
    '''
    logger.debug("create_json_config(%s, %s)",  output_filename, repr(geo_extent))
    try:
        fp = open(output_filename, "w")
    except:
        print("ERROR - cannot open file", output_filename)
        return
    # Sort by display name before saving to file
    sorted_model_dict_list = sorted(model_dict_list, key=lambda x: x['display_name'])
    config_dict = { "properties": { "crs": "EPSG:3857", "extent": geo_extent,
                                    "name": "Name of model",
                                    "init_cam_dist": 500000.0 },
                    "type": "GeologicalModel",
                    "version": 1.0,
                    "groups": {"Group Name": sorted_model_dict_list }
                   }
    json.dump(config_dict, fp, indent=4, sort_keys=True)
    fp.close()

     
def read_json_config(file_name):
    ''' Reads a JSON file and returns the contents
        file_name  - file name of JSON file
    '''
    fp = open(file_name, "r")
    try:
        config_dict = json.load(fp)
    except JSONDecodeError:
        config_dict = {}
        print("ERROR - cannot read JSON file", file_name)
    fp.close()
    return config_dict


# MAIN PART OF PROGRAMME
if __name__ == "__main__":

    # Parse the arguments
    parser = argparse.ArgumentParser(description='Convert GOCAD files into files used to display a geological model')
    parser.add_argument('src', help='GOCAD source directory or source file', metavar='GOCAD source dir or file')
    parser.add_argument('--config_in', '-i', action='store', help='Input JSON config file', metavar='input config file')
    parser.add_argument('--config_out', '-o', action='store', help='Output JSON config file', metavar='output config file')
    parser.add_argument('--create', '-c', action='store_true', help='Create a JSON config file, must be used with -o option')
    parser.add_argument('--no_bores', '-n', action='store_true', help='Do not add WFS boreholes to model')
    parser.add_argument('--recursive', '-r', action='store_true', help='Recursively search directories for files')
    parser.add_argument('--debug', '-d', action='store_true', help='Print debug statements during execution')
    parser.add_argument('--nondefault_coord', '-x', action='store_true', help='Tolerate non-default GOCAD coordinate system')
    parser.add_argument('--voxel_gltf', '-l', action='store_true', help='Write out voxels as GLTF instead of upper layer as PNG')
    args = parser.parse_args()

    model_dict_list = {}
    is_dir = False
    gocad_src = args.src
    geo_extent = [0.0, 0.0, 0.0, 0.0]

    # Set debug level
    if args.debug:
        DEBUG_LVL = logging.DEBUG
    else:
        DEBUG_LVL = logging.NOTSET

    if args.nondefault_coord:
        NONDEF_COORDS = True

    if args.voxel_gltf:
        OUTPUT_VOXEL_GLTF = True
    
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
            model_dict_list, geo_extent = find(gocad_src)

        # Only search local directory
        else: 
            model_dict_list, geo_extent = find_and_process(gocad_src)

    # Process a single file
    elif os.path.isfile(gocad_src):
        success, model_dict_list, extent = process(gocad_src)

        # Convert all files from collada to GLTF v2
        if success and CONVERT_COLLADA:
            file_name, file_ext = os.path.splitext(gocad_src)
            collada2gltf.convert_file(file_name+".dae")

        if not success:
            print("Could not convert file")
            sys.exit(1)

    else:
        print("ERROR - ", gocad_src, "does not exist")
        sys.exit(1)
       
    # Update a config file
    if args.config_in!=None and args.config_out!=None:
        json_template = args.config_in
        json_output = args.config_out
        if os.path.isfile(json_template):
            if is_dir and not args.no_bores:
                update_json_config(model_dict_list, json_template, json_output, gocad_src)
            else:
                update_json_config(model_dict_list, json_template, json_output)
        else:
            print("ERROR - ", json_template, "does not exist")
            sys.exit(1)

    # Create a config file
    elif args.create and args.config_out!=None:
        json_output = args.config_out
        create_json_config(model_dict_list, json_output, geo_extent)

    elif args.config_in!=None or args.config_out!=None or args.create:
        print("You must specify either input and output files or create flag and output file")
        sys.exit(1)
