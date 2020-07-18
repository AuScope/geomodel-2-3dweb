"""
Contains the NetCDFKit class
"""

import sys
import logging
from collections import defaultdict
import numpy
from netCDF4 import Dataset


from lib.db.style.false_colour import calculate_false_colour_num, make_false_colour_tup
import ExportKit

class NetCDFKit(ExportKit):
    ''' Class used to output NetCDF4 files, given geometry, style and metadata data structures
    '''

    def __init__(self, debug_level):
        ''' Initialise class

        :param debug_level: debug level taken from python's 'logging' module
        '''
        # Call parent class
        ExportKit.__init__(self, debug_level)


    def write_points(self, geom_obj, style_obj, meta_obj, out_filename):
        ''' Write out a NetCDF file from a point geometry file

        :param geom_obj: MODEL_GEOMETRY object that hold geometry and text
        :param style_obj: STYLE object containing colour info
        :param meta_obj: METADATA object, used for labelling
        :param out_filename: path & filename of NetCDF file to output, without extension
        '''
        self.logger.debug("NetCDFKit.write_points(%s)", out_filename)
        self.logger.debug("NetCDFKit.write_points() geom_obj=%s", repr(geom_obj))

        if not geom_obj.is_point():
            self.logger.error("ERROR - Cannot use NetCDFKit.write_points for line, triangle or volume")
            sys.exit(1)

        root_grp = Dataset(out_filename+".nc", "w", format="NETCDF4")
        points_grp = root_grp.createGroup("points")
        points_grp.createDimension('points list', None)

        # Just does a single fp value for each XYZ, later expand to multiple values
        xyzd_dtype = numpy.dtype([("x", numpy.float32), ("y", numpy.float32), ("z", numpy.float32), ("data", numpy.float32)])
        points_type = points_grp.createCompoundType(xyzd_dtype, "xyzd_dtype")

        size = len(geom_obj.vrtx_arr)
        popup_dict = {}
        geometry_name = meta_obj.name
        points_list = points_grp.createVariable("points_list", points_type, "points list", zlib=True)

        data = numpy.empty(size, points_type)
        node_list = []
        prop_dict = geom_obj.get_loose_3d_data(True)

        geom_label=''
        for point_cnt, vrtx in enumerate(geom_obj.vrtx_arr):
            data[point_cnt]["x"] = vrtx.xyz[0]
            data[point_cnt]["y"] = vrtx.xyz[1]
            data[point_cnt]["z"] = vrtx.xyz[2]
            geom_label = "{0}-{1:010d}".format(geometry_name, point_cnt)

            # Create popup info
            popup_dict[geom_label] = {'name': meta_obj.get_property_name(),
                                      'title': geometry_name.replace('_', ' ')}
            if vrtx.xyz in prop_dict:
                popup_dict[geom_label]['val'] = prop_dict[vrtx.xyz]
                try:
                    data[point_cnt]["data"] = float(prop_dict[vrtx.xyz])
                except ValueError:
                    pass

        # Write points to file
        self.logger.info("write_points() Writing NetCDF file: %s.nc", out_filename)
        points_list[:] = data
        try:
            root_grp.close()
        except OSError as os_exc:
            self.logger.error("ERROR - Cannot write file %s.nc: %s", out_filename, repr(os_exc))
            return {}

        return popup_dict

#  END OF NetCDFKit CLASS
