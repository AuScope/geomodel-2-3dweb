#!/usr/bin/env python3
"""
# This code creates a set of COLLADA (.dae) or GLTF files and a sqlite database
# which can be used to embed NVCL boreholes in a geological model
"""

import sys
import os

import json
from json import JSONDecodeError
from types import SimpleNamespace
import logging
import argparse

from pyproj import Proj, transform

from lib.exports.bh_utils import make_borehole_filename, make_borehole_label
from lib.exports.assimp_kit import AssimpKit
from lib.exports.geometry_gen import colour_borehole_gen
from lib.db.db_tables import QueryDB, QUERY_DB_FILE

from nvcl_kit.reader import GSMLP_IDS, NVCLReader


LOG_LVL = logging.INFO
''' Initialise debug level to minimal debugging
'''

# Set up debugging
LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(LOG_LVL)

if not LOGGER.hasHandlers():

    # Create logging console handler
    HANDLER = logging.StreamHandler(sys.stdout)

    # Create logging formatter
    FORMATTER = logging.Formatter('%(name)s -- %(levelname)s - %(message)s')

    # Add formatter to ch
    HANDLER.setFormatter(FORMATTER)

    # Add handler to LOGGER and set level
    LOGGER.addHandler(HANDLER)

# We are exporting using AssimpKit, could also use ColladaKit
EXPORT_KIT = AssimpKit(LOG_LVL)


MAX_BOREHOLES = 9999
''' Maximum number of boreholes processed
'''


def get_json_input_param(input_file):
    ''' Reads the parameters from input JSON file and stores them in global 'Param' object

    :param input_file: filename of input parameter file
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
        if field_name not in param_dict['BoreholeData']:
            LOGGER.error("Cannot find '%s' key in input file %s", field_name, input_file)
            sys.exit(1)
        setattr(param_obj, field_name, param_dict['BoreholeData'][field_name])

    if 'west' not in param_obj.BBOX or 'south' not in param_obj.BBOX or \
       'east' not in param_obj.BBOX or 'north' not in param_obj.BBOX:
        LOGGER.error("Cannot find 'west','south','east','north' in 'BBOX' in input file %s",
                     input_file)
        sys.exit(1)
    return param_obj


def convert_coords(input_crs, output_crs, x_y):
    ''' Converts coordinate systems

    :param input_crs: coordinate reference system of input coordinates
    :param output_crs: coordinate reference system of output coordinates
    :param x_y: input coordinates in [x,y] format
    :returns: converted coordinates [x,y]
    '''
    p_in = Proj(init=__clean_crs(input_crs))
    p_out = Proj(init=__clean_crs(output_crs))
    return transform(p_in, p_out, x_y[0], x_y[1])

def __clean_crs(crs):
    ''' Removes namespace prefixes from a CRS:
          e.g. 'urn:x-ogc:def:crs:EPSG:4326' becomes 'EPSG:4326'

    :param crs: crs string to be cleaned
    :returns: cleaned crs string
    '''
    pair = crs.split(':')[-2:]
    return pair[0]+':'+pair[1]



def get_bh_info_dict(borehole_dict, param_obj):
    ''' Returns a dict of borehole info for displaying in a popup box
        when user clicks on a borehole in the model

    :param borehole_dict: dict of borehole information
        expected keys are: 'x', 'y', 'z', 'href' and GSMLP_IDS
    :param param_obj: object containing command line parameters
    :return: dict of borehole information
    '''
    info_obj = {}
    info_obj['title'] = borehole_dict['name']
    for key in GSMLP_IDS:
        if key not in ['name', 'identifier', 'metadata_uri'] and borehole_dict[key]:
            info_obj[key] = borehole_dict[key]
    info_obj['href'] = [{'label': 'WFS URL', 'URL': borehole_dict['href']},
                        {'label': 'AuScope URL', 'URL': param_obj.EXTERNAL_LINK['URL']}]
    if borehole_dict['metadata_uri']:
        info_obj['href'].append({'label': 'Metadata URI', 'URL': borehole_dict['metadata_uri']})
    return info_obj


def get_loadconfig_dict(borehole_dict, param_obj):
    ''' Creates a config dictionary, used to load a static GLTF file
    :param borehole_dict: dictionary of borehole data
    :param param_obj: object containing command line parameters
    :return: config dictionary
    '''
    j_dict = {}
    j_dict['type'] = 'GLTFObject'
    x_m, y_m = convert_coords(param_obj.BOREHOLE_CRS, param_obj.MODEL_CRS,
                              [borehole_dict['x'], borehole_dict['y']])
    j_dict['position'] = [x_m, y_m, borehole_dict['z']]
    j_dict['model_url'] = make_borehole_filename(borehole_dict['name'])+".gltf"
    j_dict['display_name'] = borehole_dict['name']
    j_dict['include'] = True
    j_dict['displayed'] = True
    return j_dict


def get_blob_boreholes(borehole_dict, param_obj):
    ''' Retrieves borehole data and writes 3D model files to a blob

    :param borehole_dict:
    :param param_obj: input parameters
    :returns: GLTF blob object
    '''
    LOGGER.debug("get_blob_boreholes(%s)", str(borehole_dict))
    height_res = 10.0

    reader = NVCLReader(param_obj)
    if all(key in borehole_dict for key in ['name', 'x', 'y', 'z', 'nvcl_id']):
        bh_data_dict, base_xyz = get_nvcl_data(reader, param_obj, height_res, borehole_dict['x'], borehole_dict['y'], borehole_dict['z'], borehole_dict['nvcl_id'])
        
        # If there's data, then create the borehole
        if bh_data_dict != {}:
            blob_obj = EXPORT_KIT.write_borehole(base_xyz, borehole_dict['name'],
                                                 bh_data_dict, height_res, '')
            LOGGER.debug("Returning: blob_obj = %s", str(blob_obj))
            return blob_obj

        LOGGER.debug("No borehole data len=%d", len(log_ids))

    return None


def get_nvcl_data(reader, param_obj, height_res, x, y, z, nvcl_id):
    ''' Process the output of NVCL_kit's 'get_imagelog_data()'
        :param reader: NVCL_Kit object
        :param param_obj: NVCL_Kit constructor input
        :param height_res: borehole data height resolution (float, metres)
        :param x,y,z: x,y,z coordinates of borehole collar
        :param nvcl_id: NVCL id of borehole
        :returns: dictionary: key: depth (float)
                              value: SimpleNamespace('classText', 'className', 'colour')
                  Returns empty dict upon error or no data
                  and 'base_xyz' - (x,y,z) converted coordinate tuple in borehole
                  CRS
    '''
    x_m, y_m = convert_coords(param_obj.BOREHOLE_CRS, param_obj.MODEL_CRS,
                              [x, y])
    base_xyz = (x_m, y_m, z)
    # Look for NVCL mineral data
    imagelog_list = reader.get_imagelog_data(nvcl_id)
    LOGGER.debug('imagelog_list = %s', str(imagelog_list))
    if not imagelog_list:
        return {}, base_xyz
    ret_dict = {}
    for il in imagelog_list:
        # For the moment, only process log type '1' and 'Grp1 uTSAS'
        # Min1,2,3 = 1st, 2nd, 3rd most common mineral
        # Grp1,2,3 = 1st, 2nd, 3rd most common group of minerals
        # uTSAV = visible light, uTSAS = shortwave IR, uTSAT = thermal IR
        if il.log_type == '1' and il.log_name == 'Grp1 uTSAS':
            bh_data_dict = reader.get_borehole_data(il.log_id, height_res, 'Grp1 uTSAS')
            for depth in bh_data_dict:
                ret_dict[depth] = bh_data_dict[depth].__dict__
            break
    return ret_dict, base_xyz


def get_boreholes(reader, qdb, param_obj, output_mode='GLTF', dest_dir=''):
    ''' Retrieves borehole data and writes 3D model files to a directory or a blob
        If 'dest_dir' is supplied, then files are written
        If output_mode != 'GLTF' then 'dest_dir' must not be ''

    :param reader: NVCLReader object
    :param qdb: opened query database 'QueryDB' object
    :param param_obj: input parameters
    :param output_mode: optional flag, when set to 'GLTF' outputs GLTF to file/blob,
                        else outputs COLLADA (.dae) to file
    :param dest_dir: optional directory where 3D model files are written
    :returns: config object list and optional GLTF blob object
    '''
    LOGGER.debug("get_boreholes(%s, %s, %s)", str(param_obj), output_mode, dest_dir)

    # Get all NVCL scanned boreholes within BBOX
    borehole_list = reader.get_boreholes_list()
    if not borehole_list:
        LOGGER.warning("No NVCL boreholes found for %s using %s", param_obj.modelUrlPath,
                       param_obj.WFS_URL)
        return [], None

    height_res = 10.0
    LOGGER.debug("borehole_list = %s", str(borehole_list))
    blob_obj = None
    # Parse response for all boreholes, make COLLADA files
    bh_cnt = 0
    loadconfig_list = []
    for borehole_dict in borehole_list:

        # Get borehole information dictionary, and add to query db
        bh_info_dict = get_bh_info_dict(borehole_dict, param_obj)
        is_ok, p_obj = qdb.add_part(json.dumps(bh_info_dict))
        if not is_ok:
            LOGGER.warning("Cannot add part to db: %s", p_obj)
            continue

        if all(key in borehole_dict for key in ['name', 'x', 'y', 'z', 'nvcl_id']):
            bh_data_dict, base_xyz = get_nvcl_data(reader, param_obj, height_res, borehole_dict['x'], borehole_dict['y'], borehole_dict['z'], borehole_dict['nvcl_id'])
            if bh_data_dict == {}:
                LOGGER.warning('NVCL data not available for %s', borehole_dict['nvcl_id'])
                continue
            # If there's NVCL data, then create the borehole
            first_depth = -1
            # pylint: disable=W0612
            for vert_list, indices, colour_idx, depth, colour_info, mesh_name in \
                colour_borehole_gen(base_xyz, borehole_dict['name'], bh_data_dict, height_res):
                if first_depth < 0:
                    first_depth = int(depth)
                popup_info = colour_info.copy()
                del popup_info['colour']
                is_ok, s_obj = qdb.add_segment(json.dumps(popup_info))
                if not is_ok:
                    LOGGER.warning("Cannot add segment to db: %s", s_obj)
                    continue
                # Using 'make_borehole_label()' ensures that name is the same
                # in both db and GLTF file
                bh_label = make_borehole_label(borehole_dict['name'], first_depth)
                bh_str = "{0}_{1}".format(bh_label.decode('utf-8'), colour_idx)
                is_ok, r_obj = qdb.add_query(bh_str, param_obj.modelUrlPath,
                                             s_obj, p_obj, None, None)
                if not is_ok:
                    LOGGER.warning("Cannot add query to db: %s", r_obj)
                    continue
                LOGGER.debug("ADD_QUERY(%s, %s)", mesh_name, param_obj.modelUrlPath)

            file_name = make_borehole_filename(borehole_dict['name'])
            if output_mode == 'GLTF':
                blob_obj = EXPORT_KIT.write_borehole(base_xyz, borehole_dict['name'],
                                                     bh_data_dict, height_res,
                                                     os.path.join(dest_dir, file_name))

            elif dest_dir != '':
                import exports.collada2gltf
                from exports.collada_kit import ColladaKit
                export_kit = ColladaKit(LOG_LVL)
                export_kit.write_borehole(base_xyz, borehole_dict['name'], bh_data_dict,
                                          height_res, os.path.join(dest_dir, file_name))
                blob_obj = None
            else:
                LOGGER.warning("ColladaKit cannot write blobs")
                sys.exit(1)
            loadconfig_list.append(get_loadconfig_dict(borehole_dict, param_obj))
            bh_cnt += 1

    LOGGER.info("Found NVCL data for %d/%d boreholes", bh_cnt, len(borehole_list))
    if output_mode != 'GLTF':
        # Convert COLLADA files to GLTF
        exports.collada2gltf.convert_dir(dest_dir, "Borehole*.dae")
        # Return borehole objects

    LOGGER.debug("Returning: loadconfig_list, blobobj = %s, %s", str(loadconfig_list),
                 str(blob_obj))
    return loadconfig_list, blob_obj


def process_single(dest_dir, input_file, db_name, create_db=True):
    ''' Process a single model's boreholes

    :param dest_dir: directory to output database and files
    :param input_file: conversion parameter file
    :param db_name: name of database
    :param create_db: optional (default True) create new database or append to existing one

    '''
    LOGGER.info("Processing %s", input_file)
    out_filename = os.path.join(dest_dir, 'borehole_'+os.path.basename(input_file))
    param_obj = get_json_input_param(input_file)
    reader = NVCLReader(param_obj)
    if reader.wfs is None:
        LOGGER.error("Cannot contact web service")
        return
    qdb = QueryDB(create=create_db, db_name=db_name)
    err_str = qdb.get_error()
    if err_str != '':
        LOGGER.error("Cannot open/create database: %s", err_str)
        sys.exit(1)
    # pylint: disable=W0612
    borehole_loadconfig, none_obj = get_boreholes(reader, qdb, param_obj, output_mode='GLTF',
                                                  dest_dir=dest_dir)
    LOGGER.debug("borehole_loadconfig = %s", repr(borehole_loadconfig))
    if borehole_loadconfig:
        LOGGER.info("Writing to: %s", out_filename)
        with open(out_filename, 'w') as file_p:
            json.dump(borehole_loadconfig, file_p, indent=4, sort_keys=True)


if __name__ == "__main__":
    PARSER = argparse.ArgumentParser(description='Create borehole data: GLTF, JSON and database.')
    PARSER.add_argument('dest_dir', help='directory to hold output files',
                        metavar='Output directory')
    PARSER.add_argument('-i', '--input', help='single input file')
    PARSER.add_argument('-b', '--batch',
                        help='filename of a text file containing paths of many input files,' \
                             ' one input file per line')
    PARSER.add_argument('-d', '--database', help='filename of output database file',
                        default=QUERY_DB_FILE)
    PARSER.add_argument('--debug', help='turn on debug statements', action='store_true')
    ARGS = PARSER.parse_args()

    # Set debug level
    if ARGS.debug:
        LOG_LVL = logging.DEBUG

    LOGGER.setLevel(LOG_LVL)

    # Check and create output directory, if necessary
    if not os.path.isdir(ARGS.dest_dir):
        LOGGER.warning("Output directory %s does not exist", ARGS.dest_dir)
        try:
            LOGGER.info("Creating %s", ARGS.dest_dir)
            os.mkdir(ARGS.dest_dir)
        except OSError as os_exc:
            LOGGER.error("Cannot create dir %s: %s", ARGS.dest_dir, str(os_exc))
            sys.exit(1)

    # Check input file
    if getattr(ARGS, 'input', None) is not None:
        if not os.path.isfile(ARGS.input):
            LOGGER.error("Input file does not exist: %s", ARGS.input)
            sys.exit(1)
        process_single(ARGS.dest_dir, ARGS.input, os.path.join(ARGS.dest_dir, ARGS.database))

    # Check batch file
    elif getattr(ARGS, 'batch', None) is not None:
        if not os.path.isfile(ARGS.batch):
            LOGGER.error("Batch file does not exist: %s", ARGS.batch)
            sys.exit(1)
        CREATE_DB = True
        with open(ARGS.batch, 'r') as fp:
            for line in fp:
                # Skip lines starting with '#'
                if line[0] != '#':
                    process_single(ARGS.dest_dir, line.rstrip('\n'),
                                   os.path.join(ARGS.dest_dir, ARGS.database), CREATE_DB)
                    CREATE_DB = False
    else:
        print("No input file or batch file specified\n")
        PARSER.print_help()
