"""
Contains the GZSONKit class
"""

import sys
import logging
from collections import defaultdict
import numpy
import gzip
import json
from geojson import Feature, FeatureCollection, Point, LineString


from lib.db.style.false_colour import make_false_colour_tup
from lib.exports.export_kit import ExportKit

class GZSONKit(ExportKit):
    ''' Class used to output large numbers of points and lines to GZipped GEOJSON files, given geometry, style and
        metadata data structures. Why do we need this?
        1. Unfortunately GLTF 2.0 does not fully specify points and lines (https://github.com/KhronosGroup/glTF/issues/1277)
        2. Rendering points and lines as GLTF rectangles (pairs of triangles) is not feasible when there are hundreds
           of thousands lines and points
        So I have to send the data in compressed format and draw my own lines and points
    '''

    def __init__(self, debug_level):
        ''' Initialise class

        :param debug_level: debug level taken from python's 'logging' module
        '''
        # Call parent class
        ExportKit.__init__(self, debug_level)


    def write_points(self, geom_obj, style_obj, meta_obj, out_filename):
        ''' Write out a GZipped GEOJSON file containing point geometries

        :param geom_obj: MODEL_GEOMETRY object that holds geometry and text
        :param style_obj: STYLE object containing colour info
        :param meta_obj: METADATA object, used for labelling
        :param out_filename: path & filename of GZSON file to output, without extension
        '''
        self.logger.debug("GZSONKit.write_points(%s)", out_filename)
        self.logger.debug("GZSONKit.write_points() geom_obj=%s", repr(geom_obj))

        if not geom_obj.is_point():
            self.logger.error("ERROR - Cannot use GZSONKit.write_points for line, triangle or volume")
            sys.exit(1)

        popup_dict = {}
        geometry_name = meta_obj.name

        feature_list = []
        prop_dict = geom_obj.get_loose_3d_data(True)
        prop_max = geom_obj.get_max_data()
        prop_min = geom_obj.get_min_data()

        # geom_label=''
        for point_cnt, vrtx in enumerate(geom_obj.vrtx_arr):
            geom_label = "{0}-{1:010d}".format(geometry_name, point_cnt)

            # 'popup_dict' not used at the moment
            ## Create popup info
            #popup_dict[geom_label] = {'name': meta_obj.get_property_name(),
            #                          'title': geometry_name.replace('_', ' ')}
            # Create a list of features
            if vrtx.xyz in prop_dict:
                # Not used at the moment
                #popup_dict[geom_label]['val'] = prop_dict[vrtx.xyz]
                try:
                    pt = Point(vrtx.xyz)
                    colour_tup = make_false_colour_tup(float(prop_dict[vrtx.xyz]), prop_min, prop_max)
                    feature_list.append(Feature(geometry=pt, properties={"colour": colour_tup,
                                                                         "val": f"{prop_dict[vrtx.xyz]:.3}"}))
                except (ValueError, TypeError):
                    # Makes white points when no colour is available
                    feature_list.append(Feature(geometry=pt, properties={"colour": (1.0, 1.0, 1.0, 1.0),
                                                                         "val": "Unknown"}))

        # Write feature collecton to file
        self.logger.info("write_points() Writing gzson file: %s.gzson", out_filename)
        if self._write_file(out_filename, FeatureCollection(feature_list)):
            return popup_dict
        return {}
            
    def write_lines(self, geom_obj, style_obj, meta_obj, out_filename):
        ''' Write out a GZSON (GZipped GEOJSON) file containing line geometries

        :param geom_obj: MODEL_GEOMETRY object that holds geometry and text
        :param style_obj: STYLE object containing colour info
        :param meta_obj: METADATA object, used for labelling
        :param out_filename: path & filename of GZSON file to output, without extension
        '''
        self.logger.info("GZSONKit.write_lines(%s)", out_filename)
        self.logger.info("GZSONKit.write_lines() geom_obj=%s", repr(geom_obj))

        if not geom_obj.is_line():
            self.logger.error("ERROR - Cannot use GZSONKit.write_lines for point, triangle or volume")
            sys.exit(1)

        # geometry_name = meta_obj.name
        feature_list = []
        prop_dict = geom_obj.get_loose_3d_data(True)

        # geom_label=''
        for seg_cnt, seg in enumerate(geom_obj.seg_arr):
            xyz1 = geom_obj.vrtx_arr[seg.ab[0]-1]
            xyz2 = geom_obj.vrtx_arr[seg.ab[1]-1]
            # Create popup info
            # Not used at present
            # geom_label = "{0}-{1:010d}".format(geometry_name, seg_cnt)
            # popup_dict[geom_label] = {'name': meta_obj.get_property_name(),
            #                          'title': geometry_name.replace('_', ' ')}
            # Grab first data value
            # Create a list of line features
            # Not used at present
            # popup_dict[geom_label]['val'] = prop_dict[coord.xyz]
            ls = LineString([xyz1.xyz, xyz2.xyz])
            if style_obj.has_single_colour():
                feature_list.append(Feature(geometry=ls, properties={"colour": style_obj.get_rgba_tup()}))
            else:
                # If no colour, then add yellow lines
                feature_list.append(Feature(geometry=ls, properties={"colour": (1.0, 1.0, 0.0, 1.0)}))

        # Write feature collection to file
        self.logger.info("write_lines() Writing gzson file: %s.gzson", out_filename)
        if self._write_file(out_filename, FeatureCollection(feature_list)):
            return {}  # popup_dict
        return {}

    def _write_file(self, out_filename, json_obj):
        """ Write points to file
        :param out_filename: path & filename of GZSON file to output, without extension
        :param json_obj: JSON object to write to file
        """
        self.logger.info("write_points() Writing gzson file: %s.gzson", out_filename)
        json_str = json.dumps(json_obj) + "\n"
        json_byt = json_str.encode('utf-8', 'ignore')
        try:
            with gzip.open(out_filename+'.gzson', "wb") as fp:
                fp.write(json_byt)
        except OSError as os_exc:
            self.logger.error("ERROR - Cannot write file %s.gzson: %s", out_filename, repr(os_exc))
            return False
        return True

#  END OF GZSONKit CLASS
