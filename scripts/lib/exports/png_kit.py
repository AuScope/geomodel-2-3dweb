import os
import sys
import logging
import array
import PIL
from lib.db.style.false_colour import make_false_colour_tup

class PNG_KIT:
    ''' Class used to output PNG files, given geometry, style and metadata data structures
    '''

    def __init__(self, debug_level):
        ''' Initialise class

        :param debug_level: debug level taken from python's 'logging' module
        '''
        # Set up logging, use an attribute of class name so it is only called once
        if not hasattr(PNG_KIT, 'logger'):
            PNG_KIT.logger = logging.getLogger(__name__)

            # Create console handler
            handler = logging.StreamHandler(sys.stdout)

            # Create formatter
            formatter = logging.Formatter('%(asctime)s -- %(name)s -- %(levelname)s - %(message)s')

            # Add formatter to ch
            handler.setFormatter(formatter)

            # Add handler to logger and set level
            PNG_KIT.logger.addHandler(handler)

        PNG_KIT.logger.setLevel(debug_level)
        self.logger = PNG_KIT.logger


    def write_single_voxel_png(self, geom_obj, style_obj, meta_obj, file_name):
        ''' Writes out a PNG file of the top layer of the voxel data

        :param geom_obj: MODEL_GEOMETRY object that holds voxel data
        :param style_obj: SYTLE object, contains colour map
        :param meta_obj: FILENAME object, contains object information
        :param file_name: filename of PNG file, without extension
        '''
        self.logger.debug("write_single_voxel_png(%s)",file_name)
        colour_arr = array.array("B")
        z = geom_obj.vol_sz[2]-1
        pixel_cnt = 0
        colour_map = style_obj.get_colour_table()
        self.logger.debug("style_obj.get_colour_table() = %s", repr(colour_map))
        self.logger.debug("geom_obj.get_min_data() = %s", repr(geom_obj.get_min_data()))
        self.logger.debug("geom_obj.get_max_data() = %s", repr(geom_obj.get_max_data()))
        # If colour table is provided within source file, use it
        if len(colour_map) > 0:
            self.logger.debug("Using style colour map")
            for x in range(0, geom_obj.vol_sz[0]):
                for y in range(0, geom_obj.vol_sz[1]):
                    try:
                        #(r,g,b) = colour_map[int(geom_obj.vol_data[x][y][z] - geom_obj.get_min_data())]
                        (r,g,b) = colour_map[int(geom_obj.vol_data[x][y][z])]
                    except ValueError:
                        (r,g,b) = (0.0, 0.0, 0.0)
                    pixel_colour = [int(r*255.0), int(g*255.0), int(b*255.0)]
                    colour_arr.fromlist(pixel_colour)
                    pixel_cnt += 1
        # Else use a false colour map
        else:
            self.logger.debug("Using false colour map")
            for x in range(0, geom_obj.vol_sz[0]):
                for y in range(0, geom_obj.vol_sz[1]):
                    try:
                        (r,g,b,a) = make_false_colour_tup(geom_obj.vol_data[x][y][z], geom_obj.get_min_data(), geom_obj.get_max_data())
                    except ValueError:
                        (r,g,b,a) = (0.0, 0.0, 0.0, 0.0)
                    pixel_colour = [int(r*255.0), int(g*255.0), int(b*255.0)]
                    colour_arr.fromlist(pixel_colour)
                    pixel_cnt += 1

        img = PIL.Image.frombytes('RGB', (geom_obj.vol_sz[1], geom_obj.vol_sz[0]), colour_arr.tobytes())
        self.logger.info("Writing PNG file: %s.PNG", file_name)
        img.save(file_name+".PNG")
        property_name = meta_obj.get_property_name()
        if len(property_name) > 0:
            label_str = property_name
        else:
            label_str = meta_obj.name
        popup_dict = { os.path.basename(file_name): { 'title': label_str, 'name': label_str } }
        return popup_dict

