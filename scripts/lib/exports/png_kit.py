"""
Contains PngKit class
"""
import os
import sys
import logging
import array
import PIL

from lib.db.style.false_colour import make_false_colour_tup
from lib.exports.export_kit import ExportKit

class PngKit(ExportKit):
    ''' Class used to output PNG files, given geometry, style and metadata data structures
    '''

    def __init__(self, debug_level):
        ''' Initialise class

        :param debug_level: debug level taken from Python's 'logging' module
        '''
        # Call parent class
        ExportKit.__init__(self, debug_level)


    def write_single_voxel_png(self, geom_obj, style_obj, meta_obj, file_name):
        ''' Writes out a PNG file of the top layer of the voxel data

        :param geom_obj: MODEL_GEOMETRY object that holds voxel data
        :param style_obj: SYTLE object, contains colour map
        :param meta_obj: FILENAME object, contains object information
        :param file_name: filename of PNG file, without extension
        '''
        self.logger.debug(f"write_single_voxel_png({file_name})")
        colour_arr = array.array("B")
        z_val = geom_obj.vol_sz[2] - 1
        pixel_cnt = 0
        # Volume data are RGBA, data is stored in geom_obj's xyz_data
        if geom_obj.vol_data_type == 'RGBA':
            self.logger.debug("Using in-situ RGBA data")
            # Use False to get data using IJK int indexes
            xyz_data = geom_obj.get_loose_3d_data(is_xyz=False)
            for x_val in range(0, geom_obj.vol_sz[0]):
                for y_val in range(0, geom_obj.vol_sz[1]):
                    try:
                        pixel_colour = xyz_data.get((x_val, y_val, z_val), (0, 0, 0, 0))
                    except ValueError:
                        pixel_colour = (0, 0, 0, 0)
                    colour_arr.fromlist(list(pixel_colour))
                    pixel_cnt += 1
        # Volume data are floats, stored in geom_obj's vol_data
        else:  
            colour_map = style_obj.get_colour_table()
            self.logger.debug(f"style_obj.get_colour_table() = {colour_map}")
            self.logger.debug(f"geom_obj.get_min_data() = {geom_obj.get_min_data()}")
            self.logger.debug(f"geom_obj.get_max_data() = {geom_obj.get_max_data()}")
            # If colour table is provided within source file, use it
            if colour_map:
                self.logger.debug("Using style colour map")
                for x_val in range(0, geom_obj.vol_sz[0]):
                    for y_val in range(0, geom_obj.vol_sz[1]):
                        try:
                            val = int(geom_obj.vol_data[x_val][y_val][z_val])
                            if val in colour_map:
                                (r_val, g_val, b_val, a_val) = colour_map[val]
                            else:
                                # If key val not in map, try previous one in colour map
                                less_arr = [k for k in list(colour_map.keys()) if k < val]
                                if len(less_arr) > 0:
                                    col_key = less_arr[-1]
                                    (r_val, g_val, b_val, a_val) = colour_map[col_key]
                                    self.logger.debug(f"Colour map missing value at {val}, using {col_key} instead")
                                else:
                                    # Use invisible black colour if no previous one exists
                                    (r_val, g_val, b_val, a_val) = (0.0, 0.0, 0.0, 0.0)
                                    self.logger.warning(f"Colour map missing value at {val}, using RGBA=0,0,0,0 instead")
                            pixel_colour = [int(r_val * 255.0), int(g_val * 255.0), int(b_val * 255.0),
                                            int(a_val * 255.0)]
                        except ValueError:
                            # Bad values in colour map ?
                            pixel_colour = [0, 0, 0, 0]
                            self.logger.warning("Bad value in colour map, using RGBA=0,0,0,0 instead")
                        colour_arr.fromlist(pixel_colour)
                        pixel_cnt += 1
            # Else use a false colour map
            else:
                self.logger.debug("Using false colour map")
                for x_val in range(0, geom_obj.vol_sz[0]):
                    for y_val in range(0, geom_obj.vol_sz[1]):
                        try:
                            # pylint:disable=W0612
                            (r_val, g_val, b_val, a_val) = make_false_colour_tup(
                                geom_obj.vol_data[x_val][y_val][z_val],
                                geom_obj.get_min_data(),
                                geom_obj.get_max_data())
                            pixel_colour = [int(r_val * 255.0), int(g_val * 255.0), int(b_val * 255.0),
                                            int(a_val * 255.0)]
                        except ValueError:
                            pixel_colour = [0, 0, 0, 0]
                        colour_arr.fromlist(pixel_colour)
                        pixel_cnt += 1

        img = PIL.Image.frombytes('RGBA', (geom_obj.vol_sz[1], geom_obj.vol_sz[0]),
                                  colour_arr.tobytes())
        self.logger.info(f"Writing PNG file: {file_name}.PNG")
        try:
            img.save(file_name + ".PNG")
        except OSError as os_exc:
            self.logger.error(f"ERROR - Cannot write file {file_name}.PNG: {os_exc}")
            return {}
        property_name = meta_obj.get_property_name()
        if property_name:
            label_str = property_name
        else:
            label_str = meta_obj.name
        popup_dict = {os.path.basename(file_name): {'title': label_str, 'name': label_str}}
        return popup_dict
