'''
 A collection of Python functions used to create boreholes and fetch NVCL borehole data
'''

import logging, sys

from lib.coords import convert_coords
from nvcl_kit.reader import NVCLReader
from lib.exports.gltf_kit import GltfKit
from nvcl_kit.generators import gen_scalar_by_depth
from nvcl_kit.constants import Scalar
from nvcl_kit.param_builder import param_builder


LOG_LVL = logging.DEBUG
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



def get_blob_boreholes(borehole_dict, model_param_dict):
    ''' Retrieves borehole data and writes 3D model files to a blob

    :param borehole_dict: information about borehole
    :param model_param_dict: input parameters, contains 'PROVIDER'
    :returns: GLTF blob object
    '''
    LOGGER.debug(f"get_blob_boreholes({borehole_dict}, {model_param_dict})")
    # Height resolution (depth in metres between data points)
    height_res = 10.0

    param_obj = param_builder(model_param_dict.PROVIDER)
    reader = NVCLReader(param_obj)
    if reader.wfs is not None and all(key in borehole_dict for key in ['name', 'x', 'y', 'z', 'nvcl_id']):
        bh_data_dict, base_xyz = get_nvcl_data(reader, param_obj, model_param_dict.MODEL_CRS, height_res, borehole_dict['x'], borehole_dict['y'], borehole_dict['z'], borehole_dict['nvcl_id'])

        # If there's data, then create the borehole
        if bh_data_dict != {}:
            gltf_kit = GltfKit(LOG_LVL)
            blob_obj = gltf_kit.write_borehole(base_xyz, borehole_dict['name'],
                                                 bh_data_dict, height_res, '')
            LOGGER.debug(f"Returning: blob_obj = {blob_obj}")
            return blob_obj

    LOGGER.debug("No borehole data")
    return None


def get_nvcl_data(reader, param_obj, output_crs, height_res, x, y, z, nvcl_id):
    ''' Process the output of NVCL_kit's 'get_imagelog_data()'

        :param reader: NVCL_Kit object
        :param param_obj: NVCL_Kit constructor input
        :param output_crs: borehole coordinates will be output in this CRS
        :param height_res: borehole data height resolution (float, metres)
        :param x,y,z: x,y,z coordinates of borehole collar
        :param nvcl_id: NVCL id of borehole
        :returns: dictionary: key: depth (float) \
                              value: SimpleNamespace('classText', 'className', 'colour') \
                  Returns empty dict upon error or no data \
                  and 'base_xyz' - (x,y,z) converted coordinate tuple in borehole CRS
    '''
    x_m, y_m = convert_coords(param_obj.BOREHOLE_CRS, output_crs, [x, y])
    base_xyz = (x_m, y_m, z)
    ret_dict = {}
    # Look for NVCL mineral data
    # For the moment, only process 'Grp1 uTSAS'
    # Min1,2,3 = 1st, 2nd, 3rd most common mineral
    # Grp1,2,3 = 1st, 2nd, 3rd most common group of minerals
    # uTSAV = visible light, uTSAS = shortwave IR, uTSAT = thermal IR
    for nvcl_id, log_id, sca_list in gen_scalar_by_depth(reader, nvcl_id_list=[nvcl_id], scalar_class=Scalar.Grp1_uTSAS, log_type='1', resolution=height_res):
        for depth in sca_list:
            ret_dict[depth] = sca_list[depth]
    return ret_dict, base_xyz
