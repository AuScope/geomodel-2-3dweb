"""
Contains ModelGeometries class
"""
import sys
import numpy as np

def unit_vector(vector):
    ''' :returns: the unit vector of the vector.
    '''
    return vector / np.linalg.norm(vector)

class ModelGeometries:
    ''' Class used to store abstract geometry of parts of a geological model and its data
        It should be independent as possible of any model's input format
        Each class only stores data for 1 volume, but for many line segments and triangle faces
        All sequence numbers for _*_arr start at 1
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

        self.max_x = -sys.float_info.max
        ''' Maximum X coordinate, used to calculate extent
        '''

        self.min_x = sys.float_info.max
        ''' Minimum X coordinate, used to calculate extent
        '''

        self.max_y = -sys.float_info.max
        ''' Maximum Y coordinate, used to calculate extent
        '''

        self.min_y = sys.float_info.max
        ''' Minimum Y coordinate, used to calculate extent
        '''

        self.max_z = -sys.float_info.max
        ''' Maximum Z coordinate, used to calculate extent
        '''

        self.min_z = sys.float_info.max
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

        self.vol_sz = []
        ''' 3 dimensional size of voxel volume
        '''

        self.vol_data = None
        ''' 3d numpy array of volume data
        '''

        self.vol_data_type = "FLOAT_32"
        ''' Type of data in 'vol_data'/'_xyz_data' e.g. 'FLOAT_32' 'INT_16', 'RGBA'
            NB: If >8 bits, always stored in big-endian fashion
        '''

        self._xyz_data = []
        ''' Generic property data associated with XYZ points
            This is an array of a dictionary mapping (X,Y,Z) => [data1, data2, data3, ... ]
        '''

        self._max_data = []
        ''' Array of maximum values in 'xyz_data' or 'vol_data'
        '''

        self._min_data = []
        ''' Array of minimum value in 'xyz_data' or 'vol_data'
        '''

        self._no_data_marker = []
        ''' Array of values indicating no data exists at a point in space
        '''

    def __repr__(self):
        ''' Print friendly representation
        '''
        ret_str = ''
        for field in dir(self):
            if field[-2:] != '__' and not callable(getattr(self, field)):
                ret_str += field + ": " + repr(getattr(self, field))[:500] + "\n"
        return ret_str


    # Properties

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
        return (len(self._vrtx_arr) > 0 or len(self._atom_arr) > 0) and len(self._trgl_arr) == 0 \
               and len(self._seg_arr) == 0


    def is_volume(self):
        ''' Returns True iff this contains volume data

        '''
        return len(self.vol_sz) > 2


    def is_single_layer_vo(self):
        ''' Returns True if this is extracted from a GOCAD VOXEL that only has a single layer
            and should be converted into a PNG instead of a GLTF
        '''
        return self.is_volume() and self.vol_sz[2] == 1


    def calc_minmax(self, x_coord, y_coord, z_coord):
        ''' Calculates and stores the max and min of all x,y,z coords

        :param x_coord, y_coord, z_coord: x,y,z coords
        '''
        if x_coord > self.max_x:
            self.max_x = x_coord
        if x_coord < self.min_x:
            self.min_x = x_coord
        if y_coord > self.max_y:
            self.max_y = y_coord
        if y_coord < self.min_y:
            self.min_y = y_coord
        if z_coord > self.max_z:
            self.max_z = z_coord
        if z_coord < self.min_z:
            self.min_z = z_coord


    def get_extent(self):
        ''' :returns: estimate of the geographic extent of the model, using max and min
            coordinate values format is [min_x, max_x, min_y, max_y]
        '''
        return [self.min_x, self.max_x, self.min_y, self.max_y]


    def get_vol_side_lengths(self):
        ''' :returns: the lengths of the sides of a volume in [X, Y, Z] form, where X,Y,Z are floats
        '''
        return [self.max_x - self.min_x, self.max_y - self.min_y, self.max_z - self.min_z]


    def get_rotation(self):
        ''' :returns: three unit vectors of the volume's XYZ axes
        '''
        u_vec = unit_vector(self.vol_axis_u)
        v_vec = unit_vector(self.vol_axis_v)
        w_vec = unit_vector(self.vol_axis_w)
        ret = [tuple(u_vec), tuple(v_vec), tuple(w_vec)]
        return ret


    def get_max_data(self, idx=0):
        ''' Retrieves maximum value of data point
        :param idx: index into property data, omit for volume data
        :returns: maximum data value
        '''
        if len(self._max_data) > idx:
            return self._max_data[idx]
        return None


    def get_min_data(self, idx=0):
        ''' Retrieves minimum value of data point
        :param idx: index into property data, omit for volume data
        :returns: minimum data value
        '''
        if len(self._min_data) > idx:
            return self._min_data[idx]
        return None


    def get_no_data_marker(self, idx=0):
        ''' Retrieve no data marker
        :param idx: index into property data, omit for volume data
        :returns: no data marker
        '''
        if len(self._no_data_marker) > idx:
            return self._no_data_marker[idx]
        return None


    def add_stats(self, min_val, max_val, no_data):
        ''' Adds minimum, maximum and no data marker
        :param min_val: minimum value
        :param max_val: maximum value
        :param no_data: value used in a dataset when no data is recorded for a location
        '''
        self._min_data.append(min_val)
        self._max_data.append(max_val)
        self._no_data_marker.append(no_data)


    def add_xyz_data(self, xyz_data):
        ''' Adds an instance of XYZ data
        :param xyz_data: dictionary of (X,Y,Z) => data value to be added
        '''
        self._xyz_data.append(xyz_data)


    def get_xyz_data(self, idx=0):
        ''' Retrieves data from xyz data dictionary
        :param idx: index for when there are multiple values for each point in space,
                    omit for volumes
        :returns: dictionary of (X,Y,Z) => data value
        '''
        if len(self._xyz_data) > idx:
            return self._xyz_data[idx]
        return {}
