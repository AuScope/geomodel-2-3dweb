import numpy
import sys
import os
import struct
from collections import namedtuple
from collections import OrderedDict
import logging
import traceback
import numpy as np
import copy

from db.geometry.model_geometries import MODEL_GEOMETRIES
from imports.gocad.props import PROPS
from db.style.style import STYLE
from db.geometry.types import VRTX, ATOM, TRGL, SEG
from db.metadata.metadata import METADATA, MapFeat

# Set up debugging
local_logger = logging.getLogger("gocad_vessel")

# Create console handler
local_handler = logging.StreamHandler(sys.stdout)

# Create formatter
local_formatter = logging.Formatter('%(asctime)s -- %(name)s -- %(levelname)s - %(message)s')

# Add formatter to ch
local_handler.setFormatter(local_formatter)

# Add handler to logger
local_logger.addHandler(local_handler)



def de_concat(filename_lines):
    ''' Separates joined GOCAD entries within a file

    :param filename_lines: lines from concatenated GOCAD file
    '''
    file_lines_list = []
    part_list = []
    in_file = False
    for line in filename_lines:
        line_str = line.rstrip(' \n\r').upper()
        if not in_file:
            for marker in GOCAD_VESSEL.GOCAD_HEADERS.values():
                if line_str == marker[0]:
                    in_file = True
                    part_list.append(line)
                    break
        elif in_file:
            part_list.append(line)
            if line_str == 'END':
                in_file = False
                part_list.append(line)
                file_lines_list.append(part_list)
                part_list = []
    return file_lines_list



def extract_from_grp(src_dir, filename_str, file_lines, base_xyz, debug_lvl, nondef_coords, ct_file_dict):
    ''' Extracts GOCAD files from a GOCAD group file

    :param filename_str: filename of GOCAD file
    :param file_lines: lines extracted from GOCAD group file
    :returns: a list of (MODEL_GEOMETRIES, STYLE, METADATA) objects
    '''
    local_logger.setLevel(debug_lvl)
    local_logger.debug("extract_from_grp(%s,%s)", src_dir, filename_str)
    global CtFileDict
    main_gsm_list = []
    firstLine = True
    inMember = False
    inGoCAD = False
    gocad_lines = []
    fileName, fileExt = os.path.splitext(filename_str)
    for line in file_lines:
        line_str = line.rstrip(' \n\r').upper()
        splitstr_arr = line_str.split(' ')
        if firstLine:
            firstLine = False
            if fileExt.upper() != '.GP' or line_str not in GOCAD_VESSEL.GOCAD_HEADERS['GP']:
                local_logger.error("SORRY - not a GOCAD GP file %s", repr(line_str))
                local_logger.error("    filename_str = %s", filename_str)
                sys.exit(1)
        if line_str == "BEGIN_MEMBERS":
            inMember = True
        elif line_str == "END_MEMBERS":
            inMember = False
        elif inMember and splitstr_arr[0]=="GOCAD":
            inGoCAD = True
        elif inMember and line_str == "END":
            inGoCAD = False
            gv = GOCAD_VESSEL(debug_lvl, base_xyz=base_xyz, group_name=os.path.basename(fileName).upper(), nondefault_coords=nondef_coords, ct_file_dict=ct_file_dict)
            is_ok, gsm_list = gv.process_gocad(src_dir, filename_str, gocad_lines)
            if is_ok:
                main_gsm_list += gsm_list
            gocad_lines = []
        if inMember and inGoCAD:
            gocad_lines.append(line)

    local_logger.debug("extract_gocad() returning len(main_gsm_list)=%d", len(main_gsm_list))
    return main_gsm_list





class GOCAD_VESSEL():
    ''' Class used to read GOCAD files and store their details
    '''

    GOCAD_HEADERS = {
                 'TS':['GOCAD TSURF 1'],
                 'VS':['GOCAD VSET 1'],
                 'PL':['GOCAD PLINE 1'],
                 'GP':['GOCAD HETEROGENEOUSGROUP 1', 'GOCAD HOMOGENEOUSGROUP 1'],
                 'VO':['GOCAD VOXET 1'],
                 'WL':['GOCAD WELL 1'],
    }
    ''' Constant assigns possible headers to each flename extension
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


    COORD_OFFSETS = { 'FROM_SHAPE' : (535100.0, 0.0, 0.0) }
    ''' Coordinate offsets, when file contains a coordinate system  that is not "DEFAULT" 
        The named coordinate system and (X,Y,Z) offset will apply
    '''


    STOP_ON_EXC = True 
    ''' Stop upon exception, regardless of debug level
    '''

    SKIP_FLAGS_FILE = True
    ''' Don't read flags file 
    '''


    def __init__(self, debug_level, base_xyz=(0.0, 0.0, 0.0), group_name="", nondefault_coords=False, stop_on_exc=True, ct_file_dict={}):
        ''' Initialise class

        :param debug_level: debug level taken from 'logging' module e.g. logging.DEBUG
        :param base_xyz: optional (x,y,z) floating point tuple, base_xyz is added to all coordinates
            before they are output, default is (0.0, 0.0, 0.0)
        :param group_name: optional string, name of group of this gocad file is within a group, default is ""
        :param nondefault_coords: optional flag, supports non-default coordinates, default is False
        '''
        super().__init__()
        # Set up logging, use an attribute of class name so it is only called once
        if not hasattr(GOCAD_VESSEL, 'logger'):
            GOCAD_VESSEL.logger = logging.getLogger(__name__)

            # Create console handler
            handler = logging.StreamHandler(sys.stdout)

            # Create formatter
            formatter = logging.Formatter('%(asctime)s -- %(name)s -- %(levelname)s - %(message)s')

            # Add formatter to ch
            handler.setFormatter(formatter)

            # Add handler to logger and set level
            GOCAD_VESSEL.logger.addHandler(handler)

        GOCAD_VESSEL.logger.setLevel(debug_level)

        self.logger = GOCAD_VESSEL.logger 

        # A dictionary of files which contain colour tables
        # key is GOCAD filename, val is CSV file
        self.ct_file_dict = ct_file_dict
        self.logger.debug("self.ct_file_dict = %s", self.ct_file_dict)

        self.STOP_ON_EXC = stop_on_exc

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

        self.__axis_u = None
        ''' U-axis volume vector
        '''

        self.__axis_v = None
        ''' V-axis volume vector
        '''

        self.__axis_w = None
        ''' W-axis volume vector
        '''

        self.__axis_o = None
        ''' Volume's origin (X,Y,Z)
        '''

        self.__axis_min = None
        ''' 3 dimensional minimum point of voxet volume
        '''

        self.__axis_max = None
        ''' 3 dimensional maximum point of voxet volume
        '''

        self.vol_sz = None
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
        ''' Labels and bit numbers for each region in a flags file, key is number (as string), value is label
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

        self.usesDefaultCoords = True
        ''' Uses default coordinates
        '''

        self.rock_label_idx = {}
        ''' Some voxet files have floats that are indexes to rock types
        '''

        
        self.geom_obj = MODEL_GEOMETRIES()
        self.style_obj = STYLE()
        self.meta_obj = METADATA()
        ''' Seed copies of MODEL_GEOMETRIES, STYLE, METADATA for data gathering purposes
        '''

        self.gsm_list = []
        ''' List of (MODEL_GEOMETRIES, STYLE, METADATA)
        '''


    def __handle_exc(self, exc):
        ''' If STOP_ON_EXC is set or debug is on, print details of exception and stop

        :param exc: exception
        ''' 
        if self.logger.getEffectiveLevel() == logging.DEBUG or self.STOP_ON_EXC:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            if self.STOP_ON_EXC:
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
            if '__' != field[-2:] and not callable(getattr(self,field)):
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
        for idx, v in enumerate(self.__vrtx_arr, 1):
            vert_dict[v.n] = idx

        # Assign atoms to dict
        for atom in self.__atom_arr:
            for idx, vert in enumerate(self.__vrtx_arr, 1):
                if vert.n == atom.v:
                    vert_dict[atom.n] = idx
                    break
        return vert_dict


    def line_gen(self, filename_str, file_lines):
        ''' This is a Python generator function that processes lines of the GOCAD object file
            and returns each line in various forms, from quite unprocessed to fully processed
        :param filename_str: filename of gocad file
        :param file_lines: array of strings of lines from gocad file
        :returns array of field strings in upper case with double quotes removed from strings,
                 array of field string in original case without double quotes removed,
                 line of GOCAD file in upper case,
                 boolean, True iff it is the last line of the file
        '''
        for line in file_lines:
            line_str = line.rstrip(' \n\r').upper()
            # Look out for double-quoted strings
            while line_str.count('"') >= 2:
                before_tup = line_str.partition('"')
                after_tup = before_tup[2].partition('"')
                line_str = before_tup[0]+" "+after_tup[0].strip(' ').replace(' ','_')+" "+after_tup[2]
            splitstr_arr_raw = line.rstrip(' \n\r').split()
            splitstr_arr = line_str.split()

            # Skip blank lines
            if len(splitstr_arr)==0:
                continue
            yield splitstr_arr, splitstr_arr_raw, line_str, line == file_lines[-1:][0]
        yield [], [], '', True



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

        fileName, fileExt = os.path.splitext(filename_str)
        self.np_filename = os.path.basename(fileName)

        # Check that we have a GOCAD file that we can process
        # Nota bene: This will return if called for the header of a GOCAD group file
        if not self.__setType(fileExt, file_lines[0].rstrip(' \n\r').upper()):
            self.logger.error("process_gocad() Can't detect GOCAD file object type, return False")
            return False, []

        line_gen = self.line_gen(filename_str, file_lines)
        is_last = False
        while not is_last:
            splitstr_arr, splitstr_arr_raw, line_str, is_last = next(line_gen)
    
            if is_last and len(splitstr_arr)==0:
                break

            self.logger.debug("splitstr_arr = %s line_str = %s is_last = %s", repr(splitstr_arr), repr(line_str), repr(is_last))

            # Skip the subsets keywords
            if splitstr_arr[0] in ["SUBVSET", "ILINE", "TFACE", "TVOLUME"]:
                self.logger.debug("Skip subset keywords")
                continue

            # Skip control nodes (used to denote fixed points in GOCAD)
            if splitstr_arr[0] == "CNP":
                self.logger.debug("Skip control nodes")
                continue

            try:
                # Are we in the main header?
                if splitstr_arr[0] == "HEADER":
                    self.logger.debug("Processing header")
                    is_last = self.__process_header(line_gen)

                # Are we within coordinate system header?
                elif splitstr_arr[0] == "GOCAD_ORIGINAL_COORDINATE_SYSTEM":
                    self.logger.debug("Processing coordinate system")
                    # Process coordinate header fields
                    is_last, is_error = self.__process_coord_hdr(line_gen)
                    if is_error:
                        self.logger.debug("process_gocad() return False")
                        return False, []
            
                # Are we in the property class header?
                elif splitstr_arr[0] == "PROPERTY_CLASS_HEADER":
                    self.logger.debug("Processing property class header")
                    is_last = self.__process_prop_class_hdr(line_gen, splitstr_arr)

                # Property names, this is not the class names
                elif splitstr_arr[0] == "PROPERTIES":
                    if len(self.local_props) == 0:
                        for class_name in splitstr_arr[1:]:
                            self.local_props[class_name] = PROPS(class_name, debug_lvl)
                    self.logger.debug(" properties list = %s", repr(splitstr_arr[1:]))

                # These are the property names for the point properties (e.g. PVRTX, PATOM)
                elif splitstr_arr[0] == "PROPERTY_CLASSES":
                    if len(self.local_props) == 0:
                        for class_name in splitstr_arr[1:]:
                            self.local_props[class_name] = PROPS(class_name, debug_lvl)
                    self.logger.debug(" property classes = %s", repr(splitstr_arr[1:]))

                # This is the number of floats/ints for each property, usually it is '1',
                # but XYZ values are '3'
                elif splitstr_arr[0] == "ESIZES":
                    for idx, prop_obj in enumerate(self.local_props.values(), 1):
                        is_ok, l = self.__parse_int(splitstr_arr[idx])
                        if is_ok:
                            prop_obj.data_sz = l
                    self.logger.debug(" property_sizes = %s", repr(splitstr_arr[1:]))

                # Read values representing no data for this property at a coordinate point
                elif splitstr_arr[0] == "NO_DATA_VALUES":
                    for idx, prop_obj in enumerate(self.local_props.values(), 1):
                        try:
                            converted, fp  = self.__parse_float(splitstr_arr[idx])
                            if converted:
                                prop_obj.no_data_marker = fp
                                self.logger.debug("prop_obj.no_data_marker = %f", prop_obj.no_data_marker)
                        except IndexError as exc:
                            self.__handle_exc(exc)
                    self.logger.debug(" property_nulls = %s", repr(splitstr_arr[1:]))
                
                # Atoms, with or without properties
                elif splitstr_arr[0] == "ATOM" or splitstr_arr[0] == 'PATOM':
                    seq_no_prev = seq_no
                    is_ok_s, seq_no = self.__parse_int(splitstr_arr[1])
                    is_ok, v_num = self.__parse_int(splitstr_arr[2])
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
                        if splitstr_arr[0] == "PATOM":
                            vert_dict = self.__make_vertex_dict()
                            self.__parse_props(splitstr_arr, self.__vrtx_arr[vert_dict[v_num] - 1].xyz, True)
                  
                # Grab the vertices and properties, does not care if there are gaps in the sequence number
                elif splitstr_arr[0] == "PVRTX" or  splitstr_arr[0] == "VRTX":
                    seq_no_prev = seq_no
                    is_ok_s, seq_no = self.__parse_int(splitstr_arr[1])
                    is_ok, x_flt, y_flt, z_flt = self.__parse_XYZ(True, splitstr_arr[2], splitstr_arr[3], splitstr_arr[4], True)
                    self.logger.debug("ParseXYZ %s %f %f %f from %s %s %s", repr(is_ok), x_flt, y_flt, z_flt,  splitstr_arr[2], splitstr_arr[3], splitstr_arr[4])
                    if not is_ok_s or not is_ok:
                        seq_no = seq_no_prev
                    else:
                        # Add vertex
                        if self.invert_zaxis:
                            z_flt = -z_flt
                        self.__vrtx_arr.append(VRTX(seq_no, (x_flt, y_flt, z_flt)))
   
                        # Vertices with attached properties
                        if splitstr_arr[0] == "PVRTX":
                            self.__parse_props(splitstr_arr, (x_flt, y_flt, z_flt))

                # Grab the triangular edges
                elif splitstr_arr[0] == "TRGL":
                    seq_no_prev = seq_no
                    is_ok_s, seq_no = self.__parse_int(splitstr_arr[1])
                    is_ok, a_int, b_int, c_int = self.__parse_XYZ(False, splitstr_arr[1], splitstr_arr[2], splitstr_arr[3], False, False)
                    if not is_ok or not is_ok_s:
                        seq_no = seq_no_prev
                    else:
                        self.__trgl_arr.append(TRGL(seq_no, (a_int, b_int, c_int)))

                # Grab the segments
                elif splitstr_arr[0] == "SEG":
                    is_ok_a, a_int = self.__parse_int(splitstr_arr[1])
                    is_ok_b, b_int = self.__parse_int(splitstr_arr[2])
                    if is_ok_a and is_ok_b:
                        self.__seg_arr.append(SEG((a_int, b_int)))

                # Grab metadata - see 'metadata.py' for more info
                elif splitstr_arr[0] in ("STRATIGRAPHIC_POSITION","GEOLOGICAL_FEATURE"):
                    self.meta_obj.geofeat_name = splitstr_arr[1]
                    if splitstr_arr[0] == 'STRATIGRAPHIC_POSITION':
                        is_ok, self.meta_obj.geoevent_numeric_age_range = self.__parse_int(splitstr_arr[2], 0)
                        self.meta_obj.mapped_feat = MapFeat.GEOLOGICAL_UNIT

                elif splitstr_arr[0] == "GEOLOGICAL_TYPE":
                    if splitstr_arr[1] == "FAULT":
                        self.meta_obj.mapped_feat = MapFeat.SHEAR_DISP_STRUCT
                    elif  splitstr_arr[1] == "INTRUSIVE":
                        self.meta_obj.mapped_feat = MapFeat.GEOLOGICAL_UNIT
                    elif splitstr_arr[1] in ("BOUNDARY","UNCONFORMITY","INTRAFORMATIONAL"):
                        self.meta_obj.mapped_feat = MapFeat.CONTACT


                # What kind of property is this? Is it a measurement, or a reference to a rock colour table?
                elif splitstr_arr[0] == "PROPERTY_SUBCLASS":
                    if len(splitstr_arr) > 2 and splitstr_arr[2] == "ROCK": 
                        prop_idx = splitstr_arr[1]
                        self.prop_dict[prop_idx].is_index_data = True
                        self.logger.debug("self.prop_dict[%s].is_index_data = True", prop_idx) 
                        # Sometimes there is an array of indexes and labels
                        self.logger.debug(" len(splitstr_arr) = %d",  len(splitstr_arr))
                        if len(splitstr_arr) > 4:
                            for idx in range(4, len(splitstr_arr), 2):
                                rock_label = splitstr_arr[idx] 
                                is_ok, l = self.__parse_int(splitstr_arr[1+idx])
                                if is_ok:
                                    rock_index = l
                                    self.rock_label_idx.setdefault(prop_idx, {})
                                    self.rock_label_idx[prop_idx][rock_index] = rock_label
                                    self.logger.debug("self.rock_label_idx[%s] = %s", prop_idx, repr(self.rock_label_idx[prop_idx]))
                    
                # Extract binary file name
                elif splitstr_arr[0] == "PROP_FILE":
                    self.prop_dict[splitstr_arr[1]].file_name = os.path.join(src_dir, splitstr_arr_raw[2])
                    self.logger.debug("self.prop_dict[%s].file_name = %s", splitstr_arr[1], self.prop_dict[splitstr_arr[1]].file_name)

                # Size of each value in binary file (measured in bytes, usually 1,2,4)
                elif splitstr_arr[0] == "PROP_ESIZE":
                    is_ok, l = self.__parse_int(splitstr_arr[2])
                    if is_ok:
                       self.prop_dict[splitstr_arr[1]].data_sz = l
                       self.logger.debug("self.prop_dict[%s].data_sz = %d", splitstr_arr[1], self.prop_dict[splitstr_arr[1]].data_sz)

                # The type of non-float value in binary file: OCTET, SHORT, RGBA
                # IF this is present, then it is assumed not to be floating point
                # FIXME: Must support 'RGBA' storage type too
                elif splitstr_arr[0] == "PROP_STORAGE_TYPE":
                    # Single byte integer
                    if splitstr_arr[2] == "OCTET":
                        self.prop_dict[splitstr_arr[1]].data_type = "b"
                    # Short int, 2 bytes long
                    elif splitstr_arr[2] == "SHORT":
                        self.prop_dict[splitstr_arr[1]].data_type = "h"
                    # Colour data
                    elif splitstr_arr[2] == "RGBA":
                        self.logger.error("Unsupported storage type: RGBA")
                        sys.exit(1)
                    else:
                        self.logger.error("Unknown type %s", splitstr_arr[2])
                        sys.exit(1)
                    self.logger.debug("self.prop_dict[%s].data_type = %s", splitstr_arr[1], self.prop_dict[splitstr_arr[1]].data_type)

                # If binary file contains integers, are they signed integers?
                elif splitstr_arr[0] == "PROP_SIGNED":
                    self.prop_dict[splitstr_arr[1]].signed_int = (splitstr_arr[2] == "1")
                    self.logger.debug("self.prop_dict[%s].signed_int = %s", splitstr_arr[1], repr(self.prop_dict[splitstr_arr[1]].signed_int))

                # Type of value in binary file: IBM, IEEE
                # NB: We do not support IBM-style floats
                elif splitstr_arr[0] == "PROP_ETYPE":
                    if splitstr_arr[2] != "IEEE":
                        self.logger.error("Cannot process %s type floating points", splitstr_arr[1])
                        sys.exit(1)

                # Binary file format: RAW or SEGY
                # NB: Cannot process SEGY formats 
                elif splitstr_arr[0] == "PROP_EFORMAT":
                    if splitstr_arr[2] != "RAW":
                        self.logger.error("Cannot process %s format volume data", splitstr_arr[1])
                        sys.exit(1)

                # Offset in bytes within binary file
                elif splitstr_arr[0] == "PROP_OFFSET":
                     is_ok, l = self.__parse_int(splitstr_arr[2])
                     if is_ok:
                         self.prop_dict[splitstr_arr[1]].offset = l
                         self.logger.debug("self.prop_dict[%s].offset = %d",  splitstr_arr[1], self.prop_dict[splitstr_arr[1]].offset)

                # The number that is used to represent 'no data' in binary file
                elif splitstr_arr[0] == "PROP_NO_DATA_VALUE":
                    converted, fp = self.__parse_float(splitstr_arr[2])
                    if converted:
                        self.prop_dict[splitstr_arr[1]].no_data_marker = fp
                        self.logger.debug("self.prop_dict[%s].no_data_marker = %f", splitstr_arr[1], self.prop_dict[splitstr_arr[1]].no_data_marker)

                # Layout of VOXET data
                elif self.__is_vo:
                    if splitstr_arr[0] == "AXIS_O":
                        is_ok, x_flt, y_flt, z_flt = self.__parse_XYZ(True, splitstr_arr[1], splitstr_arr[2], splitstr_arr[3], True)
                        if is_ok:
                            self.__axis_o = (x_flt, y_flt, z_flt)
                            self.logger.debug("self.__axis_o = %s", repr(self.__axis_o))
    
                    elif splitstr_arr[0] == "AXIS_U":
                        is_ok, x_flt, y_flt, z_flt = self.__parse_XYZ(True, splitstr_arr[1], splitstr_arr[2], splitstr_arr[3], False, False)
                        if is_ok:
                            self.__axis_u = (x_flt, y_flt, z_flt)
                            self.logger.debug("self.__axis_u = %s", repr(self.__axis_u))

                    elif splitstr_arr[0] == "AXIS_V":
                        is_ok, x_flt, y_flt, z_flt = self.__parse_XYZ(True, splitstr_arr[1], splitstr_arr[2], splitstr_arr[3], False, False)
                        if is_ok:
                            self.__axis_v = (x_flt, y_flt, z_flt)
                            self.logger.debug("self.__axis_v = %s", repr(self.__axis_v))

                    elif splitstr_arr[0] == "AXIS_W":
                        is_ok, x_flt, y_flt, z_flt = self.__parse_XYZ(True, splitstr_arr[1], splitstr_arr[2], splitstr_arr[3], False, False)
                        if is_ok:
                            self.__axis_w = (x_flt, y_flt, z_flt)
                            self.logger.debug("self.axis_w= %s", repr(self.__axis_w))

                    elif splitstr_arr[0] == "AXIS_N":
                        is_ok, x_int, y_int, z_int = self.__parse_XYZ(False, splitstr_arr[1], splitstr_arr[2], splitstr_arr[3], False, False)
                        if is_ok:
                            self.vol_sz = (x_int, y_int, z_int)
                            self.logger.debug("self.vol_sz= %s", repr(self.vol_sz))

                    elif splitstr_arr[0] == "AXIS_MIN":
                        is_ok, x_flt, y_flt, z_flt = self.__parse_XYZ(True, splitstr_arr[1], splitstr_arr[2], splitstr_arr[3], False, False)
                        if is_ok:
                            self.__axis_min = (x_flt, y_flt, z_flt)
                            self.logger.debug("self.__axis_min= %s", repr(self.__axis_min))

                    elif splitstr_arr[0] == "AXIS_MAX":
                        is_ok, x_flt, y_flt, z_flt = self.__parse_XYZ(True, splitstr_arr[1], splitstr_arr[2], splitstr_arr[3], False, False)
                        if is_ok:
                            self.__axis_max = (x_flt, y_flt, z_flt)
                            self.logger.debug("self.__axis_max= %s", repr(self.__axis_max))

                    elif splitstr_arr[0] == "AXIS_UNIT":
                        self.__process_axis_unit(splitstr_arr)

                    elif splitstr_arr[0] == "FLAGS_ARRAY_LENGTH":
                        is_ok, l = self.__parse_int(splitstr_arr[1])
                        if is_ok:
                            self.flags_array_length = l
                            self.logger.debug("self.flags_array_length= %d", self.flags_array_length)

                    elif splitstr_arr[0] == "FLAGS_BIT_LENGTH":
                        is_ok, l = self.__parse_int(splitstr_arr[1])
                        if is_ok:
                            self.flags_bit_length = l
                            self.logger.debug("self.flags_bit_length= %d", self.flags_bit_length)
    
                    elif splitstr_arr[0] == "FLAGS_ESIZE":
                        is_ok, l = self.__parse_int(splitstr_arr[1])
                        if is_ok:
                            self.flags_bit_size = l
                            self.logger.debug("self.flags_bit_size= %d", self.flags_bit_size)
    
                    elif splitstr_arr[0] == "FLAGS_OFFSET":
                        is_ok, l = self.__parse_int(splitstr_arr[1])
                        if is_ok:
                            self.flags_offset = l
                            self.logger.debug("self.flags_offset= %d", self.flags_offset)

                    elif splitstr_arr[0] == "FLAGS_FILE":
                        self.flags_file =  os.path.join(src_dir, splitstr_arr_raw[1])
                        self.logger.debug("self.flags_file= %s", self.flags_file)

                    elif splitstr_arr[0] == "REGION":
                        self.region_dict[splitstr_arr[2]] = splitstr_arr[1]
                        self.logger.debug("self.region_dict[%s] = %s", splitstr_arr[2], splitstr_arr[1])

                # If a well object
                elif self.__is_wl:
                    pass

            except IndexError as exc:
                self.__handle_exc(exc)
    
            # END OF TEXT PROCESSING LOOP


        # Read in any binary data files and flags files attached to voxel files
        if self.__is_vo:
            ret_val = self.__read_voxel_binary_files()

        # Complete initalisation of geometry object
        if len(self.local_props)>0:
            geom_obj = copy.deepcopy(self.geom_obj)
            style_obj = copy.deepcopy(self.style_obj)
            meta_obj = copy.deepcopy(self.meta_obj)
            propIdxList = self.local_props.keys()
            self.__init_metadata(meta_obj, localPropIdxList=propIdxList)
            self.__init_geometry(geom_obj, localPropIdxList=propIdxList)
            self.__init_style(style_obj, localPropIdxList=propIdxList)
            self.gsm_list.append((geom_obj, style_obj, meta_obj)) 

        elif len(self.prop_dict)>0:
            for propIdx in self.prop_dict:
                geom_obj = copy.deepcopy(self.geom_obj)
                style_obj = copy.deepcopy(self.style_obj)
                meta_obj = copy.deepcopy(self.meta_obj)
                self.__init_metadata(meta_obj, propIdx=propIdx)
                self.__init_geometry(geom_obj, propIdx=propIdx)
                self.__init_style(style_obj, propIdx=propIdx)
                self.gsm_list.append((geom_obj, style_obj, meta_obj)) 
                
        else:
            self.__init_metadata(self.meta_obj)
            self.__init_geometry(self.geom_obj)
            self.gsm_list.append((self.geom_obj, self.style_obj, self.meta_obj)) 
            
          

        # Complete initialisation of metadata object

        self.logger.debug("process_gocad() returns %s, %s", repr(ret_val), repr(self.gsm_list))
        return ret_val, self.gsm_list


    def __init_style(self, style_obj, localPropIdxList=None, propIdx=None):
        ''' Extract style data from GOCAD_VESSEL and place in style object
        :param style_obj: style object which will hold data taken from GOCAD_VESSEL object
        :param localPropIdxList: optional, if set, then will place multiple local property data values in object
        :param propIdx: optional, if set, then will place property data in object
        '''
        if localPropIdxList:
            for localPropIdx in localPropIdxList:
                prop = self.local_props[localPropIdx]
                style_obj.add_tables(prop.colour_map, prop.rock_label_table)
        if propIdx:
            prop = self.prop_dict[propIdx]
            style_obj.add_tables(prop.colour_map, prop.rock_label_table)
            


    def __init_metadata(self, meta_obj, localPropIdxList=None, propIdx=None):
        ''' Extract metadata from GOCAD_VESSEL and place in metadata object
        :param meta_obj: metadata object which will hold data from GOCAD_VESSEL object
        :param localPropIdxList: optional, if set, then will place multiple local property data values in object
        :param propIdx: optional, if set, then will place property data in object
        '''
        group_name = ''
        if len(self.group_name)>0:
            group_name = self.group_name+"-"
        if len(self.header_name)>0:
            meta_obj.name = group_name + self.header_name
        else:
            meta_obj.name = group_name + "geometry"
        if localPropIdxList:
            for localPropIdx in localPropIdxList:
                meta_obj.add_property_name(localPropIdx)
        if propIdx:
            meta_obj.add_property_name(self.prop_dict[propIdx].class_name)
            meta_obj.is_index_data = self.prop_dict[propIdx].is_index_data
            if len(self.prop_dict[propIdx].rock_label_table) > 0:
                meta_obj.rock_label_table = self.prop_dict[propIdx].rock_label_table
            meta_obj.src_filename = self.prop_dict[propIdx].file_name


    def __init_geometry(self, geom_obj, localPropIdxList=None, propIdx=None):
        ''' Convert GOCAD_VESSEL to MODEL_GEOMETRY version
        :param geom_obj: MODEL_GEOMETRY object where GOCAD_VESSEL data is placed
        :param localPropIdxList: optional, if set, then will place multiple local property data values in object
        :param propIdx: optional, if set, then will place property data in object
        '''
        # Convert GOCAD's volume geometry spec 
        if self.__is_vo and self.vol_sz:
            geom_obj.vol_origin = self.__axis_o
            geom_obj.vol_sz = self.vol_sz
            min_vec = np.array(self.__axis_min)
            max_vec = np.array(self.__axis_max)
            mult_vec = max_vec - min_vec 
        
            geom_obj.vol_axis_u = tuple((mult_vec * np.array(self.__axis_u)).tolist())
            geom_obj.vol_axis_v = tuple((mult_vec * np.array(self.__axis_v)).tolist())
            geom_obj.vol_axis_w = tuple((mult_vec * np.array(self.__axis_w)).tolist())

        # Re-enumerate all geometries, because some GOCAD files have missing vertex numbers
        vert_dict = self.__make_vertex_dict()
        for v_old in self.__vrtx_arr:
            v = VRTX(vert_dict[v_old.n], v_old.xyz)
            geom_obj.vrtx_arr.append(v)

        for t_old in self.__trgl_arr:
            t = TRGL(t_old.n, (vert_dict[t_old.abc[0]], vert_dict[t_old.abc[1]], vert_dict[t_old.abc[2]]))
            geom_obj.trgl_arr.append(t)

        for s_old in self.__seg_arr:
            s = SEG((vert_dict[s_old.ab[0]], vert_dict[s_old.ab[1]]))
            geom_obj.seg_arr.append(s)

        for a_old in self.__atom_arr:
            a = ATOM(vert_dict[a_old.n], vert_dict[a_old.v])
            geom_obj.atom_arr.append(a)
        
        # Add PVTRX, PATOM data (and eventually SGRID)
        # Multiple properties' data points are stored in one geom_obj
        if localPropIdxList:
            for localPropIdx in localPropIdxList:
                prop = self.local_props[localPropIdx]
                geom_obj.add_xyz_data(prop.data_xyz)
                geom_obj.add_stats(prop.data_stats['min'], prop.data_stats['max'], prop.no_data_marker)

        # Add volume data
        # Only one set of data per geom_obj
        if propIdx:
            prop = self.prop_dict[propIdx]
            geom_obj.vol_data = prop.data_3d
            geom_obj.vol_data_type = prop.get_str_data_type()
            geom_obj.add_stats(prop.data_stats['min'], prop.data_stats['max'], prop.no_data_marker)
        

    def __setType(self, fileExt, firstLineStr):
        ''' Sets the type of GOCAD file: TSURF, VOXEL, PLINE etc.

        :param fileExt: the file extension
        :param firstLineStr: first line in the file
        :returns: returns True if it could determine the type of file
            Will return False when given the header of a GOCAD group file, since
            cannot create a vessel object from the group file itself, only from the group members
        '''
        self.logger.debug("setType(%s,%s)", fileExt, firstLineStr)
        ext_str = fileExt.lstrip('.').upper()
        # Look for other GOCAD file types within a group file
        if ext_str=='GP':
            found = False
            for key in self.GOCAD_HEADERS:
                if key!='GP' and firstLineStr in self.GOCAD_HEADERS[key]:
                    ext_str = key
                    found = True
                    break
            if not found:
                return False

        if ext_str in self.GOCAD_HEADERS:
            if ext_str=='TS' and firstLineStr in self.GOCAD_HEADERS['TS']:
                self.__is_ts = True
                return True
            elif ext_str=='VS' and firstLineStr in self.GOCAD_HEADERS['VS']:
                self.__is_vs = True
                return True
            elif ext_str=='PL' and firstLineStr in self.GOCAD_HEADERS['PL']:
                self.__is_pl = True
                return True
            elif ext_str=='VO' and firstLineStr in self.GOCAD_HEADERS['VO']:
                self.__is_vo = True
                return True
            elif ext_str=='WL' and firstLineStr in self.GOCAD_HEADERS['WL']:
                self.__is_wl = True
                return True

        return False


    def __parse_property_header(self, prop_obj, line_str):
        ''' Parses the PROPERTY header, extracting the colour table info and storing it in PROPS object

        :params prop_obj: a PROPS object to store the data
        :params line_str: current line
        '''
        name_str, sep, value_str = line_str.partition(':')
        name_str = name_str.strip()
        value_str = value_str.strip()
        if name_str=='*COLORMAP*SIZE':
            self.logger.debug("colourmap-size %s", value_str)
        elif name_str=='*COLORMAP*NBCOLORS':
            self.logger.debug("numcolours %s", value_str)
        elif name_str=='HIGH_CLIP':
            self.logger.debug("highclip %s", value_str)
        elif name_str=='LOW_CLIP':
            self.logger.debug("lowclip %s", value_str)
        # Read in the name of the colour map for this property
        elif name_str=='COLORMAP':
            prop_obj.colourmap_name = value_str
            self.logger.debug("prop_obj.colourmap_name = %s", prop_obj.colourmap_name)
        # Read in the colour map for this property
        elif name_str=='*COLORMAP*'+prop_obj.colourmap_name+'*COLORS' or name_str=='*'+prop_obj.colourmap_name+'*ROCK_COLORS':
            lut_arr = value_str.split(' ')
            for idx in range(0, len(lut_arr), 4):
                try:
                    prop_obj.colour_map[int(lut_arr[idx])] = (float(lut_arr[idx+1]), float(lut_arr[idx+2]), float(lut_arr[idx+3]))
                    self.logger.debug("prop_obj.colour_map = %s", prop_obj.colour_map)
                except (IndexError, OverflowError, ValueError) as exc:
                    self.__handle_exc(exc)



    def __read_voxel_binary_files(self):
        ''' Open up and read binary voxel file
        '''
        if self.vol_sz==None:
            self.logger.error("Cannot process voxel file, cube size is not defined, missing 'AXIS_N'")
            sys.exit(1)
        for file_idx, prop_obj in self.prop_dict.items():
            # Sometimes filename needs a .vo on the end
            if not os.path.isfile(prop_obj.file_name) and prop_obj.file_name[-2:]=="@@" and \
                                          os.path.isfile(prop_obj.file_name+".vo"):
                prop_obj.file_name += ".vo"

            # If there is a colour table in CSV file then read it
            bin_file = os.path.basename(prop_obj.file_name)
            if bin_file in self.ct_file_dict:
                csv_file_path = os.path.join(os.path.dirname(prop_obj.file_name), self.ct_file_dict[bin_file])
                prop_obj.read_colour_table_csv(csv_file_path)
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
                    self.logger.error("SORRY - Cannot process voxel file - length (%d) is less than estimated size (%d): %s", file_sz, est_sz, prop_obj.file_name)
                    sys.exit(1)

                # Initialise data array to zeros
                prop_obj.data_3d = numpy.zeros((self.vol_sz[0], self.vol_sz[1], self.vol_sz[2]))

                # Prepare 'numpy' dtype object for binary float, integer signed/unsigned data types
                dt = prop_obj.make_numpy_dtype()

                # Read entire file, assumes file small enough to store in memory
                self.logger.info("Reading binary file: %s", prop_obj.file_name)
                elem_offset = prop_obj.offset//prop_obj.data_sz
                self.logger.debug("elem_offset = %s", repr(elem_offset))
                f_arr = numpy.fromfile(prop_obj.file_name, dtype=dt, count=num_voxels+elem_offset)
                fl_idx = elem_offset 
                mult = [(self.__axis_max[0]-self.__axis_min[0])/self.vol_sz[0],
                        (self.__axis_max[1]-self.__axis_min[1])/self.vol_sz[1],
                        (self.__axis_max[2]-self.__axis_min[2])/self.vol_sz[2]]
                for z in range(self.vol_sz[2]):
                    for y in range(self.vol_sz[1]):
                        for x in range(self.vol_sz[0]):
                            converted, fp = self.__parse_float(f_arr[fl_idx], prop_obj.no_data_marker)
                            # self.logger.debug("fp[%d, %d, %d] = %f", x,y,z, fp)
                            fl_idx +=1
                            if not converted:
                                continue
                            prop_obj.assign_to_3d(x,y,z, fp)

                            # Calculate the XYZ coords and their maxs & mins
                            X_coord = self.__axis_o[0]+ \
                              (float(x)*self.__axis_u[0]*mult[0] + float(y)*self.__axis_u[1]*mult[1] + float(z)*self.__axis_u[2]*mult[2])
                            Y_coord = self.__axis_o[1]+ \
                              (float(x)*self.__axis_v[0]*mult[0] + float(y)*self.__axis_v[1]*mult[1] + float(z)*self.__axis_v[2]*mult[2])
                            Z_coord = self.__axis_o[2]+ \
                              (float(x)*self.__axis_w[0]*mult[0] + float(y)*self.__axis_w[1]*mult[1] + float(z)*self.__axis_w[2]*mult[2]) 
                            self.geom_obj.calc_minmax(X_coord, Y_coord, Z_coord)
                             
            except IOError as e:
                self.logger.error("SORRY - Cannot process voxel file IOError %s %s %s", prop_obj.file_name, str(e), e.args)
                sys.exit(1)

        # Process flags file if desired
        if self.flags_file!='':
            if not self.SKIP_FLAGS_FILE:
                self.__read_flags_file()
            else:
                self.logger.warning("SKIP_FLAGS_FILE = True  => Skipping flags file %s", self.flags_file)
        return True


                    
    def __read_flags_file(self):
        ''' This reads the flags file and looks for regions.
        '''
        if self.flags_array_length != self.vol_sz[0]*self.vol_sz[1]*self.vol_sz[2]:
            self.logger.warning("SORRY - Cannot process voxel flags file, inconsistent size between data file and flag file")
            self.logger.debug("__read_flags_file() return False")
            return False
        # Check file does not exist, sometimes needs a '.vo' on the end
        if not os.path.isfile(self.flags_file) and self.flags_file[-2:]=="@@" and \
                                                        os.path.isfile(self.flags_file+".vo"):
            self.flags_file += ".vo"

        try: 
            # Check file size first
            file_sz = os.path.getsize(self.flags_file)
            num_voxels = self.vol_sz[0]*self.vol_sz[1]*self.vol_sz[2]
            est_sz =  self.flags_bit_size*num_voxels+self.flags_offset
            if file_sz < est_sz:
                self.logger.error("SORRY - Cannot process voxel flags file %s - length (%d) is less than calculated size (%d)", self.flags_file, file_sz, est_sz)
                sys.exit(1)

            # Initialise data array to zeros
            flag_data = numpy.zeros((self.vol_sz[0], self.vol_sz[1], self.vol_sz[2]))

            # Prepare 'numpy' dtype object for binary float, integer signed/unsigned data types
            dt =  numpy.dtype(('B',(self.flags_bit_size)))

            # Read entire file, assumes file small enough to store in memory
            self.logger.info("Reading binary flags file: %s", self.flags_file)
            f_arr = numpy.fromfile(self.flags_file, dtype=dt)
            f_idx = self.flags_offset//self.flags_bit_size
            self.flags_prop = PROPS(self.flags_file, self.logger.getEffectiveLevel())
            # self.debug('self.region_dict.keys() = %s', self.region_dict.keys())
            for z in range(0,self.vol_sz[2]):
                for y in range(0, self.vol_sz[1]):
                    for x in range(0, self.vol_sz[0]):
                        # self.logger.debug("%d %d %d %d => %s", x, y, z, f_idx, repr(f_arr[f_idx]))
                        # convert floating point number to a bit mask
                        bit_mask = ''
                        # NB: Single bytes are not returned as arrays
                        if self.flags_bit_size==1:
                            bit_mask = '{0:08b}'.format(f_arr[f_idx])
                        else:
                            for b in range(self.flags_bit_size-1, -1, -1):
                                bit_mask += '{0:08b}'.format(f_arr[f_idx][b])
                        # self.logger.debug('bit_mask= %s', bit_mask)
                        # self.logger.debug('self.region_dict = %s', repr(self.region_dict))
                        cnt = self.flags_bit_size*8-1
                        # Examine the bit mask one bit at a time, starting at the highest bit
                        for bit in bit_mask:
                            if str(cnt) in self.region_dict and bit=='1':
                                key = self.region_dict[str(cnt)]
                                # self.logger.debug('cnt = %d bit = %d', cnt, bit)
                                # self.logger.debug('key = %s', key)
                                self.flags_prop.append_to_xyz((x,y,z), key)
                            cnt -= 1
                        f_idx += 1
            
        except IOError as e:
            self.logger.error("SORRY - Cannot process voxel flags file, IOError %s %s %s", self.flags_file, str(e), e.args)
            self.logger.debug("__read_flags_file() return False")
            return False

        return True



    def __parse_props(self, splitstr_arr, coord_tup, is_patom = False):
        ''' This parses a line of properties associated with a PVTRX or PATOM line

        :param splitstr_arr: array of strings representing line with properties
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
                fp_str = splitstr_arr[col_idx]
                # Skip GOCAD control nodes e.g. 'CNXY', 'CNXYZ'
                if fp_str[:2].upper()=='CN':
                    col_idx += 1
                    fp_str = splitstr_arr[col_idx]
                converted, fp = self.__parse_float(fp_str, prop_obj.no_data_marker)
                if converted:
                    prop_obj.assign_to_xyz(coord_tup, fp)
                    self.logger.debug("prop_obj.data_xyz[%s] = %f", repr(coord_tup), fp)
                col_idx += 1
            # Property has 3 floats i.e. XYZ
            elif prop_obj.data_sz == 3:
                fp_strX = splitstr_arr[col_idx]
                # Skip GOCAD control nodes e.g. 'CNXY', 'CNXYZ'
                if fp_strX[:2].upper()=='CN':
                    col_idx += 1
                    fp_strX = splitstr_arr[col_idx]
                fp_strY = splitstr_arr[col_idx+1]
                fp_strZ = splitstr_arr[col_idx+2]
                convertedX, fpX = self.__parse_float(fp_strX, prop_obj.no_data_marker)
                convertedY, fpY = self.__parse_float(fp_strY, prop_obj.no_data_marker)
                convertedZ, fpZ = self.__parse_float(fp_strZ, prop_obj.no_data_marker)
                if convertedZ and convertedY and convertedX:
                    prop_obj.assign_to_xyz(coord_tup, (fpX, fpY, fpZ))
                    self.logger.debug("prop_obj.data_xyz[%s] = (%f,%f,%f)", repr(coord_tup), fpX, fpY, fpZ)
                col_idx += 3
            else:
                self.logger.error("Cannot process property size of != 3 and !=1: %d %s", prop_obj.data_sz, repr(prop_obj))
                sys.exit(1)


    def __parse_float(self, fp_str, null_val=None):
        ''' Converts a string to float, handles infinite values 

        :param fp_str: string to convert to a float
        :param null_val: value representing 'no data'
        :returns: a boolean and a float
            If could not convert then return (False, None) else if 'null_val' is defined return (False, null_val)
        '''
        # Handle GOCAD's C++ floating point infinity for Windows and Linux
        if fp_str in ["1.#INF","INF"]:
            fp = sys.float_info.max
        elif fp_str in ["-1.#INF","-INF"]:
            fp = -sys.float_info.max
        else:
            try:
                fp = float(fp_str)
                if null_val != None and fp == null_val:
                    return False, null_val
            except (OverflowError, ValueError) as exc:
                self.__handle_exc(exc)
                return False, 0.0
        return True, fp

           
    def __parse_int(self, int_str, null_val=None):
        ''' Converts a string to an int

        :param int_str: string to convert to int
        :param null_val: value representing 'no data'
        :returns: a boolean and an integer
            If could not convert then return (False, None) else if 'null_val' is defined return (False, null_val)
        '''
        try:
            num = int(int_str)
        except (OverflowError, ValueError) as exc:
             self.__handle_exc(exc)
             return False, null_val
        return True, num 


    def __parse_XYZ(self, is_float, x_str, y_str, z_str, do_minmax=False, convert=True):
        ''' Helpful function to read XYZ cooordinates

        :param is_float: if true parse x y z as floats else try integers
        :param x_str, y_str, z_str: X,Y,Z coordinates in string form
        :param do_minmax: calculate min/max of the X,Y,Z coords
        :param convert: convert from kms to metres if necessary
        :returns: returns tuple of four parameters: success - true if could convert the strings to floats/ints
            x,y,z - floating point values, converted to metres if units are kms
        '''
        x = y = z = None
        if is_float:
            converted1, x = self.__parse_float(x_str)
            converted2, y = self.__parse_float(y_str)
            converted3, z = self.__parse_float(z_str)
            if not converted1 or not converted2 or not converted3:
                return False, None, None, None
        else:
            try:
                x = int(x_str)
                y = int(y_str)
                z = int(z_str)
            except (OverflowError, ValueError) as exc:
                self.__handle_exc(exc)
                return False, None, None, None

        # Convert to metres if units are kms
        if convert and isinstance(x, float):
            x *= self.xyz_mult[0]
            y *= self.xyz_mult[1]
            z *= self.xyz_mult[2]

        # Calculate and store minimum and maximum XYZ
        if do_minmax:
            self.geom_obj.calc_minmax(x,y,z)
            x += self.base_xyz[0]
            y += self.base_xyz[1]
            z += self.base_xyz[2]

        return True, x, y, z 


    
    def __parse_colour(self, colour_str):
        ''' Parse a colour string into RGBA tuple.

        :param colour_str: colour can either be spaced RGBA/RGB floats, or '#' + 6 digit hex string
        :returns: a tuple with 4 floats, (R,G,B,A)
        '''
        rgba_tup = (1.0, 1.0, 1.0, 1.0)
        try:
            if colour_str[0]!='#':
                rgbsplit_arr = colour_str.split(' ')
                if len(rgbsplit_arr)==3:
                    rgba_tup = (float(rgbsplit_arr[0]), float(rgbsplit_arr[1]), float(rgbsplit_arr[2]), 1.0)
                elif len(rgbsplit_arr)==4:
                    rgba_tup = (float(rgbsplit_arr[0]), float(rgbsplit_arr[1]), float(rgbsplit_arr[2]), float(rgbsplit_arr[3]))
                else:
                    self.logger.debug("Could not parse colour %s", repr(colour_str))
            else:
                rgba_tup = (float(int(colour_str[1:3],16))/255.0, float(int(colour_str[3:5],16))/255.0, float(int(colour_str[5:7],16))/255.0, 1.0) 
        except (ValueError, OverflowError, IndexError) as exc:
            self.__handle_exc(exc)
            rgba_tup = (1.0, 1.0, 1.0, 1.0)
        return rgba_tup


    def __check_vertex(self, num):
        ''' If vertex exists then returns true else false

        :param num: vertex number to search for
        '''
        for vrtx in self.__vrtx_arr:
            if vrtx.n == num:
                return True
        return False


    def __process_coord_hdr(self, line_gen):
        ''' Process fields within coordinate header.
        :param line_gen: line generator
        :returns: two booleans, the first is True iff reached end of sequence,
                  the second is True iff there is an unrecoverable error
        '''
        while True:
            splitstr_arr, splitstr_arr_raw, line_str, is_last = next(line_gen) 
            
            # End of sequence?
            if is_last:
                return True, False

            # Are we leaving coordinate system header?
            if splitstr_arr[0] == "END_ORIGINAL_COORDINATE_SYSTEM":
                self.logger.debug("Coord System End")
                return False, False

            # Within coordinate system header and not using the default coordinate system
            if splitstr_arr[0] == "NAME":
                self.coord_sys_name = splitstr_arr[1]
                if splitstr_arr[1] != "DEFAULT":
                    self.usesDefaultCoords = False
                    self.logger.debug("usesDefaultCoords False")

                    # FIXME: I can't support non default coords yet - need to enter via command line?
                    # If does not support default coords then exit
                    if not self.nondefault_coords:
                        self.logger.warning("SORRY - Does not support non-DEFAULT coordinates: %s", repr(splitstr_arr[1]))
                        return False, True

            # Does coordinate system use inverted z-axis?
            elif splitstr_arr[0] == "ZPOSITIVE" and splitstr_arr[1] == "DEPTH":
                self.invert_zaxis=True
                self.logger.debug("invert_zaxis = %s", repr(self.invert_zaxis))

            # Axis units - check if units are kilometres, and update coordinate multiplier
            elif splitstr_arr[0] == "AXIS_UNIT":
                self.__process_axis_unit(splitstr_arr)


    def __process_axis_unit(self, splitstr_arr):
        ''' Processes the AXIS_UNIT keyword
        :param splitstr_arr: array of field strings
        '''
        for idx in range(0,3):
            unit_str = splitstr_arr[idx+1].strip('"').strip(' ').strip("'")
            if unit_str=='KM':
                self.xyz_mult[idx] =  1000.0
            # Warn if not metres or kilometres or unitless etc.
            elif unit_str not in ['M', 'UNITLESS', 'NUMBER', 'MS', 'NONE']:
                self.logger.warning("WARNING - nonstandard units in 'AXIS_UNIT' "+ splitstr_arr[idx+1])
            else:
                self.xyz_unit[idx] = unit_str


    def __process_header(self, line_gen):
        ''' Process fields in the GOCAD header
        :param line_gen: line generator
        :returns: a boolean, is True iff we are at last line
        '''
        while True:
            splitstr_arr, splitstr_arr_raw, line_str, is_last = next(line_gen) 
            # Are we on the last line?
            if is_last:
                self.logger.debug("Process header: last line")
                return True
                
            # Are we out of the header? 
            if splitstr_arr[0] == "}" or is_last:
                self.logger.debug("End of header")
                return False

            # When in the HEADER get the colours
            name_str, sep, value_str = line_str.partition(':')
            name_str = name_str.strip()
            value_str = value_str.strip()
            self.logger.debug("inHeader name_str = %s value_str = %s", name_str, value_str)
            if name_str=='*SOLID*COLOR' or name_str=='*ATOMS*COLOR':
                self.style_obj.add_rgba_tup(self.__parse_colour(value_str))
                self.logger.debug("self.style_obj.rgba_tup = %s", repr(self.style_obj.get_rgba_tup()))
            elif name_str[:9]=='*REGIONS*' and name_str[-12:]=='*SOLID*COLOR':
                region_name = name_str.split('*')[2]
                self.region_colour_dict[region_name] = self.__parse_colour(value_str)
                self.logger.debug("region_colour_dict[%s] = %s", region_name, repr(self.region_colour_dict[region_name]))
            # Get header name
            elif name_str=='NAME':
                self.header_name = value_str.replace('/','-')
                self.logger.debug("self.header_name = %s", self.header_name)


    def __process_prop_class_hdr(self, line_gen, splitstr_arr):
        ''' Process the property class header
        :param line_gen: line generator
        :param splitstr_arr: array of field strings from first line of prop class header
        :returns: a boolean, is True iff we are at last line
        '''
        propClassIndex = splitstr_arr[1]
        # There are two kinds of PROPERTY_CLASS_HEADER
        # First, properties attached to local points
        if splitstr_arr[2] == '{':
            inLocalPropClassHeader = True
            while True:
                splitstr_arr, splitstr_arr_raw, line_str, is_last = next(line_gen) 
                # Are we on the last line?
                if is_last:
                    self.logger.debug("Property class header: last line")
                    return True

                # Leaving header
                if splitstr_arr[0] == "}":
                    self.logger.debug("Property class header: end header")
                    return False
                else:
                    # When in the PROPERTY CLASS headers, get the colour table
                    if propClassIndex in self.local_props:
                        self.__parse_property_header(self.local_props[propClassIndex], line_str)

        # Second, properties of binary files 
        elif splitstr_arr[3] == '{':
            if propClassIndex not in self.prop_dict:
                self.prop_dict[propClassIndex] = PROPS(splitstr_arr[2], self.logger.getEffectiveLevel())
            while True:
                splitstr_arr, splitstr_arr_raw, line_str, is_last = next(line_gen) 
                # Are we on the last line?
                if is_last:
                    self.logger.debug("Property class header: last line")
                    return True

                # Leaving header
                if splitstr_arr[0] == "}":
                    self.logger.debug("Property class header: end header")
                    return False

                else:
                    # When in the PROPERTY CLASS headers, get the colour table
                    self.__parse_property_header(self.prop_dict[propClassIndex], line_str)

        else:
            self.logger.error("Cannot parse property header")
            sys.exit(1)

        self.logger.debug("inPropClassHeader = %s", repr(inPropClassHeader))



#  END OF GOCAD_VESSEL CLASS
