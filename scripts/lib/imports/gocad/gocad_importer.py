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
from lib.imports.gocad.gocad_filestr_types import GocadFileDataStrMap

from .helpers import make_line_gen, check_vertex

# Set up debugging
LOCAL_LOGGER = logging.getLogger(__name__)

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
    grp_gocad_obj = GocadImporter(debug_lvl, base_xyz=base_xyz,
                              group_name=os.path.basename(file_name).upper(),
                              nondefault_coords=nondef_coords, ct_file_dict=ct_file_dict)
    for line_idx, line in enumerate(file_lines):
        line_str = line.rstrip(' \n\r').upper()
        field = line_str.split(' ')
        LOCAL_LOGGER.debug("extract_from_grp(): line_str = %s", line_str)
        if first_line:
            first_line = False
            # Check that this isn't trying to parse a group file
            if file_ext.upper() != '.GP' or line_str not in GocadFileDataStrMap.GOCAD_HEADERS['GP']:
                LOCAL_LOGGER.error("SORRY - not a GOCAD GP file %s", repr(line_str))
                LOCAL_LOGGER.error("    filename_str = %s", filename_str)
                sys.exit(1)

        # Only set 'in_gocad' if enclosed object is not another group object
        if line_str == "BEGIN_MEMBERS" and line_idx+1 < len(file_lines) \
                               and not is_group_header(file_lines[line_idx+1]):
            in_member = True
            LOCAL_LOGGER.debug("extract_from_grp(): in_member = True")
        elif line_str == "END_MEMBERS":
            in_member = False
            LOCAL_LOGGER.debug("extract_from_grp(): in_member = False")
        elif in_member and field[0] == "GOCAD":
            in_gocad = True
            LOCAL_LOGGER.debug("extract_from_grp(): in_gocad = True")

        # If at end of GOCAD object then process it
        elif in_member and line_str == "END":
            in_gocad = False
            LOCAL_LOGGER.debug("extract_from_grp(): in_gocad = False, start processing")
            gocad_obj = GocadImporter(debug_lvl, base_xyz=base_xyz,
                              group_name=os.path.basename(file_name).upper(),
                              nondefault_coords=nondef_coords, ct_file_dict=ct_file_dict)
            # Make a copy of style of group GOCAD object, so it inherits colour defns etc.
            # from group obj
            gocad_obj.style_obj = copy.deepcopy(grp_gocad_obj.style_obj)
            is_ok, gsm_list = gocad_obj.process_gocad(src_dir, filename_str, gocad_lines)
            if is_ok:
                main_gsm_list += gsm_list
                LOCAL_LOGGER.debug("gsm_list = %s", repr(gsm_list))
            gocad_lines = []

        # If found a group header, then process it to fetch its colour defns etc.
        elif not in_member and not in_gocad and field[0] == "HEADER":
            LOCAL_LOGGER.debug("Processing header in GRP file")
            line_gen = make_line_gen(file_lines[line_idx:])
            grp_gocad_obj.process_header(line_gen)

        # If in a GOCAD file, then accumulate lines for processing
        if in_member and in_gocad:
            LOCAL_LOGGER.debug("extract_from_grp(): Appending line")
            gocad_lines.append(line)

    LOCAL_LOGGER.debug("extract_gocad() returning len(main_gsm_list)=%d", len(main_gsm_list))
    return main_gsm_list


def is_group_header(line_str):
    ''' Returns true iff line string is a GOCAD group header
        :param line_str: line string
        :returns: true iif line string is a GOCAD group header
    '''
    return line_str.rstrip('\n\r ').upper() in GocadFileDataStrMap.GOCAD_HEADERS['GP']


class GocadImporter():
    ''' Class used to read GOCAD files and store their details
    '''
    from .parsers import parse_property_header, parse_props, parse_float
    from .parsers import parse_int, parse_xyz, parse_colour, parse_axis_unit
    from .processors import process_coord_hdr, process_header, process_ascii_well_path
    from .processors import process_well_info, process_well_curve, process_prop_class_hdr, process_well_binary_file
    from .processors import process_vol_data
    from .volumes import read_volume_binary_files, calc_vo_xyz, calc_sg_xyz, read_region_flags_file

    SUPPORTED_EXTS = [
        'TS',
        'VS',
        'PL',
        'GP',
        'VO',
        'WL',
        'SG'
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

    WELL_LINE_WIDTH = 10
    ''' Line width for drawing wells
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
        ''' PROPS object used for the voxet flags file which has region data in
            it and for SGRID files
        '''

        self.invert_zaxis = False
        ''' Set to true if z-axis inversion is turned on in this GOCAD file
        '''

        self.local_props = OrderedDict()
        ''' OrderedDict of PROPS objects for attached PVRTX and PATOM properties
        '''

        self._is_ts = False
        ''' True iff it is a GOCAD TSURF file
        '''

        self._is_vs = False
        ''' True iff it is a GOCAD VSET file
        '''

        self._is_pl = False
        ''' True iff it is a GOCAD PLINE file
        '''

        self._is_vo = False
        ''' True iff it is a GOCAD VOXET file
        '''

        self._is_wl = False
        ''' True iff it is a GOCAD WELL file
        '''

        self._is_sg = False
        ''' True iff it is a GOCAD SGRID file
        '''

        self.xyz_mult = [1.0, 1.0, 1.0]
        ''' Used to convert to metres if the units are in kilometres
        '''

        self.xyz_unit = [None, None, None]
        ''' Units of XYZ axes
        '''

        self._vrtx_arr = []
        ''' Array of named tuples 'VRTX' used to store vertex data
        '''

        self._atom_arr = []
        ''' Array of named tuples 'ATOM' used to store atom data
        '''

        self._trgl_arr = []
        ''' Array of named tuples 'TRGL' used store triangle face data
        '''

        self._seg_arr = []
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

        self.points_offset = 0
        ''' Offset within points file (SGRID)
        '''

        self.points_file = ""
        ''' Points file (SGRID)
        '''

        self.region_dict = {}
        ''' Labels and bit numbers for each region in a flags file,
            key is number (as string), value is label
        '''

        self.region_colour_dict = {}
        ''' Region colour dict, key is region name, value is RGB (float, float, float)
        '''

        self.sgrid_cell_align = True
        ''' Is SGRID aligned to cells or points ?
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
        for idx, vrtx in enumerate(self._vrtx_arr, 1):
            vert_dict[vrtx.n] = idx

        # Assign atoms to dict
        for atom in self._atom_arr:
            for idx, vert in enumerate(self._vrtx_arr, 1):
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

        # Create a line generator to parse each line
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

            self.logger.debug(f"field = {field} field_raw={field_raw} line_str = {line_str} is_last = {is_last}") 
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
                elif self._is_wl:
                    # All well files
                    if field[0] == "PATH_ZM_UNIT" or field[0] == "WREF":
                        self.logger.debug("Processing ASCII well path")
                        is_last, well_path, self.meta_obj.label_list = self.process_ascii_well_path(line_gen, field)

                        # Convert well path into a series of SEG types
                        if len(well_path) > 1:
                            self._vrtx_arr.append(VRTX(1, well_path[0]))
                            for idx in range(1, len(well_path)):
                                self._seg_arr.append(SEG((idx, idx + 1)))
                                self._vrtx_arr.append(VRTX(idx + 1, well_path[idx]))
                             
                        self.logger.debug(f"Well path: {well_path}")
                        self.logger.debug(f"Label list: {self.meta_obj.label_list}")
                        retry = True

                    # Well files with well curve block
                    elif field[0] == "WELL_CURVE":
                        self.logger.debug("Processing well curve")
                        field, field_raw, is_last = self.process_well_curve(line_gen, field)

                    elif field[0] == "BINARY_DATA_FILE":
                        bin_file = os.path.join(src_dir, field_raw[1])
                        self.logger.debug(f"Opening well binary file: {bin_file}")
                        flt_arr = self.process_well_binary_file(bin_file)
                        self.logger.debug(f"bin_flts={flt_arr[:40]}")

                    elif field[0] == "WP_CATALOG_FILE":
                        bin_file = os.path.join(src_dir, field_raw[1])
                        self.logger.debug(f"Opening well wp catalog file: {bin_file}")
                        flt_arr = self.process_well_binary_file(bin_file)
                        self.logger.debug(f"p_flts={flt_arr[:40]}")

                    elif field[0] == "STATION":
                        """ Format is:  STATION MD INC AZ
                            MD = measured depth
                            INC = inclination
                            AZ = azimuth
                        """
                        well_path = self.process_station_well_path(line_gen, field)

                # Atoms, with or without properties
                elif field[0] == "ATOM" or field[0] == 'PATOM':
                    seq_no_prev = seq_no
                    is_ok_s, seq_no = self.parse_int(field[1])
                    is_ok, v_num = self.parse_int(field[2])
                    if not is_ok_s or not is_ok:
                        seq_no = seq_no_prev
                    else:
                        if check_vertex(v_num, self._vrtx_arr):
                            self._atom_arr.append(ATOM(seq_no, v_num))
                        else:
                            self.logger.error("ATOM refers to VERTEX that has not been defined yet")
                            self.logger.error("    seq_no = %d", seq_no)
                            self.logger.error("    v_num = %d", v_num)
                            self.logger.error("    line = %s", line_str)
                            sys.exit(1)

                        # Atoms with attached properties
                        if field[0] == "PATOM":
                            vert_dict = self.__make_vertex_dict()
                            self.parse_props(field, self._vrtx_arr[vert_dict[v_num] - 1].xyz,
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
                        self._vrtx_arr.append(VRTX(seq_no, (x_flt, y_flt, z_flt)))

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
                        self._trgl_arr.append(TRGL(seq_no, (a_int, b_int, c_int)))

                # Grab the segments
                elif field[0] == "SEG":
                    is_ok_a, a_int = self.parse_int(field[1])
                    is_ok_b, b_int = self.parse_int(field[2])
                    if is_ok_a and is_ok_b:
                        self._seg_arr.append(SEG((a_int, b_int)))

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
                elif self._is_vo and field[0][:4] == "AXIS":
                    self.logger.debug('VOXET: found field[0] = %s', field[0])
                    field, field_raw, is_last = self.process_vol_data(line_gen, field, field_raw, src_dir)


                # Process SGRID data
                elif self._is_sg and field[0][:4] == "AXIS":
                    self.logger.debug('SGRID: field[0] = %s', field[0])
                    field, field_raw, is_last = self.process_vol_data(line_gen, field, field_raw, src_dir)


            except IndexError as exc:
                self.handle_exc(exc)

            # END OF TEXT PROCESSING LOOP


        # Read in any binary data files and flags files attached to voxel files
        if self._is_vo or self._is_sg:
            ret_val = self.read_volume_binary_files()

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
        :param local_prop_idx_list: optional, if set, then will place multiple local \
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
        :param local_prop_idx_list: optional, if set, then will place multiple \
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
        :param local_prop_idx_list: optional, if set, then will place multiple \
                                    local property data values in object
        :param prop_idx: optional, if set, then will place property data in object
        '''
        # Convert GOCAD's volume geometry spec (SGRID & VOXET)
        if self.vol_sz:
            if self._is_sg:
                geom_obj.vol_sz = self.vol_sz
                self.axis_o = (self.geom_obj.min_x, self.geom_obj.min_y, self.geom_obj.min_z)
                geom_obj.vol_origin = (self.geom_obj.min_x, self.geom_obj.min_y, self.geom_obj.min_z)
                self.axis_min = (0.0,0.0,0.0)
                self.axis_max = (1.0,1.0,1.0)
                self.axis_u = (self.geom_obj.max_x - self.geom_obj.min_x, 0.0, 0.0)
                self.axis_v = (0.0, self.geom_obj.max_y - self.geom_obj.min_y, 0.0)
                self.axis_w = (0.0, 0.0, self.geom_obj.max_z - self.geom_obj.min_z)

            elif self._is_vo:
                geom_obj.vol_sz = self.vol_sz
                geom_obj.vol_origin = self.axis_o

            if self._is_vo or self._is_sg:
                min_vec = np.array(self.axis_min)
                max_vec = np.array(self.axis_max)
                mult_vec = max_vec - min_vec

                geom_obj.vol_axis_u = tuple((mult_vec * np.array(self.axis_u)).astype(float).tolist())
                geom_obj.vol_axis_v = tuple((mult_vec * np.array(self.axis_v)).astype(float).tolist())
                geom_obj.vol_axis_w = tuple((mult_vec * np.array(self.axis_w)).astype(float).tolist())

        # If it's a well, then set line to vertical with a narrow width
        if self._is_wl:
            geom_obj.is_vert_line = True
            geom_obj.line_width = self.WELL_LINE_WIDTH

        # Re-enumerate all geometries, because some GOCAD files have missing vertex numbers
        vert_dict = self.__make_vertex_dict()
        for v_old in self._vrtx_arr:
            vrtx = VRTX(vert_dict[v_old.n], v_old.xyz)
            geom_obj.vrtx_arr.append(vrtx)

        for t_old in self._trgl_arr:
            tri = TRGL(t_old.n, (vert_dict[t_old.abc[0]], vert_dict[t_old.abc[1]],
                                 vert_dict[t_old.abc[2]]))
            geom_obj.trgl_arr.append(tri)

        for s_old in self._seg_arr:
            sgm = SEG((vert_dict[s_old.ab[0]], vert_dict[s_old.ab[1]]))
            geom_obj.seg_arr.append(sgm)

        for a_old in self._atom_arr:
            atm = ATOM(vert_dict[a_old.n], vert_dict[a_old.v])
            geom_obj.atom_arr.append(atm)

        # Add PVTRX, PATOM data
        # Multiple properties' data points are stored in one geom_obj
        if local_prop_idx_list:
            for local_prop_idx in local_prop_idx_list:
                prop = self.local_props[local_prop_idx]
                geom_obj.add_loose_3d_data(True, prop.data_xyz)
                geom_obj.add_stats(prop.data_stats['min'], prop.data_stats['max'],
                                   prop.no_data_marker)

        # Add volume data (SGRID, VOXEL)
        # Only one set of data per geom_obj
        if prop_idx:
            prop = self.prop_dict[prop_idx]
            geom_obj.vol_data = prop.data_3d
            # Add 3d data indexed on XYZ coords
            if prop.data_xyz:
                geom_obj.add_loose_3d_data(True, prop.data_xyz)
            # Add 3d data indexed on IJK indexes
            if prop.data_ijk:
                geom_obj.add_loose_3d_data(False, prop.data_ijk)
            geom_obj.vol_data_type = prop.get_str_data_type()
            geom_obj.add_stats(prop.data_stats['min'], prop.data_stats['max'],
                               prop.no_data_marker)


    def __set_type(self, file_ext, first_line_str):
        ''' Sets the type of GOCAD file: TSURF, VOXEL, PLINE etc.

        :param fileExt: the file extension
        :param firstLineStr: first line in the file
        :returns: returns True if it could determine the type of file \
            Will return False when given the header of a GOCAD group file, since \
            cannot create a vessel object from the group file itself, only from the group members
        '''
        self.logger.debug("setType(%s,%s)", file_ext, first_line_str)
        ext_str = file_ext.lstrip('.').upper()
        # Look for other GOCAD file types within a group file
        if ext_str == 'GP':
            found = False
            for key in GocadFileDataStrMap.GOCAD_HEADERS:
                if key != 'GP' and first_line_str in GocadFileDataStrMap.GOCAD_HEADERS[key]:
                    ext_str = key
                    found = True
                    break
            if not found:
                return False

        if ext_str in GocadFileDataStrMap.GOCAD_HEADERS:
            if ext_str == 'TS' and first_line_str in GocadFileDataStrMap.GOCAD_HEADERS['TS']:
                self._is_ts = True
                return True
            if ext_str == 'VS' and first_line_str in GocadFileDataStrMap.GOCAD_HEADERS['VS']:
                self._is_vs = True
                return True
            if ext_str == 'PL' and first_line_str in GocadFileDataStrMap.GOCAD_HEADERS['PL']:
                self._is_pl = True
                return True
            if ext_str == 'VO' and first_line_str in GocadFileDataStrMap.GOCAD_HEADERS['VO']:
                self._is_vo = True
                return True
            if ext_str == 'WL' and first_line_str in GocadFileDataStrMap.GOCAD_HEADERS['WL']:
                self._is_wl = True
                return True
            if ext_str == 'SG' and first_line_str in GocadFileDataStrMap.GOCAD_HEADERS['SG']:
                self._is_sg = True
                return True


        return False


#  END OF GocadImporter CLASS
