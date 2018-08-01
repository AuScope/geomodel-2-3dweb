import sys
import logging

class OBJ_OUT():
    ''' Class to output geometries to Wavefront OBJ format
    '''

    def __init__(self, debug_level):
        ''' Initialise class
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


    def write_voxel_obj(self, v_obj, out_fp, fileName, src_file_str, step_sz, use_full_cubes):
        ''' Writes out voxel data to Wavefront OBJ and MTL files
            out_fp - open file handle of OBJ file
            v_obj - vessel object that holds details of GOCAD file
            fileName - filename of OBJ file without the 'OBJ' extension
            src_file_str - filename of gocad file
            step_sz  - when stepping through the voxel block this is the step size
            use_full_cubes - will write out full cubes to file if true, else will remove non-visible faces
        '''
        self.logger.debug("write_voxel_obj(%s,%s)",  fileName, src_file_str)
        # Limit to 256 colours
        mtl_fp = open(fileName+".MTL", 'w')
        for colour_idx in range(256):
            diffuse_colour = self.make_colour_map(float(colour_idx), 0.0, 255.0)
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
        for z in range(0,v_obj.vol_sz[2],step_sz):
            for y in range(0,v_obj.vol_sz[1],step_sz):
                for x in range(0,v_obj.vol_sz[0],step_sz):
                    colour_num = int(255.0*(v_obj.voxel_data[x][y][z] - v_obj.voxel_data_stats['min'])/(v_obj.voxel_data_stats['max'] - v_obj.voxel_data_stats['min']))
                    # NB: Assumes AXIS_MIN = 0, and AXIS_MAX = 1
                    u_offset = v_obj.axis_origin[0]+ float(x)/v_obj.vol_sz[0]*v_obj.axis_u[0]
                    v_offset = v_obj.axis_origin[1]+ float(y)/v_obj.vol_sz[1]*v_obj.axis_v[1]
                    w_offset = v_obj.axis_origin[2]+ float(z)/v_obj.vol_sz[2]*v_obj.axis_w[2]
                    v = (u_offset, v_offset, w_offset)
                    pt_size = (step_sz*v_obj.axis_u[0]/v_obj.vol_sz[0]/2, step_sz*v_obj.axis_v[1]/v_obj.vol_sz[1]/2, step_sz*v_obj.axis_w[2]/v_obj.vol_sz[2]/2)
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
                        if z==v_obj.vol_sz[2]-1:
                            indice_list.append((5, 8, 4, 1))
                        # SOUTH FACE
                        if y==0:
                            indice_list.append((2, 6, 5, 1))
                        # NORTH FACE
                        if y==v_obj.vol_sz[1]:
                            indice_list.append((8, 7, 3, 4))
                        # EAST FACE
                        if x==0:
                            indice_list.append((6, 7, 8, 5))
                        # WEST FACE
                        if x==v_obj.vol_sz[0]:
                            indice_list.append((4, 3, 2, 1))

                    # Only write if there are indices to write
                    if len(indice_list)>0:
                        for vert in vert_list:
                            bvert = (vert[0]+v_obj.base_xyz[0], vert[1]+v_obj.base_xyz[1], vert[2]+v_obj.base_xyz[2])
                            out_fp.write("v {0:f} {1:f} {2:f}\n".format(bvert[0],bvert[1],bvert[2]))
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


    def write_OBJ(self, v_obj, fileName, src_file_str):
        ''' Writes out an OBJ file
            v_obj - vessel object that holds details of GOCAD file
            fileName - filename of OBJ file, without extension
            src_file_str - filename of gocad file

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
        vert_dict = v_obj.make_vertex_dict()
        if v_obj.is_ts:
            if len(v_obj.rgba_tup)==4:
                out_fp.write("mtllib "+fileName+".MTL\n")
        if v_obj.is_ts or v_obj.is_pl or v_obj.is_vs:
            for v in v_obj.get_vrtx_arr():
                bv = (v.xyz[0]+v_obj.base_xyz[0], v.xyz[1]+v_obj.base_xyz[1], v.xyz[2]+v_obj.base_xyz[2])
                out_fp.write("v {0:f} {1:f} {2:f}\n".format(bv[0],bv[1],bv[2]))
        out_fp.write("g main\n")
        if v_obj.is_ts:
            out_fp.write("usemtl colouring\n")
            for f in v_obj.get_trgl_arr():
                out_fp.write("f {0:d} {1:d} {2:d}\n".format(vert_dict[f[0]], vert_dict[f[1]], vert_dict[f[2]]))

        elif v_obj.is_pl:
            for s in v_obj.get_seg_arr():
                out_fp.write("l {0:d} {1:d}\n".format(vert_dict[s[0]], vert_dict[s[1]]))

        elif v_obj.is_vs:
            out_fp.write("p");
            for p in range(len(v_obj.get_vrtx_arr())):
                out_fp.write(" {0:d}".format(p+1))
            out_fp.write("\n")

        elif v_obj.is_vo:
            ct_done=self.write_voxel_obj(out_fp, fileName, src_file_str, 64, False)
        out_fp.close()

        # Create an MTL file for the colour
        if len(v_obj.rgba_tup)==4 and not ct_done:
            out_fp = open(fileName+".MTL", 'w')
            out_fp.write("# Wavefront MTL file converted from  '{0}'\n\n".format(src_file_str))
            out_fp.write("newmtl colouring\n")
            out_fp.write("Ka {0:.3f} {1:.3f} {2:.3f}\n".format(v_obj.rgba_tup[0], v_obj.rgba_tup[1], v_obj.rgba_tup[2]))
            out_fp.write("Kd {0:.3f} {1:.3f} {2:.3f}\n".format(v_obj.rgba_tup[0], v_obj.rgba_tup[1], v_obj.rgba_tup[2]))
            out_fp.write("Ks 0.000 0.000 0.000\n")
            out_fp.write("d 1.0\n")
            out_fp.close()


