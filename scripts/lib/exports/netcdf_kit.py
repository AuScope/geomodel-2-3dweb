"""
Contains the NetCDFKit class
"""

import sys
import logging
from collections import defaultdict
import numpy
from netCDF4 import Dataset


from lib.db.style.false_colour import calculate_false_colour_num, make_false_colour_tup
from lib.exports.export_kit import ExportKit

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
        ''' Write out a NetCDF file containing point geometries

        :param geom_obj: MODEL_GEOMETRY object that holds geometry and text
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
                except (ValueError, TypeError):
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

    def write_lines(self, geom_obj, style_obj, meta_obj, out_filename):
        ''' Write out a NetCDF file containing line geometries

        :param geom_obj: MODEL_GEOMETRY object that holds geometry and text
        :param style_obj: STYLE object containing colour info
        :param meta_obj: METADATA object, used for labelling
        :param out_filename: path & filename of NetCDF file to output, without extension
        '''
        self.logger.debug("NetCDFKit.write_lines(%s)", out_filename)
        self.logger.debug("NetCDFKit.write_lines() geom_obj=%s", repr(geom_obj))

        if not geom_obj.is_line():
            self.logger.error("ERROR - Cannot use NetCDFKit.write_lines for point, triangle or volume")
            sys.exit(1)

        root_grp = Dataset(out_filename+".nc", "w", format="NETCDF4")
        lines_grp = root_grp.createGroup("lines")
        lines_grp.createDimension('lines list', None)

        # Just does a single fp value for each XYZ pair, later expand to multiple values
        xyzxyzd_dtype = numpy.dtype([("x1", numpy.float32), ("y1", numpy.float32), ("z1", numpy.float32),
                                  ("x2", numpy.float32), ("y2", numpy.float32), ("z2", numpy.float32),
                                  ("data", numpy.float32)])
        lines_type = lines_grp.createCompoundType(xyzxyzd_dtype, "xyzxyzd_dtype")

        size = len(geom_obj.seg_arr)
        popup_dict = {}
        geometry_name = meta_obj.name
        lines_list = lines_grp.createVariable("lines_list", lines_type, "lines list", zlib=True)

        data = numpy.empty(size, lines_type)
        prop_dict = geom_obj.get_loose_3d_data(True)

        geom_label=''
        for seg_cnt, seg in enumerate(geom_obj.seg_arr):
            xyz1 = geom_obj.vrtx_arr[seg.ab[0]-1]
            xyz2 = geom_obj.vrtx_arr[seg.ab[1]-1]
            data[seg_cnt]["x1"] = xyz1.xyz[0]
            data[seg_cnt]["y1"] = xyz1.xyz[1]
            data[seg_cnt]["z1"] = xyz1.xyz[2]
            data[seg_cnt]["x2"] = xyz2.xyz[0]
            data[seg_cnt]["y2"] = xyz2.xyz[1]
            data[seg_cnt]["z2"] = xyz2.xyz[2]
            geom_label = "{0}-{1:010d}".format(geometry_name, seg_cnt)

            # Create popup info
            # Not used at present
            # popup_dict[geom_label] = {'name': meta_obj.get_property_name(),
            #                          'title': geometry_name.replace('_', ' ')}
            # Grab first data value
            for coord in (xyz1, xyz2):
                if coord.xyz in prop_dict:
                    # Not used at present
                    # popup_dict[geom_label]['val'] = prop_dict[coord.xyz]
                    try:
                        data[seg_cnt]["data"] = float(prop_dict[coord.xyz])
                    except (ValueError, TypeError):
                        pass
                    break

        # Write lines to file
        self.logger.info("write_lines() Writing NetCDF file: %s.nc", out_filename)
        lines_list[:] = data
        try:
            root_grp.close()
        except OSError as os_exc:
            self.logger.error("ERROR - Cannot write file %s.nc: %s", out_filename, repr(os_exc))
            return {}

        return popup_dict

#  END OF NetCDFKit CLASS
