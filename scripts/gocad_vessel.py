import numpy
import sys
import os
import struct
from collections import namedtuple
from collections import OrderedDict
import logging
import traceback

class PROPS:
    ''' This class holds GOCAD properties
        e.g. information about binary files (PROP_FILE)
             information attached to XYZ points (PATOM, PVRTX)
    '''

    def __init__(self, class_name):

        self.file_name = ""
        ''' Name of binary file associated with GOCAD file
        '''
       
        self.data_sz = 0 
        ''' Number of bytes in floating point number in binary file
        '''

        self.data_type = "f"
        ''' Type of data in binary file e.g. 'h' - short int, 'f' = float
        '''

        self.signed_int = False
        ''' Is True iff binary data is a signed integer else False
        '''

        self.data = {}
        ''' Property data collected from binary file, stored as a 3d numpy array.
            or property data attached to XYZ points (index is XYZ coordinate)
        '''

        self.data_stats = {}
        ''' Property data statistics: min & max
        '''

        self.colour_map = {}
        ''' If colour map was specified, then it is stored here
        '''

        self.colourmap_name = ""
        ''' Name of colour map
        '''

        self.class_name = class_name
        ''' Property class names
        '''

        self.no_data_marker = None
        ''' Value representing 'no data' values
        '''

    
    def __repr__(self):
        ''' A print friendly representation
        '''
        return "self = {:}\n".format(hex(id(self))) + \
               "file_name = {:}\n".format(repr(self.file_name)) + \
               "data_sz = {:d}\n".format(self.data_sz) + \
               "data_type = {:}\n".format(repr(self.data_type)) + \
               "signed_int = {:}\n".format(self.signed_int) + \
               "data = {:}\n".format(repr(self.data)) + \
               "data_stats = {:}\n".format(repr(self.data_stats)) + \
               "colour_map = {:}\n".format(repr(self.colour_map)) + \
               "colourmap_name = {:}\n".format(repr(self.colourmap_name)) + \
               "class_name = {:}\n".format(repr(self.class_name)) + \
               "no_data_marker = {:}\n".format(repr(self.no_data_marker))

    def make_numpy_dtype(self):
        ''' Returns a string that can be passed to 'numpy' to read a binary file
        '''
        # Prepare 'numpy' binary float integer signed/unsigned data types, always big-endian
        if self.data_type == 'h' or self.data_type == 'b':
            if not self.signed_int:
                return numpy.dtype('>'+self.data_type.upper())
            else:
                return numpy.dtype('>'+self.data_type)
        return numpy.dtype('>'+self.data_type+str(self.data_sz))



class GOCAD_VESSEL:
    ''' Class used to read gocad files and store their details
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

    VRTX = namedtuple('VRTX', 'n xyz')
    ''' Immutable named tuple which stores vertex data
        n = sequence number
        xyz = coordinates
    '''

    ATOM = namedtuple('ATOM', 'n v')
    ''' Immutable named tuple which stores atom data
        n = sequence number
        v = vertex it refers to
    '''

    TRGL = namedtuple('TRGL', 'n abc')
    ''' Immutable named tuple which stores triangle data
        n = sequence number
        abc = triangle vertices
    '''

    SEG = namedtuple('SEG', 'n ab')
    ''' Immutable named tuple which stores segment data
        n = sequence number
        ab = segment vertices
    '''

    STOP_ON_EXC = True
    ''' Stop upon exception, regardless of debug level
    '''


    def __init__(self, debug_level, base_xyz=(0.0, 0.0, 0.0), group_name="", nondefault_coords=False):
        ''' Initialise class
            debug_level - debug level taken from 'logging' module e.g. logging.DEBUG
            base_xyz - optional (x,y,z) floating point tuple, base_xyz is subtracted from all coordinates
                       before they are output, default is (0.0, 0.0, 0.0)
            group_name - optional string, name of group of this gocad file is within a group, default is ""
            nondefault_coords - optional flag, supports non-default coordinates, default is False
        '''
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

        # Initialise input vars
        self.base_xyz = base_xyz
        self.group_name = group_name
        self.nondefault_coords = nondefault_coords

        self.header_name = ""
        ''' Contents of the name field in the header
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

        self.prop_dict = {}
        ''' Dictionary of PROPS objects, stores GOCAD "PROPERTY" objects
            Dictionary index is the PROPERTY number e.g. '1', '2', '3' ...
        '''

        self.invert_zaxis = False
        ''' Set to true if z-axis inversion is turned on in this GOCAD file
        '''

        self.rgba_tup = (1.0, 1.0, 1.0, 1.0)
        ''' If one colour is specified then it is stored here
        '''

        self.local_props = OrderedDict()
        ''' OrderedDict of PROPS objects for attached PVRTX and PATOM  properties
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

        self.axis_origin = None
        ''' Origin of XYZ axis
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

        self.vol_dims = None
        ''' 3 dimensional size of voxel volume
        '''

        self.axis_min = None
        ''' 3 dimensional minimum point of voxel volume
        '''

        self.axis_max = None
        ''' 3 dimensional maximum point of voxel volume
        '''

        self.np_filename = ""
        ''' Filename of GOCAD file without path or extension
        '''

        self.max_X =  -sys.float_info.max
        ''' Maximum X coordinate, used to calculate extent
        '''

        self.min_X =  sys.float_info.max
        ''' Minimum X coordinate, used to calculate extent
        '''

        self.max_Y =  -sys.float_info.max
        ''' Maximum Y coordinate, used to calculate extent
        '''

        self.min_Y =  sys.float_info.max
        ''' Minimum Y coordinate, used to calculate extent
        '''

        self.max_Z =  -sys.float_info.max
        ''' Maximum Z coordinate, used to calculate extent
        '''

        self.min_Z =  sys.float_info.max
        ''' Minimum Z coordinate, used to calculate extent
        '''
        
        self.coord_sys_name = "DEFAULT"
        ''' Name of the GOCAD coordinate system
        '''

        self.usesDefaultCoords = True
        ''' Uses default coordinates
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
        return "is_ts {0} is_vs {1} is_pl {2} is_vo {3} len(vrtx_arr)={4}\n".format(self.is_ts, self.is_vs, self.is_pl, self.is_vo, len(self.__vrtx_arr))


    def __check_vertex(self, num):
        ''' If vertex exists then returns true else false
            num - vertex number to search for
        '''
        for vrtx in self.__vrtx_arr:
            if vrtx.n == num:
                return True
        return False


    def get_vrtx_arr(self):
        ''' Returns array of VRTX objects after GOCAD file has been processed
        '''
        return self.__vrtx_arr 


    def get_trgl_arr(self):
        ''' Returns array of TRGL objects after GOCAD file has been processed
        '''
        return self.__trgl_arr


    def get_seg_arr(self):
        ''' Returns array of SEG objects after GOCAD file has been processed
        '''
        return self.__seg_arr


    def get_extent(self):
        ''' Returns estimate of the geographic extent of the model, using max and min coordinate values
            format is [min_x, max_x, min_y, max_y]
        '''
        return [self.min_X, self.max_X, self.min_Y, self.max_Y]


    def make_vertex_dict(self):
        ''' Make a dictionary to associate vertex insertion order with vertex sequence number
            Ordinarily the vertex sequence number is the same as the insertion order in the vertex
            array, but some GOCAD files have missing vertices etc.
            The first element starts at '1'
        '''
        vert_dict = {}
        idx = 1
        # Assign vertices to dict
        for v in self.__vrtx_arr:
            vert_dict[v.n] = idx
            idx += 1

        # Assign atoms to dict
        for atom in self.__atom_arr:
            idx = 1
            for vert in self.__vrtx_arr:
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
        
        # Within attached binary file property class header (PROP_FILE)
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

            # Are we within coordinate system header?
            elif splitstr_arr[0] == "GOCAD_ORIGINAL_COORDINATE_SYSTEM":
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
                        print("SORRY - Does not support non-DEFAULT coordinates:", splitstr_arr[1])
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
                    #if propClassIndex not in self.local_props:
                    #    self.local_props[propClassIndex] = PROPS(propClassIndex)
                    inLocalPropClassHeader = True
                # Properties of binary files 
                elif splitstr_arr[3] == '{':
                    if propClassIndex not in self.prop_dict:
                        self.prop_dict[propClassIndex] = PROPS(splitstr_arr[2])
                    inPropClassHeader = True
                else:
                    print("ERROR - Cannot parse property header")
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
                if name_str=='*SOLID*COLOR' or name_str=='*ATOMS*COLOR':
                    # Colour can either be spaced RGBA/RGB floats, or '#' + 6 digit hex string
                    try:
                        if value_str[0]!='#':
                            rgbsplit_arr = value_str.split(' ')
                            if len(rgbsplit_arr)==3:
                                self.rgba_tup = (float(rgbsplit_arr[0]), float(rgbsplit_arr[1]), float(rgbsplit_arr[2]), 1.0)
                            elif len(rgbsplit_arr)==4:
                                self.rgba_tup = (float(rgbsplit_arr[0]), float(rgbsplit_arr[1]), float(rgbsplit_arr[2]), float(rgbsplit_arr[3]))
                            else:
                                self.logger.debug("Could not parse colour %s", repr(value_str))
                        else:
                            self.rgba_tup = (int(value_str[1:3],16), int(value_str[3:5],16), int(value_str[5:7],16)) 
                    except (ValueError, OverflowError, IndexError) as exc:
                        self.__handle_exc(exc)
                        self.rgba_tup = (1.0, 1.0, 1.0, 1.0)

                    self.logger.debug("self.rgba_tup = %s", repr(self.rgba_tup))
           
                if name_str=='NAME':
                    self.header_name = value_str.replace('/','-')
                    self.logger.debug("self.header_name = %s", repr(self.header_name))

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
                    try:
                        prop_obj.data_sz = int(splitstr_arr[idx])
                    except (ValueError, IndexError, OverflowError) as exc:
                        self.__handle_exc(exc)
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
                    except IndexError as exc:
                        self.__handle_exc(exc)
                    idx += 1
                self.logger.debug(" property_nulls = %s", repr(splitstr_arr[1:]))
                
            # Atoms, with or without properties
            elif splitstr_arr[0] == "ATOM" or splitstr_arr[0] == 'PATOM':
                seq_no_prev = seq_no
                try:
                    seq_no = int(splitstr_arr[1])
                    v_num = int(splitstr_arr[2])
                except (OverflowError, ValueError, IndexError) as exc:
                    self.__handle_exc(exc)
                    seq_no = seq_no_prev
                else:
                    if self.__check_vertex(v_num):
                        self.__atom_arr.append(self.ATOM(seq_no, v_num))
                    else:
                        self.logger.debug("ERROR - ATOM refers to VERTEX that has not been defined yet")
                        self.logger.debug("    seq_no = %d", seq_no)
                        self.logger.debug("    v_num = %d", v_num)
                        self.logger.debug("    line = %s", line_str)
                        sys.exit(1)

                    # Atoms with attached properties
                    if splitstr_arr[0] == "PATOM":
                        try:
                            vert_dict = self.__make_vertex_dict()
                            self.__parse_props(splitstr_arr, self.__vrtx_arr[vert_dict[v_num]].xyz)
                        except IndexError as exc:
                            self.__handle_exc(exc)
                  
            # Grab the vertices and properties, does not care if there are gaps in the sequence number
            elif splitstr_arr[0] == "PVRTX" or  splitstr_arr[0] == "VRTX":
                seq_no_prev = seq_no
                try:
                    seq_no = int(splitstr_arr[1])
                    is_ok, x_flt, y_flt, z_flt = self.__parse_XYZ(True, splitstr_arr[2], splitstr_arr[3], splitstr_arr[4], True)
                except (IndexError, ValueError, OverflowError) as exc:
                    self.__handle_exc(exc)
                    seq_no = seq_no_prev
                else:
                    if is_ok:
                        # Add vertex
                        if self.invert_zaxis:
                            z_flt = -z_flt
                        self.__vrtx_arr.append(self.VRTX(seq_no, (x_flt, y_flt, z_flt)))

                        # Vertices with attached properties
                        if splitstr_arr[0] == "PVRTX":
                            self.__parse_props(splitstr_arr, (x_flt, y_flt, z_flt))

            # Grab the triangular edges
            elif splitstr_arr[0] == "TRGL":
                seq_no_prev = seq_no
                try:
                    seq_no = int(splitstr_arr[1])
                    is_ok, a_int, b_int, c_int = self.__parse_XYZ(False, splitstr_arr[1], splitstr_arr[2], splitstr_arr[3])
                except (IndexError, ValueError, OverflowError) as exc:
                    self.__handle_exc(exc)
                    seq_no = seq_no_prev
                else:
                    if is_ok:
                        self.__trgl_arr.append(self.TRGL(seq_no, (a_int, b_int, c_int)))

            # Grab the segments
            elif splitstr_arr[0] == "SEG":
                try:
                    a_int = int(splitstr_arr[1])
                    b_int = int(splitstr_arr[2])
                except (IndexError, ValueError) as exc:
                    self.__handle_exc(exc)
                    seq_no = seq_no_prev
                else:
                    self.__seg_arr.append(self.SEG(seq_no, (a_int, b_int)))

            # Extract binary file name
            elif splitstr_arr[0] == "PROP_FILE":
                self.prop_dict[splitstr_arr[1]].file_name = os.path.join(src_dir, splitstr_arr_raw[2])

            # Size of each float in binary file (measured in bytes)
            elif splitstr_arr[0] == "PROP_ESIZE":
                try:
                    self.prop_dict[splitstr_arr[1]].data_sz = int(splitstr_arr[2])
                except (IndexError, ValueError) as exc:
                    self.__handle_exc(exc)

            # Is property an integer ? What size?
            elif splitstr_arr[0] == "PROP_STORAGE_TYPE":
                if splitstr_arr[2] == "OCTET":
                    self.prop_dict[splitstr_arr[1]].data_type = "b"
                elif splitstr_arr[2] == "SHORT":
                    self.prop_dict[splitstr_arr[1]].data_type = "h"
                else:
                    print("ERROR - unknown storage type")

            # Is property a signed integer ?
            elif splitstr_arr[0] == "PROP_SIGNED":
                self.prop_dict[splitstr_arr[1]].signed_int = (splitstr_arr[2] == "1")

            # Cannot process IBM-style floats
            elif splitstr_arr[0] == "PROP_ETYPE":
                if splitstr_arr[2] != "IEEE":
                    print("ERROR - Cannot process ", splitstr_arr[1], " type floating points")
                    sys.exit(1)

            # Cannot process SEGY formats 
            elif splitstr_arr[0] == "PROP_EFORMAT":
                if splitstr_arr[2] != "RAW":
                    print("ERROR - Cannot process ", splitstr_arr[1], " format floating points")
                    sys.exit(1)

            # FIXME: Cannot do offsets within binary file
            elif splitstr_arr[0] == "PROP_OFFSET":
                if int(splitstr_arr[2]) != 0:
                    print("ERROR - Cannot process offsets of more than 0")
                    sys.exit(1)

            # The number that is used to represent 'no data'
            elif splitstr_arr[0] == "PROP_NO_DATA_VALUE":
                converted, fp = self.__parse_float(splitstr_arr[2])
                if converted:
                    self.prop_dict[splitstr_arr[1]].no_data_marker = fp

            # Layout of VOXET data
            elif splitstr_arr[0] == "AXIS_O":
                is_ok, x_flt, y_flt, z_flt = self.__parse_XYZ(True, splitstr_arr[1], splitstr_arr[2], splitstr_arr[3])
                if is_ok:
                    self.axis_origin = (x_flt, y_flt, z_flt)

            elif splitstr_arr[0] == "AXIS_U":
                is_ok, x_flt, y_flt, z_flt = self.__parse_XYZ(True, splitstr_arr[1], splitstr_arr[2], splitstr_arr[3])
                if is_ok:
                    self.axis_u = (x_flt, y_flt, z_flt)

            elif splitstr_arr[0] == "AXIS_V":
                is_ok, x_flt, y_flt, z_flt = self.__parse_XYZ(True, splitstr_arr[1], splitstr_arr[2], splitstr_arr[3])
                if is_ok:
                    self.axis_v = (x_flt, y_flt, z_flt)

            elif splitstr_arr[0] == "AXIS_W":
                is_ok, x_flt, y_flt, z_flt = self.__parse_XYZ(True, splitstr_arr[1], splitstr_arr[2], splitstr_arr[3])
                if is_ok:
                    self.axis_w = (x_flt, y_flt, z_flt)

            elif splitstr_arr[0] == "AXIS_N":
                is_ok, x_int, y_int, z_int = self.__parse_XYZ(False, splitstr_arr[1], splitstr_arr[2], splitstr_arr[3])
                if is_ok:
                    self.vol_dims = (x_int, y_int, z_int)

            elif splitstr_arr[0] == "AXIS_MIN":
                is_ok, x_int, y_int, z_int = self.__parse_XYZ(True, splitstr_arr[1], splitstr_arr[2], splitstr_arr[3])
                if is_ok:
                    self.axis_min = (x_int, y_int, z_int)

            elif splitstr_arr[0] == "AXIS_MAX":
                is_ok, x_int, y_int, z_int = self.__parse_XYZ(True, splitstr_arr[1], splitstr_arr[2], splitstr_arr[3])
                if is_ok:
                    self.axis_max = (x_int, y_int, z_int)

            # END OF TEXT PROCESSING LOOP

        self.logger.debug("process_gocad() filename_str = %s", filename_str)
            
        # Calculate max and min of properties
        for prop_obj in self.local_props.values():
            prop_obj.data_stats = { 'min': sys.float_info.max, 'max': -sys.float_info.max }
            # Some properties are XYZ, so only take X for calculating max and min
            if len(prop_obj.data.values()) > 0:
                first_val_list = list(map(lambda x: x if type(x) is float else x[0], prop_obj.data.values()))
                prop_obj.data_stats['max'] = max(list(first_val_list))
                prop_obj.data_stats['min'] = min(list(first_val_list))

        self.logger.debug("process_gocad() return True")
        retVal = self.__read_voxel_files()
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
        elif name_str=='*COLORMAP*'+prop_obj.colourmap_name+'*COLORS':
            lut_arr = value_str.split(' ')
            for idx in range(0, len(lut_arr), 4):
                try:
                    prop_obj.colour_map[int(lut_arr[idx])] = (float(lut_arr[idx+1]), float(lut_arr[idx+2]), float(lut_arr[idx+3]))
                    self.logger.debug("prop_obj.colour_map = %s", prop_obj.colour_map)
                except (IndexError, OverflowError, ValueError) as exc:
                    self.__handle_exc(exc)



    def __read_voxel_files(self):
        ''' Open up and read binary voxel file
        '''
        if self.is_vo and len(self.prop_dict)>0:
            for file_idx, prop_obj in self.prop_dict.items():
                try:
                    # Check file size first
                    file_sz = os.path.getsize(prop_obj.file_name)
                    num_voxels = prop_obj.data_sz*self.vol_dims[0]*self.vol_dims[1]*self.vol_dims[2]
                    if file_sz != num_voxels:
                        print("SORRY - Cannot process voxel file - length (", repr(num_voxels), ") is not correct", prop_obj.file_name)
                        sys.exit(1)

                    # Initialise data array to zeros
                    prop_obj.data = numpy.zeros((self.vol_dims[0], self.vol_dims[1], self.vol_dims[2]))

                    # Prepare 'numpy' dtype object for binary float, integer signed/unsigned data types
                    dt = prop_obj.make_numpy_dtype()

                    # Read entire file, assumes file small enough to store in memory
                    print("Reading binary file: ", prop_obj.file_name)
                    f_arr = numpy.fromfile(prop_obj.file_name, dtype=dt)
                    fl_idx = 0
                    prop_obj.data_stats = { 'max': -sys.float_info.max, 'min': sys.float_info.max }
                    for z in range(self.vol_dims[2]):
                        for y in range(self.vol_dims[1]):
                            for x in range(self.vol_dims[0]):
                                converted, fp = self.__parse_float(f_arr[fl_idx], prop_obj.no_data_marker)
                                fl_idx +=1
                                if not converted:
                                    continue
                                prop_obj.data[x][y][z] = fp
                                if (prop_obj.data[x][y][z] > prop_obj.data_stats['max']):
                                    prop_obj.data_stats['max'] = prop_obj.data[x][y][z]
                                if (prop_obj.data[x][y][z] < prop_obj.data_stats['min']):
                                    prop_obj.data_stats['min'] = prop_obj.data[x][y][z]
                                        
                except IOError as e:
                    print("SORRY - Cannot process voxel file IOError", filename_str, str(e), e.args)
                    self.logger.debug("process_gocad() return False")
                    return False

        return True



    def __parse_props(self, splitstr_arr, coord_tup):
        ''' This parses a line of properties associated with a PVTRX or PATOM line
            splitstr_arr - array of strings representing line with properties
            coord_tup - (X,Y,Z) float tuple of the coordinates 
        '''
        # Properties start at the 6th column
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
                    prop_obj.data[coord_tup] = fp
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
                    prop_obj.data[coord_tup] = (fpX, fpY, fpZ)
                col_idx += 3
            else:
                print("ERROR - Cannot process property size of != 3 and !=1: ", prop_obj.data_sz, prop_obj)
                sys.exit(1)


    def __parse_float(self, fp_str, null_val=None):
        ''' Converts a string to float, handles infinite values 
            fp_str - string to convert to a float
            null_val - value representing 'no data'
            Returns a boolean and a float
            If could not convert then return (False, 0.0) else if converts to 'null_val' return (False, null_val)
        '''
        # Handle GOCAD's C++ floating point infinity for Windows and Linux
        if fp_str in ["1.#INF","inf"]:
            fp = sys.float_info.max
        elif fp_str in ["-1.#INF","-inf"]:
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
           

    def __parse_XYZ(self, is_float, x_str, y_str, z_str, do_minmax=False):
        ''' Helpful function to read XYZ cooordinates
            is_float - if true parse x y z as floats else try integers
            x_str, y_str, z_str - X,Y,Z coordinates in string form
            do_minmax - record the X,Y,Z coords for calculating extent
            Returns four parameters: success  - true if could convert the strings to floats
                                   x,y,z - floating point values
        '''
        x = y = z = None
        if is_float:
            converted, x = self.__parse_float(x_str)
            converted, y = self.__parse_float(y_str)
            converted, z = self.__parse_float(z_str)
            if not converted:
                return False, None, None, None
        else:
            try:
                x = int(x_str)
                y = int(y_str)
                z = int(z_str)
            except (OverflowError, ValueError) as exc:
                self.__handle_exc(exc)
                return False, None, None, None

        # Calculate minimum and maximum XYZ
        if do_minmax:
            if x > self.max_X:
                self.max_X = x
            if x < self.min_X:
                self.min_X = x
            if y > self.max_Y:
                self.max_Y = y
            if y < self.min_Y:
                self.min_Y = y
            if z > self.max_Z:
                self.max_Z = z
            if z < self.min_Z:
                self.min_Z = z
        return True, x, y, z


#  END OF GOCAD_VESSEL CLASS