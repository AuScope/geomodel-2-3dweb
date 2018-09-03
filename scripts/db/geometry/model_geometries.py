''' Class used to store abstract parts of a model
    It should be independent as possible of any model's input format
    All sequence numbers for *_arr start at 1
'''

import sys
from collections import namedtuple

from .types import VRTX, ATOM, TRGL, SEG

class MODEL_GEOMETRIES:

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

        self.vol_origin = None
        ''' Origin of volume's XYZ axes
        '''

        self.vol_axis_u = None
        ''' Full length U-axis volume vector
        '''

        self.vol_axis_v = None
        ''' Full length V-axis volume vector
        '''

        self.vol_axis_w = None
        ''' Full length W-axis volume vector
        '''

        self.vol_sz = None
        ''' 3 dimensional size of voxel volume
        '''

        self.vol_data = None
        ''' 3d numpy array of volume data
        '''

        self.xyz_data = {}
        ''' Generic property data associated with XYZ points
        '''
 
        self.max_data = None
        ''' Maximum value in 'xyz_data' or 'vol_data'
        '''

        self.min_data = None
        ''' Minimum value in 'xyz_data' or 'vol_data'
        '''

    def __repr__(self):
        ''' Print friendly representation
        '''
        ret_str = ''
        for field in dir(self):
            if field[-2:] != '__' and not callable(getattr(self, field)):
                ret_str += field + ": " + repr(getattr(self, field))[:500] + "\n"
        return ret_str


    # properties

    @property
    def vrtx_arr(self):
        ''' Returns array of VRTX objects
        '''
        return self._vrtx_arr 


    @property
    def atom_arr(self):
        ''' Returns array of ATOM objects 
        '''
        return self._atom_arr


    @property
    def trgl_arr(self):
        ''' Returns array of TRGL objects
        '''
        return self._trgl_arr


    @property
    def seg_arr(self):
        ''' Returns array of SEG objects
        '''
        return self._seg_arr


    def is_trgl(self):
        ''' Returns True iff this contains triangle data
        '''
        return len(self._trgl_arr) > 0


    def is_line(self):
        ''' Returns True iff this contails line data
        '''
        return len(self._seg_arr) > 0


    def is_point(self):
        ''' Returns True iff this contains point data
        '''
        return (len(self._vrtx_arr) > 0 or len(self._atom_arr) > 0) and len(self._trgl_arr) == 0 and len(self._seg_arr) == 0


    def is_volume(self):
        ''' Returns True iff this contains volume data
          
        '''
        return self.vol_sz != None


    def calc_minmax(self, x, y, z):
        ''' Calculates and stores the max and min of all x,y,z coords
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

