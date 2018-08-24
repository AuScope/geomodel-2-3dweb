import numpy
import sys
import os
import struct
from collections import namedtuple
from collections import OrderedDict
import logging
import traceback

from db.model_geometries import MODEL_GEOMETRIES
from imports.gocad.props import PROPS

class GOCAD_VESSEL(MODEL_GEOMETRIES):
    ''' Class used to read GOCAD files and store their details
    '''

    GOCAD_HEADERS = {
                 'TS':['GOCAD TSURF 1'],
                 'VS':['GOCAD VSET 1'],
                 'PL':['GOCAD PLINE 1'],
                 'GP':['GOCAD HETEROGENEOUSGROUP 1', 'GOCAD HOMOGENEOUSGROUP 1'],
                 'VO':['GOCAD VOXET 1'],
    }
    ''' Constant assigns possible headers to each flename extension
    '''

    SUPPORTED_EXTS = [
                   'TS',
                   'VS',
                    'PL',
                    'GP',
                    'VO',
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
            debug_level - debug level taken from 'logging' module e.g. logging.DEBUG
            base_xyz - optional (x,y,z) floating point tuple, base_xyz is added to all coordinates
                       before they are output, default is (0.0, 0.0, 0.0)
            group_name - optional string, name of group of this gocad file is within a group, default is ""
            nondefault_coords - optional flag, supports non-default coordinates, default is False
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
        ''' Dictionary of PROPS objects, stores GOCAD "PROPERTY" objects
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

        self.is_ts = False
        ''' True iff it is a GOCAD TSURF file
        '''

        self.is_vs = False
        ''' True iff it is a GOCAD VSET file
        '''

        self.is_pl = False
        ''' True iff it is a GOCAD PLINE file
        '''

        self.is_vo = False
        ''' True iff it is a GOCAD VOXET file
        '''

        self.xyz_mult = [1.0, 1.0, 1.0]
        ''' Used to convert to metres if the units are in kilometres
        '''

        self.xyz_unit = [None, None, None]
        ''' Units of XYZ axes
        ''' 

        self.axis_origin = None
        ''' Origin of XYZ axes
        '''

        self.axis_u = None
        ''' Length of u-axis
        '''

        self.axis_v = None
        ''' Length of v-axis
        '''

        self.axis_w = None
        ''' Length of w-axis
        '''

        self.vol_sz = None
        ''' 3 dimensional size of voxel volume
        '''

        self.axis_min = None
        ''' 3 dimensional minimum point of voxel volume
        '''

        self.axis_max = None
        ''' 3 dimensional maximum point of voxel volume
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


    def __handle_exc(self, exc):
        ''' If STOP_ON_EXC is set or debug is on, print details of exception and stop
            exc - exception
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
        ''' A very basic print friendly representation
        '''
        return "is_ts {0} is_vs {1} is_pl {2} is_vo {3} len(vrtx_arr)={4}\n".format(self.is_ts, self.is_vs, self.is_pl, self.is_vo, len(self._vrtx_arr))


    def is_single_layer_vo(self):
        ''' Returns True if this is extracted from a GOCAD VOXEL that only has a single layer and should be converted into a PNG
            instead of a GLTF
        '''
        return self.is_vo and self.vol_sz[2]==1


    def make_vertex_dict(self):
        ''' Make a dictionary to associate vertex insertion order with vertex sequence number
            Ordinarily the vertex sequence number is the same as the insertion order in the vertex
            array, but some GOCAD files have missing vertices etc.
            The first element starts at '1'
        '''
        vert_dict = {}
        idx = 1
        # Assign vertices to dict
        for v in self._vrtx_arr:
            vert_dict[v.n] = idx
            idx += 1

        # Assign atoms to dict
        for atom in self._atom_arr:
            idx = 1
            for vert in self._vrtx_arr:
                if vert.n == atom.v:
                    vert_dict[atom.n] = idx
                    break
                idx += 1
        return vert_dict


    def process_gocad(self, src_dir, filename_str, file_lines):
        ''' Extracts details from gocad file. This should be called before other functions!
            filename_str - filename of gocad file
            file_lines - array of strings of lines from gocad file
            Returns true if could process file
        '''
        self.logger.debug("process_gocad(%s,%s,%d)", src_dir, filename_str, len(file_lines))

        # State variable for reading first line
        firstLine = True
        
        # For being within header
        inHeader = False
        
        # For being within coordinate header
        inCoord = False
        
        # Within attached binary file property class header (PROPERTY_CLASS HEADER)
        inPropClassHeader = False
        
        # Within header for properties attached to points (PVRTX, PATOM)
        inLocalPropClassHeader = False

        # Index for property class header currently being parsed
        propClassIndex = ''
        
        # For keeping track of the ID of VRTX, ATOM, PVRTX, SEG etc.
        seq_no = 0
        seq_no_prev = -1

        fileName, fileExt = os.path.splitext(filename_str)
        self.np_filename = os.path.basename(fileName)
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

            self.logger.debug("splitstr_arr = %s", repr(splitstr_arr))

            # Check that we have a GOCAD file that we can process
            # Nota bene: This will return if called for the header of a GOCAD group file
            if firstLine:
                firstLine = False
                if not self.__setType(fileExt, line_str):
                    self.logger.debug("process_gocad() Can't set type, return False")
                    return False
                continue

            # Skip the subsets keywords
            if splitstr_arr[0] in ["SUBVSET", "ILINE", "TFACE", "TVOLUME"]:
                self.logger.debug("Skip subset keywords")
                continue

            # Skip control nodes (used to denote fixed points in GOCAD)
            if splitstr_arr[0] == "CNP":
                self.logger.debug("Skip control nodes")
                continue

            try:

                # Are we within coordinate system header?
                if splitstr_arr[0] == "GOCAD_ORIGINAL_COORDINATE_SYSTEM":
                    inCoord = True
                    self.logger.debug("inCoord True")
            
                # Are we leaving coordinate system header?
                elif splitstr_arr[0] == "END_ORIGINAL_COORDINATE_SYSTEM":
                    inCoord = False
                    self.logger.debug("inCoord False")
            
                # Within coordinate system header and not using the default coordinate system
                elif inCoord and splitstr_arr[0] == "NAME":
                    self.coord_sys_name = splitstr_arr[1]
                    if splitstr_arr[1] != "DEFAULT":
                        self.usesDefaultCoords = False
                        self.logger.debug("usesDefaultCoords False")

                        # FIXME: I can't support non default coords yet - need to enter via command line?
                        # If does not support default coords then exit
                        if not self.nondefault_coords:
                            self.logger.warning("SORRY - Does not support non-DEFAULT coordinates: %s", repr(splitstr_arr[1]))
                            self.logger.debug("process_gocad() return False")
                            return False 
                
                # Does coordinate system use inverted z-axis?
                elif inCoord and splitstr_arr[0] == "ZPOSITIVE" and splitstr_arr[1] == "DEPTH":
                    self.invert_zaxis=True
                    self.logger.debug("invert_zaxis = %s", repr(self.invert_zaxis))
            
                # Are we in the header?
                elif splitstr_arr[0] == "HEADER":
                    inHeader = True
                    self.logger.debug("inHeader = %s", repr(inHeader))

                # Are we in the property class header?
                elif splitstr_arr[0] == "PROPERTY_CLASS_HEADER":
                    propClassIndex = splitstr_arr[1]
                    # There are two kinds of PROPERTY_CLASS_HEADER
                    # First, properties attached to points
                    if splitstr_arr[2] == '{':
                        inLocalPropClassHeader = True
                    # Properties of binary files 
                    elif splitstr_arr[3] == '{':
                        if propClassIndex not in self.prop_dict:
                            self.prop_dict[propClassIndex] = PROPS(splitstr_arr[2])
                        inPropClassHeader = True
                    else:
                        self.logger.error("ERROR - Cannot parse property header")
                        sys.exit(1)
                    self.logger.debug("inPropClassHeader = %s", repr(inPropClassHeader))

                # Are we out of the header?    
                elif inHeader and splitstr_arr[0] == "}":
                    inHeader = False
                    self.logger.debug("inHeader = %s", repr(inHeader))

                # Property class headers for binary files
                elif inPropClassHeader:
                    # Leaving header
                    if splitstr_arr[0] == "}":
                        inPropClassHeader = False
                        propClassIndex = ''
                        self.logger.debug("inPropClassHeader = %s", repr(inPropClassHeader))
                    else:
                        # When in the PROPERTY CLASS headers, get the colour table
                        self.__parse_property_header(self.prop_dict[propClassIndex], line_str)

                # Property class headers for local points
                elif inLocalPropClassHeader:
                    # Leaving header
                    if splitstr_arr[0] == "}":
                        inLocalPropClassHeader = False
                        propClassIndex = ''
                        self.logger.debug("inLocalPropClassHeader = %s", repr(inLocalPropClassHeader))
                    else:
                        # When in the PROPERTY CLASS headers, get the colour table
                        if propClassIndex in self.local_props:
                            self.__parse_property_header(self.local_props[propClassIndex], line_str)

                # When in the HEADER get the colours
                elif inHeader:
                    name_str, sep, value_str = line_str.partition(':')
                    name_str = name_str.strip()
                    value_str = value_str.strip()
                    self.logger.debug("inHeader name_str = %s value_str = %s", name_str, value_str)
                    if name_str=='*SOLID*COLOR' or name_str=='*ATOMS*COLOR':
                        self.rgba_tup = self.__parse_colour(value_str)

                        self.logger.debug("self.rgba_tup = %s", repr(self.rgba_tup))
                    elif name_str[:9]=='*REGIONS*' and name_str[-12:]=='*SOLID*COLOR':
                        region_name = name_str.split('*')[2] 
                        self.region_colour_dict[region_name] = self.__parse_colour(value_str)
                        self.logger.debug("region_colour_dict[%s] = %s", region_name, repr(self.region_colour_dict[region_name]))
           
                    if name_str=='NAME':
                        self.header_name = value_str.replace('/','-')
                        self.logger.debug("self.header_name = %s", self.header_name)

                # Axis units - check if units are kilometres, and update coordinate multiplier
                elif splitstr_arr[0] == "AXIS_UNIT":
                    for idx in range(0,3):
                        unit_str = splitstr_arr[idx+1].strip('"').strip(' ').strip("'")
                        if unit_str=='KM':
                            self.xyz_mult[idx] =  1000.0
                        # Warn if not metres or kilometres or unitless etc.
                        elif unit_str not in ['M', 'UNITLESS', 'NUMBER', 'MS']:
                            self.logger.warning("WARNING - nonstandard units in 'AXIS_UNIT' "+ splitstr_arr[idx+1])
                        else:
                            self.xyz_unit[idx] = unit_str

                # Property names, this is not the class names
                elif splitstr_arr[0] == "PROPERTIES":
                    if len(self.local_props) == 0:
                        for class_name in splitstr_arr[1:]:
                            self.local_props[class_name] = PROPS(class_name)
                    self.logger.debug(" properties list = %s", repr(splitstr_arr[1:]))

                # These are the property names for the point properties (e.g. PVRTX, PATOM)
                elif splitstr_arr[0] == "PROPERTY_CLASSES":
                    if len(self.local_props) == 0:
                        for class_name in splitstr_arr[1:]:
                            self.local_props[class_name] = PROPS(class_name)
                    self.logger.debug(" property classes = %s", repr(splitstr_arr[1:]))

                # This is the number of floats/ints for each property, usually it is '1',
                # but XYZ values are '3'
                elif splitstr_arr[0] == "ESIZES":
                    idx = 1
                    for prop_obj in self.local_props.values():
                        is_ok, l = self.__parse_int(splitstr_arr[idx])
                        if is_ok:
                            prop_obj.data_sz = l
                        idx += 1 
                    self.logger.debug(" property_sizes = %s", repr(splitstr_arr[1:]))

                # Read values representing no data for this property at a coordinate point
                elif splitstr_arr[0] == "NO_DATA_VALUES":
                    idx = 1
                    for prop_obj in self.local_props.values():
                        try:
                            converted, fp  = self.__parse_float(splitstr_arr[idx])
                            if converted:
                                prop_obj.no_data_marker = fp
                                self.logger.debug("prop_obj.no_data_marker = %f", prop_obj.no_data_marker)
                        except IndexError as exc:
                            self.__handle_exc(exc)
                        idx += 1
                    self.logger.debug(" property_nulls = %s", repr(splitstr_arr[1:]))
                
                # Atoms, with or without properties
                elif splitstr_arr[0] == "ATOM" or splitstr_arr[0] == 'PATOM':
                    seq_no_prev = seq_no
                    is_ok_s, seq_no = self.__parse_int(splitstr_arr[1])
                    is_ok, v_num = self.__parse_int(splitstr_arr[2])
                    if not is_ok_s or not is_ok:
                        seq_no = seq_no_prev
                    else:
                        if self._check_vertex(v_num):
                            self._atom_arr.append(self.ATOM(seq_no, v_num))
                        else:
                            self.logger.error("ERROR - ATOM refers to VERTEX that has not been defined yet")
                            self.logger.error("    seq_no = %d", seq_no)
                            self.logger.error("    v_num = %d", v_num)
                            self.logger.error("    line = %s", line_str)
                            sys.exit(1)

                        # Atoms with attached properties
                        if splitstr_arr[0] == "PATOM":
                            vert_dict = self.make_vertex_dict()
                            self.__parse_props(splitstr_arr, self._vrtx_arr[vert_dict[v_num]].xyz, True)
                  
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
                        self._vrtx_arr.append(self.VRTX(seq_no, (x_flt, y_flt, z_flt)))
   
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
                        self._trgl_arr.append(self.TRGL(seq_no, (a_int, b_int, c_int)))

                # Grab the segments
                elif splitstr_arr[0] == "SEG":
                    is_ok_a, a_int = self.__parse_int(splitstr_arr[1])
                    is_ok_b, b_int = self.__parse_int(splitstr_arr[2])
                    if is_ok_a and is_ok_b:
                        self._seg_arr.append(self.SEG((a_int, b_int)))

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

                # Size of each float in binary file (measured in bytes)
                elif splitstr_arr[0] == "PROP_ESIZE":
                    is_ok, l = self.__parse_int(splitstr_arr[2])
                    if is_ok:
                       self.prop_dict[splitstr_arr[1]].data_sz = l
                       self.logger.debug("self.prop_dict[%s].data_sz = %d", splitstr_arr[1], self.prop_dict[splitstr_arr[1]].data_sz)

                # Is property an integer ? What size?
                # FIXME: Must support 'RGBA' storage type too
                elif splitstr_arr[0] == "PROP_STORAGE_TYPE":
                    if splitstr_arr[2] == "OCTET":
                        self.prop_dict[splitstr_arr[1]].data_type = "b"
                    elif splitstr_arr[2] == "SHORT":
                        self.prop_dict[splitstr_arr[1]].data_type = "h"
                    else:
                        self.logger.error("ERROR - unknown storage type")
                        sys.exit(1)
                    self.logger.debug("self.prop_dict[%s].data_type = %s", splitstr_arr[1], self.prop_dict[splitstr_arr[1]].data_type)

                # Is property a signed integer ?
                elif splitstr_arr[0] == "PROP_SIGNED":
                    self.prop_dict[splitstr_arr[1]].signed_int = (splitstr_arr[2] == "1")
                    self.logger.debug("self.prop_dict[%s].signed_int = %s", splitstr_arr[1], repr(self.prop_dict[splitstr_arr[1]].signed_int))

                # Cannot process IBM-style floats
                elif splitstr_arr[0] == "PROP_ETYPE":
                    if splitstr_arr[2] != "IEEE":
                        self.logger.error("ERROR - Cannot process %s type floating points", splitstr_arr[1])
                        sys.exit(1)

                # Cannot process SEGY formats 
                elif splitstr_arr[0] == "PROP_EFORMAT":
                    if splitstr_arr[2] != "RAW":
                        self.logger.error("ERROR - Cannot process %s format floating points", splitstr_arr[1])
                        sys.exit(1)

                # Offset in bytes within binary file
                elif splitstr_arr[0] == "PROP_OFFSET":
                     is_ok, l = self.__parse_int(splitstr_arr[2])
                     if is_ok:
                         self.prop_dict[splitstr_arr[1]].offset = l
                         self.logger.debug("self.prop_dict[%s].offset = %d",  splitstr_arr[1], self.prop_dict[splitstr_arr[1]].offset)

                # The number that is used to represent 'no data'
                elif splitstr_arr[0] == "PROP_NO_DATA_VALUE":
                    converted, fp = self.__parse_float(splitstr_arr[2])
                    if converted:
                        self.prop_dict[splitstr_arr[1]].no_data_marker = fp
                        self.logger.debug("self.prop_dict[%s].no_data_marker = %f", splitstr_arr[1], self.prop_dict[splitstr_arr[1]].no_data_marker)

                # Layout of VOXET data
                elif splitstr_arr[0] == "AXIS_O":
                    is_ok, x_flt, y_flt, z_flt = self.__parse_XYZ(True, splitstr_arr[1], splitstr_arr[2], splitstr_arr[3])
                    if is_ok:
                        self.axis_origin = (x_flt, y_flt, z_flt)
                        self.logger.debug("self.axis_origin = %s", repr(self.axis_origin))
    
                elif splitstr_arr[0] == "AXIS_U":
                    is_ok, x_flt, y_flt, z_flt = self.__parse_XYZ(True, splitstr_arr[1], splitstr_arr[2], splitstr_arr[3], False, False)
                    if is_ok:
                        self.axis_u = (x_flt, y_flt, z_flt)
                        self.logger.debug("self.axis_u = %s", repr(self.axis_u))

                elif splitstr_arr[0] == "AXIS_V":
                    is_ok, x_flt, y_flt, z_flt = self.__parse_XYZ(True, splitstr_arr[1], splitstr_arr[2], splitstr_arr[3], False, False)
                    if is_ok:
                        self.axis_v = (x_flt, y_flt, z_flt)
                        self.logger.debug("self.axis_v = %s", repr(self.axis_v))

                elif splitstr_arr[0] == "AXIS_W":
                    is_ok, x_flt, y_flt, z_flt = self.__parse_XYZ(True, splitstr_arr[1], splitstr_arr[2], splitstr_arr[3], False, False)
                    if is_ok:
                        self.axis_w = (x_flt, y_flt, z_flt)
                        self.logger.debug("self.axis_w= %s", repr(self.axis_w))

                elif splitstr_arr[0] == "AXIS_N":
                    is_ok, x_int, y_int, z_int = self.__parse_XYZ(False, splitstr_arr[1], splitstr_arr[2], splitstr_arr[3], False, False)
                    if is_ok:
                        self.vol_sz = (x_int, y_int, z_int)
                        self.logger.debug("self.vol_sz= %s", repr(self.vol_sz))

                elif splitstr_arr[0] == "AXIS_MIN":
                    is_ok, x_flt, y_flt, z_flt = self.__parse_XYZ(True, splitstr_arr[1], splitstr_arr[2], splitstr_arr[3], False, False)
                    if is_ok:
                        self.axis_min = (x_flt, y_flt, z_flt)
                        self.logger.debug("self.axis_min= %s", repr(self.axis_min))

                elif splitstr_arr[0] == "AXIS_MAX":
                    is_ok, x_flt, y_flt, z_flt = self.__parse_XYZ(True, splitstr_arr[1], splitstr_arr[2], splitstr_arr[3], False, False)
                    if is_ok:
                        self.axis_max = (x_flt, y_flt, z_flt)
                        self.logger.debug("self.axis_max= %s", repr(self.axis_max))

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

            except IndexError as exc:
                self.__handle_exc(exc)
    
            # END OF TEXT PROCESSING LOOP

        # Read in any binary data files and flags files attached to voxel files
        retVal = self.__read_voxel_binary_files()

        self.logger.debug("process_gocad() returns")
        return retVal


    def __setType(self, fileExt, firstLineStr):
        ''' Sets the type of GOCAD file: TSURF, VOXEL, PLINE etc.
            fileExt - the file extension
            firstLineStr - first line in the file
            Returns True if it could determine the type of file
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
                self.is_ts = True
                return True
            elif ext_str=='VS' and firstLineStr in self.GOCAD_HEADERS['VS']:
                self.is_vs = True
                return True
            elif ext_str=='PL' and firstLineStr in self.GOCAD_HEADERS['PL']:
                self.is_pl = True
                return True
            elif ext_str=='VO' and firstLineStr in self.GOCAD_HEADERS['VO']:
                self.is_vo = True
                return True

        return False


    def __parse_property_header(self, prop_obj, line_str):
        ''' Parses the PROPERTY header, extracting the colour table info and storing it in PROPS object
            prop_obj - a PROPS object to store the data
            line_str - current line
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
        if self.is_vo and len(self.prop_dict)>0:
            if self.vol_sz==None:
                self.logger.error("ERROR - Cannot process voxel file, cube size is not defined, missing 'AXIS_N'")
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
                    mult = [(self.axis_max[0]-self.axis_min[0])/self.vol_sz[0],
                            (self.axis_max[1]-self.axis_min[1])/self.vol_sz[1],
                            (self.axis_max[2]-self.axis_min[2])/self.vol_sz[2]]
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
                                X_coord = self.axis_origin[0]+ \
                                  (float(x)*self.axis_u[0]*mult[0] + float(y)*self.axis_u[1]*mult[1] + float(z)*self.axis_u[2]*mult[2])
                                Y_coord = self.axis_origin[1]+ \
                                  (float(x)*self.axis_v[0]*mult[0] + float(y)*self.axis_v[1]*mult[1] + float(z)*self.axis_v[2]*mult[2])
                                Z_coord = self.axis_origin[2]+ \
                                  (float(x)*self.axis_w[0]*mult[0] + float(y)*self.axis_w[1]*mult[1] + float(z)*self.axis_w[2]*mult[2]) 
                                self._calc_minmax(X_coord, Y_coord, Z_coord)
                                 
                except IOError as e:
                    self.logger.error("SORRY - Cannot process voxel file IOError %s %s %s", prop_obj.file_name, str(e), e.args)
                    sys.exit(1)

            if not self.SKIP_FLAGS_FILE:
                self.__read_flags_file()
        return True


                    
    def __read_flags_file(self):
        ''' This reads the flags file and looks for regions.
        '''
        if self.flags_file!='':
            if self.flags_array_length != self.vol_sz[0]*self.vol_sz[1]*self.vol_sz[2]:
                self.logger.warning("SORRY - Cannot process voxel flags file, inconsistent size between data file and flag file")
                self.logger.debug("process_gocad() return False")
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
                self.flags_prop = PROPS(self.flags_file)
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
                self.logger.debug("process_gocad() return False")
                return False

        return True



    def __parse_props(self, splitstr_arr, coord_tup, is_patom = False):
        ''' This parses a line of properties associated with a PVTRX or PATOM line
            splitstr_arr - array of strings representing line with properties
            coord_tup - (X,Y,Z) float tuple of the coordinates
            is_patom - this is from a PATOM, default False
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
                self.logger.error("ERROR - Cannot process property size of != 3 and !=1: %d %s", prop_obj.data_sz, repr(prop_obj))
                sys.exit(1)


    def __parse_float(self, fp_str, null_val=None):
        ''' Converts a string to float, handles infinite values 
            fp_str - string to convert to a float
            null_val - value representing 'no data'
            Returns a boolean and a float
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
            int_str - string to convert to int
            null_val - value representing 'no data'
            Returns a boolean and an integer
            If could not convert then return (False, None) else if 'null_val' is defined return (False, null_val)
        '''
        try:
            num = int(int_str)
        except (OverflowError, ValueError) as exc:
             self.__handle_exc(exc)
             return False, null_val
        return True, num 


    def __parse_XYZ(self, is_float, x_str, y_str, z_str, do_minmax=False, convert = True):
        ''' Helpful function to read XYZ cooordinates
            is_float - if true parse x y z as floats else try integers
            x_str, y_str, z_str - X,Y,Z coordinates in string form
            do_minmax - record the X,Y,Z coords for calculating extent
            convert - convert from kms to metres if necessary
            Returns four parameters: success - true if could convert the strings to floats
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

        # Calculate minimum and maximum XYZ
        if do_minmax:
            self._calc_minmax(x,y,z)

        return True, x, y, z 


    
    def __parse_colour(self, colour_str):
        ''' Parse a colour string into RGBA tuple.
            colour_str - colour can either be spaced RGBA/RGB floats, or '#' + 6 digit hex string
            Returns a tuple with 4 floats
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


#  END OF GOCAD_VESSEL CLASS
