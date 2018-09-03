''' Container class for style (colour, shading etc.) of objects
'''


class STYLE:
    def __init__(self):

        self.__rgba_tup = (1.0, 1.0, 1.0, 1.0)
        ''' If one colour is specified then it is stored here
        '''

        self.__is_set = False
        ''' rgba_tup has been set
        '''

    def __repr__(self):
        return("STYLE(): rgba_tup={0}".format(str(self.rgba_tup)))

    @property
    def rgba_tup(self):
        return self.__rgba_tup

    @rgba_tup.setter
    def rgba_tup(self, val):
        self.__rgba_tup = val
        self.__is_set = True

    def has_single_colour(self):
        return self.__is_set
        
