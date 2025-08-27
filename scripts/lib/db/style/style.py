import random

"""
Contains the STYLE class
"""
class STYLE:
    ''' Container class for style (colour, shading etc.) of objects
    '''
    # Used to generate random colours when no colour is provided
    COLOUR_LIST = [ (235, 77, 77), (235, 77, 111), (235, 77, 156), (235, 77, 219), (193, 77, 235),
                    (141, 77, 235), (101, 77, 235), (77, 112, 235), (77, 167, 235), (77, 216, 235),
                    (77, 235, 215), (77, 235, 161), (77, 235, 95), (192, 235, 77), (230, 235, 77),
                    (235, 192, 77), (235, 171, 77), (235, 136, 77), (240, 194, 195), (240, 194, 231),
                    (226, 194, 240), (194, 195, 240), (194, 217, 240), (194, 240, 240), (194, 240, 216),
                    (220, 240, 194), (238, 240, 194), (240, 227, 194), (240, 209, 194)
                  ]

    def __init__(self):

        self.__rgba_tup = []
        ''' If one colour is specified then it is stored here as an (R,G,B,A) 4 float tuple
        '''

        self.__is_single_colour = []
        ''' Boolean, True if rgba_tup has been set, and colour table has not been set
        '''

        self.__colour_table = []
        ''' colour table dictionary, integer keys, (R,G,B,A) 4-float tuple values
        '''

        self.__label_table = []
        ''' label table dict, keys are integers, values are strings
        '''


    def __repr__(self):
        ''' Pretty print version of this class
        '''
        return f"STYLE(): rgba_tup={self.__rgba_tup}" + \
               f" colour_table={self.__colour_table}" + \
               f" label_table={self.__label_table}"


    def get_rgba_tup(self, idx=None, def_rand=False):
        ''' Gets the previously stored single colour (for objects of only one colour)
        :param idx: optional index into colour array
        :param def_rand: optional boolean will generate a random colour if no colour stored
        :returns: colour (R,G,B,A) 4-float tuple
        '''
        if len(self.__rgba_tup) > 0:
            # If caller supplied a valid index return its colour
            if idx is not None and len(self.__rgba_tup) > idx:
                return self.__rgba_tup[idx]
            # If no valid index supplied, return last colour in array
            return self.__rgba_tup[-1]

        # Return a random or a default if no colour specified
        if def_rand:
            r, g, b = random.choice(self.COLOUR_LIST)
            return(r / 256.0, g / 256.0, b / 256.0, 1.0)
        return (1.0, 1.0, 1.0, 1.0)


    def add_rgba_tup(self, val):
        ''' Sets the single colour for objects of only one colour
        :param val: single colour, (R,G,B,A) 4-float tuple
        '''
        self.__rgba_tup.append(val)
        self.__is_single_colour.append(True)


    def has_single_colour(self, idx=0):
        ''' Returns True if this STYLE instance has only one colour, rather than a colour table
        :returns: boolean, True for single colour style, else false
        '''
        if len(self.__is_single_colour) > idx:
            return self.__is_single_colour[idx]
        return True


    def get_colour_table(self, idx=0):
        ''' Get the colour table
        :returns: dictionary, integer keys, (R,G,B,A) 4-float tuple values
        '''
        if len(self.__colour_table) > idx:
            return self.__colour_table[idx]
        return {}


    def add_tables(self, colour_table, label_table):
        ''' Add a colour table and a label table
        :param colour_table: new colour table value
        :param label_table: new colour table value
        '''
        self.__colour_table.append(colour_table)
        self.__is_single_colour.append(False)
        self.__label_table.append(label_table)


    def get_label_table(self, idx=0):
        ''' Get the label table
        :returns: dictionary, integer keys, string values
        '''
        if len(self.__label_table) > idx:
            return self.__label_table[idx]
        return {}
