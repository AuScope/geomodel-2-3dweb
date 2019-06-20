#!/usr/bin/env python3
"""
This converts GOCAD to COLLADA and GLTF
It accepts many types of GOCAD files (TS, GP, VS, PL, VO) and support colours
and 'ZPOSITIVE' flag etc.
"""

import sys
import os
import glob
import argparse
import logging
import gzip
import shutil
from types import SimpleNamespace

from lib.exports.png_kit import PngKit
from lib.exports.collada_kit import ColladaKit
from lib.imports.gocad.gocad_importer import GocadImporter, extract_from_grp
from lib.imports.gocad.helpers import de_concat
from lib.file_processing import find, create_json_config, read_json_file, reduce_extents
from lib.file_processing import add_config2popup, add_vol_config, is_only_small
import lib.exports.collada2gltf as collada2gltf

CONVERT_COLLADA = True
''' Runs the collada2gltf program after creating COLLADA files
'''

GROUP_LIMIT = 8
''' If there are more than GROUP_LIMIT number of GOCAD objects in a group file
    then use one COLLADA file else put use separate COLLADA files for each object
'''

NONDEF_COORDS = False
''' Will tolerate non default coordinates
'''

VOL_SLICER = True
''' If 'True', it will create a volume slicer for voxet files
    else will create cubes, which will only work for smaller volumes
'''

DEBUG_LVL = logging.CRITICAL
''' Initialise debug level to minimal debugging
'''



class Gocad2Collada:
    """ Converts GOCAD files to COLLADA, then GLTFs
    """

    def __init__(self, debug_lvl, param_file):

        # Create logging console handler
        handler = logging.StreamHandler(sys.stdout)

        # Create logging formatter
        formatter = logging.Formatter('%(asctime)s -- %(name)s -- %(levelname)s - %(message)s')

        # Add formatter to ch
        handler.setFormatter(formatter)

        # Set up debugging
        self.logger = logging.getLogger(__name__)

        # Add handler to LOGGER and set level
        self.logger.addHandler(handler)
        self.logger.setLevel(debug_lvl)

        # Coordinate Offsets are stored here, key is filename, value is (x,y,z)
        self.coord_offset = {}

        # Colour table files: key is GOCAD filename, value is CSV colour table filename (w/o path)
        self.ct_file_dict = {}

        # Process the parameter file
        self.params = self.initialise_params(param_file)


    def find_and_process(self, src_dir, dest_dir, ext_list):
        ''' Searches for files in local directory and processes them

        :param src_dir: source directory where there are 3rd party model files
        :param dest_dir: destination directory where output is written to
        :param ext_list: list of supported file extensions
        :returns: a list of model dicts
            (model dict list format: [ { model_attr:
                                         { object_name: { 'attr_name': attr_val, ... } } } ] )
            and a list of geographical extents [ [min_x, max_x, min_y, max_y], ... ]
            both can be used to create a config file
        '''
        self.logger.debug("find_and_process(%s, %s )", src_dir, dest_dir)
        ret_list = []
        extent_list = []
        for ext_str in ext_list:
            wildcard_str = os.path.join(src_dir, "*."+ext_str.lower())
            file_list = glob.glob(wildcard_str)
            for filename_str in file_list:
                success, model_dict_list, extent = self.process(filename_str, dest_dir)
                if success:
                    ret_list += model_dict_list
                    extent_list.append(extent)

        # Convert all files from COLLADA to GLTF v2
        if CONVERT_COLLADA:
            collada2gltf.convert_dir(dest_dir)
        return ret_list, reduce_extents(extent_list)


    def process(self, filename_str, dest_dir):
        ''' Processes a GOCAD file. This one GOCAD file can contain many parts and produce many
            output files

        :param filename_str: filename of GOCAD file, including path
        :param dest_dir: destination directory
        :returns: success/failure flag, model dictionary list,
            (model dict list format: [ { model_attr:  { object_name: {
                                                           'attr_name': attr_val, ... } } } ] )
            and geographical extent [min_x, max_x, min_y, max_y]
        '''
        self.logger.info("\nProcessing %s", filename_str)
        # If there is an offset from the input parameter file, then apply it
        base_xyz = (0.0, 0.0, 0.0)
        basefile = os.path.basename(filename_str)
        if basefile in self.coord_offset:
            base_xyz = self.coord_offset[basefile]
        model_dict_list = []
        popup_dict = {}
        extent_list = []
        file_name, file_ext = os.path.splitext(filename_str)
        out_filename = os.path.join(dest_dir, os.path.basename(file_name))
        ext_str = file_ext.lstrip('.').upper()
        src_dir = os.path.dirname(filename_str)
        coll_kit_obj = ColladaKit(DEBUG_LVL)
        png_kit_obj = PngKit(DEBUG_LVL)
        # Open GOCAD file and read all its contents, assume it fits in memory
        try:
            file_d = open(filename_str, 'r')
            whole_file_lines = file_d.readlines()
        except OSError as os_exc:
            self.logger.error("Can't open or read - skipping file %s %s", filename_str, os_exc)
            return False, [], []
        has_result = False

        # VS files usually have lots of data points and thus one COLLADA file for each GOCAD file
        if ext_str == 'VS':
            file_lines_list = de_concat(whole_file_lines, GocadImporter.GOCAD_HEADERS)
            for mask_idx, file_lines in enumerate(file_lines_list):
                if len(file_lines_list) > 1:
                    out_filename = "{0}_{1:d}".format(os.path.join(dest_dir,
                                                                   os.path.basename(file_name)),
                                                      mask_idx)
                gocad_obj = GocadImporter(DEBUG_LVL, base_xyz=base_xyz,
                                          nondefault_coords=NONDEF_COORDS,
                                          ct_file_dict=self.ct_file_dict)

                # Check that conversion worked
                is_ok, gsm_list = gocad_obj.process_gocad(src_dir, filename_str, file_lines)
                if not is_ok:
                    self.logger.warning("Could not process %s", filename_str)
                    continue

                # Write out files
                prop_filename = out_filename
                if len(gsm_list) > 1:
                    prop_filename += "_0"
                # Loop around when several properties in one GOCAD object
                for prop_idx, (geom_obj, style_obj, meta_obj) in enumerate(gsm_list):
                    if prop_idx > 0:
                        prop_filename = "{0}_{1:d}".format(out_filename, prop_idx)
                    popup_dict = coll_kit_obj.write_collada(geom_obj, style_obj, meta_obj,
                                                            prop_filename)
                    model_dict_list.append(add_config2popup(self.params.grp_struct_dict,
                                                            meta_obj.name,
                                                            popup_dict, prop_filename))
                    has_result = True
                    extent_list.append(geom_obj.get_extent())

        # One VO file can produce many other files
        elif ext_str == 'VO':
            file_lines_list = de_concat(whole_file_lines, GocadImporter.GOCAD_HEADERS)
            for mask_idx, file_lines in enumerate(file_lines_list):
                if len(file_lines_list) > 1:
                    out_filename = "{0}_{1:d}".format(os.path.join(dest_dir,
                                                                   os.path.basename(file_name)),
                                                      mask_idx)
                gocad_obj = GocadImporter(DEBUG_LVL, base_xyz=base_xyz,
                                          nondefault_coords=NONDEF_COORDS,
                                          ct_file_dict=self.ct_file_dict)

                # Check that conversion worked
                is_ok, gsm_list = gocad_obj.process_gocad(src_dir, filename_str, file_lines)
                if not is_ok:
                    self.logger.warning("Could not process %s", filename_str)
                    continue

                # Loop around when several binary files in one GOCAD VOXET object
                for prop_idx, (geom_obj, style_obj, meta_obj) in enumerate(gsm_list):
                    out_filename = os.path.join(dest_dir, os.path.basename(meta_obj.src_filename))
                    md_list = self.write_single_volume((coll_kit_obj, png_kit_obj),
                                                       (geom_obj, style_obj, meta_obj),
                                                       src_dir, out_filename, prop_idx)
                    model_dict_list += md_list
                    has_result = True
                    extent_list.append(geom_obj.get_extent())


        # For triangles, wells and lines, place multiple GOCAD objects in one COLLADA file
        elif ext_str in ['TS', 'PL', 'WL']:
            file_lines_list = de_concat(whole_file_lines, GocadImporter.GOCAD_HEADERS)
            coll_kit_obj.start_collada()
            popup_dict = {}
            node_label = ''
            for file_lines in file_lines_list:
                gocad_obj = GocadImporter(DEBUG_LVL, base_xyz=base_xyz,
                                          nondefault_coords=NONDEF_COORDS)
                is_ok, gsm_list = gocad_obj.process_gocad(src_dir, filename_str, file_lines)
                if not is_ok:
                    self.logger.warning("WARNING - could not process %s", filename_str)
                    continue
                for geom_obj, style_obj, meta_obj in gsm_list:

                    # Check that conversion worked and write out files
                    if ext_str == 'TS' and geom_obj.vrtx_arr and geom_obj.trgl_arr \
                               or (ext_str in ['PL', 'WL']) and geom_obj.vrtx_arr  \
                               and geom_obj.seg_arr:
                        p_dict, node_label = coll_kit_obj.add_geom_to_collada(geom_obj,
                                                                              style_obj, meta_obj)
                        popup_dict.update(p_dict)
                        extent_list.append(geom_obj.get_extent())
                        has_result = True

            if has_result:
                model_dict_list.append(add_config2popup(self.params.grp_struct_dict,
                                                        os.path.basename(file_name),
                                                        popup_dict, file_name))
                coll_kit_obj.end_collada(out_filename, node_label)


        # Process group files, depending on the number of GOCAD objects inside
        elif ext_str == 'GP':
            gsm_list = extract_from_grp(src_dir, filename_str, whole_file_lines, base_xyz,
                                        DEBUG_LVL, NONDEF_COORDS, self.ct_file_dict)

            # If there are too many entries in the GP file, then use one COLLADA file only
            if len(gsm_list) > GROUP_LIMIT or is_only_small(gsm_list):
                self.logger.debug("All group objects in one COLLADA file")
                coll_kit_obj.start_collada()
                popup_dict = {}
                node_label = ''
                for geom_obj, style_obj, meta_obj in gsm_list:
                    p_dict, node_label = coll_kit_obj.add_geom_to_collada(geom_obj, style_obj,
                                                                          meta_obj)
                    popup_dict.update(p_dict)
                    extent_list.append(geom_obj.get_extent())
                    has_result = True
                if has_result:
                    model_dict_list.append(add_config2popup(self.params.grp_struct_dict,
                                                            os.path.basename(file_name), popup_dict,
                                                            file_name))
                    coll_kit_obj.end_collada(out_filename, node_label)

            # Else place each GOCAD object in its own COLLADA file
            else:
                for file_idx, (geom_obj, style_obj, meta_obj) in enumerate(gsm_list):
                    if geom_obj.is_volume():
                        out_filename = os.path.join(dest_dir,
                                                    os.path.basename(meta_obj.src_filename))
                        md_list = self.write_single_volume((coll_kit_obj, png_kit_obj),
                                                           (geom_obj, style_obj, meta_obj),
                                                           src_dir, out_filename, file_idx)
                        model_dict_list += md_list
                    else:
                        prop_filename = "{0}_{1:d}".format(out_filename, file_idx)
                        p_dict = coll_kit_obj.write_collada(geom_obj, style_obj, meta_obj,
                                                            prop_filename)
                        model_dict_list.append(add_config2popup(self.params.grp_struct_dict,
                                                                meta_obj.name,
                                                                p_dict, prop_filename))
                    extent_list.append(geom_obj.get_extent())
                    has_result = True

        file_d.close()
        if has_result:
            self.logger.debug("process() returns True")
            return True, model_dict_list, reduce_extents(extent_list)

        self.logger.debug("process() returns False, no result")
        return False, [], []


    def write_single_volume(self, kit_obj, gsm_obj, src_dir, out_filename, prop_idx):
        ''' Write a single volume to disk
        :param kit_obj: a tuple of (ColladaKit, PngKit) objects, used to output COLLADA & PNG files
        :param gsm_obj: (MODEL_GEOMETRY, STYLE, METADATA) tuple, contains the geometry of the
                        volume, the volume's style & metadata
        :param src_dir: source directory where there are 3rd party model files
        :param out_filename: output filename without extension
        :param prop_idx: property index of volume's properties, integer
        '''
        coll_kit_obj, png_kit_obj = kit_obj
        geom_obj, style_obj, meta_obj = gsm_obj
        self.logger.debug("write_single_volume(geom_obj=%s, style_obj=%s, meta_obj=%s)",
                          repr(geom_obj), repr(style_obj), repr(meta_obj))
        self.logger.debug("src_dir=%s, out_filename=%s, prop_idx=%d)", src_dir, out_filename,
                          prop_idx)

        model_dict_list = []
        if not geom_obj.vol_data is None:
            if not geom_obj.is_single_layer_vo():
                if VOL_SLICER:
                    in_filename = os.path.join(src_dir, os.path.basename(out_filename))
                    with open(in_filename, 'rb') as fp_in:
                        with gzip.open(out_filename + '.gz', 'wb') as fp_out:
                            shutil.copyfileobj(fp_in, fp_out)
                            model_dict_list.append(add_vol_config(self.params.grp_struct_dict,
                                                                  geom_obj, style_obj, meta_obj))

                else:
                    # Produce GLTFs from voxet file
                    popup_list = coll_kit_obj.write_vol_collada(geom_obj, style_obj, meta_obj,
                                                                out_filename)
                    for popup_dict_key, popup_dict, out_file in popup_list:
                        model_dict_list.append(add_config2popup(self.params.grp_struct_dict,
                                                                popup_dict_key, popup_dict,
                                                                out_file))

            # Produce a PNG file from voxet file
            else:
                popup_dict = png_kit_obj.write_single_voxel_png(geom_obj, style_obj, meta_obj,
                                                                out_filename)
                model_dict_list.append(add_config2popup(self.params.grp_struct_dict,
                                                        "{0}_{1}".format(meta_obj.name, prop_idx+1),
                                                        popup_dict, out_filename, file_ext='.PNG',
                                                        position=geom_obj.vol_origin))
        return model_dict_list


    def check_input_params(self, param_dict, param_file):
        """ Checks that the input parameter file has all the madatory fields and
            that there are no duplicate labels

            :param param_dict: parameter file as a dict
            :param param_file: filename of parameter file (string)
        """
        if 'ModelProperties' not in param_dict:
            self.logger.error("Cannot find 'ModelProperties' key in JSON file %s", param_file)
            sys.exit(1)
        if 'GroupStructure' not in param_dict:
            self.logger.error("Cannot find 'GroupStructure' key in JSON file %s", param_file)
            sys.exit(1)

        # Check for duplicate group names
        group_names = param_dict['GroupStructure'].keys()
        if len(group_names) > len(set(group_names)):
            self.logger.error("Cannot process JSON file %s: duplicate group names", param_file)
            sys.exit(1)

        # Check for duplicate labels
        for part_list in param_dict['GroupStructure'].values():
            display_name_set = set()
            filename_set = set()
            for part in part_list:
                if part["FileNameKey"] in filename_set:
                    self.logger.error("Cannot process JSON file %s: duplicate FileNameKey %s",
                                      param_file, part["FileNameKey"])
                    sys.exit(1)
                filename_set.add(part["FileNameKey"])
                if "display_name" in part["Insert"] and \
                                     part["Insert"]["display_name"] in display_name_set:
                    self.logger.error("Cannot process JSON file %s: duplicate display_name %s",
                                      param_file, part["Insert"]["display_name"])
                    sys.exit(1)
                display_name_set.add(part["Insert"]["display_name"])


    def initialise_params(self, param_file):
        ''' Reads the input parameter file and initialises the global 'PARAMS' object

        :param param_file: file name of input parameter file
        '''
        params_obj = SimpleNamespace()
        param_dict = read_json_file(param_file)
        self.check_input_params(param_dict, param_file)

        # Mandatory parameters
        for field_name in ['crs', 'name', 'init_cam_dist']:
            if field_name not in param_dict['ModelProperties']:
                self.logger.error('Field "%s" not in "ModelProperties" in JSON input param file %s',
                                  field_name, param_file)
                sys.exit(1)
            setattr(params_obj, field_name, param_dict['ModelProperties'][field_name])
        # Optional parameter
        if 'proj4_defn' in param_dict['ModelProperties']:
            setattr(params_obj, 'proj4_defn', param_dict['ModelProperties']['proj4_defn'])
        # Optional Coordinate Offsets
        if 'CoordOffsets' in param_dict:
            for coord_offset_obj in param_dict['CoordOffsets']:
                self.coord_offset[coord_offset_obj['filename']] = tuple(coord_offset_obj['offset'])
        # Optional colour table files for VOXET file
        if 'VoxetColourTables' in param_dict:
            for ct_obj in param_dict['VoxetColourTables']:
                colour_table = ct_obj['colour_table']
                filename = ct_obj['filename']
                self.ct_file_dict[filename] = colour_table

        # Optional labels for sidebars
        setattr(params_obj, 'grp_struct_dict', {})
        if 'GroupStructure' in param_dict:
            for group_name, command_list in param_dict['GroupStructure'].items():
                for command in command_list:
                    params_obj.grp_struct_dict[command["FileNameKey"]] = (group_name,
                                                                          command["Insert"])
        return params_obj



# MAIN PART OF PROGRAMME
if __name__ == "__main__":

    # Parse the arguments
    PARSER = argparse.ArgumentParser(description='Convert GOCAD files into geological model files')
    PARSER.add_argument('src', help='GOCAD source directory or source file',
                        metavar='GOCAD source dir/file')
    PARSER.add_argument('param_file', help='Input parameters in JSON format',
                        metavar='JSON input param file')
    PARSER.add_argument('-o', '--output_config', action='store', help='Output JSON config file',
                        default='output_config.json')
    PARSER.add_argument('-r', '--recursive', action='store_true',
                        help='Recursively search directories for files')
    PARSER.add_argument('-d', '--debug', action='store_true',
                        help='Print debug statements during execution')
    PARSER.add_argument('-x', '--nondefault_coord', action='store_true',
                        help='Tolerate non-default GOCAD coordinate system')
    PARSER.add_argument('-f', '--output_folder', action='store',
                        help='Output folder for graphics files')
    PARSER.add_argument('-g', '--no_gltf', action='store_true',
                        help='Create COLLADA files, but do not convert to GLTF')
    ARGS = PARSER.parse_args()

    # If just want to create COLLADA files without converting them to GLTF
    if ARGS.no_gltf:
        CONVERT_COLLADA = False

    MODEL_DICT_LIST = {}
    GOCAD_SRC = ARGS.src
    GEO_EXTENT = [0.0, 0.0, 0.0, 0.0]

    # Initialise output directory, default is source directory
    DEST_DIR = os.path.dirname(ARGS.src)
    if ARGS.output_folder is not None:
        if not os.path.isdir(ARGS.output_folder):
            print("Output folder", repr(ARGS.output_folder), "is not a directory", )
            sys.exit(1)
        DEST_DIR = ARGS.output_folder

    # Set debug level
    if ARGS.debug:
        DEBUG_LVL = logging.DEBUG
    else:
        DEBUG_LVL = logging.INFO

    # Will tolerate non default coords
    if ARGS.nondefault_coord:
        NONDEF_COORDS = True

    CONVERTER = Gocad2Collada(DEBUG_LVL, ARGS.param_file)

    # Process a directory of files
    if os.path.isdir(GOCAD_SRC):

        # Recursively search subdirectories
        if ARGS.recursive:
            MODEL_DICT_LIST, GEO_EXTENT = find(GOCAD_SRC, DEST_DIR,
                                               GocadImporter.SUPPORTED_EXTS,
                                               CONVERTER.find_and_process)

        # Only search local directory
        else:
            MODEL_DICT_LIST, GEO_EXTENT = CONVERTER.find_and_process(GOCAD_SRC, DEST_DIR,
                                                                     GocadImporter.SUPPORTED_EXTS)

    # Process a single file
    elif os.path.isfile(GOCAD_SRC):
        SUCCESS, MODEL_DICT_LIST, GEO_EXTENT = CONVERTER.process(GOCAD_SRC, DEST_DIR)

        # Convert all files from collada to GLTF v2
        if SUCCESS and CONVERT_COLLADA:
            FILE_NAME, FILE_EXT = os.path.splitext(GOCAD_SRC)
            collada2gltf.convert_file(os.path.join(DEST_DIR,
                                                   os.path.basename(FILE_NAME) + ".dae"))

        if not SUCCESS:
            print("Could not convert file", GOCAD_SRC)
            sys.exit(1)

    else:
        print(GOCAD_SRC, "does not exist")
        sys.exit(1)

    # Always create a config file
    create_json_config(MODEL_DICT_LIST, ARGS.output_config, DEST_DIR, GEO_EXTENT, CONVERTER.params)
