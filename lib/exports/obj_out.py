import sys
import logging

from db.style.false_colour import make_false_colour_tup

class OBJ_OUT():
    ''' Class to output geometries to Wavefront OBJ format
    '''

    def __init__(self, debug_level):
        ''' Initialise class

        :param debug_level: debug level, using python's 'logging' module
        '''
        # Set up logging, use an attribute of class name so it is only called once
        if not hasattr(OBJ_OUT, 'logger'):
            OBJ_OUT.logger = logging.getLogger(__name__)

            # Create console handler
            handler = logging.StreamHandler(sys.stdout)

            # Create formatter
            formatter = logging.Formatter('%(asctime)s -- %(name)s -- %(levelname)s - %(message)s')

            # Add formatter to ch

            # Add handler to logger and set level
            OBJ_OUT.logger.addHandler(handler)

        OBJ_OUT.logger.setLevel(debug_level)
        self.logger = OBJ_OUT.logger

        # Limit to 256 colours
        self.MAX_COLOURS = 256.0


    def write_voxel_obj(self, geom_obj, out_fp, fileName, src_file_str, step_sz, use_full_cubes):
        ''' Writes out voxel data to Wavefront OBJ and MTL files

        :param out_fp: open file handle of OBJ file
        :param geom_obj: MODEL_GEOMETRY object
        :param fileName: filename of OBJ file without the 'OBJ' extension
        :param src_file_str: filename of gocad file
        :param step_sz: when stepping through the voxel block this is the step size
        :param use_full_cubes: will write out full cubes to file if true, else will remove non-visible faces
        '''
        self.logger.debug("write_voxel_obj(%s,%s)",  fileName, src_file_str)
        mtl_fp = open(fileName+".MTL", 'w')
        for colour_idx in range(int(self.MAX_COLOURS)):
            diffuse_colour = make_false_colour_tup(float(colour_idx), 0.0, self.MAX_COLOURS)
            mtl_fp.write("# Wavefront MTL file converted from  '{0}'\n\n".format(src_file_str))
            mtl_fp.write("newmtl colouring-{0:03d}\n".format(colour_idx))
            mtl_fp.write("Ka {0:.3f} {1:.3f} {2:.3f}\n".format(diffuse_colour[0], diffuse_colour[1], diffuse_colour[2]))
            mtl_fp.write("Kd {0:.3f} {1:.3f} {2:.3f}\n".format(diffuse_colour[0], diffuse_colour[1], diffuse_colour[2]))
            mtl_fp.write("Ks 0.000 0.000 0.000\n")
            mtl_fp.write("d 1.0\n")
        mtl_fp.close()
        ct_done = True
        out_fp.write("mtllib "+fileName+".MTL\n")
        vert_idx = 0
        breakOut = False
        for z in range(0,geom_obj.vol_sz[2],step_sz):
            for y in range(0,geom_obj.vol_sz[1],step_sz):
                for x in range(0,geom_obj.vol_sz[0],step_sz):
                    colour_num = int(255.0*(geom_obj.voxel_data[x][y][z] - geom_obj.voxel_data_stats['min'])/(geom_obj.voxel_data_stats['max'] - geom_obj.voxel_data_stats['min']))

                    # NB: Assumes AXIS_MIN = 0, and AXIS_MAX = 1
                    u_offset = geom_obj.vol_origin[0]+ float(x)/geom_obj.vol_sz[0]*geom_obj.vol_axis_u[0]
                    v_offset = geom_obj.vol_origin[1]+ float(y)/geom_obj.vol_sz[1]*geom_obj.vol_axis_v[1]
                    w_offset = geom_obj.vol_origin[2]+ float(z)/geom_obj.vol_sz[2]*geom_obj.vol_axis_w[2]
                    v = (u_offset, v_offset, w_offset)
                    pt_size = (step_sz*geom_obj.vol_axis_u[0]/geom_obj.vol_sz[0]/2, step_sz*geom_obj.vol_axis_v[1]/geom_obj.vol_sz[1]/2, step_sz*geom_obj.vol_axis_w[2]/geom_obj.vol_sz[2]/2)
                    vert_list = [ (v[0]-pt_size[0], v[1]-pt_size[1], v[2]+pt_size[2]),
                                  (v[0]-pt_size[0], v[1]-pt_size[1], v[2]-pt_size[2]),
                                  (v[0]-pt_size[0], v[1]+pt_size[1], v[2]-pt_size[2]),
                                  (v[0]-pt_size[0], v[1]+pt_size[1], v[2]+pt_size[2]),
                                  (v[0]+pt_size[0], v[1]-pt_size[1], v[2]+pt_size[2]),
                                  (v[0]+pt_size[0], v[1]-pt_size[1], v[2]-pt_size[2]),
                                  (v[0]+pt_size[0], v[1]+pt_size[1], v[2]-pt_size[2]),
                                  (v[0]+pt_size[0], v[1]+pt_size[1], v[2]+pt_size[2]),
                                ]
                    indice_list = []

                    # Create a full cube for each voxel
                    if use_full_cubes:
                        indice_list = [ (4, 3, 2, 1), # WEST
                                        (2, 6, 5, 1), # SOUTH
                                        (3, 7, 6, 2), # BOTTOM
                                        (8, 7, 3, 4), # NORTH
                                        (5, 8, 4, 1), # TOP
                                        (6, 7, 8, 5), # EAST
                                      ]
                    # To save space, only create surfaces at the edges, assuming a block shape (valid??)
                    else:
                        # BOTTOM FACE
                        if z==0:
                            indice_list.append((3, 7, 6, 2))
                        # TOP FACE
                        if z==geom_obj.vol_sz[2]-1:
                            indice_list.append((5, 8, 4, 1))
                        # SOUTH FACE
                        if y==0:
                            indice_list.append((2, 6, 5, 1))
                        # NORTH FACE
                        if y==geom_obj.vol_sz[1]:
                            indice_list.append((8, 7, 3, 4))
                        # EAST FACE
                        if x==0:
                            indice_list.append((6, 7, 8, 5))
                        # WEST FACE
                        if x==geom_obj.vol_sz[0]:
                            indice_list.append((4, 3, 2, 1))

                    # Only write if there are indices to write
                    if len(indice_list)>0:
                        for vert in vert_list:
                            out_fp.write("v {0:f} {1:f} {2:f}\n".format(vert[0],vert[1],ert[2]))
                        out_fp.write("g main-{0:010d}\n".format(vert_idx))
                        out_fp.write("usemtl colouring-{0:03d}\n".format(colour_num))
                        for ind in indice_list:
                            out_fp.write("f {0:d} {1:d} {2:d} {3:d}\n".format(ind[0]+vert_idx, ind[1]+vert_idx, ind[2]+vert_idx, ind[3]+vert_idx))
                        out_fp.write("\n")
                        vert_idx += len(vert_list)
                        if vert_idx > 99999999999:
                            breakOut = True
                            break
                if breakOut:
                    break
            if breakOut:
                break
        return ct_done


    def write_OBJ(self, geom_obj, fileName, src_file_str):
        ''' Writes out an OBJ file

        :param geom_obj: MODEL_GEOMETRY object
        :param fileName: filename of OBJ file, without extension
        :param src_file_str: filename of gocad file

        NOTES:
            OBJ is very simple, and has shortcomings:
            1. Does not include annotations (only comments and a group name)
            2. Lines and points do not have a colour

        I am only using it here because GOCAD VOXEL files are too big for COLLADA format
        '''
        self.logger.debug("write_OBJ(%s,%s)", fileName, src_file_str)

        # Output to OBJ file
        print("Writing OBJ file: ",fileName+".OBJ")
        out_fp = open(fileName+".OBJ", 'w')
        out_fp.write("# Wavefront OBJ file converted from '{0}'\n\n".format(src_file_str))
        ct_done = False
        # This dictionary returns the insertion order of the vertex in the vrtx_arr given its sequence number
        vert_dict = geom_obj.make_vertex_dict()
        if geom_obj.is_trgl():
            if len(style_obj.get_rgba_tup())==4:
                out_fp.write("mtllib "+fileName+".MTL\n")
        if geom_obj.is_trgl() or geom_obj.is_line() or geom_obj.is_point():
            for v in geom_obj.vrtx_arr:
                out_fp.write("v {0:f} {1:f} {2:f}\n".format(v.xyz[0],v.xyz[1],v.xyz[2]))
        out_fp.write("g main\n")
        if geom_obj.is_trgl():
            out_fp.write("usemtl colouring\n")
            for f in geom_obj.trgl_arr:
                out_fp.write("f {0:d} {1:d} {2:d}\n".format(vert_dict[f.abc[0]], vert_dict[f.abc[1]], vert_dict[f.abc[2]]))

        elif geom_obj.is_line():
            for s in geom_obj.seg_arr:
                out_fp.write("l {0:d} {1:d}\n".format(vert_dict[s.ab[0]], vert_dict[s.ab[1]]))

        elif geom_obj.is_point():
            out_fp.write("p");
            for p in range(len(geom_obj.vrtx_arr)):
                out_fp.write(" {0:d}".format(p+1))
            out_fp.write("\n")

        elif geom_obj.is_volume():
            ct_done=self.write_voxel_obj(out_fp, fileName, src_file_str, 64, False)
        out_fp.close()

        # Create an MTL file for the colour
        rgba_tup = style_obj.get_rgba_tup()
        if len(rgba_tup)==4 and not ct_done:
            out_fp = open(fileName+".MTL", 'w')
            out_fp.write("# Wavefront MTL file converted from  '{0}'\n\n".format(src_file_str))
            out_fp.write("newmtl colouring\n")
            out_fp.write("Ka {0:.3f} {1:.3f} {2:.3f}\n".format(rgba_tup[0], rgba_tup[1], rgba_tup[2]))
            out_fp.write("Kd {0:.3f} {1:.3f} {2:.3f}\n".format(rgba_tup[0], rgba_tup[1], rgba_tup[2]))
            out_fp.write("Ks 0.000 0.000 0.000\n")
            out_fp.write("d 1.0\n")
            out_fp.close()


