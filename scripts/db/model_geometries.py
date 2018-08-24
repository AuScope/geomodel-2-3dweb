''' Class used to store abstract parts of a model
    It should be independent as possible of any model's input format
    All sequence numbers etc. start at 1
'''

import sys
from collections import namedtuple

class MODEL_GEOMETRIES:
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

    SEG = namedtuple('SEG', 'ab')
    ''' Immutable named tuple which stores segment data
        ab = segment vertices
    '''

    def __init__(self):

        self._vrtx_arr = []
        ''' Array of named tuples 'VRTX' used to store vertex data
        '''

        self._atom_arr = []
        ''' Array of named tuples 'ATOM' used to store atom data
        '''

        self._trgl_arr = []
        ''' Array of named tuples 'TRGL' used store triangle face data
        '''

        self._seg_arr = []
        ''' Array of named tuples 'SEG' used to store line segment data
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

        self.rgba_tup = (1.0, 1.0, 1.0, 1.0)
        ''' If one colour is specified then it is stored here
        '''

    def get_vrtx_arr(self):
        ''' Returns array of VRTX objects
        '''
        return self._vrtx_arr 


    def get_atom_arr(self):
        ''' Returns array of ATOM objects 
        '''
        return self._atom_arrr


    def get_trgl_arr(self):
        ''' Returns array of TRGL objects
        '''
        return self._trgl_arr


    def get_seg_arr(self):
        ''' Returns array of SEG objects
        '''
        return self._seg_arr


    def _check_vertex(self, num):
        ''' If vertex exists then returns true else false
            num - vertex number to search for
        '''
        for vrtx in self._vrtx_arr:
            if vrtx.n == num:
                return True
        return False


    def _calc_minmax(self, x, y, z):
        ''' Calculate the max and min of all x,y,z coords
        '''
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


    def get_extent(self):
        ''' Returns estimate of the geographic extent of the model, using max and min coordinate values
            format is [min_x, max_x, min_y, max_y]
        '''
        return [self.min_X, self.max_X, self.min_Y, self.max_Y]

