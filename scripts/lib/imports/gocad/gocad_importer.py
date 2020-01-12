''' This contains the GocadImporter class, which is the main class used for parsing
    GOCAD object files. It also contains other functions for parsing GOCAD group files.
'''
import sys
import os
from collections import OrderedDict
import logging
import traceback
import copy

import numpy as np


from lib.db.geometry.model_geometries import ModelGeometries
from lib.imports.gocad.props import PROPS
from lib.db.style.style import STYLE
from lib.db.geometry.types import VRTX, ATOM, TRGL, SEG
from lib.db.metadata.metadata import METADATA, MapFeat

from .helpers import make_line_gen

# Set up debugging
LOCAL_LOGGER = logging.getLogger("gocad_importer")

# Create console handler
LOCAL_HANDLER = logging.StreamHandler(sys.stdout)

# Create formatter
LOCAL_FORMATTER = logging.Formatter('%(asctime)s -- %(name)s -- %(levelname)s - %(message)s')

# Add formatter to ch
LOCAL_HANDLER.setFormatter(LOCAL_FORMATTER)

# Add handler to logger
LOCAL_LOGGER.addHandler(LOCAL_HANDLER)



def extract_from_grp(src_dir, filename_str, file_lines, base_xyz, debug_lvl,
                     nondef_coords, ct_file_dict):
    ''' Extracts GOCAD files from a GOCAD group file

    :param src_dir: source directory for GOCAD file
    :param filename_str: filename of GOCAD file
    :param file_lines: lines extracted from GOCAD group file
    :param base_xyz: base coordinates as (x,y,z) tuple added to all 3d coordinates
    :param debug_lvl: debug level for debug output e.g. logging.DEBUG
    :param nondefault_coords: optional flag, supports non-default coordinates, default is False
    :param ct_file_dict: a dictionary of files which contain a tuple: (filename of CSV colour table,
                        list of values to be rendered transparent) key is GOCAD filename 
    :returns: a list of (ModelGeometries, STYLE, METADATA) objects
    '''
    LOCAL_LOGGER.setLevel(debug_lvl)
    LOCAL_LOGGER.debug("extract_from_grp(%s,%s)", src_dir, filename_str)
    main_gsm_list = []
    first_line = True
    in_member = False
    in_gocad = False
    gocad_lines = []
    file_name, file_ext = os.path.splitext(filename_str)
    for line in file_lines:
        line_str = line.rstrip(' \n\r').upper()
        field = line_str.split(' ')
        if first_line:
            first_line = False
            if file_ext.upper() != '.GP' or line_str not in GocadImporter.GOCAD_HEADERS['GP']:
                LOCAL_LOGGER.error("SORRY - not a GOCAD GP file %s", repr(line_str))
                LOCAL_LOGGER.error("    filename_str = %s", filename_str)
                sys.exit(1)
        if line_str == "BEGIN_MEMBERS":
            in_member = True
        elif line_str == "END_MEMBERS":
            in_member = False
        elif in_member and field[0] == "GOCAD":
            in_gocad = True
        elif in_member and line_str == "END":
            in_gocad = False
            gocad_obj = GocadImporter(debug_lvl, base_xyz=base_xyz,
                                      group_name=os.path.basename(file_name).upper(),
                                      nondefault_coords=nondef_coords, ct_file_dict=ct_file_dict)
            is_ok, gsm_list = gocad_obj.process_gocad(src_dir, filename_str, gocad_lines)
            if is_ok:
                main_gsm_list += gsm_list
            gocad_lines = []
        if in_member and in_gocad:
            gocad_lines.append(line)

    LOCAL_LOGGER.debug("extract_gocad() returning len(main_gsm_list)=%d", len(main_gsm_list))
    return main_gsm_list



class GocadImporter():
    ''' Class used to read GOCAD files and store their details
    '''
    from .parsers import parse_property_header, parse_props, parse_float
    from .parsers import parse_int, parse_xyz, parse_colour, parse_axis_unit
    from .processors import process_coord_hdr, process_header, process_ascii_well_path
    from .processors import process_well_info, process_well_curve, process_prop_class_hdr
    from .processors import process_vol_data

    GOCAD_HEADERS = {
        'TS':['GOCAD TSURF 1'],
        'VS':['GOCAD VSET 1'],
        'PL':['GOCAD PLINE 1'],
        'GP':['GOCAD HETEROGENEOUSGROUP 1', 'GOCAD HOMOGENEOUSGROUP 1'],
        'VO':['GOCAD VOXET 1'],
        'WL':['GOCAD WELL 1'],
    }
    ''' Constant assigns possible headers to each filename extension
    '''

    SUPPORTED_EXTS = [
        'TS',
        'VS',
        'PL',
        'GP',
        'VO',
        'WL'
    ]
    ''' List of file extensions to search for
    '''


    COORD_OFFSETS = {'FROM_SHAPE' :(535100.0, 0.0, 0.0)}
    ''' Coordinate offsets, when file contains a coordinate system  that is not "DEFAULT"
        The named coordinate system and (X,Y,Z) offset will apply
    '''


    stop_on_exc = True
    ''' Stop upon exception, regardless of debug level
    '''

    SKIP_FLAGS_FILE = True
    ''' Don't read flags file
    '''


    def __init__(self, debug_level, base_xyz=(0.0, 0.0, 0.0), group_name="",
                 nondefault_coords=False, stop_on_exc=True, ct_file_dict={}):
        ''' Initialise class

        :param debug_level: debug level taken from 'logging' module e.g. logging.DEBUG
        :param base_xyz: optional (x,y,z) floating point tuple, base_xyz is added to all coordinates
            before they are output, default is (0.0, 0.0, 0.0)
        :param group_name: optional string, name of group if this gocad file is within a group,
                           default is ""
        :param nondefault_coords: optional flag, supports non-default coordinates, default is False
        :param ct_file_dict: a dictionary of files which contain a tuple: (filename of CSV colour table,
                            list of values to be rendered transparent) key is GOCAD filename 
        '''
        super().__init__()
        # Set up logging, use an attribute of class name so it is only called once
        if not hasattr(GocadImporter, 'logger'):
            GocadImporter.logger = logging.getLogger(__name__)

            # Create console handler
            handler = logging.StreamHandler(sys.stdout)

            # Create formatter
            formatter = logging.Formatter('%(asctime)s -- %(name)s -- %(levelname)s - %(message)s')

            # Add formatter to ch
            handler.setFormatter(formatter)

            # Add handler to logger and set level
            GocadImporter.logger.addHandler(handler)

        GocadImporter.logger.setLevel(debug_level)

        self.logger = GocadImporter.logger

        self.ct_file_dict = ct_file_dict
        ''' A dictionary of files which contain colour tables
            key is GOCAD filename, val is CSV file
        '''
        self.logger.debug("self.ct_file_dict = %s", repr(self.ct_file_dict))

        self.stop_on_exc = stop_on_exc

        # Initialise input vars
        self.base_xyz = base_xyz
        self.group_name = group_name
        self.nondefault_coords = nondefault_coords

        self.header_name = ""
        ''' Contents of the name field in the header
        '''

        self.prop_dict = {}
        ''' Dictionary of PROPS objects, stores GOCAD "PROPERTY" objects from VOXET files
            Dictionary index is the PROPERTY number e.g. '1', '2', '3' ...
        '''

        self.flags_prop = None
        ''' PROPS object used for the voxet flags file which has region data in it
        '''

        self.invert_zaxis = False
        ''' Set to true if z-axis inversion is turned on in this GOCAD file
        '''

        self.local_props = OrderedDict()
        ''' OrderedDict of PROPS objects for attached PVRTX and PATOM properties
        '''

        self.__is_ts = False
        ''' True iff it is a GOCAD TSURF file
        '''

        self.__is_vs = False
        ''' True iff it is a GOCAD VSET file
        '''

        self.__is_pl = False
        ''' True iff it is a GOCAD PLINE file
        '''

        self.__is_vo = False
        ''' True iff it is a GOCAD VOXET file
        '''

        self.__is_wl = False
        ''' True iff it is a GOCAD WELL file
        '''

        self.xyz_mult = [1.0, 1.0, 1.0]
        ''' Used to convert to metres if the units are in kilometres
        '''

        self.xyz_unit = [None, None, None]
        ''' Units of XYZ axes
        '''

        self.__vrtx_arr = []
        ''' Array of named tuples 'VRTX' used to store vertex data
        '''

        self.__atom_arr = []
        ''' Array of named tuples 'ATOM' used to store atom data
        '''

        self.__trgl_arr = []
        ''' Array of named tuples 'TRGL' used store triangle face data
        '''

        self.__seg_arr = []
        ''' Array of named tuples 'SEG' used to store line segment data
        '''

        self.axis_u = []
        ''' U-axis volume vector
        '''

        self.axis_v = []
        ''' V-axis volume vector
        '''

        self.axis_w = []
        ''' W-axis volume vector
        '''

        self.axis_o = []
        ''' Volume's origin (X,Y,Z)
        '''

        self.axis_min = []
        ''' 3 dimensional minimum point of voxet volume
        '''

        self.axis_max = []
        ''' 3 dimensional maximum point of voxet volume
        '''

        self.vol_sz = []
        ''' Size of voxet volume
        '''

        self.flags_array_length = 0
        ''' Size of flags file
        '''

        self.flags_bit_length = 0
        ''' Number of bit in use in flags file
        '''

        self.flags_bit_size = 0
        ''' Size (number of bytes) of each element in flags file
        '''

        self.flags_offset = 0
        ''' Offset within the flags file  where data starts
        '''

        self.flags_file = ""
        ''' Name of flags file associated with voxel file
        '''

        self.region_dict = {}
        ''' Labels and bit numbers for each region in a flags file,
            key is number (as string), value is label
        '''

        self.region_colour_dict = {}
        ''' Region colour dict, key is region name, value is RGB (float, float, float)
        '''

        self.np_filename = ""
        ''' Filename of GOCAD file without path or extension
        '''

        self.coord_sys_name = "DEFAULT"
        ''' Name of the GOCAD coordinate system
        '''

        self.uses_default_coords = True
        ''' Uses default coordinates
        '''

        self.rock_label_idx = {}
        ''' Some voxet files have floats that are indexes to rock types
        '''


        self.geom_obj = ModelGeometries()
        self.style_obj = STYLE()
        self.meta_obj = METADATA()
        ''' Seed copies of ModelGeometries, STYLE, METADATA for data gathering purposes
        '''

        self.gsm_list = []
        ''' List of (ModelGeometries, STYLE, METADATA)
        '''


    def handle_exc(self, exc):
        ''' If stop_on_exc is set or debug is on, print details of exception and stop

        :param exc: exception
        '''
        if self.logger.getEffectiveLevel() == logging.DEBUG or self.stop_on_exc:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            if self.stop_on_exc:
                print("DEBUG MODE: CAUGHT EXCEPTION:")
                print(exc)
                print(traceback.format_exception(exc_type, exc_value, exc_traceback))
                sys.exit(1)
            self.logger.debug("DEBUG MODE: CAUGHT EXCEPTION:")
            self.logger.debug(exc)
            self.logger.debug(repr(traceback.format_exception(exc_type, exc_value, exc_traceback)))
            sys.exit(1)


    def __repr__(self):
        ''' A basic print friendly representation
        '''
        ret_str = ''
        for field in dir(self):
            if field[-2:] != '__' and not callable(getattr(self, field)):
                ret_str += field + ": " + repr(getattr(self, field))[:200] + "\n"
        return ret_str


    def __make_vertex_dict(self):
        ''' Make a dictionary to associate vertex insertion order with vertex sequence number
            Ordinarily the vertex sequence number is the same as the insertion order in the vertex
            array, but some GOCAD files have missing vertices etc.
            The first element starts at '1'
        '''
        vert_dict = {}
        # Assign vertices to dict
        for idx, vrtx in enumerate(self.__vrtx_arr, 1):
            vert_dict[vrtx.n] = idx

        # Assign atoms to dict
        for atom in self.__atom_arr:
            for idx, vert in enumerate(self.__vrtx_arr, 1):
                if vert.n == atom.v:
                    vert_dict[atom.n] = idx
                    break
        return vert_dict


    def process_gocad(self, src_dir, filename_str, file_lines):
        ''' Extracts details from gocad file. This should be called before other functions!

        :param filename_str: filename of gocad file
        :param file_lines: array of strings of lines from gocad file
        :returns: true if could process file, and a list of (geometry, style, metadata) objects
        '''
        self.logger.debug("process_gocad(%s,%s,%d)", src_dir, filename_str, len(file_lines))

        ret_val = True

        debug_lvl = self.logger.getEffectiveLevel()

        # For keeping track of the ID of VRTX, ATOM, PVRTX, SEG etc.
        seq_no = 0
        seq_no_prev = -1

        file_name, file_ext = os.path.splitext(filename_str)
        self.np_filename = os.path.basename(file_name)

        # Check that we have a GOCAD file that we can process
        # Nota bene: This will return if called for the header of a GOCAD group file
        if not self.__set_type(file_ext, file_lines[0].rstrip(' \n\r').upper()):
            self.logger.error("process_gocad() Can't detect GOCAD file object type, return False")
            return False, []

        line_gen = make_line_gen(file_lines)
        is_last = False
        # Retry flag forces parsing of the field array without asking for the next line
        retry = False
        while not is_last:
            if not retry:
                field, field_raw, line_str, is_last = next(line_gen)
            retry = False
            if is_last and not field:
                break

            self.logger.debug("field = %s line_str = %s is_last = %s",
                              repr(field), repr(line_str), repr(is_last))

            # Skip the subsets keywords
            if field[0] in ["SUBVSET", "ILINE", "TFACE", "TVOLUME"]:
                self.logger.debug("Skip subset keywords")
                continue

            # Skip control nodes (used to denote fixed points in GOCAD)
            if field[0] == "CNP":
                self.logger.debug("Skip control nodes")
                continue

            try:
                # Are we in the main header?
                if field[0] == "HEADER":
                    self.logger.debug("Processing header")
                    is_last = self.process_header(line_gen)

                # Are we within coordinate system header?
                elif field[0] == "GOCAD_ORIGINAL_COORDINATE_SYSTEM":
                    self.logger.debug("Processing coordinate system")
                    # Process coordinate header fields
                    is_last, is_error = self.process_coord_hdr(line_gen)
                    if is_error:
                        self.logger.debug("process_gocad() return False")
                        return False, []

                # Are we in the property class header?
                elif field[0] == "PROPERTY_CLASS_HEADER":
                    self.logger.debug("Processing property class header")
                    is_last = self.process_prop_class_hdr(line_gen, field)

                # Property names, this is not the class names
                elif field[0] == "PROPERTIES":
                    if not self.local_props:
                        for class_name in field[1:]:
                            self.local_props[class_name] = PROPS(class_name, debug_lvl)
                    self.logger.debug(" properties list = %s", repr(field[1:]))

                # These are the property names for the point properties (e.g. PVRTX, PATOM)
                elif field[0] == "PROPERTY_CLASSES":
                    if not self.local_props:
                        for class_name in field[1:]:
                            self.local_props[class_name] = PROPS(class_name, debug_lvl)
                    self.logger.debug(" property classes = %s", repr(field[1:]))

                # This is the number of floats/ints for each property, usually it is '1',
                # but XYZ values are '3'
                elif field[0] == "ESIZES":
                    for idx, prop_obj in enumerate(self.local_props.values(), 1):
                        is_ok, d_sz = self.parse_int(field[idx])
                        if is_ok:
                            prop_obj.data_sz = d_sz
                    self.logger.debug(" property_sizes = %s", repr(field[1:]))

                # Read values representing no data for this property at a coordinate point
                elif field[0] == "NO_DATA_VALUES":
                    for idx, prop_obj in enumerate(self.local_props.values(), 1):
                        try:
                            converted, fltp = self.parse_float(field[idx])
                            if converted:
                                prop_obj.no_data_marker = fltp
                                self.logger.debug("prop_obj.no_data_marker = %f",
                                                  prop_obj.no_data_marker)
                        except IndexError as exc:
                            self.handle_exc(exc)
                    self.logger.debug(" property_nulls = %s", repr(field[1:]))

                # If a well object
                elif self.__is_wl:
                    # All well files
                    if field[0] == "PATH_ZM_UNIT" or field[0] == "WREF":
                        self.logger.debug("Processing ASCII well path")
                        is_last, well_path, self.meta_obj.label_list = self.process_ascii_well_path(line_gen, field)

                        # Convert well path into a series of SEG types
                        if len(well_path) > 1:
                            self.__vrtx_arr.append(VRTX(1, well_path[0]))
                            for idx in range(1,len(well_path)):
                                self.__seg_arr.append(SEG((idx, idx+1)))
                                self.__vrtx_arr.append(VRTX(idx+1, well_path[idx]))
                             
                        self.logger.debug("Well path: %s", repr(well_path))
                        self.logger.debug("Label list: %s", repr(self.meta_obj.label_list))
                        retry = True

                    # Well files with well curve block
                    elif field[0] == "WELL_CURVE":
                        self.logger.debug("Processing well curve")
                        field, field_raw, is_last = self.process_well_curve(line_gen, field)

                    elif field[0] == "BINARY_DATA_FILE":
                        pass
                    elif field[0] == "WP_CATALOG_FILE":
                        pass

                # Atoms, with or without properties
                elif field[0] == "ATOM" or field[0] == 'PATOM':
                    seq_no_prev = seq_no
                    is_ok_s, seq_no = self.parse_int(field[1])
                    is_ok, v_num = self.parse_int(field[2])
                    if not is_ok_s or not is_ok:
                        seq_no = seq_no_prev
                    else:
                        if self.__check_vertex(v_num):
                            self.__atom_arr.append(ATOM(seq_no, v_num))
                        else:
                            self.logger.error("ATOM refers to VERTEX that has not been defined yet")
                            self.logger.error("    seq_no = %d", seq_no)
                            self.logger.error("    v_num = %d", v_num)
                            self.logger.error("    line = %s", line_str)
                            sys.exit(1)

                        # Atoms with attached properties
                        if field[0] == "PATOM":
                            vert_dict = self.__make_vertex_dict()
                            self.parse_props(field, self.__vrtx_arr[vert_dict[v_num] - 1].xyz,
                                             True)

                # Grab the vertices and properties, does not care if there are
                # gaps in the sequence number
                elif field[0] == "PVRTX" or  field[0] == "VRTX":
                    seq_no_prev = seq_no
                    is_ok_s, seq_no = self.parse_int(field[1])
                    is_ok, x_flt, y_flt, z_flt = self.parse_xyz(True, field[2], field[3],
                                                                field[4], True)
                    self.logger.debug("ParseXYZ %s %f %f %f from %s %s %s", repr(is_ok),
                                      x_flt, y_flt, z_flt,
                                      field[2], field[3], field[4])
                    if not is_ok_s or not is_ok:
                        seq_no = seq_no_prev
                    else:
                        # Add vertex
                        if self.invert_zaxis:
                            z_flt = -1.0 * z_flt
                        self.__vrtx_arr.append(VRTX(seq_no, (x_flt, y_flt, z_flt)))

                        # Vertices with attached properties
                        if field[0] == "PVRTX":
                            self.parse_props(field, (x_flt, y_flt, z_flt))

                # Grab the triangular edges
                elif field[0] == "TRGL":
                    seq_no_prev = seq_no
                    is_ok_s, seq_no = self.parse_int(field[1])
                    is_ok, a_int, b_int, c_int = self.parse_xyz(False, field[1], field[2],
                                                                field[3], False, False)
                    if not is_ok or not is_ok_s:
                        seq_no = seq_no_prev
                    else:
                        self.__trgl_arr.append(TRGL(seq_no, (a_int, b_int, c_int)))

                # Grab the segments
                elif field[0] == "SEG":
                    is_ok_a, a_int = self.parse_int(field[1])
                    is_ok_b, b_int = self.parse_int(field[2])
                    if is_ok_a and is_ok_b:
                        self.__seg_arr.append(SEG((a_int, b_int)))

                # Grab metadata - see 'metadata.py' for more info
                elif field[0] in ("STRATIGRAPHIC_POSITION", "GEOLOGICAL_FEATURE"):
                    self.meta_obj.geofeat_name = field[1]
                    if field[0] == 'STRATIGRAPHIC_POSITION':
                        is_ok, self.meta_obj.geoevent_numeric_age_range = \
                                               self.parse_int(field[-1:][0], 0)
                        self.meta_obj.mapped_feat = MapFeat.GEOLOGICAL_UNIT

                elif field[0] == "GEOLOGICAL_TYPE":
                    if field[1] == "FAULT":
                        self.meta_obj.mapped_feat = MapFeat.SHEAR_DISP_STRUCT
                    elif  field[1] == "INTRUSIVE":
                        self.meta_obj.mapped_feat = MapFeat.GEOLOGICAL_UNIT
                    elif field[1] in ("BOUNDARY", "UNCONFORMITY", "INTRAFORMATIONAL"):
                        self.meta_obj.mapped_feat = MapFeat.CONTACT


                # What kind of property is this? Is it a measurement,
                # or a reference to a rock colour table?
                elif field[0] == "PROPERTY_SUBCLASS":
                    if len(field) > 2 and field[2] == "ROCK":
                        prop_idx = field[1]
                        self.prop_dict[prop_idx].is_index_data = True
                        self.logger.debug("self.prop_dict[%s].is_index_data = True", prop_idx)
                        # Sometimes there is an array of indexes and labels
                        self.logger.debug(" len(field) = %d", len(field))
                        if len(field) > 4:
                            for idx in range(4, len(field), 2):
                                rock_label = field[idx]
                                is_ok, int_val = self.parse_int(field[1+idx])
                                if is_ok:
                                    rock_index = int_val
                                    self.rock_label_idx.setdefault(prop_idx, {})
                                    self.rock_label_idx[prop_idx][rock_index] = rock_label
                                    self.logger.debug("self.rock_label_idx[%s] = %s",
                                                      prop_idx, repr(self.rock_label_idx[prop_idx]))

                # Extract binary file name
                elif field[0] == "PROP_FILE":
                    self.prop_dict[field[1]].file_name = os.path.join(src_dir, field_raw[2])
                    self.logger.debug("self.prop_dict[%s].file_name = %s",
                                      field[1], self.prop_dict[field[1]].file_name)

                # Size of each value in binary file (measured in bytes, usually 1,2,4)
                elif field[0] == "PROP_ESIZE":
                    is_ok, int_val = self.parse_int(field[2])
                    if is_ok:
                        self.prop_dict[field[1]].data_sz = int_val
                        self.logger.debug("self.prop_dict[%s].data_sz = %d", field[1],
                                          self.prop_dict[field[1]].data_sz)

                # The type of non-float value in binary file: OCTET, SHORT, RGBA
                # IF this is present, then it is assumed not to be floating point
                elif field[0] == "PROP_STORAGE_TYPE":
                    # Single byte integer
                    if field[2] == "OCTET":
                        self.prop_dict[field[1]].data_type = "b"
                    # Short int, 2 bytes long
                    elif field[2] == "SHORT":
                        self.prop_dict[field[1]].data_type = "h"
                    # Colour data
                    elif field[2] == "RGBA":
                        self.prop_dict[field[1]].data_type = "rgba"
                    else:
                        self.logger.error("Unknown type %s", field[2])
                        sys.exit(1)
                    self.logger.debug("self.prop_dict[%s].data_type = %s",
                                      field[1], self.prop_dict[field[1]].data_type)

                # If binary file contains integers, are they signed integers?
                elif field[0] == "PROP_SIGNED":
                    self.prop_dict[field[1]].signed_int = (field[2] == "1")
                    self.logger.debug("self.prop_dict[%s].signed_int = %s",
                                      field[1],
                                      repr(self.prop_dict[field[1]].signed_int))

                # Type of value in binary file: IBM, IEEE
                # NB: We do not support IBM-style floats
                elif field[0] == "PROP_ETYPE":
                    if field[2] != "IEEE":
                        self.logger.error("Cannot process %s type floating points", field[1])
                        sys.exit(1)

                # Binary file format: RAW or SEGY
                # NB: Cannot process SEGY formats
                elif field[0] == "PROP_EFORMAT":
                    if field[2] != "RAW":
                        self.logger.error("Cannot process %s format volume data", field[1])
                        sys.exit(1)

                # Offset in bytes within binary file
                elif field[0] == "PROP_OFFSET":
                    is_ok, int_val = self.parse_int(field[2])
                    if is_ok:
                        self.prop_dict[field[1]].offset = int_val
                        self.logger.debug("self.prop_dict[%s].offset = %d",
                                          field[1], self.prop_dict[field[1]].offset)

                # The number that is used to represent 'no data' in binary file
                elif field[0] == "PROP_NO_DATA_VALUE":
                    converted, fltp = self.parse_float(field[2])
                    if converted:
                        self.prop_dict[field[1]].no_data_marker = fltp
                        self.logger.debug("self.prop_dict[%s].no_data_marker = %f",
                                          field[1],
                                          self.prop_dict[field[1]].no_data_marker)

                # Process VOXET data
                elif self.__is_vo and field[0][:4] == "AXIS":
                    self.logger.debug('field[0][:4] = %s', field[0][:4])
                    field, field_raw, is_last = self.process_vol_data(line_gen, field, field_raw, src_dir)

            except IndexError as exc:
                self.handle_exc(exc)

            # END OF TEXT PROCESSING LOOP


        # Read in any binary data files and flags files attached to voxel files
        if self.__is_vo:
            ret_val = self.__read_voxel_binary_files()

        # Complete initalisation of geometry object
        if self.local_props:
            geom_obj = copy.deepcopy(self.geom_obj)
            style_obj = copy.deepcopy(self.style_obj)
            meta_obj = copy.deepcopy(self.meta_obj)
            prop_idx_list = self.local_props.keys()
            self.__init_metadata(meta_obj, local_prop_idx_list=prop_idx_list)
            self.__init_geometry(geom_obj, local_prop_idx_list=prop_idx_list)
            self.__init_style(style_obj, local_prop_idx_list=prop_idx_list)
            self.gsm_list.append((geom_obj, style_obj, meta_obj))

        elif self.prop_dict:
            for prop_idx in self.prop_dict:
                geom_obj = copy.deepcopy(self.geom_obj)
                style_obj = copy.deepcopy(self.style_obj)
                meta_obj = copy.deepcopy(self.meta_obj)
                self.__init_metadata(meta_obj, prop_idx=prop_idx)
                self.__init_geometry(geom_obj, prop_idx=prop_idx)
                self.__init_style(style_obj, prop_idx=prop_idx)
                self.gsm_list.append((geom_obj, style_obj, meta_obj))

        else:
            self.__init_metadata(self.meta_obj)
            self.__init_geometry(self.geom_obj)
            self.gsm_list.append((self.geom_obj, self.style_obj, self.meta_obj))



        # Complete initialisation of metadata object

        self.logger.debug("process_gocad() returns %s, %s", repr(ret_val), repr(self.gsm_list))
        return ret_val, self.gsm_list


    def __init_style(self, style_obj, local_prop_idx_list=None, prop_idx=None):
        ''' Extract style data from GocadImporter and place in style object
        :param style_obj: style object which will hold data taken from GocadImporter object
        :param local_prop_idx_list: optional, if set, then will place multiple local
               property data values in object
        :param prop_idx: optional, if set, then will place property data in object
        '''
        if local_prop_idx_list:
            for local_prop_idx in local_prop_idx_list:
                prop = self.local_props[local_prop_idx]
                style_obj.add_tables(prop.colour_map, prop.rock_label_table)
        if prop_idx:
            prop = self.prop_dict[prop_idx]
            style_obj.add_tables(prop.colour_map, prop.rock_label_table)



    def __init_metadata(self, meta_obj, local_prop_idx_list=None, prop_idx=None):
        ''' Extract metadata from GocadImporter and place in metadata object
        :param meta_obj: metadata object which will hold data from GocadImporter object
        :param local_prop_idx_list: optional, if set, then will place multiple
                                    local property data values in object
        :param prop_idx: optional, if set, then will place property data in object
        '''
        group_name = ''
        if self.group_name:
            group_name = self.group_name+"-"
        if self.header_name:
            meta_obj.name = group_name + self.header_name
        else:
            meta_obj.name = group_name + "geometry"
        if local_prop_idx_list:
            for local_prop_idx in local_prop_idx_list:
                meta_obj.add_property_name(local_prop_idx)
        if prop_idx:
            meta_obj.add_property_name(self.prop_dict[prop_idx].class_name)
            meta_obj.is_index_data = self.prop_dict[prop_idx].is_index_data
            if self.prop_dict[prop_idx].rock_label_table:
                meta_obj.rock_label_table = self.prop_dict[prop_idx].rock_label_table
            meta_obj.src_filename = self.prop_dict[prop_idx].file_name


    def __init_geometry(self, geom_obj, local_prop_idx_list=None, prop_idx=None):
        ''' Convert GocadImporter to MODEL_GEOMETRY version
        :param geom_obj: MODEL_GEOMETRY object where GocadImporter data is placed
        :param local_prop_idx_list: optional, if set, then will place multiple
                                    local property data values in object
        :param prop_idx: optional, if set, then will place property data in object
        '''
        # Convert GOCAD's volume geometry spec
        if self.__is_vo and self.vol_sz:
            geom_obj.vol_origin = self.axis_o
            geom_obj.vol_sz = self.vol_sz
            min_vec = np.array(self.axis_min)
            max_vec = np.array(self.axis_max)
            mult_vec = max_vec - min_vec

            geom_obj.vol_axis_u = tuple((mult_vec * np.array(self.axis_u)).tolist())
            geom_obj.vol_axis_v = tuple((mult_vec * np.array(self.axis_v)).tolist())
            geom_obj.vol_axis_w = tuple((mult_vec * np.array(self.axis_w)).tolist())

        # Re-enumerate all geometries, because some GOCAD files have missing vertex numbers
        vert_dict = self.__make_vertex_dict()
        for v_old in self.__vrtx_arr:
            vrtx = VRTX(vert_dict[v_old.n], v_old.xyz)
            geom_obj.vrtx_arr.append(vrtx)

        for t_old in self.__trgl_arr:
            tri = TRGL(t_old.n, (vert_dict[t_old.abc[0]], vert_dict[t_old.abc[1]],
                                 vert_dict[t_old.abc[2]]))
            geom_obj.trgl_arr.append(tri)

        for s_old in self.__seg_arr:
            sgm = SEG((vert_dict[s_old.ab[0]], vert_dict[s_old.ab[1]]))
            geom_obj.seg_arr.append(sgm)

        for a_old in self.__atom_arr:
            atm = ATOM(vert_dict[a_old.n], vert_dict[a_old.v])
            geom_obj.atom_arr.append(atm)

        # Add PVTRX, PATOM data (and eventually SGRID)
        # Multiple properties' data points are stored in one geom_obj
        if local_prop_idx_list:
            for local_prop_idx in local_prop_idx_list:
                prop = self.local_props[local_prop_idx]
                geom_obj.add_xyz_data(prop.data_xyz)
                geom_obj.add_stats(prop.data_stats['min'], prop.data_stats['max'],
                                   prop.no_data_marker)

        # Add volume data
        # Only one set of data per geom_obj
        if prop_idx:
            prop = self.prop_dict[prop_idx]
            geom_obj.vol_data = prop.data_3d
            if prop.data_xyz:
                geom_obj.add_xyz_data(prop.data_xyz)
            geom_obj.vol_data_type = prop.get_str_data_type()
            geom_obj.add_stats(prop.data_stats['min'], prop.data_stats['max'],
                               prop.no_data_marker)


    def __set_type(self, file_ext, first_line_str):
        ''' Sets the type of GOCAD file: TSURF, VOXEL, PLINE etc.

        :param fileExt: the file extension
        :param firstLineStr: first line in the file
        :returns: returns True if it could determine the type of file
            Will return False when given the header of a GOCAD group file, since
            cannot create a vessel object from the group file itself, only from the group members
        '''
        self.logger.debug("setType(%s,%s)", file_ext, first_line_str)
        ext_str = file_ext.lstrip('.').upper()
        # Look for other GOCAD file types within a group file
        if ext_str == 'GP':
            found = False
            for key in self.GOCAD_HEADERS:
                if key != 'GP' and first_line_str in self.GOCAD_HEADERS[key]:
                    ext_str = key
                    found = True
                    break
            if not found:
                return False

        if ext_str in self.GOCAD_HEADERS:
            if ext_str == 'TS' and first_line_str in self.GOCAD_HEADERS['TS']:
                self.__is_ts = True
                return True
            if ext_str == 'VS' and first_line_str in self.GOCAD_HEADERS['VS']:
                self.__is_vs = True
                return True
            if ext_str == 'PL' and first_line_str in self.GOCAD_HEADERS['PL']:
                self.__is_pl = True
                return True
            if ext_str == 'VO' and first_line_str in self.GOCAD_HEADERS['VO']:
                self.__is_vo = True
                return True
            if ext_str == 'WL' and first_line_str in self.GOCAD_HEADERS['WL']:
                self.__is_wl = True
                return True

        return False






    def __read_voxel_binary_files(self):
        ''' Open up and read binary voxel file
        '''
        if not self.vol_sz:
            self.logger.error("Cannot process voxel file, cube size is not defined, " \
                              "missing 'AXIS_N'")
            sys.exit(1)
        # pylint: disable=W0612
        for file_idx, prop_obj in self.prop_dict.items():
            # Sometimes filename needs a .vo on the end
            if not os.path.isfile(prop_obj.file_name) and prop_obj.file_name[-2:] == "@@" and \
                                          os.path.isfile(prop_obj.file_name+".vo"):
                prop_obj.file_name += ".vo"

            # If there is a colour table in CSV file then read it
            bin_file = os.path.basename(prop_obj.file_name)
            if bin_file in self.ct_file_dict:
                csv_file_path = os.path.join(os.path.dirname(prop_obj.file_name),
                                             self.ct_file_dict[bin_file][0])
                prop_obj.read_colour_table_csv(csv_file_path, self.ct_file_dict[bin_file][1])
                self.logger.debug("prop_obj.colour_map = %s", repr(prop_obj.colour_map))
                self.logger.debug("prop_obj.rock_label_table = %s", repr(prop_obj.rock_label_table))

            # Read and process binary file
            try:
                # Check file size first
                file_sz = os.path.getsize(prop_obj.file_name)
                num_voxels = self.vol_sz[0]*self.vol_sz[1]*self.vol_sz[2]
                self.logger.debug("num_voxels = %s", repr(num_voxels))
                est_sz = prop_obj.data_sz*num_voxels+prop_obj.offset
                if file_sz < est_sz:
                    self.logger.error("SORRY - Cannot process voxel file - length (%d)" \
                                      " is less than estimated size (%d): %s",
                                      file_sz, est_sz, prop_obj.file_name)
                    sys.exit(1)

                # Initialise data array to zeros
                prop_obj.data_3d = np.zeros((self.vol_sz[0], self.vol_sz[1], self.vol_sz[2]))

                # Prepare 'numpy' dtype object for binary float, integer signed/unsigned data types
                d_typ = prop_obj.make_numpy_dtype()

                # Read entire file, assumes file small enough to store in memory
                self.logger.info("Reading binary file: %s", prop_obj.file_name)
                elem_offset = prop_obj.offset//prop_obj.data_sz
                self.logger.debug("elem_offset = %s", repr(elem_offset))
                f_arr = np.fromfile(prop_obj.file_name, dtype=d_typ, count=num_voxels+elem_offset)
                fl_idx = elem_offset
                mult = [(self.axis_max[0]-self.axis_min[0])/self.vol_sz[0],
                        (self.axis_max[1]-self.axis_min[1])/self.vol_sz[1],
                        (self.axis_max[2]-self.axis_min[2])/self.vol_sz[2]]
                for z_val in range(self.vol_sz[2]):
                    for y_val in range(self.vol_sz[1]):
                        for x_val in range(self.vol_sz[0]):
                            # If numeric
                            if prop_obj.data_type != 'rgba':
                                converted, data_val = self.parse_float(f_arr[fl_idx],
                                                               prop_obj.no_data_marker)
                                if not converted:
                                    continue
                                prop_obj.assign_to_3d(x_val, y_val, z_val, data_val)
                            # If RGBA
                            else:
                                data_val = f_arr[fl_idx]
                                prop_obj.assign_to_xyz((x_val, y_val, z_val), data_val)

                            # self.logger.debug("fp[%d, %d, %d] = %s", x_val, y_val, z_val, repr(data_val))
                            fl_idx += 1

                            # Calculate the XYZ coords and their maxs & mins
                            x_coord = self.axis_o[0]+ \
                              (float(x_val)*self.axis_u[0]*mult[0] + \
                              float(y_val)*self.axis_u[1]*mult[1] + \
                              float(z_val)*self.axis_u[2]*mult[2])
                            y_coord = self.axis_o[1]+ \
                              (float(x_val)*self.axis_v[0]*mult[0] + \
                              float(y_val)*self.axis_v[1]*mult[1] + \
                              float(z_val)*self.axis_v[2]*mult[2])
                            z_coord = self.axis_o[2]+ \
                              (float(x_val)*self.axis_w[0]*mult[0] + \
                              float(y_val)*self.axis_w[1]*mult[1] + \
                              float(z_val)*self.axis_w[2]*mult[2])
                            self.geom_obj.calc_minmax(x_coord, y_coord, z_coord)

            except IOError as io_exc:
                self.logger.error("SORRY - Cannot process voxel file IOError %s %s %s",
                                  prop_obj.file_name, str(io_exc), io_exc.args)
                sys.exit(1)

        # Process flags file if desired
        if self.flags_file != '':
            if not self.SKIP_FLAGS_FILE:
                self.__read_flags_file()
            else:
                self.logger.warning("SKIP_FLAGS_FILE = True  => Skipping flags file %s",
                                    self.flags_file)
        return True



    def __read_flags_file(self):
        ''' This reads the flags file and looks for regions.
        '''
        if self.flags_array_length != self.vol_sz[0]*self.vol_sz[1]*self.vol_sz[2]:
            self.logger.warning("SORRY - Cannot process voxel flags file, inconsistent size" \
                                " between data file and flag file")
            self.logger.debug("__read_flags_file() return False")
            return False
        # Check file does not exist, sometimes needs a '.vo' on the end
        if not os.path.isfile(self.flags_file) and self.flags_file[-2:] == "@@" and \
                                                        os.path.isfile(self.flags_file+".vo"):
            self.flags_file += ".vo"

        try:
            # Check file size first
            file_sz = os.path.getsize(self.flags_file)
            num_voxels = self.vol_sz[0]*self.vol_sz[1]*self.vol_sz[2]
            est_sz = self.flags_bit_size*num_voxels+self.flags_offset
            if file_sz < est_sz:
                self.logger.error("SORRY - Cannot process voxel flags file %s - length (%d) " \
                                  "is less than calculated size (%d)",
                                  self.flags_file, file_sz, est_sz)
                sys.exit(1)

            # Initialise data array to zeros
            np.zeros((self.vol_sz[0], self.vol_sz[1], self.vol_sz[2]))

            # Prepare 'numpy' dtype object for binary float, integer signed/unsigned data types
            d_typ = np.dtype(('B', (self.flags_bit_size)))

            # Read entire file, assumes file small enough to store in memory
            self.logger.info("Reading binary flags file: %s", self.flags_file)
            f_arr = np.fromfile(self.flags_file, dtype=d_typ)
            f_idx = self.flags_offset//self.flags_bit_size
            self.flags_prop = PROPS(self.flags_file, self.logger.getEffectiveLevel())
            # self.debug('self.region_dict.keys() = %s', self.region_dict.keys())
            for z_val in range(0, self.vol_sz[2]):
                for y_val in range(0, self.vol_sz[1]):
                    for x_val in range(0, self.vol_sz[0]):
                        # self.logger.debug("%d %d %d %d => %s", x, y, z, f_idx, repr(f_arr[f_idx]))
                        # convert floating point number to a bit mask
                        bit_mask = ''
                        # NB: Single bytes are not returned as arrays
                        if self.flags_bit_size == 1:
                            bit_mask = '{0:08b}'.format(f_arr[f_idx])
                        else:
                            for bit in range(self.flags_bit_size-1, -1, -1):
                                bit_mask += '{0:08b}'.format(f_arr[f_idx][bit])
                        # self.logger.debug('bit_mask= %s', bit_mask)
                        # self.logger.debug('self.region_dict = %s', repr(self.region_dict))
                        cnt = self.flags_bit_size*8-1
                        # Examine the bit mask one bit at a time, starting at the highest bit
                        for bit in bit_mask:
                            if str(cnt) in self.region_dict and bit == '1':
                                key = self.region_dict[str(cnt)]
                                # self.logger.debug('cnt = %d bit = %d', cnt, bit)
                                # self.logger.debug('key = %s', key)
                                self.flags_prop.append_to_xyz((x_val, y_val, z_val), key)
                            cnt -= 1
                        f_idx += 1

        except IOError as io_exc:
            self.logger.error("SORRY - Cannot process voxel flags file, IOError %s %s %s",
                              self.flags_file, str(io_exc), io_exc.args)
            self.logger.debug("__read_flags_file() return False")
            return False

        return True


    def __check_vertex(self, num):
        ''' If vertex exists then returns true else false

        :param num: vertex number to search for
        '''
        for vrtx in self.__vrtx_arr:
            if vrtx.n == num:
                return True
        return False



#  END OF GocadImporter CLASS
