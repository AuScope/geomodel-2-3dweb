'''
A collection of Python generator functions used to create geometries,
including: borehole sticks, lines, cubes and pyramids
'''
import math
from types import SimpleNamespace
import numpy as np
from lib.exports.bh_utils import make_borehole_label

def colour_borehole_gen(pos, borehole_name, colour_info_dict, ht_resol):
    ''' A generator which is used to make a borehole marker stick with triangular cross section

    :param pos: x,y,z position of collar of borehole, tuple of 3 floats
    :param borehole_name: borehole's name
    :param colour_info_dict: dict of: key = height, float; \
                                      value = SimpleNamespace({ 'colour': (R,G,B,A) floats, \
                                                'classText': <mineral name>, \
                                                'className': <measurement class> })
    :param ht_reso: height resolution, float
    :returns vert_list - list of floats, (x,y,z) vertices; \
        indices - list of integers, index pointers to which vertices are joined as triangles; \
        colour_idx - integer index pointing to material object array; \
        depth - depth of borehole segment, float; \
        rgba_colour - RGBA colour 4-tuple, floats; \
        class_dict - dict of mineral information,  { 'classText': <mineral name>, \
                                                     'className': <measurement class> } \
        mesh_name - used to label meshes during mesh generation (bytes object)
    '''
    bh_width = 10.0 # Width of stick

    # Convert bv to an equilateral triangle of floats
    angl_rad = math.radians(30.0)
    cos_flt = math.cos(angl_rad)
    sin_flt = math.sin(angl_rad)
    for colour_idx, (depth, colour_info) in enumerate(colour_info_dict.items()):
        height = pos[2] + ht_resol - depth
        pt_a_high = [pos[0], pos[1] + bh_width*cos_flt, height]
        pt_b_high = [pos[0] + bh_width*cos_flt, pos[1] - bh_width*sin_flt, height]
        pt_c_high = [pos[0] - bh_width*cos_flt, pos[1] - bh_width*sin_flt, height]
        pt_a_low = [pos[0], pos[1] + bh_width*cos_flt, height - ht_resol]
        pt_b_low = [pos[0] + bh_width*cos_flt, pos[1] - bh_width*sin_flt, height - ht_resol]
        pt_c_low = [pos[0] - bh_width*cos_flt, pos[1] - bh_width*sin_flt, height - ht_resol]

        vert_list = [pt_a_high, pt_b_high, pt_c_high, pt_a_low, pt_c_low, pt_b_low]

        indices = [[0, 2, 1],
                   [3, 5, 4],
                   [1, 2, 5],
                   [2, 4, 5],
                   [0, 4, 2],
                   [0, 3, 4],
                   [0, 1, 3],
                   [1, 5, 3]]

        mesh_name = make_borehole_label(borehole_name, depth)

        # If there is missing colour and mineral information, then add blank one
        if not isinstance(colour_info, list) or len(colour_info) < 1:
            rgba_colour = (1.0, 1.0, 1.0, 1.0)
            class_dict = { 'classText': 'unknown', 'className': 'unknown'}
        else:
            # NB: Only takes the colour of the most common mineral at that depth
            rgba_colour = colour_info[0].colour
            class_dict = { 'classText': colour_info[0].classText, 'className': colour_info[0].className }

        yield vert_list, indices, colour_idx, depth, rgba_colour, class_dict, mesh_name

def tri_gen(trgl_arr, vrtx_arr, mesh_name):
    ''' A generator which is used to make a triangular mesh

    :param trgl_arr triangle array, an array of TRGL objects
    :param vrtx_arr: vertex array, an array of VRTX objects
    '''
    sorted_vrtx_list = sorted(vrtx_arr, key=lambda k: k.n)
    sorted_trgl_list = sorted(trgl_arr, key=lambda k: k.n)
    trgl_list = []
    vrtx_list = []
    for vrtx_obj in sorted_vrtx_list:
        vrtx_list += vrtx_obj.xyz
    for trgl_obj in sorted_trgl_list:
        trgl_list += [trgl_obj.abc[0] - 1, trgl_obj.abc[1] - 1, trgl_obj.abc[2] - 1]

    yield vrtx_list, trgl_list, bytes(mesh_name, 'ascii')


def line_gen(seg_arr, vrtx_arr, line_width, z_expand):
    ''' A generator which is used to make lines

    :param seg_arr: line segment array, an array of SEG objects
    :param vrtx_arr: vertex array, an array of VRTX objects
    :param line_width: line width, float
    :param z_expand: if true will expand width in z-direction, else x-direction
    :returns point_cnt, vert_floats, indices: point_cnt - count of iterations; \
        vert_floats - list of (x,y,z) vertices, floats; \
        indices - integer index pointers to which vertices are joined as triangles
    '''
    # Draw lines as a series of triangles
    for point_cnt, line in enumerate(seg_arr):
        v_0 = vrtx_arr[line.ab[0]-1]
        v_1 = vrtx_arr[line.ab[1]-1]
        if z_expand:
            z_width = line_width
            x_width = 0
        else:
            x_width = line_width
            z_width = 0
        vert_floats = list(v_0.xyz) + [v_0.xyz[0]+x_width, v_0.xyz[1], v_0.xyz[2]+z_width] + \
                      list(v_1.xyz) + [v_1.xyz[0]+x_width, v_1.xyz[1], v_1.xyz[2]+z_width]
        indices = [0, 2, 3, 3, 1, 0]

        yield point_cnt, vert_floats, indices


def cube_gen(x_val, y_val, z_val, geom_obj, pt_size):
    ''' A single iteration generator which is used to create a cube

    :param x,y,z: x,y,z index coordinates of cube, integers
    :param geom_obj: MODEL_GEOMETRY object, holds the volume geometry details
    :param pt_size: size of cube, three float tuple
    :returns vert_floats, indices: vert_floats - list of (x,y,z) vertices, floats; \
        indices - integer index pointers to which vertices are joined as triangles
    '''
    uvw = (geom_obj.vol_origin[0]+ float(x_val)/geom_obj.vol_sz[0]*abs(geom_obj.vol_axis_u[0]),
           geom_obj.vol_origin[1]+ float(y_val)/geom_obj.vol_sz[1]*abs(geom_obj.vol_axis_v[1]),
           geom_obj.vol_origin[2]+ float(z_val)/geom_obj.vol_sz[2]*abs(geom_obj.vol_axis_w[2]))
    vert_floats = [uvw[0]-pt_size[0], uvw[1]-pt_size[1], uvw[2]+pt_size[2]] \
                + [uvw[0]-pt_size[0], uvw[1]+pt_size[1], uvw[2]+pt_size[2]] \
                + [uvw[0]+pt_size[0], uvw[1]-pt_size[1], uvw[2]+pt_size[2]] \
                + [uvw[0]+pt_size[0], uvw[1]+pt_size[1], uvw[2]+pt_size[2]] \
                + [uvw[0]-pt_size[0], uvw[1]-pt_size[1], uvw[2]-pt_size[2]] \
                + [uvw[0]-pt_size[0], uvw[1]+pt_size[1], uvw[2]-pt_size[2]] \
                + [uvw[0]+pt_size[0], uvw[1]-pt_size[1], uvw[2]-pt_size[2]] \
                + [uvw[0]+pt_size[0], uvw[1]+pt_size[1], uvw[2]-pt_size[2]]

    indices = [1, 3, 7, 1, 7, 5, 0, 4, 6, 0, 6, 2, 2, 6, 7, 2, 7, 3,
               4, 5, 6, 5, 7, 6, 0, 2, 3, 0, 3, 1, 0, 1, 5, 0, 5, 4]

    yield vert_floats, indices


def pyramid_gen(vrtx, point_sz):
    ''' A single iteration generator which is used to create a pyramid

    :param vrtx: VRTX object, position of pyramid
    :param pt_size: size of pyramid, float
    :returns vert_floats, indices: vert_floats - list of (x,y,z) vertices, floats; \
        indices - integer index pointers to which vertices are joined as triangles
    '''

    # Vertices of the pyramid
    vert_floats = [vrtx.xyz[0], vrtx.xyz[1], vrtx.xyz[2]+point_sz*2] + \
                  [vrtx.xyz[0]+point_sz, vrtx.xyz[1]+point_sz, vrtx.xyz[2]] + \
                  [vrtx.xyz[0]+point_sz, vrtx.xyz[1]-point_sz, vrtx.xyz[2]] + \
                  [vrtx.xyz[0]-point_sz, vrtx.xyz[1]-point_sz, vrtx.xyz[2]] + \
                  [vrtx.xyz[0]-point_sz, vrtx.xyz[1]+point_sz, vrtx.xyz[2]]
    indices = [0, 2, 1, 0, 1, 4, 0, 4, 3, 0, 3, 2, 4, 1, 2, 2, 3, 4]

    yield vert_floats, indices
