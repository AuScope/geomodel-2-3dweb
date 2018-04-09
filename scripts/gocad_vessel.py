import numpy
import sys
import os
import struct
from collections import namedtuple

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
    ''' Constant assigns possible headers to each flename extension'''

    SUPPORTED_EXTS = [
                   'TS',
                   'VS',
                    'PL',
                    'GP',
                    'VO',
    ]
    ''' List of file extensions to search for '''


    COORD_OFFSETS = { 'FROM_SHAPE' : (535100.0, 0.0, 0.0) }
    ''' Coordinate offsets, when file contains a coordinate system  that is not "DEFAULT" 
        The named coordinate system and (X,Y,Z) offset will apply '''

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

    def __init__(self, base_xyz=(0.0, 0.0, 0.0), group_name=""):
        ''' Initialise class
            base_xyz - optional (x,y,z) floating point tuple, base_xyz is subtracted from all coordinates
                       before they are output
            group_name - optional string, name of group of this gocad file is within a group
        '''
        self.base_xyz = base_xyz
        self.group_name = group_name

        self.header_name = ""
        ''' Contents of the name field in the header '''

        self.vrtx_arr = []
        ''' Array of named tuples 'VRTX' used to store vertex data'''

        self.atom_arr = []
        ''' Array of named tuples 'ATOM' used to store atom data'''

        self.trgl_arr = []
        ''' Array of named tuples 'TRGL' used store triangle face data '''

        self.seg_arr = []
        ''' Array of named tuples 'SEG' used to store line segment data '''

        self.invert_zaxis = False
        ''' Set to true if z-axis inversion is turned on in this GOCAD file '''

        self.rgba_tup = (1.0, 1.0, 1.0, 1.0)
        ''' If one colour is specified in the file it is stored here '''

        self.prop_dict = {}
        ''' Property dictionary for PVRTX lines '''

        self.is_ts = False
        ''' True iff it is a GOCAD TSURF file '''

        self.is_vs = False
        ''' True iff it is a GOCAD VSET file '''

        self.is_pl = False
        ''' True iff it is a GOCAD PLINE file '''

        self.is_vo = False
        ''' True iff it is a GOCAD VOXEL file '''

        self.prop_meta = {}
        ''' Property metadata '''

        self.voxel_file = ""
        ''' Name of binary file associated with VOXEL file '''

        self.axis_origin = None
        ''' Origin of XYZ axis '''

        self.axis_u = None
        ''' Length of u-axis '''

        self.axis_v = None
        ''' Length of v-axis '''

        self.axis_w = None
        ''' Length of w-axis '''

        self.vol_dims = None
        ''' 3 dimensional size of voxel volume '''

        self.axis_min = None
        ''' 3 dimensional minimum point of voxel volume '''

        self.axis_max = None
        ''' 3 dimensional maximum point of voxel volume '''

        self.voxel_data = numpy.zeros((1,1,1))
        ''' Voxel data collected from binary file, stored as a 3d numpy array '''

        self.voxel_data_stats = { 'min': sys.float_info.max , 'max': -sys.float_info.max }
        ''' Voxel data statistics: min & max '''

        self.colour_map = {}
        ''' If colour map was specified, then it is stored here '''

        self.colourmap_name = ""
        ''' Name of colour map '''

        self.np_filename = ""
        ''' Filename of GOCAD file without path or extension '''

        self.max_X =  -sys.float_info.max
        ''' Maximum X coordinate, used to calculate extent '''

        self.min_X =  sys.float_info.max
        ''' Minimum X coordinate, used to calculate extent '''

        self.max_Y =  -sys.float_info.max
        ''' Maximum Y coordinate, used to calculate extent '''

        self.min_Y =  sys.float_info.max
        ''' Minimum Y coordinate, used to calculate extent '''

        self.max_Z =  -sys.float_info.max
        ''' Maximum Z coordinate, used to calculate extent '''

        self.min_Z =  sys.float_info.max
        ''' Minimum Z coordinate, used to calculate extent '''
        
        self.coord_sys_name = "DEFAULT"
        ''' Name of the GOCAD coordinate system '''


    def __repr__(self):
        ''' A very basic print friendly representation
        '''
        return "is_ts {0} is_vs {1} is_pl {2} is_vo {3} len(vrtx_arr)={4}\n".format(self.is_ts, self.is_vs, self.is_pl, self.is_vo, len(self.vrtx_arr))


    def make_vertex_dict(self):
        ''' Make a dictionary to associate vertex insertion order with vertex sequence number
            Ordinarily the vertex sequence number is the same as the insertion order in the vertex
            array, but some GOCAD files have missing vertices etc.
            The first element starts at '1'
        '''
        vert_dict = {}
        idx = 1
        # Assign vertices to dict
        for v in self.vrtx_arr:
            vert_dict[v.n] = idx
            idx += 1

        # Assign atoms to dict
        for atom in self.atom_arr:
            idx = 1
            for vert in self.vrtx_arr:
                if vert.n == atom.v:
                    vert_dict[atom.n] = idx
                    break
                idx += 1
        return vert_dict


    def check_vertex(self, num):
        ''' If vertex exists then returns true else false
            num - vertex number to search for
        '''
        for vrtx in self.vrtx_arr:
            if vrtx.n == num:
                return True
        return False

    def get_extent(self):
        ''' Returns estimate of the extent of the model, using max and min coordinate values
            format is [min_x, max_x, min_y, max_y]
        '''
        return [self.min_X, self.max_X, self.min_Y, self.max_Y]


    def setType(self, fileExt, firstLineStr):
        ''' Sets the type of GOCAD file: TSURF, VOXEL, PLINE etc.
            fileExt - the file extension
            firstLineStr - first line in the file
            Returns True if it could determine the type of file
        '''
        print("setType(", fileExt, firstLineStr, ")")
        ext_str = fileExt.lstrip('.').upper()
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


    def process_gocad(self, src_dir, filename_str, file_lines):
        ''' Extracts details from gocad file
            filename_str - filename of gocad file
            file_lines - array of strings of lines from gocad file
             Returns true if could process file
        '''
        print("process_gocad(", filename_str, len(file_lines), ")")

        # Reading first line
        firstLine = True
        
        # Within header
        inHeader = False
        
        # Within coordinate header
        inCoord = False
        
        # Within property class header
        inPropClassHeader = False
        
        seq_no = 0
        seq_no_prev = -1
        properties_list = []
        usesDefaultCoords = True
        fileName, fileExt = os.path.splitext(filename_str)
        self.np_filename = os.path.basename(fileName)
        for line in file_lines:
            line_str = line.rstrip(' \n\r').upper()
            splitstr_arr_raw = line.rstrip(' \n\r').split(' ')
            splitstr_arr = line_str.split(' ')

            # Check that we have a GOCAD file
            if firstLine:
                firstLine = False
                if not self.setType(fileExt, line_str):
                    print("SORRY - not a GOCAD file", line_str)
                    return False
                continue

            # Skip the subsets keywords
            if splitstr_arr[0] in ["SUBVSET", "ILINE", "TFACE", "TVOLUME"]:
                continue

            # Are we within coordinate system header?
            elif splitstr_arr[0] == "GOCAD_ORIGINAL_COORDINATE_SYSTEM":
                inCoord = True
                print("inCoord True")
            
            # Are we leaving coordinate system header?
            elif splitstr_arr[0] == "END_ORIGINAL_COORDINATE_SYSTEM":
                inCoord = False
                print("inCoord False")
            
            # Within coordinate system header and not using the default coordinate system
            elif inCoord and splitstr_arr[0] == "NAME":
                self.coord_sys_name = splitstr_arr[1]
                if splitstr_arr[1] != "DEFAULT":
                    usesDefaultCoords = False
                    print("usesDefaultCoords False")

                    # I can't support this GOCAD feature yet
                    print("SORRY - Does not support non-DEFAULT coordinates")
                    return False 
                else:
                    usesDefaultCoords = True
                    print("usesDefaultCoords True")
                    
                
            # Does coordinate system use inverted z-axis?
            elif inCoord and splitstr_arr[0] == "ZPOSITIVE" and splitstr_arr[1] == "DEPTH":
                self.invert_zaxis=True
            
            # Are we in the header?
            elif splitstr_arr[0] == "HEADER":
                inHeader = True

            # Are we in the property class header?
            elif splitstr_arr[0] == "PROPERTY_CLASS_HEADER":
                self.prop_class_name = splitstr_arr[2]
                inPropClassHeader = True

            # Are we out of the header?    
            elif inHeader and splitstr_arr[0] == "}":
                inHeader = False

            # Leaving property class header
            elif inPropClassHeader and splitstr_arr[0] == "}":
                inPropClassHeader = False

            # When in the HEADER get the colours
            elif inHeader:
                name_str, sep, value_str = line_str.partition(':')
                if name_str=='*SOLID*COLOR' or name_str=='*ATOMS*COLOR':
                    # Colour can either be spaced RGBA floats, or '#' + 6 digit hex string
                    try:
                        if value_str[0]!='#':
                            rgbsplit_arr = value_str.split(' ')
                            self.rgba_tup = (float(rgbsplit_arr[0]), float(rgbsplit_arr[1]), float(rgbsplit_arr[2]), float(rgbsplit_arr[3]))
                        else:
                            self.rgba_tup = (int(value_str[1:3],16), int(value_str[3:5],16), int(value_str[5:7],16)) 
                    except (ValueError, OverflowError, IndexError):
                        self.rgba_tup = (1.0, 1.0, 1.0, 1.0)
           
                if name_str=='NAME':
                    self.header_name = value_str.replace('/','-')
            
            # When in the PROPERTY CLASS header, get the colours
            elif inPropClassHeader:
                name_str, sep, value_str = line_str.partition(':')
                if name_str=='*COLORMAP*SIZE':
                    print("colourmap-size", value_str)
                elif name_str=='*COLORMAP*NBCOLORS':
                    print("numcolours", value_str)
                elif name_str=='HIGH_CLIP':
                    print("highclip", value_str)
                elif name_str=='LOW_CLIP':
                    print("lowclip", value_str)
                elif name_str=='COLORMAP':
                    print("colourmap id", value_str)
                    self.colourmap_name = value_str
                elif hasattr(self, 'colourmap_name') and name_str=='*COLORMAP*'+self.colourmap_name+'*COLORS':
                    lut_arr = value_str.split(' ')
                    for idx in range(0, len(lut_arr), 4):
                        try:
                            self.colour_map[int(lut_arr[idx])] = (float(lut_arr[idx+1]), float(lut_arr[idx+2]), float(lut_arr[idx+3]))
                        except (IndexError, OverflowError, ValueError):
                            pass

            # Property names
            elif splitstr_arr[0] == "PROPERTIES":
                properties_list = splitstr_arr[1:]

            # Atoms, with or without properties
            elif splitstr_arr[0] == "ATOM" or splitstr_arr[0] == 'PATOM':
                seq_no_prev = seq_no
                try:
                    seq_no = int(splitstr_arr[1])
                    v_num = int(splitstr_arr[2])
                except (OverflowError, ValueError, IndexError):
                    seq_no = seq_no_prev
                else:
                    if self.check_vertex(v_num):
                        self.atom_arr.append(self.ATOM(seq_no, v_num))
                    else:
                        print("ERROR - ATOM refers to VERTEX that has not been defined yet")
                        print("    seq_no = ", seq_no)
                        print("    v_num = ", v_num)
                        print("    line = ", line_str)
                        sys.exit(1)

                    # Atoms with properties
                    if splitstr_arr[0] == "PATOM":
                        try:
                            vert_dict = self.make_vertex_dict()
                            self.parse_props(splitstr_arr, properties_list, self.vrtx_arr[vert_dict[v_num]].xyz)
                        except IndexError:
                            pass
                  
            # Grab the vertices and properties, does not care if there are gaps in the sequence number
            elif splitstr_arr[0] == "PVRTX" or  splitstr_arr[0] == "VRTX":
                seq_no_prev = seq_no
                try:
                    seq_no = int(splitstr_arr[1])
                    is_ok, x_flt, y_flt, z_flt = self.parse_XYZ(True, splitstr_arr[2], splitstr_arr[3], splitstr_arr[4], True)
                except (IndexError, ValueError, OverflowError):
                    seq_no = seq_no_prev
                else:
                    if is_ok:
                        # Add vertex
                        if self.invert_zaxis:
                            z_flt = -z_flt
                        self.vrtx_arr.append(self.VRTX(seq_no, (x_flt, y_flt, z_flt)))

                        # Add properties to vertex at X,Y,Z
                        if splitstr_arr[0] == "PVRTX":
                            self.parse_props(splitstr_arr, properties_list, (x_flt, y_flt, z_flt))

            # Grab the triangular edges
            elif splitstr_arr[0] == "TRGL":
                seq_no_prev = seq_no
                try:
                    seq_no = int(splitstr_arr[1])
                    is_ok, a_int, b_int, c_int = self.parse_XYZ(False, splitstr_arr[1], splitstr_arr[2], splitstr_arr[3])
                except (IndexError, ValueError, OverflowError):
                    seq_no = seq_no_prev
                else:
                    if is_ok:
                        self.trgl_arr.append(self.TRGL(seq_no, (a_int, b_int, c_int)))

            # Grab the segments
            elif splitstr_arr[0] == "SEG":
                try:
                    a_int = int(splitstr_arr[1])
                    b_int = int(splitstr_arr[2])
                except (IndexError, ValueError):
                    seq_no = seq_no_prev
                else:
                    self.seg_arr.append(self.SEG(seq_no, (a_int, b_int)))

            # Voxel file attributes
            elif splitstr_arr[0] == "PROP_FILE":
                self.voxel_file = os.path.join(src_dir, splitstr_arr_raw[2])

            elif splitstr_arr[0] == "AXIS_O":
                is_ok, x_flt, y_flt, z_flt = self.parse_XYZ(True, splitstr_arr[1], splitstr_arr[2], splitstr_arr[3])
                if is_ok:
                    self.axis_origin = (x_flt, y_flt, z_flt)

            elif splitstr_arr[0] == "AXIS_U":
                is_ok, x_flt, y_flt, z_flt = self.parse_XYZ(True, splitstr_arr[1], splitstr_arr[2], splitstr_arr[3])
                if is_ok:
                    self.axis_u = (x_flt, y_flt, z_flt)

            elif splitstr_arr[0] == "AXIS_V":
                is_ok, x_flt, y_flt, z_flt = self.parse_XYZ(True, splitstr_arr[1], splitstr_arr[2], splitstr_arr[3])
                if is_ok:
                    self.axis_v = (x_flt, y_flt, z_flt)

            elif splitstr_arr[0] == "AXIS_W":
                is_ok, x_flt, y_flt, z_flt = self.parse_XYZ(True, splitstr_arr[1], splitstr_arr[2], splitstr_arr[3])
                if is_ok:
                    self.axis_w = (x_flt, y_flt, z_flt)

            elif splitstr_arr[0] == "AXIS_N":
                is_ok, x_int, y_int, z_int = self.parse_XYZ(False, splitstr_arr[1], splitstr_arr[2], splitstr_arr[3])
                if is_ok:
                    self.vol_dims = (x_int, y_int, z_int)

            elif splitstr_arr[0] == "AXIS_MIN":
                is_ok, x_int, y_int, z_int = self.parse_XYZ(False, splitstr_arr[1], splitstr_arr[2], splitstr_arr[3])
                if is_ok:
                    self.axis_min = (x_int, y_int, z_int)

            elif splitstr_arr[0] == "AXIS_MAX":
                is_ok, x_int, y_int, z_int = self.parse_XYZ(False, splitstr_arr[1], splitstr_arr[2], splitstr_arr[3])
                if is_ok:
                    self.axis_max = (x_int, y_int, z_int)

            # END OF TEXT PROCESSING LOOP

        print("filename_str=", filename_str)
            
        # Calculate max and min of properties rather than read them from file
        for prop_str in self.prop_dict:
            self.prop_meta.setdefault(prop_str,{})
            self.prop_meta[prop_str]['max'] = max(list(self.prop_dict[prop_str].values()))
            self.prop_meta[prop_str]['min'] = min(list(self.prop_dict[prop_str].values()))


        # Open up and read binary voxel file
        if self.is_vo and len(self.voxel_file)>0:
            try:
                # Check file size first
                file_sz = os.path.getsize(self.voxel_file)
                num_voxels = 4*self.vol_dims[0]*self.vol_dims[1]*self.vol_dims[2]
                if file_sz != num_voxels:
                    print("SORRY - Cannot process voxel file - length is not correct", filename_str)
                    sys.exit(1)
                self.voxel_data = numpy.zeros((self.vol_dims[0], self.vol_dims[1], self.vol_dims[2]))
                fp = open(self.voxel_file, 'rb')
                for z in range(self.vol_dims[2]):
                    for y in range(self.vol_dims[1]):
                        for x in range(self.vol_dims[0]):
                            binData = fp.read(4)
                            val = struct.unpack(">f", binData)[0] # It's big endian!
                            if (val > self.voxel_data_stats['max']):
                                self.voxel_data_stats['max'] = val
                            if (val < self.voxel_data_stats['min']):
                                self.voxel_data_stats['min'] = val
                            self.voxel_data[x][y][z] = val
                fp.close()
            except IOError as e:
                print("SORRY - Cannot process voxel file IOError", filename_str, str(e), e.args)
                return False

        return True

    def parse_props(self, splitstr_arr, properties_list, coord_tup):
        for p_idx in range(len(splitstr_arr[5:])):
            try:
                property_name = properties_list[p_idx]
                self.prop_dict.setdefault(property_name, {})
                fp_str = splitstr_arr[p_idx+5]
                # Handle GOCAD's C++ floating point infinity for Windows and Linux
                if fp_str in ["1.#INF","inf"]:
                    self.prop_dict[property_name][coord_tup] = sys.float_info.max
                elif fp_str in ["-1.#INF","-inf"]:
                    self.prop_dict[property_name][coord_tup] = -sys.float_info.max
                else:
                    self.prop_dict[property_name][coord_tup] = float(splitstr_arr[p_idx+5])
            except (OverflowError, ValueError, IndexError):
                if self.prop_dict[property_name] == {}:
                    del self.prop_dict[property_name]


    def parse_XYZ(self, is_float, x_str, y_str, z_str, do_minmax=False):
        ''' Helpful function to read XYZ cooordinates
            x_str, y_str, z_str - X,Y,Z coordinates in string form
            do_minmax - record the X,Y,Z coords for calculating extent
            Returns four parameters: success  - true if could convert the strings to floats
                                   x,y,z - floating point values
        '''
        x = y = z = None
        if is_float:
            try:
                x = float(x_str)
                y = float(y_str)
                z = float(z_str)
            except (OverflowError, ValueError):
                return False, None, None, None
        else:
            try:
                x = int(x_str)
                y = int(y_str)
                z = int(z_str)
            except (OverflowError, ValueError):
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
