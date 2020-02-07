"""
Functions that process fields in a single line of a GOCAD file
"""


import sys

def parse_property_header(self, prop_obj, line_str):
    ''' Parses the PROPERTY header, extracting the colour table info
        and storing it in PROPS object

    :params prop_obj: a PROPS object to store the data
    :params line_str: current line
    '''
    # pylint: disable=W0612
    name_str, sep, value_str = line_str.partition(':')
    name_str = name_str.strip()
    value_str = value_str.strip()
    if name_str == '*COLORMAP*SIZE':
        self.logger.debug("colourmap-size %s", value_str)
    elif name_str == '*COLORMAP*NBCOLORS':
        self.logger.debug("numcolours %s", value_str)
    elif name_str == 'HIGH_CLIP':
        self.logger.debug("highclip %s", value_str)
    elif name_str == 'LOW_CLIP':
        self.logger.debug("lowclip %s", value_str)
    # Read in the name of the colour map for this property
    elif name_str == 'COLORMAP':
        prop_obj.colourmap_name = value_str
        self.logger.debug("prop_obj.colourmap_name = %s", prop_obj.colourmap_name)
    # Read in the colour map for this property, format is: idx1 R1 G1 B1 idx2 R2 G2 B2 ...
    elif name_str in ('*COLORMAP*'+ prop_obj.colourmap_name + '*COLORS', \
                      '*' + prop_obj.colourmap_name + '*ROCK_COLORS', \
                      'COLORMAP**COLORS'):
        lut_arr = value_str.split(' ')
        for idx in range(0, len(lut_arr), 4):
            try:
                prop_obj.colour_map[int(lut_arr[idx])] = (float(lut_arr[idx+1]),
                                                          float(lut_arr[idx+2]),
                                                          float(lut_arr[idx+3]), 1.0)
                self.logger.debug("prop_obj.colour_map = %s", prop_obj.colour_map)
            except (IndexError, OverflowError, ValueError) as exc:
                self.handle_exc(exc)


def parse_props(self, field, coord_tup, is_patom=False):
    ''' This parses a line of properties associated with a PVTRX or PATOM line

    :param field: array of strings representing line with properties
    :param coord_tup: (X,Y,Z) float tuple of the coordinates
    :param is_patom: optional, True if this is from a PATOM, default False
    '''
    if is_patom:
        # For PATOM, properties start at the 4th column
        col_idx = 3
    else:
        # For PVRTX, properties start at the 6th column
        col_idx = 5

    # Loop over each property in line
    for prop_obj in self.local_props.values():
        # Property has one float
        if prop_obj.data_sz == 1:
            fp_str = field[col_idx]
            # Skip GOCAD control nodes e.g. 'CNXY', 'CNXYZ'
            if fp_str[:2].upper() == 'CN':
                col_idx += 1
                fp_str = field[col_idx]
            converted, fltp = self.parse_float(fp_str, prop_obj.no_data_marker)
            if converted:
                prop_obj.assign_to_xyz(coord_tup, fltp)
                self.logger.debug("prop_obj.data_xyz[%s] = %f", repr(coord_tup), fltp)
            col_idx += 1
        # Property has 3 floats i.e. XYZ
        elif prop_obj.data_sz == 3:
            fp_str_x = field[col_idx]
            # Skip GOCAD control nodes e.g. 'CNXY', 'CNXYZ'
            if fp_str_x[:2].upper() == 'CN':
                col_idx += 1
                fp_str_x = field[col_idx]
            fp_str_y = field[col_idx+1]
            fp_str_z = field[col_idx+2]
            converted_x, fp_x = self.parse_float(fp_str_x, prop_obj.no_data_marker)
            converted_y, fp_y = self.parse_float(fp_str_y, prop_obj.no_data_marker)
            converted_z, fp_z = self.parse_float(fp_str_z, prop_obj.no_data_marker)
            if converted_z and converted_y and converted_x:
                prop_obj.assign_to_xyz(coord_tup, (fp_x, fp_y, fp_z))
                self.logger.debug("prop_obj.data_xyz[%s] = (%f,%f,%f)",
                                  repr(coord_tup), fp_x, fp_y, fp_z)
            col_idx += 3
        else:
            self.logger.error("Cannot process property size of != 3 and !=1: %d %s",
                              prop_obj.data_sz, repr(prop_obj))
            sys.exit(1)


def parse_float(self, fp_str, null_val=None):
    ''' Converts a string to float, handles infinite values

    :param fp_str: string to convert to a float
    :param null_val: value representing 'no data'
    :returns: a boolean and a float
        If could not convert then return (False, None)
        else if 'null_val' is defined return (False, null_val)
    '''
    # Handle GOCAD's C++ floating point infinity for Windows and Linux
    if fp_str in ["1.#INF", "INF"]:
        fltp = sys.float_info.max
    elif fp_str in ["-1.#INF", "-INF"]:
        fltp = -sys.float_info.max
    else:
        try:
            fltp = float(fp_str)
            if null_val is not None and fltp == null_val:
                return False, null_val
        except (OverflowError, ValueError) as exc:
            self.handle_exc(exc)
            return False, 0.0
    return True, fltp


def parse_int(self, int_str, null_val=None):
    ''' Converts a string to an int

    :param int_str: string to convert to int
    :param null_val: value representing 'no data'
    :returns: a boolean and an integer
        If could not convert then return (False, None)
        else if 'null_val' is defined return (False, null_val)
    '''
    try:
        num = int(int_str)
    except (OverflowError, ValueError) as exc:
        self.handle_exc(exc)
        return False, null_val
    return True, num


def parse_xyz(self, is_float, x_str, y_str, z_str, do_minmax=False, convert=True):
    ''' Helpful function to read XYZ cooordinates

    :param is_float: if true parse x y z as floats else try integers
    :param x_str, y_str, z_str: X,Y,Z coordinates in string form
    :param do_minmax: calculate min/max of the X,Y,Z coords
    :param convert: convert from kms to metres if necessary
    :returns: returns tuple of four parameters: success - true if could convert
        the strings to floats/ints
        x,y,z - floating point values, converted to metres if units are kms
    '''
    x_val = y_val = z_val = None
    if is_float:
        converted1, x_val = self.parse_float(x_str)
        converted2, y_val = self.parse_float(y_str)
        converted3, z_val = self.parse_float(z_str)
        if not converted1 or not converted2 or not converted3:
            return False, None, None, None
    else:
        try:
            x_val = int(x_str)
            y_val = int(y_str)
            z_val = int(z_str)
        except (OverflowError, ValueError) as exc:
            self.handle_exc(exc)
            return False, None, None, None

    # Convert to metres if units are kms
    if convert and isinstance(x_val, float):
        x_val *= self.xyz_mult[0]
        y_val *= self.xyz_mult[1]
        z_val *= self.xyz_mult[2]

    # Calculate and store minimum and maximum XYZ
    if do_minmax:
        self.geom_obj.calc_minmax(x_val, y_val, z_val)
        x_val += self.base_xyz[0]
        y_val += self.base_xyz[1]
        z_val += self.base_xyz[2]

    return True, x_val, y_val, z_val



def parse_colour(self, colour_str):
    ''' Parse a colour string into RGBA tuple.

    :param colour_str: colour can either be spaced RGBA/RGB floats, or '#' + 6 digit hex string
    :returns: a tuple with 4 floats, (R,G,B,A)
    '''
    rgba_tup = (1.0, 1.0, 1.0, 1.0)
    try:
        if colour_str[0] != '#':
            rgbsplit_arr = colour_str.split(' ')
            if len(rgbsplit_arr) == 3:
                rgba_tup = (float(rgbsplit_arr[0]), float(rgbsplit_arr[1]),
                            float(rgbsplit_arr[2]), 1.0)
            elif len(rgbsplit_arr) == 4:
                rgba_tup = (float(rgbsplit_arr[0]), float(rgbsplit_arr[1]),
                            float(rgbsplit_arr[2]), float(rgbsplit_arr[3]))
            else:
                self.logger.debug("Could not parse colour %s", repr(colour_str))
        else:
            rgba_tup = (float(int(colour_str[1:3], 16))/255.0,
                        float(int(colour_str[3:5], 16))/255.0,
                        float(int(colour_str[5:7], 16))/255.0, 1.0)
    except (ValueError, OverflowError, IndexError) as exc:
        self.handle_exc(exc)
        rgba_tup = (1.0, 1.0, 1.0, 1.0)
    return rgba_tup


def parse_axis_unit(self, field):
    ''' Processes the AXIS_UNIT keyword
    :param field: array of field strings
    '''
    for idx in range(0, 3):
        unit_str = field[idx+1].strip('"').strip(' ').strip("'")
        if unit_str == 'KM':
            self.xyz_mult[idx] = 1000.0
        # Warn if not metres or kilometres or unitless etc.
        elif unit_str not in ['M', 'UNITLESS', 'NUMBER', 'MS', 'NONE']:
            self.logger.warning("WARNING - nonstandard units in 'AXIS_UNIT' %s",
                                field[idx+1])
        else:
            self.xyz_unit[idx] = unit_str
