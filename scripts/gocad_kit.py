import collada as Collada
import numpy
import PIL
import sys
import os
import struct
import array

class GOCAD_KIT:
    ''' Class used to read gocad files and output them to Wavefront OBJ and COLLADA files
    '''

    GOCAD_HEADERS = {
                 'TS':['GOCAD TSURF 1'],
                 'VS':['GOCAD VSET 1'],
                 'PL':['GOCAD PLINE 1'],
                 'GP':['GOCAD HETEROGENEOUSGROUP 1', 'GOCAD HOMOGENEOUSGROUP 1'],
                 'VO':['GOCAD VOXET 1'],
    }
    ''' Constant assigns possible headers to each flename extension'''

    SUPPORTED_EXTS = [
                   'TS',
                   'VS',
                    'PL',
                    'GP',
                    'VO',
    ]
    ''' List of file extensions to search for '''


    EMISSION = (0,0,0,1)
    ''' emission parameter for pycollada material effect '''

    AMBIENT = (0,0,0,1)
    ''' ambient parameter for pycollada material effect '''

    SPECULAR=(0.7, 0.7, 0.7, 1)
    ''' specular parameter for pycollada material effect '''

    SHININESS=50.0
    ''' shininess parameter for pycollada material effect '''

    SHADING="phong"
    ''' shading parameter for pycollada material effect '''


    def __init__(self, base_xyz=(0.0, 0.0, 0.0), group_name=""):
        ''' Initialise class
            base_xyz - optional (x,y,z) floating point tuple, base_xyz is subtracted from all coordinates
                       before they are output
            group_name - optional string, name of group of this gocad file is within a group
        '''
        self.base_xyz = base_xyz
        self.group_name = group_name

        self.header_name = ""
        ''' Contents of the name field in the header '''

        self.vrtx_arr = []
        '''Array to store vertex data'''

        self.trgl_arr = []
        '''Array to store triangle face data'''

        self.seg_arr = []
        '''Array to store line segment data'''

        self.invert_zaxis = False
        '''Set to true if z-axis inversion is turned on in this GOCAD file'''

        self.rgba_tup = (1.0, 1.0, 1.0, 1.0)
        '''If one colour is specified in the file it is stored here'''

        self.prop_dict = {}
        '''Property dictionary for PVRTX lines'''

        self.is_ts = False
        '''True iff it is a GOCAD TSURF file'''

        self.is_vs = False
        '''True iff it is a GOCAD VSET file'''

        self.is_pl = False
        '''True iff it is a GOCAD PLINE file'''

        self.is_vo = False
        '''True iff it is a GOCAD VOXEL file'''

        self.prop_meta = {}
        '''Property metadata '''

        self.voxel_file = ""
        '''Name of binary file associated with VOXEL file'''

        self.axis_origin = None
        '''Origin of XYZ axis'''

        self.axis_u = None
        '''Length of u-axis'''

        self.axis_v = None
        '''Length of v-axis'''

        self.axis_w = None
        '''Length of w-axis'''

        self.vol_dims = None
        '''3 dimensional size of voxel volume'''

        self.axis_min = None
        '''3 dimensional minimum point of voxel volume '''

        self.axis_max = None
        '''3 dimensional maximum point of voxel volume '''

        self.voxel_data = numpy.zeros((1,1,1))
        '''Voxel data collected from binary file, stored as a 3d numpy array'''

        self.voxel_data_stats = { 'min': sys.float_info.max , 'max': -sys.float_info.max }
        '''Voxel data statistics: min & max'''

        self.colour_map = {}
        '''If colour map was specified, then it is stored here'''

        self.colourmap_name = ""
        '''Name of colour map'''

        self.np_filename = ""
        ''' Filename of GOCAD file without path or extension '''

        self.max_X =  -sys.float_info.max
        ''' Maximum X coordinate, used to calculate extent '''

        self.min_X =  sys.float_info.max
        ''' Minimum X coordinate, used to calculate extent '''

        self.max_Y =  -sys.float_info.max
        ''' Maximum Y coordinate, used to calculate extent '''

        self.min_Y =  sys.float_info.max
        ''' Minimum Y coordinate, used to calculate extent '''

        self.max_Z =  -sys.float_info.max
        ''' Maximum Z coordinate, used to calculate extent '''

        self.min_Z =  sys.float_info.max
        ''' Minimum Z coordinate, used to calculate extent '''



    def __repr__(self):
        ''' A very basic print friendly representation
        '''
        return "is_ts {0} is_vs {1} is_pl {2} is_vo {3} len(vrtx_arr)={4}\n".format(self.is_ts, self.is_vs, self.is_pl, self.is_vo, len(self.vrtx_arr))


    def get_extent(self):
        ''' Returns estimate of the extent of the model, using max and min coordinate values
            format is [min_x, max_x, min_y, max_y]
        '''
        return [self.min_X, self.max_X, self.min_Y, self.max_Y]


    def setType(self, fileExt, firstLineStr):
        ''' Sets the type of GOCAD file: TSURF, VOXEL, PLINE etc.
            fileExt - the file extension
            firstLineStr - first line in the file
            Returns True if it could determine the type of file
        '''
        print("setType(", fileExt, firstLineStr, ")")
        ext_str = fileExt.lstrip('.').upper()
        if ext_str=='GP':
            found = False
            for key in self.GOCAD_HEADERS:
                if key!='GP' and firstLineStr in self.GOCAD_HEADERS[key]:
                    ext_str = key
                    found = True
                    break
            if not found:
                return False

        if ext_str in self.GOCAD_HEADERS:
            if ext_str=='TS' and firstLineStr in self.GOCAD_HEADERS['TS']:
                self.is_ts = True
                return True
            elif ext_str=='VS' and firstLineStr in self.GOCAD_HEADERS['VS']:
                self.is_vs = True
                return True
            elif ext_str=='PL' and firstLineStr in self.GOCAD_HEADERS['PL']:
                self.is_pl = True
                return True
            elif ext_str=='VO' and firstLineStr in self.GOCAD_HEADERS['VO']:
                self.is_vo = True
                return True

        return False


    def write_OBJ(self, fileName, src_file_str):
        ''' Writes out an OBJ file
            fileName - filename of OBJ file, without extension
            src_file_str - filename of gocad file

            NOTES:
            OBJ is very simple, and has shortcomings:
            1. Does not include annotations (only comments and a group name)
            2. Lines and points do not have a colour

            I am only using it here because GOCAD VOXEL files are too big for COLLADA format
        '''
        # Output to OBJ file
        print("Writing ",fileName+".OBJ")
        out_fp = open(fileName+".OBJ", 'w')
        out_fp.write("# Wavefront OBJ file converted from '{0}'\n\n".format(src_file_str))
        ct_done = False
        if self.is_ts:
            if len(self.rgba_tup)==4:
                out_fp.write("mtllib "+fileName+".MTL\n")
        if self.is_ts or self.is_pl or self.is_vs:
            for v in self.vrtx_arr:
                bv = (v[0]-self.base_xyz[0], v[1]-self.base_xyz[1], v[2]-self.base_xyz[2])
                out_fp.write("v {0:f} {1:f} {2:f}\n".format(bv[0],bv[1],bv[2]))
        out_fp.write("g main\n")
        if self.is_ts:
            out_fp.write("usemtl colouring\n")
            for f in self.trgl_arr:
                out_fp.write("f {0:d} {1:d} {2:d}\n".format(f[0],f[1],f[2]))

        elif self.is_pl:
            for s in self.seg_arr:
                out_fp.write("l {0:d} {1:d}\n".format(s[0],s[1]))

        elif self.is_vs:
            out_fp.write("p");
            for p in range(len(self.vrtx_arr)):
                out_fp.write(" {0:d}".format(p+1))
            out_fp.write("\n")

        elif self.is_vo:
            ct_done=self.write_voxel_obj(out_fp, fileName, src_file_str, 64, False)
        out_fp.close()

        # Create an MTL file for the colour
        if len(self.rgba_tup)==4 and not ct_done:
            out_fp = open(fileName+".MTL", 'w')
            out_fp.write("# Wavefront MTL file converted from  '{0}'\n\n".format(src_file_str))
            out_fp.write("newmtl colouring\n")
            out_fp.write("Ka {0:.3f} {1:.3f} {2:.3f}\n".format(self.rgba_tup[0], self.rgba_tup[1], self.rgba_tup[2]))
            out_fp.write("Kd {0:.3f} {1:.3f} {2:.3f}\n".format(self.rgba_tup[0], self.rgba_tup[1], self.rgba_tup[2]))
            out_fp.write("Ks 0.000 0.000 0.000\n")
            out_fp.write("d 1.0\n")
            out_fp.close()


    def write_voxel_png(self, src_dir, fileName):
        ''' Writes out a PNG file of the top layer of the voxel data
            fileName - filename of OBJ file, without extension
            src_filen_str - filename of source gocad file
        '''
        colour_arr = array.array("B")
        z = self.vol_dims[2]-1
        pixel_cnt = 0
        for x in range(0, self.vol_dims[0]):
            for y in range(0, self.vol_dims[1]):
                (r,g,b) = self.colour_map[int(self.voxel_data[x][y][z])]
                colour_arr.append(int(r*255.0))
                colour_arr.append(int(g*255.0))
                colour_arr.append(int(b*255.0))
                pixel_cnt += 1
        img = PIL.Image.frombytes('RGB', (self.vol_dims[1], self.vol_dims[0]), colour_arr.tobytes())
        print(img)
        img.save(os.path.join(src_dir, fileName+".PNG"))
        popup_dict = { os.path.basename(fileName): { 'title': self.header_name, 'name': self.header_name } }
        return popup_dict



    def write_voxel_obj(self, out_fp, fileName, src_file_str, step_sz, use_full_cubes):
        ''' Writes out voxel data to Wavefront OBJ and MTL files
            out_fp - open file handle of OBJ file
            fileName - filename of OBJ file without the 'OBJ' extension
            src_file_str - filename of gocad file
            step_sz  - when stepping through the voxel block this is the step size
            use_full_cubes - will write out full cubes to file if true, else will remove non-visible faces
        '''
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
        for z in range(0,self.vol_dims[2],step_sz):
            for y in range(0,self.vol_dims[1],step_sz):
                for x in range(0,self.vol_dims[0],step_sz):
                    colour_num = int(255.0*(self.voxel_data[x][y][z] - self.voxel_data_stats['min'])/(self.voxel_data_stats['max'] - self.voxel_data_stats['min']))
                    # NB: Assumes AXIS_MIN = 0, and AXIS_MAX = 1
                    u_offset = self.axis_origin[0]+ float(x)/self.vol_dims[0]*self.axis_u[0]
                    v_offset = self.axis_origin[1]+ float(y)/self.vol_dims[1]*self.axis_v[1]
                    w_offset = self.axis_origin[2]+ float(z)/self.vol_dims[2]*self.axis_w[2]
                    v = (u_offset, v_offset, w_offset)
                    pt_size = (step_sz*self.axis_u[0]/self.vol_dims[0]/2, step_sz*self.axis_v[1]/self.vol_dims[1]/2, step_sz*self.axis_w[2]/self.vol_dims[2]/2)
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
                        if z==self.vol_dims[2]-1:
                            indice_list.append((5, 8, 4, 1))
                        # SOUTH FACE
                        if y==0:
                            indice_list.append((2, 6, 5, 1))
                        # NORTH FACE
                        if y==self.vol_dims[1]:
                            indice_list.append((8, 7, 3, 4))
                        # EAST FACE
                        if x==0:
                            indice_list.append((6, 7, 8, 5))
                        # WEST FACE
                        if x==self.vol_dims[0]:
                            indice_list.append((4, 3, 2, 1))

                    # Only write if there are indices to write
                    if len(indice_list)>0:
                        for vert in vert_list:
                            bvert = (vert[0]-self.base_xyz[0], vert[1]-self.base_xyz[1], vert[2]-self.base_xyz[2])
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


    #
    # COLLADA is better than OBJ, but very bulky
    #
    def write_collada(self, fileName):
        ''' Write out a COLLADA file
            fileName - filename of COLLADA file, without extension
        '''
        mesh = Collada.Collada()
        popup_dict = {}
        group_name = ""
        if len(self.group_name)>0:
            group_name = self.group_name+"-"
        if len(self.header_name)>0:
            geometry_name = group_name + self.header_name
        else:
            geometry_name = group_name + "geometry"

        # Triangles
        if self.is_ts:
            if len(self.rgba_tup)!=4:
                self.rgba_tup = (1,0,0,1.0)
            effect = Collada.material.Effect("effect0", [], self.SHADING, emission=self.EMISSION, ambient=self.AMBIENT, diffuse=self.rgba_tup, specular=self.SPECULAR, shininess=self.SHININESS, double_sided=True)
            mat = Collada.material.Material("material0", "mymaterial", effect)
            mesh.effects.append(effect)
            mesh.materials.append(mat)
            vert_floats = []
            for v in self.vrtx_arr:
                vert_floats += [v[0]-self.base_xyz[0], v[1]-self.base_xyz[1], v[2]-self.base_xyz[2]]
            vert_src = Collada.source.FloatSource("triverts-array", numpy.array(vert_floats), ('X', 'Y', 'Z'))
            geom = Collada.geometry.Geometry(mesh, "geometry0", geometry_name, [vert_src])
            input_list = Collada.source.InputList()
            input_list.addInput(0, 'VERTEX', "#triverts-array")

            indices = []
            for t in self.trgl_arr:
                indices += [t[0]-1, t[1]-1, t[2]-1]

            triset = geom.createTriangleSet(numpy.array(indices), input_list, "materialref")
            geom.primitives.append(triset)
            mesh.geometries.append(geom)

            matnode = Collada.scene.MaterialNode("materialref", mat, inputs=[])
            geomnode = Collada.scene.GeometryNode(geom, [matnode])
            node = Collada.scene.Node("node0", children=[geomnode])

            myscene = Collada.scene.Scene("myscene", [node])
            mesh.scenes.append(myscene)
            mesh.scene = myscene
            popup_dict[geometry_name] = { 'title': self.header_name, 'name': self.header_name }

        # Lines
        elif self.is_pl:
            LINE_WIDTH = 1000
            point_cnt = 0
            node_list = []
            yellow_colour = (1,1,0,1)
            effect = Collada.material.Effect("effect0", [], self.SHADING, emission=self.EMISSION, ambient=self.AMBIENT, diffuse=yellow_colour, specular=self.SPECULAR, shininess=self.SHININESS, double_sided=True)
            mat = Collada.material.Material("material0", "mymaterial0", effect)
            mesh.effects.append(effect)
            mesh.materials.append(mat)
            matnode = Collada.scene.MaterialNode("materialref-0", mat, inputs=[])
            geomnode_list = []

            for l in self.seg_arr:
                v0 = self.vrtx_arr[l[0]-1]
                v1 = self.vrtx_arr[l[1]-1]
                bv0 = (v0[0]-self.base_xyz[0], v0[1]-self.base_xyz[1], v0[2]-self.base_xyz[2])
                bv1 = (v1[0]-self.base_xyz[0], v1[1]-self.base_xyz[1], v1[2]-self.base_xyz[2])
                vert_floats = list(bv0) + [bv0[0], bv0[1], bv0[2]+LINE_WIDTH] + list(bv1) + [bv1[0], bv1[1], bv1[2]+LINE_WIDTH]
                vert_src = Collada.source.FloatSource("lineverts-array-{0:010d}".format(point_cnt), numpy.array(vert_floats), ('X', 'Y', 'Z'))
                geom_label = "{0}-{1:010d}".format(geometry_name, point_cnt)
                geom = Collada.geometry.Geometry(mesh, "geometry{0:010d}".format(point_cnt), geom_label, [vert_src])

                input_list = Collada.source.InputList()
                input_list.addInput(0, 'VERTEX', "#lineverts-array-{0:010d}".format(point_cnt))

                indices = [0, 2, 3, 3, 1, 0]

                triset = geom.createTriangleSet(numpy.array(indices), input_list, "materialref-0")

                geom.primitives.append(triset)
                mesh.geometries.append(geom)
                geomnode_list.append(Collada.scene.GeometryNode(geom, [matnode]))

                popup_dict[geom_label] = { 'title': self.header_name, 'name': self.header_name }

                point_cnt += 1

            node = Collada.scene.Node("node0", children=geomnode_list)
            node_list.append(node)
            myscene = Collada.scene.Scene("myscene", node_list)
            mesh.scenes.append(myscene)
            mesh.scene = myscene


        # Vertices
        elif self.is_vs:
            # Limit to 256 colours
            MAX_COLOURS = 256.0
            self.make_colour_materials(mesh, MAX_COLOURS)
            POINT_SIZE = 1000
            point_cnt = 0
            node_list = []
            geomnode_list = []
            vert_floats = []
            matnode_list = []
            triset_list = []
            vert_src_list = []
            prop_str = list(self.prop_dict.keys())[0]
            for v in self.vrtx_arr:
                colour_num = self.calculate_colour_num(self.prop_dict[prop_str][v], self.prop_meta[prop_str]['max'], self.prop_meta[prop_str]['min'], MAX_COLOURS)
                bv = (v[0]-self.base_xyz[0], v[1]-self.base_xyz[1], v[2]-self.base_xyz[2])

                vert_floats = list(bv) + [bv[0]+POINT_SIZE, bv[1], bv[2]] + [bv[0], bv[1]+POINT_SIZE, bv[2]] + [bv[0], bv[1], bv[2]+POINT_SIZE]
                input_list = Collada.source.InputList()
                input_list.addInput(0, 'VERTEX', "#pointverts-array-{0:010d}".format(point_cnt))
                indices = [0, 2, 1, 3, 0, 1, 3, 2, 0, 3, 1, 2]
                vert_src_list = [Collada.source.FloatSource("pointverts-array-{0:010d}".format(point_cnt), numpy.array(vert_floats), ('X', 'Y', 'Z'))]
                geom_label = "{0}-{1:010d}".format(geometry_name, point_cnt)
                geom = Collada.geometry.Geometry(mesh, "geometry{0:010d}".format(point_cnt), geom_label, vert_src_list)
                triset_list = [geom.createTriangleSet(numpy.array(indices), input_list, "materialref-{0:010d}".format(colour_num))]
                geom.primitives = triset_list
                mesh.geometries.append(geom)
                matnode_list = [Collada.scene.MaterialNode("materialref-{0:010d}".format(colour_num), mesh.materials[colour_num], inputs=[])]
                geomnode_list += [Collada.scene.GeometryNode(geom, matnode_list)]

                popup_dict[geom_label] = { 'name': prop_str, 'val': self.prop_dict[prop_str][v], 'title': geometry_name.replace('_',' ') }
                point_cnt += 1

            node = Collada.scene.Node("node0", children=geomnode_list)
            node_list.append(node)
            myscene = Collada.scene.Scene("myscene", node_list)
            mesh.scenes.append(myscene)
            mesh.scene = myscene

        # Volumes
        elif self.is_vo:
            # Limit to 256 colours, only does tetrahedrons to save space
            MAX_COLOURS = 256.0
            self.make_colour_materials(mesh, MAX_COLOURS)

            node_list = []
            point_cnt = 0
            done = False
            for z in range(self.vol_dims[2]):
                for y in range(self.vol_dims[1]):
                    for x in range(self.vol_dims[0]):
                        colour_num = self.calculate_colour_num(self.voxel_data[x][y][z], self.voxel_data_stats['max'], self.voxel_data_stats['min'], MAX_COLOURS)
                        # NB: Assumes AXIS_MIN = 0, and AXIS_MAX = 1
                        u_offset = self.axis_origin[0]+ float(x)/self.vol_dims[0]*self.axis_u[0]
                        v_offset = self.axis_origin[1]+ float(y)/self.vol_dims[1]*self.axis_v[1]
                        w_offset = self.axis_origin[2]+ float(z)/self.vol_dims[2]*self.axis_w[2]
                        v = (u_offset-self.base_xyz[0], v_offset-self.base_xyz[1], w_offset-self.base_xyz[2])
                        pt_size = (self.axis_u[0]/self.vol_dims[0], self.axis_v[1]/self.vol_dims[1], self.axis_w[2]/self.vol_dims[2])
                        geomnode_list = []
                        vert_floats = list(v) + [v[0]+pt_size[0], v[1], v[2]] + [v[0], v[1]+pt_size[1], v[2]] + [v[0], v[1], v[2]+pt_size[2]]
                        vert_src = Collada.source.FloatSource("cubeverts-array-{0:010d}".format(point_cnt), numpy.array(vert_floats), ('X', 'Y', 'Z'))
                        geom_label = "{0}-{1:010d}".format(geometry_name, point_cnt)
                        geom = Collada.geometry.Geometry(mesh, "geometry{0:010d}".format(point_cnt), geom_label, [vert_src])
                        input_list = Collada.source.InputList()
                        input_list.addInput(0, 'VERTEX', "#cubeverts-array-{0:010d}".format(point_cnt))

                        indices = [0, 2, 1,
                                   3, 0, 1,
                                   3, 2, 0,
                                   3, 1, 2]

                        triset = geom.createTriangleSet(numpy.array(indices), input_list, "materialref-{0:010d}".format(colour_num))
                        geom.primitives.append(triset)
                        mesh.geometries.append(geom)
                        matnode = Collada.scene.MaterialNode("materialref-{0:010d}".format(colour_num), mesh.materials[colour_num], inputs=[])
                        geomnode_list.append(Collada.scene.GeometryNode(geom, [matnode]))

                        node = Collada.scene.Node("node{0:010d}".format(point_cnt), children=geomnode_list)
                        node_list.append(node)
                        popup_dict[geom_label] = { 'title': self.header_name, 'name': self.header_name }
                        point_cnt += 1

                        if (point_cnt>999000000):
                            print("Stop - too much!")
                            done = True
                            break
                    if done:
                        break
                if done:
                    break

            print("Creating scene")
            myscene = Collada.scene.Scene("myscene", node_list)
            mesh.scenes.append(myscene)
            mesh.scene = myscene

        print("Writing COLLADA file")
        mesh.write(fileName+'.dae')

        return popup_dict


    def calculate_colour_num(self, val_flt, max_flt, min_flt, max_colours_flt):
        ''' Calculates a colour number via interpolation
            val_flt - value used to calculate colour number
            min_flt - lower bound of value
            max_flt - upper bound of value
            max_colours_flt - maximum number of colours
            returns integer colour number
        '''
        if (max_flt - min_flt)>0.1:
            return int((max_colours_flt-1)*(val_flt - min_flt)/(max_flt - min_flt))
        return 0


    def make_colour_materials(self, mesh, max_colours_flt):
        ''' Adds a list of coloured materials to COLLADA object
            mesh - Collada object
            max_colours_flt - number of colours to add
        '''
        for colour_idx in range(int(max_colours_flt)):
            diffuse_colour = self.make_colour_map(float(colour_idx), 0.0, max_colours_flt - 1.0)
            effect = Collada.material.Effect("effect{0:010d}".format(colour_idx), [], self.SHADING, emission=self.EMISSION, ambient=self.AMBIENT, diffuse=diffuse_colour, specular=self.SPECULAR, shininess=self.SHININESS)
            mat = Collada.material.Material("material{0:010d}".format(colour_idx), "mymaterial{0:010d}".format(colour_idx), effect)
            mesh.effects.append(effect)
            mesh.materials.append(mat)


    def process_gocad(self, src_dir, filename_str, file_lines):
        ''' Extracts details from gocad file
            filename_str - filename of gocad file
            file_lines - array of strings of lines from gocad file
        '''
        print("process_gocad(", filename_str, len(file_lines), ")")

        firstLine = True
        inHeader = False
        inPropClassHeader = False
        v_idx = 0
        properties_list = []
        fileName, fileExt = os.path.splitext(filename_str)
        self.np_filename = os.path.basename(fileName)
        for line in file_lines:
            line_str = line.rstrip(' \n\r').upper()
            splitstr_arr_raw = line.rstrip(' \n\r').split(' ')
            splitstr_arr = line_str.split(' ')

            # Check that we have a GOCAD file
            if firstLine:
                firstLine = False
                if not self.setType(fileExt, line_str):
                    print("SORRY - not a GOCAD file", line_str)
                    sys.exit(1)

            splitstr_arr = line_str.split(' ')

            # Skip the subsets keywords
            if splitstr_arr[0] in ["SUBVSET", "ILINE", "TFACE", "TVOLUME"]:
                continue

            # Get the colour
            elif splitstr_arr[0] == "HEADER":
                inHeader = True

            if splitstr_arr[0] == "PROPERTY_CLASS_HEADER":
                self.prop_class_name = splitstr_arr[2]
                inPropClassHeader = True

            elif inHeader and splitstr_arr[0] == "}":
                inHeader = False

            elif inPropClassHeader and splitstr_arr[0] == "}":
                inPropClassHeader = False

            if inHeader:
                name_str, sep, value_str = line_str.partition(':')
                if name_str=='*SOLID*COLOR':
                    rgbsplit_arr = value_str.split(' ')
                    try:
                        self.rgba_tup = (float(rgbsplit_arr[0]), float(rgbsplit_arr[1]), float(rgbsplit_arr[2]), float(rgbsplit_arr[3]))
                    except (ValueError, OverflowError):
                        self.rgba_tup = (1.0, 1.0, 1.0, 1.0)
                if name_str=='NAME':
                    self.header_name = value_str.replace('/','-')
            if inPropClassHeader:
                name_str, sep, value_str = line_str.partition(':')
                if name_str=='*COLORMAP*SIZE':
                    print("colourmap-size", value_str)
                elif name_str=='*COLORMAP*NBCOLORS':
                    print("numcolours", value_str)
                elif name_str=='HIGH_CLIP':
                    print("highclip", value_str)
                elif name_str=='LOW_CLIP':
                    print("lowclip", value_str)
                elif name_str=='COLORMAP':
                    print("colourmap id", value_str)
                    self.colourmap_name = value_str
                elif hasattr(self, 'colourmap_name') and name_str=='*COLORMAP*'+self.colourmap_name+'*COLORS':
                    lut_arr = value_str.split(' ')
                    for idx in range(0, len(lut_arr), 4):
                        try:
                            self.colour_map[int(lut_arr[idx])] = (float(lut_arr[idx+1]), float(lut_arr[idx+2]), float(lut_arr[idx+3]))
                        except (OverflowError, ValueError):
                            pass

            # If depth is positive, them must invert the z-axis
            if splitstr_arr[0].upper() == "ZPOSITIVE" and splitstr_arr[1].upper() == "DEPTH":
                self.invert_zaxis=True

            # Property names
            elif splitstr_arr[0].upper() == "PROPERTIES":
                properties_list = splitstr_arr[1:]

            # Atoms
            elif splitstr_arr[0] == "ATOM":
                v_idx += 1
                try:
                    if (int(splitstr_arr[1]))!=v_idx:
                        print("ERROR - atom ", splitstr_arr[0], " out of sequence in ", filename_str, "@", splitstr_arr[1], "!=", str(v_idx))
                        print("       line = ", line_str)
                        sys.exit(1)
                    v_num = int(splitstr_arr[2])
                    if v_num < len(self.vrtx_arr):
                        self.vrtx_arr.append(self.vrtx_arr[v_num])
                    else:
                        print("ERROR - ATOM refers to VERTEX that has not been defined yet")
                        sys.exit(1)
                except (OverflowError, ValueError, IndexError):
                    v_idx -= 1
                  
            # Grab the vertices and properties
            # NB: Assumes vertices are numbered sequentially, will stop if they are not
            elif splitstr_arr[0] == "PVRTX" or  splitstr_arr[0] == "VRTX":
                is_ok, x_flt, y_flt, z_flt = self.parse_XYZ(True, splitstr_arr[2], splitstr_arr[3], splitstr_arr[4])
                if is_ok:
                    if self.invert_zaxis:
                        z_flt = -z_flt
                    self.vrtx_arr.append((x_flt, y_flt, z_flt))
                    v_idx += 1
                    if (int(splitstr_arr[1]))!=v_idx:
                        print("ERROR - vertex ", splitstr_arr[0], " out of sequence in ", filename_str, "@", splitstr_arr[1], "!=", str(v_idx))
                        print("       line = ", line_str)
                        sys.exit(1)
                    if splitstr_arr[0] == "PVRTX":
                        for p_idx in range(len(splitstr_arr[5:])):
                            try:
                                property_name = properties_list[p_idx]
                                self.prop_dict.setdefault(property_name, {})
                                fp_str = splitstr_arr[p_idx+5]
                                # Handle GOCAD's C++ floating point infinity for Windows and Linux
                                if fp_str in ["1.#INF","inf"]:
                                    self.prop_dict[property_name][(x_flt, y_flt, z_flt)] = sys.float_info.max
                                elif fp_str in ["-1.#INF","-inf"]:
                                    self.prop_dict[property_name][(x_flt, y_flt, z_flt)] = -sys.float_info.max
                                else:
                                    self.prop_dict[property_name][(x_flt, y_flt, z_flt)] = float(splitstr_arr[p_idx+5])
                            except (OverflowError, ValueError, IndexError):
                                if self.prop_dict[property_name] == {}:
                                    del self.prop_dict[property_name]

            # Grab the triangular edges
            elif splitstr_arr[0] == "TRGL":
                is_ok, a_int, b_int, c_int = self.parse_XYZ(False, splitstr_arr[1], splitstr_arr[2], splitstr_arr[3])
                if is_ok:
                    self.trgl_arr.append((a_int, b_int, c_int))

            # Grab the segments
            elif splitstr_arr[0] == "SEG":
                try:
                    a_int = int(splitstr_arr[1])
                    b_int = int(splitstr_arr[2])
                except ValueError:
                    pass
                else:
                    self.seg_arr.append((a_int, b_int))

            # Voxel file attributes
            elif splitstr_arr[0] == "PROP_FILE":
                self.voxel_file = os.path.join(src_dir, splitstr_arr_raw[2])

            elif splitstr_arr[0] == "AXIS_O":
                is_ok, x_flt, y_flt, z_flt = self.parse_XYZ(True, splitstr_arr[1], splitstr_arr[2], splitstr_arr[3])
                if is_ok:
                    self.axis_origin = (x_flt, y_flt, z_flt)

            elif splitstr_arr[0] == "AXIS_U":
                is_ok, x_flt, y_flt, z_flt = self.parse_XYZ(True, splitstr_arr[1], splitstr_arr[2], splitstr_arr[3])
                if is_ok:
                    self.axis_u = (x_flt, y_flt, z_flt)

            elif splitstr_arr[0] == "AXIS_V":
                is_ok, x_flt, y_flt, z_flt = self.parse_XYZ(True, splitstr_arr[1], splitstr_arr[2], splitstr_arr[3])
                if is_ok:
                    self.axis_v = (x_flt, y_flt, z_flt)

            elif splitstr_arr[0] == "AXIS_W":
                is_ok, x_flt, y_flt, z_flt = self.parse_XYZ(True, splitstr_arr[1], splitstr_arr[2], splitstr_arr[3])
                if is_ok:
                    self.axis_w = (x_flt, y_flt, z_flt)

            elif splitstr_arr[0] == "AXIS_N":
                is_ok, x_int, y_int, z_int = self.parse_XYZ(False, splitstr_arr[1], splitstr_arr[2], splitstr_arr[3])
                if is_ok:
                    self.vol_dims = (x_int, y_int, z_int)

            elif splitstr_arr[0] == "AXIS_MIN":
                is_ok, x_int, y_int, z_int = self.parse_XYZ(False, splitstr_arr[1], splitstr_arr[2], splitstr_arr[3])
                if is_ok:
                    self.axis_min = (x_int, y_int, z_int)

            elif splitstr_arr[0] == "AXIS_MAX":
                is_ok, x_int, y_int, z_int = self.parse_XYZ(False, splitstr_arr[1], splitstr_arr[2], splitstr_arr[3])
                if is_ok:
                    self.axis_max = (x_int, y_int, z_int)

        # Calculate max and min of properties rather than read them from file
        for prop_str in self.prop_dict:
            self.prop_meta.setdefault(prop_str,{})
            self.prop_meta[prop_str]['max'] = max(list(self.prop_dict[prop_str].values()))
            self.prop_meta[prop_str]['min'] = min(list(self.prop_dict[prop_str].values()))


        # Open up and read voxel file
        if self.is_vo and len(self.voxel_file)>0:
            print("VOXEL FILE=", self.voxel_file)
            try:
                # Check file size first
                file_sz = os.path.getsize(self.voxel_file)
                num_voxels = 4*self.vol_dims[0]*self.vol_dims[1]*self.vol_dims[2]
                if file_sz != num_voxels:
                    print("SORRY - Cannot process voxel file - length is not correct", filename_str)
                    sys.exit(1)
                self.voxel_data = numpy.zeros((self.vol_dims[0], self.vol_dims[1], self.vol_dims[2]))
                fp = open(self.voxel_file, 'rb')
                for z in range(self.vol_dims[2]):
                    for y in range(self.vol_dims[1]):
                        for x in range(self.vol_dims[0]):
                            binData = fp.read(4)
                            val = struct.unpack(">f", binData)[0] # It's big endian!
                            if (val > self.voxel_data_stats['max']):
                                self.voxel_data_stats['max'] = val
                            if (val < self.voxel_data_stats['min']):
                                self.voxel_data_stats['min'] = val
                            self.voxel_data[x][y][z] = val
                fp.close()
                print("min=", self.voxel_data_stats['min'], "max=", self.voxel_data_stats['max'])
            except IOError as e:
                print("SORRY - Cannot process voxel file IOError", filename_str, str(e), e.args)
                sys.exit(1)


    def parse_XYZ(self, is_float, x_str, y_str, z_str):
        ''' Helpful function to read XYZ cooordinates
            x_str, y_str, z_str - X,Y,Z coordinates in string form
            Returns four parameters: success  - true if could convert the strings to floats
                                   x,y,z - floating point values
        '''
        x = y = z = None
        if is_float:
            try:
                x = float(x_str)
                y = float(y_str)
                z = float(z_str)
            except (OverflowError, ValueError):
                return False, None, None, None
        else:
            try:
                x = int(x_str)
                y = int(y_str)
                z = int(z_str)
            except (OverflowError, ValueError):
                return False, None, None, None
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
        return True, x, y, z


    def interpolate(self, x_flt, xmin_flt, xmax_flt, ymin_flt, ymax_flt):
        ''' Interpolates a floating point number
            x_flt - floating point number to be interpolated
            xmin_flt - minimum value within x_flt's range
            xmax_flt - maximum value within x_flt's range
            ymin_flt - minimum possible value to output
            ymax_flt - maximum possible value to output
            Returns interpolated value
        '''
        return (x_flt - xmin_flt) / (xmax_flt - xmin_flt) * (ymax_flt - ymin_flt) + ymin_flt


    def make_colour_map(self, i_flt, imin_flt, imax_flt):
        ''' This creates a false colour map, returns an RGBA tuple. A is set to the "SAT" global var.
            Maps a floating point value that varies between a min and max value to an RGBA tuple
            i_flt - floating point value to be mapped
            imax_flt - maximum range of the floating point value
            imin_flt - minimum range of the floating point value
            Returns an RGBA tuple
        '''
        SAT = 0.8
        hue_flt = (i_flt - imin_flt)/ (imax_flt - imin_flt)
        vmin_flt = SAT * (1 - SAT)
        pix = [0.0,0.0,0.0,1.0]

        if hue_flt < 0.25:
            pix[0] = SAT
            pix[1] = self.interpolate(hue_flt, 0.0, 0.25, vmin_flt, SAT)
            pix[2] = vmin_flt

        elif hue_flt < 0.5:
            pix[0] = self.interpolate(hue_flt, 0.25, 0.5, SAT, vmin_flt)
            pix[1] = SAT
            pix[2] = vmin_flt

        elif hue_flt < 0.75:
            pix[0] = vmin_flt
            pix[1] = SAT
            pix[2] = self.interpolate(hue_flt, 0.5, 0.75, vmin_flt, SAT)

        else:
            pix[0] = vmin_flt
            pix[1] = self.interpolate(hue_flt, 0.75, 1.0, SAT, vmin_flt)
            pix[2] = SAT
        return tuple(pix)


#  END OF GOCAD_KIT CLASS
