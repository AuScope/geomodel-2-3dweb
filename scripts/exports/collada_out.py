import collada as Collada
import numpy
import logging
import sys

class COLLADA_OUT():
    ''' Class to output specific geometries as pycollada objects
    '''

    def __init__(self, debug_level):
        ''' Initialise class
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
            mesh - pycollada 'Collada' object
            colour_num - index value for colour table
            x,y,z - integer xyz coords in volume
            geom_obj - MODEL_GEOMETRY object
            pt_size - size of cube, float
            geometry_name - generic label for all cubes
            file_cnt - file counter
            point_cnt - cube counter within this file
            geomnode_list - pycollada 'GeometryNode' list
            Returns the geometry label of this cube
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


    def make_pyramid(self, mesh, geometry_name, geomnode_list, vrtx, point_cnt):
        ''' Makes a pyramid using pycollada objects
            Returns its geometry label
            mesh - pycollada 'Collada' object
            geometry_name - generic label for all cubes
            geomnode_list - list of pycollada 'GeometryNode' objects
            vrtx - VTRX object
            point_cnt - pyramid counter within this file
            
        '''

        # Vertices of the pyramid
        vert_floats = [vrtx.xyz[0], vrtx.xyz[1], vrtx.xyz[2]+POINT_SIZE*2] + \
                      [vrtx.xyz[0]+POINT_SIZE, vrtx.xyz[1]+POINT_SIZE, vrtx.xyz[2]] + \
                      [vrtx.xyz[0]+POINT_SIZE, vrtx.xyz[1]-POINT_SIZE, vrtx.xyz[2]] + \
                      [vrtx.xyz[0]-POINT_SIZE, vrtx.xyz[1]-POINT_SIZE, vrtx.xyz[2]] + \
                      [vrtx.xyz[0]-POINT_SIZE, vrtx.xyz[1]+POINT_SIZE, vrtx.xyz[2]]
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
        geomnode_list += [Collada.scene.GeometryNode(geom, matnode_list)]


    def make_borehole(self):
        pass
