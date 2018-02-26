#!/usr/bin/env python3
#
# I am writing this because the current library (LaGrit) used to read  GOCAD *.ts
# is buggy (seg faults a lot) and does not read the 'ZPOSITIVE', so some parts of models are displayed
# upside down.
#
# Eventually this will accept all types of GOCAD files and support colours and 'ZPOSITIVE' flag etc.
#
import sys
import os
import glob
import json
from json import JSONDecodeError
import argparse

from gocad_kit import GOCAD_KIT
from makeDaeBoreholes import get_boreholes
import collada2gltf

CONVERT_COLLADA = True


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
            for marker in GOCAD_KIT.GOCAD_HEADERS.values():
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
    ''' Extracts gocad files from a gocad group file
        filename_str - filename of gocad file
        file_lines - lines extracted from gocad group file
        Returns a list of GOCAD_KIT objects
    '''
    gs_list = []
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
            if fileExt.upper() != '.GP' or line_str not in GOCAD_KIT.GOCAD_HEADERS['GP']:
                print("SORRY - not a GOCAD GP file", repr(line_str))
                sys.exit(1)
        if line_str == "BEGIN_MEMBERS":
            inMember = True
        elif line_str == "END_MEMBERS":
            inMember = False
        elif inMember and splitstr_arr[0]=="GOCAD":
            inGoCAD = True
        elif inMember and line_str == "END":
            inGoCAD = False
            gs = GOCAD_KIT(base_xyz, os.path.basename(fileName).upper())
            gs.process_gocad(src_dir, filename_str, gocad_lines)
            gs_list.append(gs)
            gocad_lines = []
        if inMember and inGoCAD:
            gocad_lines.append(line)

    return gs_list




def find_and_process(gocad_src_dir, base_x=0.0, base_y=0.0, base_z=0.0):
    ''' Searches for gocad files and processes them
        gocad_src_dir - source directory where there are gocad files
        base_x, base_y, base_z - 3D coordinate offset, this is added to all
                                 coordinates
    '''
    ret_list = []
    extent_list = []
    for ext_str in GOCAD_KIT.SUPPORTED_EXTS:
        wildcard_str = os.path.join(gocad_src_dir, "*."+ext_str.lower())
        file_list = glob.glob(wildcard_str)
        for filename_str in file_list:
            popup_dict_list, extent = process(filename_str, base_x, base_y, base_z)
            ret_list += popup_dict_list
            extent_list.append(extent)
    return ret_list, reduce_extents(extent_list)


def process(filename_str, base_x=0.0, base_y=0.0, base_z=0.0):
    ''' Processes a GOCAD file
        This one GOCAD file can contain many parts and produce many output files
        filename_str - filename of GOCAD file
        base_x, base_y, base_z - 3D coordinate offset, this is added to all
                                 coordinates
    '''
    popup_dict_list = []
    popup_dict = {}
    extent_list = []
    fileName, fileExt = os.path.splitext(filename_str)
    ext_str = fileExt.lstrip('.').upper()
    gocad_src_dir = os.path.dirname(filename_str)
    try:
        fp = open(filename_str,'r')
        whole_file_lines = fp.readlines()
    except(Exception):
        print("Can't open or read - skipping file", filename_str)
        return

    if ext_str in ['TS', 'PL', 'VS', 'VO']:
        file_lines_list = de_concat(whole_file_lines)
        mask_idx = 0  
        for file_lines in file_lines_list:
            out_filename = fileName
            if len(file_lines_list)>1:
                out_filename = "{0}_{1:d}".format(fileName, mask_idx)
            gs = GOCAD_KIT((base_x, base_y, base_z))
            gs.process_gocad(gocad_src_dir, filename_str, file_lines)

            # Check that conversion worked and write out files
            if ext_str == 'TS' and len(gs.vrtx_arr) > 0 and len(gs.trgl_arr) > 0:
                popup_dict = gs.write_collada(out_filename)

            elif ext_str == 'PL' and len(gs.vrtx_arr) > 0 and len(gs.seg_arr) > 0:
                popup_dict= gs.write_collada(out_filename)

            elif ext_str == 'VS' and len(gs.vrtx_arr) > 0:
                popup_dict = gs.write_collada(out_filename)

            elif ext_str == 'VO' and gs.voxel_data.shape[0] > 1:
                # Must use PNG because some files are too large
                #popup_dict = gs.write_collada(out_filename, gs)
                #gs.write_OBJ(out_filename, filename_str)
                popup_dict = gs.write_voxel_png(gocad_src_dir, out_filename)
            mask_idx+=1
            popup_dict_list.append(add_info2popup(popup_dict, out_filename))
            popup_dict = {}
            extent_list.append(gs.get_extent())

    elif ext_str == 'GP':
        gs_list=extract_gocad(gocad_src_dir, filename_str, whole_file_lines, (base_x, base_y, base_z))
        file_idx = 0
        for gs in gs_list:
            out_filename = "{0}_{1:d}".format(fileName, file_idx)
            p_dict = gs.write_collada(out_filename)
            popup_dict_list.append(add_info2popup(p_dict, out_filename))
            popup_dict = {}
            file_idx += 1
            extent_list.append(gs.get_extent())

    fp.close()
    return popup_dict_list, reduce_extents(extent_list)



def reduce_extents(extent_list):
    ''' Reduces a list of extents to just one extent
        extent_list = list of extents
    '''
    out_extent = [sys.float_info.max, -sys.float_info.max, sys.float_info.max, -sys.float_info.max]
    for extent in extent_list:
        if extent[0] < out_extent[0]:
            out_extent[0] = extent[0]
        if extent[1] > out_extent[1]:
            out_extent[1] = extent[1]
        if extent[2] < out_extent[2]:
            out_extent[2] = extent[2]
        if extent[3] > out_extent[3]:
            out_extent[3] = extent[3]
    return out_extent
        


def add_info2popup(popup_dict, fileName):
    ''' Adds more information to popup dictionary
        popup_dict - information to display in popup window
        fileName - file and path without extension of source file
    '''
    np_filename = os.path.basename(fileName)
    j_dict = {}
    j_dict['popups'] = popup_dict
    j_dict['type'] = 'GLTFObject'
    j_dict['model_url'] = np_filename+".gltf"
    j_dict['display_name'] = np_filename.replace('_',' ')
    j_dict['include'] = True
    j_dict['displayed'] = True
    return j_dict



def update_json_config(popup_dict_list, template_filename, output_filename, borehole_outdir=""):
    ''' Updates a JSON file of GLTF objects to display in 3D
        popup_dict_list - list to write to JSON file
        template_filename - name of file which will be used as input for the update
        output_filename - name of updated config file
        borehole_outdir - optional name of diectory in which to save borehole GLTF files
    '''
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
            for popup_dict in popup_dict_list:
                if part['model_url'] == popup_dict['model_url']:
                    part['popups'] = popup_dict['popups']
                    for label, p_dict in part['popups'].items():
                        p_dict['title'] = group_name + '-' + part['display_name']
                    break
    if borehole_outdir != "":
        config_dict['groups']['Boreholes'] = get_boreholes(borehole_outdir)
    json.dump(config_dict, fp, indent=4, sort_keys=True)
    fp.close()


def create_json_config(popup_dict_list, output_filename, extent):
    ''' Creates a JSON file of GLTF objects to display in 3D
        popup_dict_list - list to write to JSON file
        output_filename - name of file containing created config file
        extent - list of coords defining boundaries of model [min_x, max_x, min_y, max_y]
    '''
    try:
        fp = open(output_filename, "w")
    except:
        print("ERROR - cannot open file", output_filename)
        return
    config_dict = { "properties": { "crs": "EPSG:3857", "extent": extent,
                                    "name": "Name of model" },
                    "type": "GeologicalModel",
                    "version": 1.0,
                    "groups": {"Group Name": popup_dict_list }
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
    parser.add_argument('--create', '-c', action='store_true', help='Create a JSON config file')
    parser.add_argument('--no_bores', '-n', action='store_true', help='Do not add boreholes to model')
    args = parser.parse_args()

    popup_list_dict = {}
    is_dir = False
    gocad_src = args.src
    extent = [0.0, 0.0, 0.0, 0.0]

    # Process a directory of files
    if os.path.isdir(gocad_src):
        is_dir = True
        popup_dict_list, extent = find_and_process(gocad_src)
        # Convert all files from collada to GLTF v2
        if CONVERT_COLLADA:
            collada2gltf.convert_dir(gocad_src)

    # Process a single file
    elif os.path.isfile(gocad_src):
        popup_dict_list, extent = process(gocad_src)
        # Convert all files from collada to GLTF v2
        if CONVERT_COLLADA:
            file_name, file_ext = os.path.splitext(gocad_src)
            collada2gltf.convert_file(file_name+".dae")

    else:
        print(gocad_src, "does not exist")
        sys.exit(1)
       
    # Update a config file
    if args.config_in!=None and args.config_out!=None:
        json_template = args.config_in
        json_output = args.config_out
        if os.path.isfile(json_template):
            if is_dir and not args.no_bores:
                update_json_config(popup_dict_list, json_template, json_output, gocad_src)
            else:
                update_json_config(popup_dict_list, json_template, json_output)
        else:
            print(json_template, "does not exist")
            sys.exit(1)

    # Create a config file
    elif args.create and args.config_out!=None:
        json_output = args.config_out
        create_json_config(popup_dict_list, json_output, extent)

    elif args.config_in!=None or args.config_out!=None or args.create:
        print("You must specify either input and output files or create flag and output file")
        sys.exit(1)
