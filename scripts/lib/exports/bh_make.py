'''
 A collection of Python functions used to create boreholes and fetch NVCL borehole data
'''

import logging, sys

from lib.coords import convert_coords
from nvcl_kit.reader import NVCLReader
from lib.exports.assimp_kit import write_borehole


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
            blob_obj = write_borehole(base_xyz, borehole_dict['name'],
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
        :returns: dictionary: key: depth (float) \
                              value: SimpleNamespace('classText', 'className', 'colour') \
                  Returns empty dict upon error or no data \
                  and 'base_xyz' - (x,y,z) converted coordinate tuple in borehole CRS
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
