

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

    SEG = namedtuple('SEG', 'n ab')
    ''' Immutable named tuple which stores segment data
        n = sequence number
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

