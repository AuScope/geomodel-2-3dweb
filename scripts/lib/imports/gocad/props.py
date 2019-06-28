"""
Contains the PROPS class
"""
import os
import csv
import sys
import logging
from collections import defaultdict
import numpy



class PROPS:
    ''' This class holds generic 3d data and properties
        e.g. information extracted from 3d binary files (e.g. from GOCAD 'PROP_FILE')
        information attached to a set of XYZ points (e.g. from GOCAD 'PATOM', 'PVRTX')
    '''

    def __init__(self, class_name, debug_level):

        # Set up logging, use an attribute of class name so it is only called once
        if not hasattr(PROPS, 'logger'):
            PROPS.logger = logging.getLogger(__name__)

            # Create console handler
            handler = logging.StreamHandler(sys.stdout)

            # Create formatter
            formatter = logging.Formatter('%(asctime)s -- %(name)s -- %(levelname)s - %(message)s')

            # Add formatter to ch
            handler.setFormatter(formatter)

            # Add handler to logger and set level
            PROPS.logger.addHandler(handler)

        PROPS.logger.setLevel(debug_level)

        self.logger = PROPS.logger

        self.file_name = ""
        ''' Name of binary file associated with GOCAD file
        '''

        self.data_sz = 0
        ''' Number of bytes in number in binary file, usually 1, 2 or 4
        '''

        self.data_type = "f"
        ''' Type of data in binary file e.g. 'h' = short 2-byte int, 'f' = float, 'b' - byte
        '''

        self.signed_int = False
        ''' Is True iff binary data is a signed integer else False
        '''

        self.data_3d = numpy.zeros((0, 0, 0))
        ''' Property data collected from binary file, value is float, stored as a 3d numpy array.
        '''

        self.data_xyz = defaultdict(list)
        ''' Property data attached to XYZ points (index is XYZ coordinate)
        '''

        self.data_stats = {'min': sys.float_info.max, 'max': -sys.float_info.max}
        ''' Property data statistics: min & max
        '''

        self.colour_map = {}
        ''' If colour map was specified, then it is stored here, integer is the key,
            value is (R,G,B,A) where R, G, B, A are floats
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

        self.is_index_data = False
        ''' Uses 'data_3d' to hold index to colour table or rock label table
        '''

        self.rock_label_table = {}
        ''' Table specifying names of rocks , key is an integer, value is the label
        '''

        self.offset = 0
        ''' Offset within binary file
        '''


    def __repr__(self):
        ''' A print friendly representation
        '''
        return "\nPROPS START\n  self = {:}\n".format(hex(id(self))) + \
               "  file_name = {:}\n".format(repr(self.file_name)) + \
               "  data_sz = {:d}\n".format(self.data_sz) + \
               "  data_type = {:}\n".format(repr(self.data_type)) + \
               "  signed_int = {:}\n".format(repr(self.signed_int)) + \
               "  data_3d = {:}\n".format(repr(self.data_3d)) + \
               "  data_xyz = {:}\n".format(repr(self.data_xyz)) + \
               "  data_stats = {:}\n".format(repr(self.data_stats)) + \
               "  colour_map = {:}\n".format(repr(self.colour_map)) + \
               "  colourmap_name = {:}\n".format(self.colourmap_name) + \
               "  class_name = {:}\n".format(self.class_name) + \
               "  no_data_marker = {:}\n".format(repr(self.no_data_marker)) + \
               "  is_index_data = {:}\n".format(repr(self.is_index_data)) + \
               "  rock_label_table = {:}\n".format(repr(self.rock_label_table)) + \
               "  str_data_type = {:}\n".format(repr(self.get_str_data_type())) + \
               "PROPS END\n\n"


    def get_str_data_type(self):
        ''' Returns a string form of the data type of the volume data
            e.g. "INT_16", "FLOAT_32", "UINT_8"
        '''
        if self.data_type == 'f' and self.data_sz == 4:
            return "FLOAT_32"
        if self.data_type == 'h' and self.data_sz == 2:
            if self.signed_int:
                return "INT_16"
            return "UINT_16"
        if self.data_type == 'b':
            if self.signed_int:
                return "INT_8"
            return "UINT_8"
        return ""


    def make_numpy_dtype(self):
        ''' Returns a string that can be passed to 'numpy' to read a binary file
            It takes the 'data_type' of 'f', 'b', h'
        '''
        # Prepare 'numpy' binary float integer signed/unsigned data types
        # Using '>' to tell 'numpy' that it is big-endian
        # Using upper case to tell 'numpy' that it is unsigned integer
        # 'numpy' recognises 'h' as a 2-byte integer and 'b' as byte
        if self.data_type == 'h' or self.data_type == 'b':
            if not self.signed_int:
                return numpy.dtype('>'+self.data_type.upper())

            return numpy.dtype('>'+self.data_type)

        # Floating point i.e. data_type = 'f'
        return numpy.dtype('>'+self.data_type+str(self.data_sz))


    def read_colour_table_csv(self, csv_file, transp_list):
        ''' Reads an RGB colour table from CSV file for use in VOXET colours
            CSV Format: col#1: integer index, col#2: R-value, col#3: G-value, col#4: B-value
            csv_file - filename of  CSV file to read, without path
            Sets the 'colour_map' and 'rock_label_table' class attibutes
            'colour_map' is a dict, key is integer, value is (R,G,B,A) tuple of floats
            'rock_label_table' is a dict, key is integer, value is string
        '''
        col_tab = {}
        lab_tab = {}
        if not os.path.isfile(csv_file):
            self.logger.error("Cannot find CSV file: %s", csv_file)
            sys.exit(1)
        try:
            csv_filehandle = open(csv_file, 'r')
            csv_reader = csv.reader(csv_filehandle)
            for row in csv_reader:
                a_val = 1.0
                if int(row[0]) in transp_list:
                    a_val = 0.0
                col_tab[int(row[0])] = (float(row[2]), float(row[3]), float(row[4]), a_val)
                lab_tab[int(row[0])] = row[1]
        except OSError as os_exc:
            self.logger.error("Cannot read CSV file %s %s", csv_file, os_exc)
            sys.exit(1)
        self.colour_map = col_tab
        self.rock_label_table = lab_tab


    def assign_to_3d(self, x_val, y_val, z_val, fltp):
        ''' Assigns a value to 3d array
            x,y,z - XYZ integer array indexes
            fltp - floating point value to be assigned

        '''
        self.data_3d[x_val][y_val][z_val] = fltp
        self.__calc_minmax(fltp)


    def assign_to_xyz(self, xyz, val):
        ''' Assigns a value to xyz dict
            xyz - (X,Y,Z) tuple array indexes (floats)
            val - value to be assigned (float or tuple)
        '''
        self.data_xyz[xyz] = val
        if isinstance(val, float):
            self.__calc_minmax(val)


    def append_to_xyz(self, xyz, val):
        ''' Appends a value to xyz dict
            xyz - (X,Y,Z) tuple array indexes (floats)
            val - value to be assigned
        '''
        self.data_xyz[xyz].append(val)



    def __calc_minmax(self, fltp):
        ''' Calculates minimum & maximum of floating point value and stores
            result locally in 'data_stats'
            fp - floating point value
        '''
        if fltp > self.data_stats['max']:
            self.data_stats['max'] = fltp
        if fltp < self.data_stats['min']:
            self.data_stats['min'] = fltp
