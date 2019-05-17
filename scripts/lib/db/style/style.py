
class STYLE:
    ''' Container class for style (colour, shading etc.) of objects
    '''

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
        return("STYLE(): rgba_tup={0} colour_table={1} label_table={2}".format(str(self.__rgba_tup), str(self.__colour_table), str(self.__label_table)))


    def get_rgba_tup(self, idx=0):
        ''' Gets the single colour for objects of only one colour
        :returns: colour (R,G,B,A) 4-float tuple
        '''
        if len(self.__rgba_tup) > idx:
            return self.__rgba_tup[idx]
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

