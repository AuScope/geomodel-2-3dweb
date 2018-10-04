import os
import sys
import logging
import array
import PIL

class PNG_KIT:
    ''' Class used to output PBG files
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


    def write_vol_png(self, geom_obj, src_dir, fileName):
        ''' Writes out PNG files from voxel data

        :param geom_obj: model geometry object that holds voxel data
        :param fileName: filename of OBJ file, without extension
        :param src_filen_str: filename of source gocad file
        '''
        popup_list = []
        self.logger.debug("write_vol_png(%s,%s)", src_dir, fileName)
        if len(geom_obj.prop_dict) > 0:
            for map_idx in sorted(geom_obj.prop_dict):
                popup_list.append(self.write_single_voxel_png(geom_obj, src_dir, fileName, map_idx))
        return popup_list


    def write_single_voxel_png(self, geom_obj, style_obj, src_dir, fileName, idx):
        ''' Writes out a PNG file of the top layer of the voxel data

        :param geom_obj: model geometry object that holds voxel data
        :param style_obj: style object, contains colour map
        :param fileName: filename of OBJ file, without extension
        :param src_filen_str: filename of source gocad file
        '''
        self.logger.debug("write_single_voxel_png(%s, %s, %s)", src_dir, fileName, idx)
        colour_arr = array.array("B")
        z = geom_obj.vol_sz[2]-1
        pixel_cnt = 0
        prop_obj = geom_obj.prop_dict[idx]
        self.logger.debug("style_obj.colour_map = %s", repr(style_obj.colour_map))
        self.logger.debug("geom_obj.min_data = %s", repr(geom_obj.min_data))
        # If colour table is provided within source file, use it
        if len(style_obj.colour_map) > 0:
            for x in range(0, geom_obj.vol_sz[0]):
                for y in range(0, geom_obj.vol_sz[1]):
                    try:
                        (r,g,b) = style_obj.colour_map[int(geom_obj.vol_data[x][y][z] - geom_obj.min_data)]
                    except ValueError:
                        (r,g,b) = (0.0, 0.0, 0.0)
                    pixel_colour = [int(r*255.0), int(g*255.0), int(b*255.0)]
                    colour_arr.fromlist(pixel_colour)
                    pixel_cnt += 1
        # Else use a false colour map
        else:
            for x in range(0, geom_obj.vol_sz[0]):
                for y in range(0, geom_obj.vol_sz[1]):
                    try:
                        (r,g,b,a) = make_false_colour_tup(geom_obj.vol_data[x][y][z], geom_obj.min_data, geom_obj.min_data)
                    except ValueError:
                        (r,g,b,a) = (0.0, 0.0, 0.0, 0.0)
                    pixel_colour = [int(r*255.0), int(g*255.0), int(b*255.0)]
                    colour_arr.fromlist(pixel_colour)
                    pixel_cnt += 1

        img = PIL.Image.frombytes('RGB', (geom_obj.vol_sz[1], geom_obj.vol_sz[0]), colour_arr.tobytes())
        self.logger.info("Writing PNG file: %s", fileName+"_"+idx+".PNG")
        img.save(os.path.join(src_dir, fileName+"_"+idx+".PNG"))
        if len(meta_obj.property_name) >0:
            label_str = meta_obj.property_name
        else:
            label_str = meta_obj.name
        popup_dict = { os.path.basename(fileName+"_"+idx): { 'title': label_str, 'name': label_str } }
        return popup_dict

