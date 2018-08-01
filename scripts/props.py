import numpy

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

        self.data_3d = {}
        ''' Property data collected from binary file, value is float, stored as a 3d numpy array.
        '''

        self.data_xyz = {}
        ''' Property data attached to XYZ points (index is XYZ coordinate)
        '''

        self.colour_3d = {}
        ''' Colours of properties, value is integer index to 'colour_map', stored as a 3d numpy array
        '''

        self.data_stats = {}
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

        self.is_colour_table = False
        ''' Uses 'colour_3d' to hold index to colour table
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

