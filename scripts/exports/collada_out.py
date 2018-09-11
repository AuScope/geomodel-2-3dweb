import collada as Collada
import numpy
import logging
import sys
import math

class COLLADA_OUT():
    ''' Class to output specific geometries as pycollada objects
    '''

    def __init__(self, debug_level):
        ''' Initialise class
 
        :param debug_level: debug level, using python's 'logger' class
        '''
        # Set up logging, use an attribute of class name so it is only called once
        if not hasattr(COLLADA_OUT, 'logger'):
            COLLADA_OUT.logger = logging.getLogger(__name__)

            # Create console handler
            handler = logging.StreamHandler(sys.stdout)

            # Create formatter
            formatter = logging.Formatter('%(asctime)s -- %(name)s -- %(levelname)s - %(message)s')

            # Add formatter to ch

            # Add handler to logger and set level
            COLLADA_OUT.logger.addHandler(handler)

        COLLADA_OUT.logger.setLevel(debug_level)
        self.logger = COLLADA_OUT.logger


    def make_cube(self, mesh, colour_num, x,y,z, geom_obj, pt_size, geometry_name, file_cnt, point_cnt, geomnode_list):
        ''' Makes a cube using pycollada objects

        :param mesh: pycollada 'Collada' object
        :param colour_num: index value for colour table
        :param x,y,z: integer xyz coords in volume
        :param geom_obj: MODEL_GEOMETRY object
        :param pt_size: size of cube, float
        :param geometry_name: generic label for all cubes
        :param file_cnt: file counter
        :param point_cnt: cube counter within this file
        :param geomnode_list: pycollada 'GeometryNode' list
        :returns: the geometry label of this cube
        '''
        #self.logger.debug("collada_cube(mesh=%s, colour_num=%s, x,y,z=%s, v_obj=%s, pt_size=%s, geometry_name=%s, file_cnt=%s, point_cnt=%s)",  repr(mesh), repr(colour_num), repr((x,y,z)), repr(v_obj), repr(pt_size), repr(geometry_name), repr(file_cnt), repr(point_cnt))
        v = (geom_obj.vol_origin[0]+ float(x)/geom_obj.vol_sz[0]*geom_obj.vol_axis_u[0],
             geom_obj.vol_origin[1]+ float(y)/geom_obj.vol_sz[1]*geom_obj.vol_axis_v[1],
             geom_obj.vol_origin[2]+ float(z)/geom_obj.vol_sz[2]*geom_obj.vol_axis_w[2])
        popup_dict = {}
        vert_floats = [v[0]-pt_size[0], v[1]-pt_size[1], v[2]+pt_size[2]] \
                    + [v[0]-pt_size[0], v[1]+pt_size[1], v[2]+pt_size[2]] \
                    + [v[0]+pt_size[0], v[1]-pt_size[1], v[2]+pt_size[2]] \
                    + [v[0]+pt_size[0], v[1]+pt_size[1], v[2]+pt_size[2]] \
                    + [v[0]-pt_size[0], v[1]-pt_size[1], v[2]-pt_size[2]] \
                    + [v[0]-pt_size[0], v[1]+pt_size[1], v[2]-pt_size[2]] \
                    + [v[0]+pt_size[0], v[1]-pt_size[1], v[2]-pt_size[2]] \
                    + [v[0]+pt_size[0], v[1]+pt_size[1], v[2]-pt_size[2]]
        vert_src = Collada.source.FloatSource("cubeverts-array-{0:010d}".format(point_cnt), numpy.array(vert_floats), ('X', 'Y', 'Z'))
        geom_label = "{0}_{1}-{2:010d}".format(geometry_name, file_cnt, point_cnt)
        geom = Collada.geometry.Geometry(mesh, "geometry{0:010d}".format(point_cnt), geom_label, [vert_src])
        input_list = Collada.source.InputList()
        input_list.addInput(0, 'VERTEX', "#cubeverts-array-{0:010d}".format(point_cnt))

        indices = [ 1,3,7, 1,7,5, 0,4,6, 0,6,2, 2,6,7, 2,7,3,
                   4,5,6, 5,7,6, 0,2,3, 0,3,1, 0,1,5, 0,5,4 ]

        material_label = "materialref-{0:010d}".format(colour_num)
        # Triangles seem to be more efficient than polygons
        triset = geom.createTriangleSet(numpy.array(indices), input_list, material_label)
        geom.primitives.append(triset)
        mesh.geometries.append(geom)
        matnode = Collada.scene.MaterialNode(material_label, mesh.materials[colour_num], inputs=[])
        geomnode_list.append(Collada.scene.GeometryNode(geom, [matnode]))

        return geom_label


    def make_pyramid(self, mesh, geometry_name, geomnode_list, vrtx, point_cnt, point_sz, colour_num):
        ''' Makes a pyramid using pycollada objects

        :param mesh: pycollada 'Collada' object
        :param geometry_name: generic label for all pyramids
        :param geomnode_list: list of pycollada 'GeometryNode' objects
        :param vrtx: VTRX object
        :param point_cnt: pyramid counter within this file
        :returns: the pyramid's geometry label
        '''

        # Vertices of the pyramid
        vert_floats = [vrtx.xyz[0], vrtx.xyz[1], vrtx.xyz[2]+point_sz*2] + \
                      [vrtx.xyz[0]+point_sz, vrtx.xyz[1]+point_sz, vrtx.xyz[2]] + \
                      [vrtx.xyz[0]+point_sz, vrtx.xyz[1]-point_sz, vrtx.xyz[2]] + \
                      [vrtx.xyz[0]-point_sz, vrtx.xyz[1]-point_sz, vrtx.xyz[2]] + \
                      [vrtx.xyz[0]-point_sz, vrtx.xyz[1]+point_sz, vrtx.xyz[2]]
        input_list = Collada.source.InputList()
        input_list.addInput(0, 'VERTEX', "#pointverts-array-{0:010d}".format(point_cnt))
        # Define the faces of the pyramid as six triangles
        indices = [0, 2, 1,  0, 1, 4,  0, 4, 3,  0, 3, 2,  4, 1, 2,  2, 3, 4]
        vert_src_list = [Collada.source.FloatSource("pointverts-array-{0:010d}".format(point_cnt), numpy.array(vert_floats), ('X', 'Y', 'Z'))]
        geom_label = "{0}-{1:010d}".format(geometry_name, point_cnt)
        geom = Collada.geometry.Geometry(mesh, "geometry{0:010d}".format(point_cnt), geom_label, vert_src_list)
        triset_list = [geom.createTriangleSet(numpy.array(indices), input_list, "materialref-{0:010d}".format(colour_num))]
        geom.primitives = triset_list
        mesh.geometries.append(geom)
        matnode_list = [Collada.scene.MaterialNode("materialref-{0:010d}".format(colour_num), mesh.materials[colour_num], inputs=[])]
        geomnode_list.append(Collada.scene.GeometryNode(geom, matnode_list))


    def make_line(self, mesh, geometry_name, geomnode_list, seg_arr, vrtx_arr, obj_cnt, line_width):
        ''' Makes a line using pycollada objects

            :param mesh: pycollada 'Collada' object
            :param geometry_name: generic label for all cubes
            :param geomnode_list: list of pycollada 'GeometryNode' objects
            :param seg_arr: array of SEG objects, defines line segments
            :param vrtx_arr: array of VRTX objects, all points along line
            :param obj_cnt: object counter within this file (an object may contain many lines)
            :param line_width: line width, float
            :returns: the line's geometry label
        '''
        matnode = Collada.scene.MaterialNode("materialref-{0:05d}".format(obj_cnt), mesh.materials[0], inputs=[])
        geom_label_list = []
        point_cnt = 0

        # Draw lines as a series of triangles
        for l in seg_arr:
            v0 = vrtx_arr[l.ab[0]-1]
            v1 = vrtx_arr[l.ab[1]-1]

            vert_floats = list(v0.xyz) + [v0.xyz[0], v0.xyz[1], v0.xyz[2]+line_width] + list(v1.xyz) + [v1.xyz[0], v1.xyz[1], v1.xyz[2]+line_width]
            vert_src = Collada.source.FloatSource("lineverts-array-{0:010d}-{1:05d}".format(point_cnt, obj_cnt), numpy.array(vert_floats), ('X', 'Y', 'Z'))
            geom_label = "line-{0}-{1:010d}".format(geometry_name, point_cnt)
            geom = Collada.geometry.Geometry(mesh, "geometry{0:010d}-{1:05d}".format(point_cnt, obj_cnt), geom_label, [vert_src])

            input_list = Collada.source.InputList()
            input_list.addInput(0, 'VERTEX', "#lineverts-array-{0:010d}-{1:05d}".format(point_cnt, obj_cnt))

            indices = [0, 2, 3, 3, 1, 0]

            triset = geom.createTriangleSet(numpy.array(indices), input_list, "materialref-{0:05d}".format(obj_cnt))
            geom.primitives.append(triset)
            mesh.geometries.append(geom)
            # NB: Assumes only one colour - this will be improved later on
            geomnode_list.append(Collada.scene.GeometryNode(geom, [matnode]))

            geom_label_list.append(geom_label)
            point_cnt += 1
       
        return geom_label_list 
            

    def make_borehole_marker(self, mesh, pos, borehole_label, geomnode_list):
        ''' Makes a borehole marker stick with triangular cross section using pycollada objects

        :param mesh: pycollada 'Collada' object
        :param pos: x,y,z position of collar of borehole
        :param borehole_label: geometry label for this borehole stick
        :param geomnode_list: list of pycollada 'GeometryNode' objects
        '''
        BH_WIDTH_UPPER = 75 # Width at uppermost point of stick
        BH_WIDTH_LOWER = 10 # width at lowermost point of stick
        BH_HEIGHT = 15000 # Height of stick above ground
        BH_DEPTH = 2000 # Depth of stick below ground

        # Convert bv to an equilateral triangle of floats
        angl_rad = math.radians(30.0)
        cos_flt = math.cos(angl_rad)
        sin_flt = math.sin(angl_rad)
        ptA_high = [pos[0], pos[1]+BH_WIDTH_UPPER*cos_flt, pos[2]+BH_HEIGHT]
        ptB_high = [pos[0]+BH_WIDTH_UPPER*cos_flt, pos[1]-BH_WIDTH_UPPER*sin_flt, pos[2]+BH_HEIGHT]
        ptC_high = [pos[0]-BH_WIDTH_UPPER*cos_flt, pos[1]-BH_WIDTH_UPPER*sin_flt, pos[2]+BH_HEIGHT]
        ptA_low = [pos[0], pos[1]+BH_WIDTH_LOWER*cos_flt, pos[2]-BH_DEPTH]
        ptB_low = [pos[0]+BH_WIDTH_LOWER*cos_flt, pos[1]-BH_WIDTH_LOWER*sin_flt, pos[2]-BH_DEPTH]
        ptC_low = [pos[0]-BH_WIDTH_LOWER*cos_flt, pos[1]-BH_WIDTH_LOWER*sin_flt, pos[2]-BH_DEPTH]

        vert_list = ptA_high + ptB_high + ptC_high + ptA_low + ptC_low + ptB_low
        vert_src = Collada.source.FloatSource("pointverts-array-0", numpy.array(vert_list), ('X', 'Y', 'Z'))
        geom = Collada.geometry.Geometry(mesh, "geometry0", borehole_label, [vert_src])
        input_list = Collada.source.InputList()
        input_list.addInput(0, 'VERTEX', "#pointverts-array-0")

        indices = [0, 2, 1,
                   3, 5, 4,
                   1, 2, 5,
                   2, 4, 5,
                   0, 4, 2,
                   0, 3, 4,
                   0, 1, 3,
                   1, 5, 3]

        triset = geom.createTriangleSet(numpy.array(indices), input_list, "materialref-0")
        geom.primitives.append(triset)
        mesh.geometries.append(geom)

        # Assumes only one colour
        matnode = Collada.scene.MaterialNode("materialref-0", mesh.materials[0], inputs=[])
        geomnode_list.append(Collada.scene.GeometryNode(geom, [matnode]))



    def make_colour_borehole_marker(self, mesh, pos, borehole_label, geomnode_list, colour_info_dict, ht_resol):
        ''' Makes a borehole marker stick with triangular cross section using pycollada objects

        :param mesh: pycollada 'Collada' object
        :param pos: x,y,z position of collar of borehole
        :param borehole_label: geometry label for this borehole stick
        :param geomnode_list: list of pycollada 'GeometryNode' objects
        :param ht_reso: height resolution
        '''
        BH_WIDTH= 75 # Width of stick
        max_depth = max(colour_info_dict.keys())
        min_depth = max(colour_info_dict.keys())

        # Convert bv to an equilateral triangle of floats
        angl_rad = math.radians(30.0)
        cos_flt = math.cos(angl_rad)
        sin_flt = math.sin(angl_rad)
        colour_idx = 0
        for depth, colour_info in colour_info_dict.items():
            height = pos[2]+max_depth+ht_resol-depth
            ptA_high = [pos[0], pos[1]+BH_WIDTH*cos_flt, height]
            ptB_high = [pos[0]+BH_WIDTH*cos_flt, pos[1]-BH_WIDTH*sin_flt, height]
            ptC_high = [pos[0]-BH_WIDTH*cos_flt, pos[1]-BH_WIDTH*sin_flt, height]
            ptA_low = [pos[0], pos[1]+BH_WIDTH*cos_flt, height-ht_resol]
            ptB_low = [pos[0]+BH_WIDTH*cos_flt, pos[1]-BH_WIDTH*sin_flt, height-ht_resol]
            ptC_low = [pos[0]-BH_WIDTH*cos_flt, pos[1]-BH_WIDTH*sin_flt, height-ht_resol]

            vert_list = ptA_high + ptB_high + ptC_high + ptA_low + ptC_low + ptB_low
            vert_src = Collada.source.FloatSource("pointverts-array-0", numpy.array(vert_list), ('X', 'Y', 'Z'))
            geom = Collada.geometry.Geometry(mesh, "geometry_{0}".format(int(depth)), "{0}_{1}".format(borehole_label, int(depth)), [vert_src])
            input_list = Collada.source.InputList()
            input_list.addInput(0, 'VERTEX', "#pointverts-array-0")

            indices = [0, 2, 1,
                       3, 5, 4,
                       1, 2, 5,
                       2, 4, 5,
                       0, 4, 2,
                       0, 3, 4,
                       0, 1, 3,
                       1, 5, 3]

            triset = geom.createTriangleSet(numpy.array(indices), input_list, "materialref-{:d}".format(int(depth)))
            geom.primitives.append(triset)
            mesh.geometries.append(geom)

            matnode = Collada.scene.MaterialNode("materialref-{:d}".format(int(depth)), mesh.materials[colour_idx], inputs=[])
            geomnode_list.append(Collada.scene.GeometryNode(geom, [matnode]))
            colour_idx += 1



