import collada as Collada
import numpy
import logging
import sys

class COLLADA_OUT():
    ''' Class to output graphics to COLLADA 
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


    def collada_cube(self, mesh, colour_num, x,y,z, geom_obj, pt_size, geometry_name, file_cnt, point_cnt):
        ''' Writes out a cube in COLLADA format, geometric object label
            Returns a pycollada node list
            mesh - pycollada mesh object
            colour_num - index value for colour table
            x,y,z - integer xyz coords in volume
            geom_obj - MODEL_GEOMETRY object
            pt_size - size of cube
            geometry_name - label for this cube
            file_cnt - file counter
            point_cnt - cube counter within this file
        '''
        #self.logger.debug("collada_cube(mesh=%s, colour_num=%s, x,y,z=%s, v_obj=%s, pt_size=%s, geometry_name=%s, file_cnt=%s, point_cnt=%s)",  repr(mesh), repr(colour_num), repr((x,y,z)), repr(v_obj), repr(pt_size), repr(geometry_name), repr(file_cnt), repr(point_cnt))
        v = (geom_obj.vol_origin[0]+ float(x)/geom_obj.vol_sz[0]*geom_obj.vol_axis_u[0],
             geom_obj.vol_origin[1]+ float(y)/geom_obj.vol_sz[1]*geom_obj.vol_axis_v[1],
             geom_obj.vol_origin[2]+ float(z)/geom_obj.vol_sz[2]*geom_obj.vol_axis_w[2])
        node_list = []
        geomnode_list = []
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

        node = Collada.scene.Node("node{0:010d}".format(point_cnt), children=geomnode_list)
        node_list.append(node)
        return node_list, geom_label
