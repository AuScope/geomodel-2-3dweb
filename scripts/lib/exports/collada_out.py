"""
Contains the ColladaOut class
"""
import logging
import sys
import numpy
import collada as Collada
from lib.exports.geometry_gen import colour_borehole_gen, line_gen, pyramid_gen, cube_gen

class ColladaOut():
    ''' Class to output specific geometries as pycollada objects
    '''

    def __init__(self, debug_level):
        ''' Initialise class

        :param debug_level: debug level, using python's 'logger' class
        '''
        # Set up logging, use an attribute of class name so it is only called once
        if not hasattr(ColladaOut, 'logger'):
            ColladaOut.logger = logging.getLogger(__name__)

            # Create console handler
            handler = logging.StreamHandler(sys.stdout)

            # Create formatter
            formatter = logging.Formatter('%(asctime)s -- %(name)s -- %(levelname)s - %(message)s')

            # Add formatter to ch
            handler.setFormatter(formatter)

            # Add handler to logger and set level
            ColladaOut.logger.addHandler(handler)

        ColladaOut.logger.setLevel(debug_level)
        self.logger = ColladaOut.logger


    def make_cube(self, mesh, colour_num, x_val, y_val, z_val, geom_obj, pt_size,
                  geometry_name, file_cnt, point_cnt, geomnode_list):
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
        #self.logger.debug("collada_cube(mesh=%s, colour_num=%s, x,y,z=%s, v_obj=%s,
        # pt_size=%s, geometry_name=%s, file_cnt=%s, point_cnt=%s)",
        # repr(mesh), repr(colour_num), repr((x,y,z)), repr(v_obj), repr(pt_size),
        # repr(geometry_name), repr(file_cnt), repr(point_cnt))
        gen = cube_gen(x_val, y_val, z_val, geom_obj, pt_size)
        vert_floats, indices = next(gen)
        vert_src = Collada.source.FloatSource("cubeverts-array-{0:010d}".format(point_cnt),
                                              numpy.array(vert_floats), ('X', 'Y', 'Z'))
        geom_label = "{0}_{1}-{2:010d}".format(geometry_name, file_cnt, point_cnt)
        geom = Collada.geometry.Geometry(mesh, "geometry{0:010d}".format(point_cnt),
                                         geom_label, [vert_src])
        input_list = Collada.source.InputList()
        input_list.addInput(0, 'VERTEX', "#cubeverts-array-{0:010d}".format(point_cnt))

        material_label = "materialref-{0:010d}".format(colour_num)
        # Triangles seem to be more efficient than polygons
        triset = geom.createTriangleSet(numpy.array(indices), input_list, material_label)
        geom.primitives.append(triset)
        mesh.geometries.append(geom)
        matnode = Collada.scene.MaterialNode(material_label, mesh.materials[colour_num], inputs=[])
        geomnode_list.append(Collada.scene.GeometryNode(geom, [matnode]))

        return geom_label


    def make_pyramid(self, mesh, geometry_name, geomnode_list, vrtx, point_cnt,
                     point_sz, colour_num):
        ''' Makes a pyramid using pycollada objects

        :param mesh: pycollada 'Collada' object
        :param geometry_name: generic label for all pyramids
        :param geomnode_list: list of pycollada 'GeometryNode' objects
        :param vrtx: VTRX object
        :param point_cnt: pyramid counter within this file
        :param point_sz: size of pyramid
        :param colour_num: integer index into mesh materials, determines colour of pyramid
        :returns: the pyramid's geometry label
        '''

        # Get pyramid geometry
        gen = pyramid_gen(vrtx, point_sz)
        vert_floats, indices = next(gen)

        input_list = Collada.source.InputList()
        input_list.addInput(0, 'VERTEX', "#pointverts-array-{0:010d}".format(point_cnt))
        vert_src_list = [Collada.source.FloatSource("pointverts-array-{0:010d}".format(point_cnt),
                                                    numpy.array(vert_floats), ('X', 'Y', 'Z'))]
        geom_label = "{0}-{1:010d}".format(geometry_name, point_cnt)
        geom = Collada.geometry.Geometry(mesh, "geometry{0:010d}".format(point_cnt),
                                         geom_label, vert_src_list)
        triset_list = [geom.createTriangleSet(numpy.array(indices), input_list,
                                              "materialref-{0:010d}".format(colour_num))]
        geom.primitives = triset_list
        mesh.geometries.append(geom)
        matnode_list = [Collada.scene.MaterialNode("materialref-{0:010d}".format(colour_num),
                                                   mesh.materials[colour_num], inputs=[])]
        geomnode_list.append(Collada.scene.GeometryNode(geom, matnode_list))
        return geom_label


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
        matnode = Collada.scene.MaterialNode("materialref-{0:05d}".format(obj_cnt),
                                             mesh.materials[0], inputs=[])
        geom_label_list = []

        for point_cnt, vert_floats, indices in line_gen(seg_arr, vrtx_arr, line_width):

            vert_src = Collada.source.FloatSource(
                "lineverts-array-{0:010d}-{1:05d}".format(point_cnt, obj_cnt),
                numpy.array(vert_floats), ('X', 'Y', 'Z'))
            geom_label = "line-{0}-{1:010d}".format(geometry_name, point_cnt)
            geom = Collada.geometry.Geometry(mesh,
                                             "geometry{0:010d}-{1:05d}".format(point_cnt, obj_cnt),
                                             geom_label, [vert_src])

            input_list = Collada.source.InputList()
            input_list.addInput(0, 'VERTEX',
                                "#lineverts-array-{0:010d}-{1:05d}".format(point_cnt, obj_cnt))

            triset = geom.createTriangleSet(numpy.array(indices),
                                            input_list, "materialref-{0:05d}".format(obj_cnt))
            geom.primitives.append(triset)
            mesh.geometries.append(geom)
            # NB: Assumes only one colour - this will be improved later on
            geomnode_list.append(Collada.scene.GeometryNode(geom, [matnode]))

            geom_label_list.append(geom_label)

        return geom_label_list


    def make_colour_borehole_marker(self, mesh, pos, borehole_label, geomnode_list,
                                    colour_info_dict, ht_resol):
        ''' Makes a borehole marker stick with triangular cross section using pycollada objects

        :param mesh: pycollada 'Collada' object
        :param pos: x,y,z position of collar of borehole
        :param borehole_label: geometry label for this borehole stick
        :param geomnode_list: list of pycollada 'GeometryNode' objects
        :param colour_info_dict: dict of: key = height, float; value = { 'colour': (R,G,B,A),
                                                                         'classText': label }
        :param ht_reso: height resolution
        '''
        cb_gen = colour_borehole_gen(pos, "borehole-{0}".format(borehole_label),
                                     colour_info_dict, ht_resol)
        # pylint:disable=W0612
        for vert_list, indices, colour_idx, depth, colour_info, mesh_name in cb_gen:
            vert_src = Collada.source.FloatSource("pointverts-array-0", numpy.array(vert_list),
                                                  ('X', 'Y', 'Z'))
            geom = Collada.geometry.Geometry(mesh, "geometry_{0}".format(int(depth)),
                                             mesh_name, [vert_src])
            input_list = Collada.source.InputList()
            input_list.addInput(0, 'VERTEX', "#pointverts-array-0")

            triset = geom.createTriangleSet(numpy.array(indices), input_list,
                                            "materialref-{:d}".format(int(depth)))
            geom.primitives.append(triset)
            mesh.geometries.append(geom)

            matnode = Collada.scene.MaterialNode("materialref-{:d}".format(int(depth)),
                                                 mesh.materials[colour_idx], inputs=[])
            geomnode_list.append(Collada.scene.GeometryNode(geom, [matnode]))
