'''
Functions to process multiple lines used for specialist purposes
'''

import sys
import os
import struct
import numpy as np

from lib.imports.gocad.props import PROPS


def to_xyz_min_curve(dia1, dia2):
    ''' Convert measured depth, inclination, azimuth to x,y,z via minimum curvature method

    :param dia1: tuple (measured depth, inclination, azimuth) \
                measured depth, metres, float \
                inclination, degrees, float, 0 = vertical, 90 = horizontal \
                azimuth, degrees, float, measured from North
    :param dia2: tuple (measured depth, inclination, azimuth)
    '''
    d1, i1_d, a1_d = dia1
    d2, i2_d, a2_d = dia2
    i1 = np.deg2rad(i1_d)
    i2 = np.deg2rad(i2_d)
    a1 = np.deg2rad(a1_d)
    a2 = np.deg2rad(a2_d)
    dMD = d2 - d1
    b = np.arccos(np.cos(i2 - i1) - (np.sin(i1) * np.sin(i2) * (1 - np.cos(a2 - a1))))
    if b == 0.0:
        rf = 0.0
    else:
        rf = 2 / b * np.tan(b / 2)
    dX = dMD / 2 * (np.sin(i1) * np.sin(a1) + np.sin(i2) * np.sin(a2)) * rf
    dY = dMD / 2 * (np.sin(i1) * np.cos(a1) + np.sin(i2) * np.cos(a2)) * rf
    dZ = dMD / 2 * (np.cos(i1) + np.cos(i2)) * rf
    return dX, dY, dZ


def to_dia(sdia):
    ''' Converts a 4-tuple to 3-tuple of floats

    :param sdia: 4-tuple ('STATION', d, i, a)
    :returns: True/False, three float tuple
    '''
    try:
        stat, d_str, i_str, a_str = sdia
        d = float(d_str)
        i = float(i_str)
        a = float(a_str)
    except ValueError:
        return False, []
    return True, [d, i, a]


def process_coord_hdr(self, line_gen):
    ''' Process fields within coordinate header.

    :param line_gen: line generator
    :returns: two booleans, the first is True iff reached end of sequence, \
              the second is True iff there is an unrecoverable error
    '''
    while True:
        # pylint: disable=W0612
        field, field_raw, line_str, is_last = next(line_gen)

        # End of sequence?
        if is_last:
            return True, False

        # Are we leaving coordinate system header?
        if field[0] == "END_ORIGINAL_COORDINATE_SYSTEM":
            self.logger.debug("Coord System End")
            return False, False

        # Within coordinate system header and not using the default coordinate system
        if field[0] == "NAME":
            self.coord_sys_name = field[1]
            if field[1] != "DEFAULT":
                self.uses_default_coords = False
                self.logger.debug("uses_default_coords False")

                # NOTE: I can't support non default coords yet - need to enter via command line?
                # If does not support default coords then exit
                if not self.nondefault_coords:
                    self.logger.warning("SORRY - Does not support non-DEFAULT coordinates: %s",
                                        repr(field[1]))
                    return False, True

        # Does coordinate system use inverted z-axis?
        elif field[0] == "ZPOSITIVE" and field[1] == "DEPTH":
            self.invert_zaxis = True
            self.logger.debug("invert_zaxis = %s", repr(self.invert_zaxis))

        # Axis units - check if units are kilometres, and update coordinate multiplier
        elif field[0] == "AXIS_UNIT":
            self.parse_axis_unit(field)



def process_header(self, line_gen):
    ''' Process fields in the GOCAD header

    :param line_gen: line generator
    :returns: a boolean, is True iff we are at last line
    '''
    while True:
        # pylint: disable=W0612
        field, field_raw, line_str, is_last = next(line_gen)
        # Are we on the last line?
        if is_last:
            self.logger.debug("Process header: last line")
            return True

        # Are we out of the header?
        if field[0] == "}" or is_last:
            self.logger.debug("End of header")
            return False

        # When in the HEADER get the colours
        # pylint: disable=W0612
        name_str, sep, value_str = line_str.partition(':')
        name_str = name_str.strip()
        value_str = value_str.strip()
        self.logger.debug("inHeader name_str = %s value_str = %s", name_str, value_str)
        if name_str in ('*SOLID*COLOR', '*ATOMS*COLOR', '*LINE*COLOR'):
            self.style_obj.add_rgba_tup(self.parse_colour(value_str))
            self.logger.debug("self.style_obj.rgba_tup = %s",
                              repr(self.style_obj.get_rgba_tup()))
        elif name_str[:9] == '*REGIONS*' and name_str[-12:] == '*SOLID*COLOR':
            region_name = name_str.split('*')[2]
            self.region_colour_dict[region_name] = self.parse_colour(value_str)
            self.logger.debug("region_colour_dict[%s] = %s", region_name,
                              repr(self.region_colour_dict[region_name]))
        # Get header name
        elif name_str == 'NAME':
            self.header_name = value_str.replace('/', '-')
            self.logger.debug("self.header_name = %s", self.header_name)



def process_ascii_well_path(self, line_gen, field):
    ''' Process ascii well path header

    :param line_gen: line generator
    :param field: array of field strings from first line of prop class header
    :returns: a boolean, is True iff we are at last line; well_path, list of \
             coordinates of well path; marker_list, list of markers
    '''
    self.logger.debug("START ascii well path, field = %s %s", repr(field[0]), repr(field[1]))
    zm_units = 'M'
    convert = False
    well_path = []
    marker_list = []
    while True:
        # KB = kelly bush height
        if field[0] == 'KB':
            # pylint: disable=W0612
            is_ok, kelly_b = self.parse_float(field[1])

        # PATH_ZM_UNIT 'M' or 'KM'
        if field[0] == 'PATH_ZM_UNIT':
            zm_units = field[1]
            if zm_units not in ['M', 'KM']:
                self.logger.error("Cannot process PATH_ZM_UNITS = %s", zm_units)
                sys.exit(1)

        # WREF X Y Z
        elif field[0] == 'WREF':
            is_ok, x_x, y_y, z_z = self.parse_xyz(True, field[1], field[2], field[3], False,
                                                  False)
            if not is_ok:
                self.logger.error("Cannot process WREF: %s", repr(field))
                sys.exit(1)
            well_path = [(x_x, y_y, z_z)]
            prev_stat = None

        elif field[0] == 'DEVIATION_SURVEY':
            pass

        elif field[0] == 'STATION':
            """ Well path. Format is: STATION MD INC AZ
                    MD = measured depth
                    INC = inclination (degrees)
                    AZ = azimuth (degrees)
            """
            if len(field) == 4:
                parse_ok = True
                if prev_stat:
                    ok1, dia1 = to_dia(prev_stat)
                    ok2, dia2 = to_dia(field)
                    if ok1 and ok2:
                        x_d, y_d, z_d = to_xyz_min_curve(dia1, dia2)
                        self.logger.debug("Converted from %s to %s => %f, %f, %f", repr(prev_stat), repr(field), x_d, y_d, z_d)
                        if len(well_path) > 0:
                            old_x = well_path[-1][0]
                            old_y = well_path[-1][1]
                            old_z = well_path[-1][2]
                            well_path.append((old_x + x_d, old_y + y_d, old_z + z_d))
                if parse_ok:
                    prev_stat = field

        elif field[0] == 'DATUM':
            pass

        elif field[0] == 'ZM_NMPTS':
            # pylint: disable=W0612
            is_ok, num_pts = self.parse_int(field[1])

        elif well_path is not None:
            # Well path
            # PATH meas-Z Z X-diff Y-diff
            if field[0] == 'PATH':
                convert = (zm_units == 'KM')
                is_ok, z_z, x_d, y_d = self.parse_xyz(True, field[2], field[3], field[4],
                                                      False, convert)
                if not is_ok:
                    self.logger.error("Cannot read PATH %s", repr(field))
                    sys.exit(1)
                old_x = well_path[-1][0]
                old_y = well_path[-1][1]
                well_path.append((old_x + x_d, old_y + y_d, z_z))

            # Vertex indicating path
            # VRTX X Y Z
            elif field[0] == 'VRTX':
                convert = (zm_units == 'KM')
                is_ok, x_x, y_y, z_z = self.parse_xyz(True, field[1], field[2], field[3],
                                                      False, convert)
                if not is_ok:
                    self.logger.error("Cannot read VRTX %s", repr(field))
                    sys.exit(1)
                well_path.append((x_x, y_y, z_z))

            # Well marker
            # MRKR name flag Z-meas
            elif field[0] == 'MRKR' and len(well_path)>0:
                is_ok, z_flt = self.parse_float(field[3])
                if is_ok:
                    marker_name = field[1]
                    field, marker_info = self.process_well_info(field, line_gen)
                    # NB: Does not follow the curve of the well
                    x = well_path[0][0]
                    y = well_path[0][1]
                    info = { 'depth': str(z_flt) }
                    info.update(marker_info)
                    marker_list.append({'name': marker_name,
                                        'position': [x,y,z_flt],
                                        'metadata': info})
                    continue

            # ZONE name Z-meas1 Z-meas2 index
            elif field[0] == 'ZONE' and len(well_path)>0:
                is_ok1, z1_flt = self.parse_float(field[2])
                is_ok2, z2_flt = self.parse_float(field[3])
                if is_ok1 and is_ok2 and len(well_path)>0:
                    # NB: Does not follow the curve of the well
                    x = well_path[0][0]
                    y = well_path[0][1]
                    zone_name = field[1]
                    # Put down 2 labels for zone, one for start, one for end
                    field, zone_info = self.process_well_info(field, line_gen)
                    info = { 'depth': str(z1_flt) }
                    info.update(marker_info)
                    marker_list.append({'name': zone_name+' zone start',
                                        'position': [x,y,z1_flt],
                                        'metadata': info})
                    info = { 'depth': str(z2_flt) }
                    info.update(marker_info)
                    marker_list.append({'name': zone_name+' zone end',
                                        'position': [x,y,z2_flt],
                                        'metadata': info})
                    continue


        # Read next line
        # pylint: disable=W0612
        field, field_raw, line_str, is_last = next(line_gen)
        if is_last or field[0] in ['END', 'WELL_CURVE']:
            break


    self.logger.debug("END ascii well path = %s marker_list = %s",
                      repr(well_path[1:]), repr(marker_list))

    # Do not return the first element in well_path, it is a WREF, not a PATH
    return is_last, well_path[1:], marker_list


def process_well_info(self, field, line_gen):
    ''' Process the information after a well marker or well zone is defined

    :param line_gen: line generator
    :param field: array of field strings from first line of prop class header
    :returns: a boolean, is True iff we are at last line and info dict
    '''
    info = { 'feature_names': [], 'unit_names': [] }
    is_last = False
    while not is_last:
        # UNIT name1,name2
        if field[0] == 'UNIT':
            info['unit_names'] += field[1].split(',')

        # FEATURE name1,name2
        elif field[0] == 'FEATURE':
            info['feature_names'] += field[1].split(',')

        # Read next line
        # pylint: disable=W0612
        field, field_raw, line_str, is_last = next(line_gen)

        # Break out if not a well info field
        if field[0] not in ['DIP', 'NORM', 'MREF', 'UNIT', 'NO_FEATURE', 'FEATURE']:
            break
    return field, info


def process_well_curve(self, line_gen, field):
    ''' Process well curve

    :param line_gen: line generator
    :param field: array of field strings from first line of prop class header
    :returns: a boolean, is True iff we are at last line
    '''
    is_last = False
    while not is_last:
        # Read next line
        # pylint: disable=W0612
        field, field_raw, line_str, is_last = next(line_gen)
        if field[0] == "PROPERTY":
            # Call function to get properties
            pass
        elif field[0] in ["LOG_FRAME_TYPE PERIODIC",
                          "LOG_FRAME_TOP", "LOG_FRAME_BOTTOM",
                          "LOG_FRAME_RATE", "LOG_FRAME_TYPE"]:
            pass
        elif field[0] == "ZM_UNIT":
            pass
        elif field[0] == "INTERPOLATION":
            pass
        elif field[0] == "BLOCKED_INTERPOLATION_METHOD":
            pass
        elif field[0] == "NPTS":
            pass
        elif field[0] == "SEEK":
            pass
        if field[0] in ['END', 'END_CURVE']:
            break

    return field, field_raw, is_last


def process_well_binary_file(self, file_name):
    try:
        stat_obj = os.stat(file_name)
        num_flts = int(stat_obj.st_size / 4 )
        self.logger.debug('num_flts=%s', repr(num_flts))
        with open(file_name, 'rb') as f:
            flt_arr = struct.unpack('>{}f'.format(num_flts), f.read(4*num_flts))
    except OSError as oe:
        self.logger.error("ERROR - Cannot read well binary file: %s: %s", file_name, repr(oe))
        return []
    return flt_arr


def process_prop_class_hdr(self, line_gen, field):
    ''' Process the property class header

    :param line_gen: line generator
    :param field: array of field strings from first line of prop class header
    :returns: a boolean, is True iff we are at last line
    '''
    self.logger.debug("START property class header")
    prop_class_index = field[1]
    # There are two kinds of PROPERTY_CLASS_HEADER
    # First, properties attached to local points
    if field[2] == '{':
        while True:
            # pylint: disable=W0612
            field, field_raw, line_str, is_last = next(line_gen)
            # Are we on the last line?
            if is_last:
                self.logger.debug("Property class header: last line")
                return True

            # Leaving header
            if field[0] == "}":
                self.logger.debug("Property class header: end header")
                return False

            # When in the PROPERTY CLASS headers, get the colour table
            if prop_class_index in self.local_props:
                self.parse_property_header(self.local_props[prop_class_index], line_str)

    # Second, properties of binary files
    elif field[3] == '{':
        if prop_class_index not in self.prop_dict:
            self.prop_dict[prop_class_index] = PROPS(field[2],
                                                     self.logger.getEffectiveLevel())
        while True:
            field, field_raw, line_str, is_last = next(line_gen)
            # Are we on the last line?
            if is_last:
                self.logger.debug("Property class header: last line")
                return True

            # Leaving header
            if field[0] == "}":
                self.logger.debug("Property class header: end header")
                return False

            # When in the PROPERTY CLASS headers, get the colour table
            self.parse_property_header(self.prop_dict[prop_class_index], line_str)

    else:
        self.logger.error("Cannot parse property header")
        sys.exit(1)

    self.logger.debug("END property class header")



def process_vol_data(self, line_gen, field, field_raw, src_dir):
    ''' Process all the voxet and sgrid data fields

        :param line_gen: line generator
        :param field: array of field strings
        :param field: array of field strings, not space separated
        :param src_dir: source directory of voxet file
    '''
    self.logger.info("START process_vol_data(field = %s)", repr(field))
    while True:
        self.logger.debug('process_vol_data processing: field= %s', repr(field))
        if field[0] == "AXIS_O":
            is_ok, x_flt, y_flt, z_flt = self.parse_xyz(True, field[1], field[2],
                                                        field[3], True)
            if is_ok:
                self.axis_o = (x_flt, y_flt, z_flt)
                self.logger.debug("self.axis_o = %s", repr(self.axis_o))

        elif field[0] == "AXIS_U":
            is_ok, x_flt, y_flt, z_flt = self.parse_xyz(True, field[1], field[2],
                                                        field[3], False, False)
            if is_ok:
                self.axis_u = (x_flt, y_flt, z_flt)
                self.logger.debug("self.axis_u = %s", repr(self.axis_u))

        elif field[0] == "AXIS_V":
            is_ok, x_flt, y_flt, z_flt = self.parse_xyz(True, field[1], field[2],
                                                        field[3], False, False)
            if is_ok:
                self.axis_v = (x_flt, y_flt, z_flt)
                self.logger.debug("self.axis_v = %s", repr(self.axis_v))

        elif field[0] == "AXIS_W":
            is_ok, x_flt, y_flt, z_flt = self.parse_xyz(True, field[1], field[2],
                                                        field[3], False, False)
            if is_ok:
                self.axis_w = (x_flt, y_flt, z_flt)
                self.logger.debug("self.axis_w= %s", repr(self.axis_w))

        elif field[0] == "AXIS_N":
            is_ok, x_int, y_int, z_int = self.parse_xyz(False, field[1], field[2],
                                                        field[3], False, False)
            if is_ok:
                self.vol_sz = (x_int, y_int, z_int)
                self.logger.debug("self.vol_sz= %s", repr(self.vol_sz))

        elif field[0] == "AXIS_MIN":
            is_ok, x_flt, y_flt, z_flt = self.parse_xyz(True, field[1], field[2],
                                                        field[3], False, False)
            if is_ok:
                self.axis_min = (x_flt, y_flt, z_flt)
                self.logger.debug("self.axis_min= %s", repr(self.axis_min))

        elif field[0] == "AXIS_MAX":
            is_ok, x_flt, y_flt, z_flt = self.parse_xyz(True, field[1], field[2],
                                                        field[3], False, False)
            if is_ok:
                self.axis_max = (x_flt, y_flt, z_flt)
                self.logger.debug("self.axis_max= %s", repr(self.axis_max))

        elif field[0] == "AXIS_UNIT":
            self.parse_axis_unit(field)

        elif field[0] in ["AXIS_NAME", "AXIS_TYPE", "AXIS_D", "AXIS_LABEL_MAX"]:
            pass

        elif field[0] == "FLAGS_ARRAY_LENGTH":
            is_ok, int_val = self.parse_int(field[1])
            if is_ok:
                self.flags_array_length = int_val
                self.logger.debug("self.flags_array_length= %d", self.flags_array_length)

        elif field[0] == "FLAGS_BIT_LENGTH":
            is_ok, int_val = self.parse_int(field[1])
            if is_ok:
                self.flags_bit_length = int_val
                self.logger.debug("self.flags_bit_length= %d", self.flags_bit_length)

        elif field[0] == "FLAGS_ESIZE":
            is_ok, int_val = self.parse_int(field[1])
            if is_ok:
                self.flags_bit_size = int_val
                self.logger.debug("self.flags_bit_size= %d", self.flags_bit_size)

        elif field[0] == "FLAGS_OFFSET":
            is_ok, int_val = self.parse_int(field[1])
            if is_ok:
                self.flags_offset = int_val
                self.logger.debug("self.flags_offset= %d", self.flags_offset)

        elif field[0] == "FLAGS_FILE":
            self.flags_file = os.path.join(src_dir, field_raw[1])
            self.logger.debug("self.flags_file= %s", self.flags_file)

        elif field[0] == "REGION":
            self.region_dict[field[2]] = field[1]
            self.logger.debug("self.region_dict[%s] = %s", field[2], field[1])

        elif field[0] == "REGION_FLAGS_ARRAY_LENGTH":
            is_ok, int_val = self.parse_int(field[1])
            if is_ok:
                self.region_flags_array_length = int_val

        elif field[0] == "REGION_FLAGS_BIT_LENGTH":
            is_ok, int_val = self.parse_int(field[1])
            if is_ok:
                self.region_flags_bit_length = int_val

        elif field[0] == "REGION_FLAGS_ESIZE":
            is_ok, int_val = self.parse_int(field[1])
            if is_ok:
                self.region_flags_bit_size = int_val

        elif field[0] == "REGION_FLAGS_OFFSET":
            is_ok, int_val = self.parse_int(field[1])
            if is_ok:
                self.region_flags_offset = int_val

        elif field[0] == "REGION_FLAGS_FILE":
            self.region_flags_file = os.path.join(src_dir, field_raw[1])
            self.logger.debug("self.flags_file= %s", self.flags_file)

        elif field[0] == "ASCII_DATA_FILE":
            self.logger.warning("Sorry - cannot process ASCII_DATA_FILE keyword")

        elif field[0] == "SPLIT":
            self.logger.warning("Sorry - cannot process SPLIT keyword")

        elif field[0] == "FACET_SET":
            self.logger.warning("Sorry - cannot process FACET_SET keyword")

        elif field[0] == "PROP_ALIGNMENT":
            # Is the SGRID aligned to CELLS or POINTS ?
            self.sgrid_cell_alignment = (field[1] == "CELLS")
            # If aligned to cells then there are fewer data values
            if self.sgrid_cell_alignment:
                self.vol_sz = (self.vol_sz[0] - 1, self.vol_sz[1] - 1, self.vol_sz[2] - 1)

        elif field[0] == "POINTS_OFFSET":
            # Offset within points file
            is_ok, int_val = self.parse_int(field[1])
            if is_ok:
                self.points_offset = int_val
                self.logger.debug("self.points_offset= %d", self.points_offset)

        elif field[0] == "POINTS_FILE":
            # Name of points file
            self.points_file = os.path.join(src_dir, field_raw[1])
            self.logger.debug("self.points_file= %s", self.points_file)

        else:
            self.logger.debug('Exiting volume data')
            return field, field_raw, False

        # pylint: disable=W0612
        field, field_raw, line_str, is_last = next(line_gen)
        if is_last:
            return field, field_raw, True
