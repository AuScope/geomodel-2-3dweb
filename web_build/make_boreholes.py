#!/usr/bin/env python3
"""
This code creates GLTF files and a sqlite database
which can be used to embed NVCL boreholes in a 3d geoscience model
"""

import sys
import os

sys.path.append(os.path.join(os.pardir, 'scripts'))

import json
from json import JSONDecodeError
from types import SimpleNamespace
import logging
import argparse

from lib.exports.bh_utils import make_borehole_filename, make_borehole_label
from lib.exports.bh_make import get_nvcl_data
from lib.exports.gltf_kit import GltfKit
from lib.exports.geometry_gen import colour_borehole_gen
from lib.db.db_tables import QueryDB, QUERY_DB_FILE
from lib.file_processing import get_input_conv_param_bh
from lib.coords import convert_coords

from nvcl_kit.reader import NVCLReader
from nvcl_kit.param_builder import param_builder

BH_INFO_KEYS = ['nvcl_id', 'identifier', 'name', 'description', 'purpose', 'status', 'drillingMethod', 'operator', 'driller',
    'drillStartDate', 'drillEndDate', 'startPoint', 'inclinationType', 'href', 'boreholeMaterialCustodian', 'boreholeLength_m',
    'elevation_m', 'elevation_srs', 'positionalAccuracy', 'source', 'x', 'y', 'z', 'parentBorehole_uri', 'metadata_uri',
    'genericSymbolizer']


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

# We are exporting using GltfKit, could also use ColladaKit
EXPORT_KIT = GltfKit(LOG_LVL)



def get_bh_info_dict(borehole: SimpleNamespace, param_obj: dict) -> dict:
    ''' Returns a dict of borehole info for displaying in a popup box
        when user clicks on a borehole in the model

    :param borehole: SimpleNamepsace() obj of borehole information, expected keys are BH_INFO_KEYS
    :param param_obj: object containing command line parameters
    :return: dict of borehole information
    '''
    info_obj = {}
    info_obj['title'] = borehole.name
    for key in BH_INFO_KEYS:
        if key not in ['name', 'identifier', 'metadata_uri'] and hasattr(borehole, key):
            info_obj[key] = getattr(borehole, key)
    info_obj['href'] = [{'label': 'WFS URL', 'URL': borehole.href}]
    if hasattr(param_obj, 'EXTERNAL_LINK'):
        info_obj['href'].append({'label': 'AuScope URL', 'URL': param_obj.EXTERNAL_LINK['URL']})
    if hasattr(borehole, 'metadata_uri'):
        info_obj['href'].append({'label': 'Metadata URI', 'URL': borehole.metadata_uri})
    return info_obj


def get_loadconfig_dict(borehole: SimpleNamespace, param_obj: dict) -> dict:
    ''' Creates a config dictionary, used to load a static GLTF file

    :param borehole: borehole data
    :param param_obj: object containing command line parameters
    :return: config dictionary
    '''
    j_dict = {}
    j_dict['type'] = 'GLTFObject'
    x_m, y_m = convert_coords(param_obj.BOREHOLE_CRS, param_obj.MODEL_CRS,
                              [borehole.x, borehole.y])
    j_dict['position'] = [x_m, y_m, borehole.z]
    j_dict['model_url'] = make_borehole_filename(borehole.name) + ".gltf"
    j_dict['display_name'] = borehole.name
    j_dict['include'] = True
    j_dict['displayed'] = True
    return j_dict


def get_boreholes(reader, qdb, param_obj, output_mode='GLTF', dest_dir=''):
    ''' Retrieves borehole data and writes 3D model files to a directory or a blob \
        If 'dest_dir' is supplied, then files are written \
        If output_mode != 'GLTF' then 'dest_dir' must not be ''

    :param reader: NVCLReader object
    :param qdb: opened query database 'QueryDB' object
    :param param_obj: input parameters
    :param output_mode: optional flag, when set to 'GLTF' outputs GLTF to file/blob, \
                        else outputs COLLADA (.dae) to file
    :param dest_dir: optional directory where 3D model files are written
    :returns: config object list and optional GLTF blob object
    '''
    LOGGER.debug(f"get_boreholes({param_obj}, {output_mode}, {dest_dir})")

    # Get all NVCL scanned boreholes within BBOX
    borehole_list = reader.get_boreholes_list()
    if not borehole_list:
        LOGGER.warning(f"No NVCL boreholes found for '{param_obj.modelUrlPath}' model")
        return [], None

    height_res = 10.0
    LOGGER.debug(f"borehole_list = {borehole_list}")
    blob_obj = None
    # Parse response for all boreholes, make COLLADA files
    bh_cnt = 0
    loadconfig_list = []

    # Loop over list of SimpleNamespace objects
    for borehole in borehole_list:

        # Get borehole information dictionary, and add to query db
        bh_info_dict = get_bh_info_dict(borehole, param_obj)
        LOGGER.debug(f"{bh_info_dict=}")
        LOGGER.debug(f"{param_obj=}")
        is_ok, p_obj = qdb.add_part(json.dumps(bh_info_dict))
        if not is_ok:
            LOGGER.warning(f"Cannot add part to db: {p_obj}")
            continue

        # Does 'borehole' have ['name', 'x', 'y', 'z', 'nvcl_id'] attributes?
        if all(key in vars(borehole) for key in ['name', 'x', 'y', 'z', 'nvcl_id']):
            bh_data_dict, base_xyz = get_nvcl_data(reader, param_obj.MODEL_CRS, height_res,
                                                   borehole.x, borehole.y, borehole.z, borehole.nvcl_id)
            if bh_data_dict == {}:
                LOGGER.warning(f"NVCL data not available for {borehole.nvcl_id}")
                continue
            # If there's NVCL data, then create the borehole
            first_depth = -1
            # pylint: disable=W0612
            LOGGER.debug("Assembling database")
            for vert_list, indices, colour_idx, depth, rgba_colour, class_dict, mesh_name in \
                colour_borehole_gen(base_xyz, borehole.name, bh_data_dict, height_res):
                if first_depth < 0:
                    first_depth = int(depth)
                is_ok, s_obj = qdb.add_segment(json.dumps(class_dict))
                if not is_ok:
                    LOGGER.warning(f"Cannot add segment to db: {s_obj}")
                    continue
                # Using 'make_borehole_label()' ensures that name is the same
                # in both db and GLTF file
                bh_label = make_borehole_label(borehole.name, first_depth)
                bh_str = f"{bh_label.decode('utf-8')}_{colour_idx}"
                is_ok, r_obj = qdb.add_query(bh_str, param_obj.modelUrlPath,
                                             s_obj, p_obj, None, None)
                if not is_ok:
                    LOGGER.warning(f"Cannot add query to db: {r_obj}")
                    continue
                LOGGER.debug(f"ADD_QUERY({mesh_name}, {param_obj.modelUrlPath})")

            LOGGER.debug("Writing GLTFs")
            file_name = make_borehole_filename(borehole.name)
            if output_mode == 'GLTF':
                blob_obj = EXPORT_KIT.write_borehole(base_xyz, borehole.name,
                                                     bh_data_dict, height_res,
                                                     os.path.join(dest_dir, file_name))

            elif dest_dir != '':
                import exports.collada2gltf
                from exports.collada_kit import ColladaKit
                export_kit = ColladaKit(LOG_LVL)
                export_kit.write_borehole(base_xyz, borehole.name, bh_data_dict,
                                          height_res, os.path.join(dest_dir, file_name))
                blob_obj = None
            else:
                LOGGER.warning("ColladaKit cannot write blobs")
                sys.exit(1)
            loadconfig_list.append(get_loadconfig_dict(borehole, param_obj))
            bh_cnt += 1
            LOGGER.debug("Next BH")

    LOGGER.info(f"Found NVCL data for {bh_cnt}/{len(borehole_list)} boreholes")
    if output_mode != 'GLTF':
        # Convert COLLADA files to GLTF
        exports.collada2gltf.convert_dir(dest_dir, "Borehole*.dae")
        # Return borehole objects

    LOGGER.debug(f"Returning: loadconfig_list, blobobj = {loadconfig_list}, {blob_obj}")
    return loadconfig_list, blob_obj


def process_single(dest_dir, input_file, db_name, overwrite_db=True):
    ''' Process a single model's boreholes

    :param dest_dir: directory to output database and files
    :param input_file: conversion parameter file
    :param db_name: name of database
    :param overwrite_db: optional (default True) remove all current database tables or not

    '''
    LOGGER.info(f"Processing {input_file}")
    out_filename = os.path.join(dest_dir, 'borehole_' + os.path.basename(input_file))
    input_params = get_input_conv_param_bh(input_file)
    builder_params = {}
    # NB: Only supports a subset of nvcl_kit parameters
    for param in ['bbox', 'wfs_version', 'wfs_url', 'nvcl_url', 'max_boreholes']:
        if hasattr(input_params, param.upper()):
            builder_params[param] = getattr(input_params, param.upper())
    bh_params = param_builder(input_params.PROVIDER, **builder_params)
    if not bh_params:
        LOGGER.error(f"Cannot build parameters from : {input_file}")
        return
    reader = NVCLReader(bh_params)
    if reader.wfs is None:
        LOGGER.error("Cannot contact web service or no boreholes in range")
        return
    qdb = QueryDB(overwrite=overwrite_db, db_name=db_name)
    err_str = qdb.get_error()
    if err_str != '':
        LOGGER.error(f"Cannot open/create database: {err_str}")
        sys.exit(1)
    # pylint: disable=W0612
    borehole_loadconfig, none_obj = get_boreholes(reader, qdb, input_params, output_mode='GLTF',
                                                  dest_dir=dest_dir)
    LOGGER.debug(f"borehole_loadconfig = {borehole_loadconfig}")
    if borehole_loadconfig:
        LOGGER.info(f"Writing to: {out_filename}")
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
        LOGGER.warning(f"Output directory {ARGS.dest_dir} does not exist")
        try:
            LOGGER.info(f"Creating {ARGS.dest_dir}")
            os.mkdir(ARGS.dest_dir)
        except OSError as os_exc:
            LOGGER.error(f"Cannot create dir {ARGS.dest_dir}: {os_exc}")
            sys.exit(1)

    # Check input file
    if getattr(ARGS, 'input', None) is not None:
        if not os.path.isfile(ARGS.input):
            LOGGER.error(f"Input file does not exist: {ARGS.input}")
            sys.exit(1)
        process_single(ARGS.dest_dir, ARGS.input, os.path.join(ARGS.dest_dir, ARGS.database))

    # Check batch file
    elif getattr(ARGS, 'batch', None) is not None:
        if not os.path.isfile(ARGS.batch):
            LOGGER.error(f"Batch file does not exist: {ARGS.batch}")
            sys.exit(1)
        db_file = os.path.join(ARGS.dest_dir, ARGS.database)
        # Remove db file
        if os.path.exists(db_file):
            LOGGER.info(f"Removing {db_file}")
            try:
                os.remove(db_file)
            except OSError as os_exc:
                LOGGER.error(f"Cannot remove db file {db_file}: {os_exc}")
                sys.exit(1)
        with open(ARGS.batch, 'r') as fp:
            for line in fp:
                # Skip lines starting with '#'
                if line[0] != '#':
                    process_single(ARGS.dest_dir, line.rstrip('\n'), db_file, overwrite_db=False)
    else:
        print("No input file or batch file specified\n")
        PARSER.print_help()
