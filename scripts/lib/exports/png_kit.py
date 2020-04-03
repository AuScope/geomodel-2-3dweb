"""
Contains PngKit class
"""
import os
import sys
import logging
import array
import PIL
from lib.db.style.false_colour import make_false_colour_tup

class PngKit:
    ''' Class used to output PNG files, given geometry, style and metadata data structures
    '''

    def __init__(self, debug_level):
        ''' Initialise class

        :param debug_level: debug level taken from python's 'logging' module
        '''
        # Set up logging, use an attribute of class name so it is only called once
        if not hasattr(PngKit, 'logger'):
            PngKit.logger = logging.getLogger(__name__)

            # Create console handler
            handler = logging.StreamHandler(sys.stdout)

            # Create formatter
            formatter = logging.Formatter('%(asctime)s -- %(name)s -- %(levelname)s - %(message)s')

            # Add formatter to ch
            handler.setFormatter(formatter)

            # Add handler to logger and set level
            PngKit.logger.addHandler(handler)

        PngKit.logger.setLevel(debug_level)
        self.logger = PngKit.logger


    def write_single_voxel_png(self, geom_obj, style_obj, meta_obj, file_name):
        ''' Writes out a PNG file of the top layer of the voxel data

        :param geom_obj: MODEL_GEOMETRY object that holds voxel data
        :param style_obj: SYTLE object, contains colour map
        :param meta_obj: FILENAME object, contains object information
        :param file_name: filename of PNG file, without extension
        '''
        self.logger.debug("write_single_voxel_png(%s)", file_name)
        colour_arr = array.array("B")
        z_val = geom_obj.vol_sz[2]-1
        pixel_cnt = 0
        # Volume data are RGBA, data is stored in geom_obj's xyz_data
        if geom_obj.vol_data_type == 'RGBA':
            self.logger.debug("Using in-situ RGBA data")
            xyz_data = geom_obj.get_xyz_data()
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
            self.logger.debug("style_obj.get_colour_table() = %s", repr(colour_map))
            self.logger.debug("geom_obj.get_min_data() = %s", repr(geom_obj.get_min_data()))
            self.logger.debug("geom_obj.get_max_data() = %s", repr(geom_obj.get_max_data()))
            # If colour table is provided within source file, use it
            if colour_map:
                self.logger.debug("Using style colour map")
                for x_val in range(0, geom_obj.vol_sz[0]):
                    for y_val in range(0, geom_obj.vol_sz[1]):
                        try:
                            val = int(geom_obj.vol_data[x_val][y_val][z_val])
                            (r_val, g_val, b_val, a_val) = colour_map[val]
                            pixel_colour = [int(r_val*255.0), int(g_val*255.0), int(b_val*255.0),
                                            int(a_val*255.0)]
                        except ValueError:
                            pixel_colour = [0, 0, 0, 0]
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
                            pixel_colour = [int(r_val*255.0), int(g_val*255.0), int(b_val*255.0),
                                            int(a_val*255.0)]
                        except ValueError:
                            pixel_colour = [0, 0, 0, 0]
                        colour_arr.fromlist(pixel_colour)
                        pixel_cnt += 1

        img = PIL.Image.frombytes('RGBA', (geom_obj.vol_sz[1], geom_obj.vol_sz[0]),
                                  colour_arr.tobytes())
        self.logger.info("Writing PNG file: %s.PNG", file_name)
        try:
            img.save(file_name+".PNG")
        except OSError as os_exc:
            self.logger.error("ERROR - Cannot write file %s.PNG: %s", file_name, repr(os_exc))
            return {}
        property_name = meta_obj.get_property_name()
        if property_name:
            label_str = property_name
        else:
            label_str = meta_obj.name
        popup_dict = {os.path.basename(file_name): {'title': label_str, 'name': label_str}}
        return popup_dict
