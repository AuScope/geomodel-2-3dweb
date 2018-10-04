import numpy
import os
import csv
import sys

class PROPS:
    ''' This class holds generic 3d data and properties
        e.g. information extracted from 3d binary files (e.g. from GOCAD 'PROP_FILE')
        information attached to a set of XYZ points (e.g. from GOCAD 'PATOM', 'PVRTX')
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

        self.data_3d = numpy.zeros((0,0,0))
        ''' Property data collected from binary file, value is float, stored as a 3d numpy array.
        '''

        self.data_xyz = {}
        ''' Property data attached to XYZ points (index is XYZ coordinate)
        '''

        self.data_stats = { 'min': sys.float_info.max, 'max': -sys.float_info.max }
        ''' Property data statistics: min & max
        '''

        self.colour_map = {}
        ''' If colour map was specified, then it is stored here, integer key, value is (R,G,B,A) where R, G, B, A are floats
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
        return "self = {:}\n".format(hex(id(self))) + \
               "file_name = {:}\n".format(repr(self.file_name)) + \
               "data_sz = {:d}\n".format(self.data_sz) + \
               "data_type = {:}\n".format(repr(self.data_type)) + \
               "signed_int = {:}\n".format(repr(self.signed_int)) + \
               "data_3d = {:}\n".format(repr(self.data_3d)) + \
               "data_xyz = {:}\n".format(repr(self.data_xyz)) + \
               "data_stats = {:}\n".format(repr(self.data_stats)) + \
               "colour_map = {:}\n".format(repr(self.colour_map)) + \
               "colourmap_name = {:}\n".format(self.colourmap_name) + \
               "class_name = {:}\n".format(self.class_name) + \
               "no_data_marker = {:}\n".format(repr(self.no_data_marker)) + \
               "is_index_data = {:}\n".format(repr(self.is_index_data)) + \
               "rock_label_table = {:}\n".format(repr(self.rock_label_table)) 


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


    def read_colour_table_csv(self, csv_file):
        ''' Reads a colour table from CSV file for use in VOXET colours
            csv_file - filename of  CSV file to read, without path
            Returns a dict, key is integer, keys start at 0, value is (R,G,B,A) tuple of floats
        '''
        ct = {}
        lt = {}
        if not os.path.isfile(csv_file):
            self.logger.error("ERROR - cannot find CSV file: %s", csv_file)
            sys.exit(1)
        try:
            csvfilehandle = open(csv_file, 'r')
            spamreader = csv.reader(csvfilehandle)
            for row in spamreader:
                ct[int(row[0])] = (float(row[2]),float(row[3]),float(row[4]), 1.0)
                lt[int(row[0])] = row[1]
        except Exception as e:
            self.logger.error("ERROR - cannot read CSV file %s %s", csv_file, e)
            sys.exit(1)
        # Make sure it is zero-based
        if min(ct.keys()) == 1:
            ret_ct = {}
            ret_lt = {}
            for key in ct:
                ret_ct[key-1] = ct[key]
                ret_lt[key-1] = lt[key]
            self.colour_map = ret_ct
            self.rock_label_table = ret_lt
        else:
            self.colour_map = ct
            self.rock_label_table = lt


    def assign_to_3d(self, x,y,z, fp):
        ''' Assigns a value to 3d array
            x,y,z - XYZ integer array indexes
            fp - floating point value to be assigned
            
        '''
        self.data_3d[x][y][z] = fp
        self.__calc_minmax(fp)


    def assign_to_xyz(self, xyz, val):
        ''' Assigns a value to xyz dict
            xyz - (X,Y,Z) tuple array indexes (floats)
            val - value to be assigned (float or tuple)
        '''
        self.data_xyz[xyz] = val
        if type(val) is float:
            self.__calc_minmax(val)


    def append_to_xyz(self, xyz, val):
        ''' Appends a value to xyz dict 
            xyz - (X,Y,Z) tuple array indexes (floats)
            val - value to be assigned 
        '''
        self.data_xyz.setdefault((x,y,z), [])
        self.data_xyz[xyz].append(val)
        


    def __calc_minmax(self, fp):
        ''' Calculates minimum & maximum of floating point value and stores result locally in 'data_stats'
            fp - floating point value
        '''
        if (fp > self.data_stats['max']):
            self.data_stats['max'] = fp
        if (fp < self.data_stats['min']):
            self.data_stats['min'] = fp



