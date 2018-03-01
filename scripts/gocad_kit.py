import collada as Collada
import numpy
import PIL
import sys
import os
import array

class GOCAD_KIT:
    ''' Class used to output GOCAD files as Wavefront OBJ or COLLADA files
    '''

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

    MAX_COLOURS = 256.0
    ''' Maximum number of colours displayed in one COLLADA file '''

    LINE_WIDTH = 1000
    ''' Width of lines created for GOCAD PL files '''

    def __init__(self):
        ''' Initialise class
        '''
        # Pycollada objects used to create a single COLLADA file using multiple input files
        self.mesh_obj = None
        self.geomnode_list = []
        self.vobj_cnt = 0

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
        # Output to OBJ file
        print("Writing ",fileName+".OBJ")
        out_fp = open(fileName+".OBJ", 'w')
        out_fp.write("# Wavefront OBJ file converted from '{0}'\n\n".format(src_file_str))
        ct_done = False
        if v_obj.is_ts:
            if len(v_obj.rgba_tup)==4:
                out_fp.write("mtllib "+fileName+".MTL\n")
        if v_obj.is_ts or v_obj.is_pl or v_obj.is_vs:
            for v in v_obj.vrtx_arr:
                bv = (v[0]-v_obj.base_xyz[0], v[1]-v_obj.base_xyz[1], v[2]-v_obj.base_xyz[2])
                out_fp.write("v {0:f} {1:f} {2:f}\n".format(bv[0],bv[1],bv[2]))
        out_fp.write("g main\n")
        if v_obj.is_ts:
            out_fp.write("usemtl colouring\n")
            for f in v_obj.trgl_arr:
                out_fp.write("f {0:d} {1:d} {2:d}\n".format(f[0],f[1],f[2]))

        elif v_obj.is_pl:
            for s in v_obj.seg_arr:
                out_fp.write("l {0:d} {1:d}\n".format(s[0],s[1]))

        elif v_obj.is_vs:
            out_fp.write("p");
            for p in range(len(v_obj.vrtx_arr)):
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


    def write_voxel_png(self, v_obj, src_dir, fileName):
        ''' Writes out a PNG file of the top layer of the voxel data
            v_obj - vessel object that holds details of GOCAD file
            fileName - filename of OBJ file, without extension
            src_filen_str - filename of source gocad file
        '''
        colour_arr = array.array("B")
        z = v_obj.vol_dims[2]-1
        pixel_cnt = 0
        for x in range(0, v_obj.vol_dims[0]):
            for y in range(0, v_obj.vol_dims[1]):
                (r,g,b) = self.colour_map[int(v_obj.voxel_data[x][y][z])]
                colour_arr.append(int(r*255.0))
                colour_arr.append(int(g*255.0))
                colour_arr.append(int(b*255.0))
                pixel_cnt += 1
        img = PIL.Image.frombytes('RGB', (v_obj.vol_dims[1], v_obj.vol_dims[0]), colour_arr.tobytes())
        print(img)
        img.save(os.path.join(src_dir, fileName+".PNG"))
        popup_dict = { os.path.basename(fileName): { 'title': v_obj.header_name, 'name': v_obj.header_name } }
        return popup_dict



    def write_voxel_obj(self, v_obj, out_fp, fileName, src_file_str, step_sz, use_full_cubes):
        ''' Writes out voxel data to Wavefront OBJ and MTL files
            out_fp - open file handle of OBJ file
            v_obj - vessel object that holds details of GOCAD file
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
        for z in range(0,v_obj.vol_dims[2],step_sz):
            for y in range(0,v_obj.vol_dims[1],step_sz):
                for x in range(0,v_obj.vol_dims[0],step_sz):
                    colour_num = int(255.0*(v_obj.voxel_data[x][y][z] - v_obj.voxel_data_stats['min'])/(v_obj.voxel_data_stats['max'] - v_obj.voxel_data_stats['min']))
                    # NB: Assumes AXIS_MIN = 0, and AXIS_MAX = 1
                    u_offset = v_obj.axis_origin[0]+ float(x)/v_obj.vol_dims[0]*v_obj.axis_u[0]
                    v_offset = v_obj.axis_origin[1]+ float(y)/v_obj.vol_dims[1]*v_obj.axis_v[1]
                    w_offset = v_obj.axis_origin[2]+ float(z)/v_obj.vol_dims[2]*v_obj.axis_w[2]
                    v = (u_offset, v_offset, w_offset)
                    pt_size = (step_sz*v_obj.axis_u[0]/v_obj.vol_dims[0]/2, step_sz*v_obj.axis_v[1]/v_obj.vol_dims[1]/2, step_sz*v_obj.axis_w[2]/v_obj.vol_dims[2]/2)
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
                        if z==v_obj.vol_dims[2]-1:
                            indice_list.append((5, 8, 4, 1))
                        # SOUTH FACE
                        if y==0:
                            indice_list.append((2, 6, 5, 1))
                        # NORTH FACE
                        if y==v_obj.vol_dims[1]:
                            indice_list.append((8, 7, 3, 4))
                        # EAST FACE
                        if x==0:
                            indice_list.append((6, 7, 8, 5))
                        # WEST FACE
                        if x==v_obj.vol_dims[0]:
                            indice_list.append((4, 3, 2, 1))

                    # Only write if there are indices to write
                    if len(indice_list)>0:
                        for vert in vert_list:
                            bvert = (vert[0]-v_obj.base_xyz[0], vert[1]-v_obj.base_xyz[1], vert[2]-v_obj.base_xyz[2])
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


    def start_collada(self):
        ''' Initiate creation of a COLLADA file
        '''
        self.mesh_obj = Collada.Collada()
        self.geomnode_list = []

        
    def add_v_to_collada(self, v_obj):
        ''' Adds a vessel object to the pycollada mesh object
            NB: Does not accept GOCAD vertex or volume files as they usually have (too) many node objects
            v_obj - GOCAD vessel object
            Returns a popup info dict or {} if you try to add a GOCAD VS (vertex) or VO (volume) file
        '''
        # Cannot do vertices *.VS or volumes *.VO
        if v_obj.is_vs or v_obj.is_vo:
          return {}
        group_name = ""
        if len(v_obj.group_name)>0:
            group_name = v_obj.group_name+"-"
        if len(v_obj.header_name)>0:
            geometry_name = group_name + v_obj.header_name
        else:
            geometry_name = group_name + "geometry"
        popup_dict = {}

        # Triangles
        if v_obj.is_ts:
            if len(v_obj.rgba_tup)!=4:
                v_obj.rgba_tup = (1,0,0,1.0)
            effect = Collada.material.Effect("effect-{0:05d}".format(self.vobj_cnt), [], self.SHADING, emission=self.EMISSION, ambient=self.AMBIENT, diffuse=v_obj.rgba_tup, specular=self.SPECULAR, shininess=self.SHININESS, double_sided=True)
            mat = Collada.material.Material("material-{0:05d}".format(self.vobj_cnt), "mymaterial-{0:05d}".format(self.vobj_cnt), effect)
            self.mesh_obj.effects.append(effect)
            self.mesh_obj.materials.append(mat)
            matnode = Collada.scene.MaterialNode("materialref-{0:05d}".format(self.vobj_cnt), mat, inputs=[])
            vert_floats = []
            for v in v_obj.vrtx_arr:
                vert_floats += [v[0]-v_obj.base_xyz[0], v[1]-v_obj.base_xyz[1], v[2]-v_obj.base_xyz[2]]
            vert_src = Collada.source.FloatSource("triverts-array-{0:05d}".format(self.vobj_cnt), numpy.array(vert_floats), ('X', 'Y', 'Z'))
            geom = Collada.geometry.Geometry(self.mesh_obj, "geometry-{0:05d}".format(self.vobj_cnt), geometry_name, [vert_src])
            input_list = Collada.source.InputList()
            input_list.addInput(0, 'VERTEX', "#triverts-array-{0:05d}".format(self.vobj_cnt))

            indices = []
            for t in v_obj.trgl_arr:
                indices += [t[0]-1, t[1]-1, t[2]-1]

            triset = geom.createTriangleSet(numpy.array(indices), input_list, "materialref-{0:05d}".format(self.vobj_cnt))


            geom.primitives.append(triset)
            self.mesh_obj.geometries.append(geom)
            self.geomnode_list.append(Collada.scene.GeometryNode(geom, [matnode]))

            popup_dict[geometry_name] = { 'title': v_obj.header_name, 'name': v_obj.header_name }

        # Lines
        elif v_obj.is_pl:
            point_cnt = 0
            yellow_colour = (1,1,0,1)
            effect = Collada.material.Effect("effect-{0:05d}".format(self.vobj_cnt), [], self.SHADING, emission=self.EMISSION, ambient=self.AMBIENT, diffuse=yellow_colour, specular=self.SPECULAR, shininess=self.SHININESS, double_sided=True)
            mat = Collada.material.Material("material-{0:05d}".format(self.vobj_cnt), "mymaterial-{0:05d}".format(self.vobj_cnt), effect)
            self.mesh_obj.effects.append(effect)
            self.mesh_obj.materials.append(mat)
            matnode = Collada.scene.MaterialNode("materialref-{0:05d}".format(self.vobj_cnt), mat, inputs=[])

            # Draw lines as a series of triangles
            for l in v_obj.seg_arr:
                v0 = v_obj.vrtx_arr[l[0]-1]
                v1 = v_obj.vrtx_arr[l[1]-1]
                bv0 = (v0[0]-v_obj.base_xyz[0], v0[1]-v_obj.base_xyz[1], v0[2]-v_obj.base_xyz[2])
                bv1 = (v1[0]-v_obj.base_xyz[0], v1[1]-v_obj.base_xyz[1], v1[2]-v_obj.base_xyz[2])
                vert_floats = list(bv0) + [bv0[0], bv0[1], bv0[2]+self.LINE_WIDTH] + list(bv1) + [bv1[0], bv1[1], bv1[2]+self.LINE_WIDTH]
                vert_src = Collada.source.FloatSource("lineverts-array-{0:010d}-{1:05d}".format(point_cnt, self.vobj_cnt), numpy.array(vert_floats), ('X', 'Y', 'Z'))
                geom_label = "line-{0}-{1:010d}".format(geometry_name, point_cnt)
                geom = Collada.geometry.Geometry(mesh, "geometry{0:010d}-{1:05d}".format(point_cnt, self.vobj_cnt), geom_label, [vert_src])

                input_list = Collada.source.InputList()
                input_list.addInput(0, 'VERTEX', "#lineverts-array-{0:010d}-{1:05d}".format(point_cnt, self.vobj_cnt))

                indices = [0, 2, 3, 3, 1, 0]

                triset = geom.createTriangleSet(numpy.array(indices), input_list, "materialref-{0:05d}".format(self.vobj_cnt))
                geom.primitives.append(triset)
                self.mesh_obj.geometries.append(geom)
                self.geomnode_list.append(Collada.scene.GeometryNode(geom, [matnode]))
                popup_dict[geom_label] = { 'title': v_obj.header_name, 'name': v_obj.header_name }
                point_cnt += 1

        self.vobj_cnt += 1
        return popup_dict



    def end_collada(self, fileName):
        ''' Close out a COLLADA, writing the mesh object to file
            fileName - filename of COLLADA file, without extension
            Returns a dictionary of popup info objects
        '''
        node = Collada.scene.Node("node0", children=self.geomnode_list)
        myscene = Collada.scene.Scene("myscene", [node])
        self.mesh_obj.scenes.append(myscene)
        self.mesh_obj.scene = myscene
        print("Writing COLLADA file")
        self.mesh_obj.write(fileName+'.dae')


    def write_collada(self, v_obj, fileName):
        ''' Write out a COLLADA file
            fileName - filename of COLLADA file, without extension
            v_obj - vessel object that holds details of GOCAD file
        '''
        if v_obj.is_vo or v_obj.is_vs:
            self.write_single_collada(v_obj, fileName)
        else:
            self.start_collada()
            self.add_v_to_collada(v_obj)
            self.end_collada(fileName)


    #
    # COLLADA is better than OBJ, but very bulky
    #
    def write_single_collada(self, v_obj, fileName):
        ''' Write out a COLLADA file
            fileName - filename of COLLADA file, without extension
            v_obj - vessel object that holds details of GOCAD file
        '''
        mesh = Collada.Collada()
        popup_dict = {}
        group_name = ""
        if len(v_obj.group_name)>0:
            group_name = v_obj.group_name+"-"
        if len(v_obj.header_name)>0:
            geometry_name = group_name + v_obj.header_name
        else:
            geometry_name = group_name + "geometry"

        # Triangles
        if v_obj.is_ts:
            if len(v_obj.rgba_tup)!=4:
                v_obj.rgba_tup = (1,0,0,1.0)
            effect = Collada.material.Effect("effect0", [], self.SHADING, emission=self.EMISSION, ambient=self.AMBIENT, diffuse=v_obj.rgba_tup, specular=self.SPECULAR, shininess=self.SHININESS, double_sided=True)
            mat = Collada.material.Material("material0", "mymaterial", effect)
            mesh.effects.append(effect)
            mesh.materials.append(mat)
            vert_floats = []
            for v in v_obj.vrtx_arr:
                vert_floats += [v[0]-v_obj.base_xyz[0], v[1]-v_obj.base_xyz[1], v[2]-v_obj.base_xyz[2]]
            vert_src = Collada.source.FloatSource("triverts-array", numpy.array(vert_floats), ('X', 'Y', 'Z'))
            geom = Collada.geometry.Geometry(mesh, "geometry0", geometry_name, [vert_src])
            input_list = Collada.source.InputList()
            input_list.addInput(0, 'VERTEX', "#triverts-array")

            indices = []
            for t in v_obj.trgl_arr:
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
            popup_dict[geometry_name] = { 'title': v_obj.header_name, 'name': v_obj.header_name }

        # Lines
        elif v_obj.is_pl:
            point_cnt = 0
            node_list = []
            yellow_colour = (1,1,0,1)
            effect = Collada.material.Effect("effect0", [], self.SHADING, emission=self.EMISSION, ambient=self.AMBIENT, diffuse=yellow_colour, specular=self.SPECULAR, shininess=self.SHININESS, double_sided=True)
            mat = Collada.material.Material("material0", "mymaterial0", effect)
            mesh.effects.append(effect)
            mesh.materials.append(mat)
            matnode = Collada.scene.MaterialNode("materialref-0", mat, inputs=[])
            geomnode_list = []

            # Draw lines using triangles
            for l in v_obj.seg_arr:
                v0 = v_obj.vrtx_arr[l[0]-1]
                v1 = v_obj.vrtx_arr[l[1]-1]
                bv0 = (v0[0]-v_obj.base_xyz[0], v0[1]-v_obj.base_xyz[1], v0[2]-v_obj.base_xyz[2])
                bv1 = (v1[0]-v_obj.base_xyz[0], v1[1]-v_obj.base_xyz[1], v1[2]-v_obj.base_xyz[2])
                vert_floats = list(bv0) + [bv0[0], bv0[1], bv0[2]+self.LINE_WIDTH] + list(bv1) + [bv1[0], bv1[1], bv1[2]+self.LINE_WIDTH]
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

                popup_dict[geom_label] = { 'title': v_obj.header_name, 'name': v_obj.header_name }

                point_cnt += 1

            node = Collada.scene.Node("node0", children=geomnode_list)
            node_list.append(node)
            myscene = Collada.scene.Scene("myscene", node_list)
            mesh.scenes.append(myscene)
            mesh.scene = myscene


        # Vertices
        elif v_obj.is_vs:
            # Limit to 256 colours
            self.make_colour_materials(mesh, self.MAX_COLOURS)
            POINT_SIZE = 1000
            point_cnt = 0
            node_list = []
            geomnode_list = []
            vert_floats = []
            matnode_list = []
            triset_list = []
            vert_src_list = []
            prop_str = list(v_obj.prop_dict.keys())[0]

            # Draw vertices as lop-sided tetrahedrons
            for v in v_obj.vrtx_arr:
                colour_num = self.calculate_colour_num(v_obj.prop_dict[prop_str][v], v_obj.prop_meta[prop_str]['max'], v_obj.prop_meta[prop_str]['min'], self.MAX_COLOURS)
                bv = (v[0]-v_obj.base_xyz[0], v[1]-v_obj.base_xyz[1], v[2]-v_obj.base_xyz[2])

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

                popup_dict[geom_label] = { 'name': prop_str, 'val': v_obj.prop_dict[prop_str][v], 'title': geometry_name.replace('_',' ') }
                point_cnt += 1

            node = Collada.scene.Node("node0", children=geomnode_list)
            node_list.append(node)
            myscene = Collada.scene.Scene("myscene", node_list)
            mesh.scenes.append(myscene)
            mesh.scene = myscene

        # Volumes
        elif v_obj.is_vo:
            # Limit to 256 colours, only does tetrahedrons to save space
            self.make_colour_materials(mesh, self.MAX_COLOURS)

            node_list = []
            point_cnt = 0
            done = False
            for z in range(v_obj.vol_dims[2]):
                for y in range(v_obj.vol_dims[1]):
                    for x in range(v_obj.vol_dims[0]):
                        colour_num = self.calculate_colour_num(v_obj.voxel_data[x][y][z], v_obj.voxel_data_stats['max'], v_obj.voxel_data_stats['min'], self.MAX_COLOURS)
                        # NB: Assumes AXIS_MIN = 0, and AXIS_MAX = 1
                        u_offset = v_obj.axis_origin[0]+ float(x)/v_obj.vol_dims[0]*v_obj.axis_u[0]
                        v_offset = v_obj.axis_origin[1]+ float(y)/v_obj.vol_dims[1]*v_obj.axis_v[1]
                        w_offset = v_obj.axis_origin[2]+ float(z)/v_obj.vol_dims[2]*v_obj.axis_w[2]
                        v = (u_offset-v_obj.base_xyz[0], v_offset-v_obj.base_xyz[1], w_offset-v_obj.base_xyz[2])
                        pt_size = (v_obj.axis_u[0]/v_obj.vol_dims[0], v_obj.axis_v[1]/v_obj.vol_dims[1], v_obj.axis_w[2]/v_obj.vol_dims[2])
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
                        popup_dict[geom_label] = { 'title': v_obj.header_name, 'name': v_obj.header_name }
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
        # Floating point arithmetic fails of the numbers are at limits
        if max_flt == abs(sys.float_info.max) or min_flt == abs(sys.float_info.max) or val_flt == abs(sys.float_info.max):
            return 0
        # Ensure denominator is not too large
        if (max_flt - min_flt) > 0.0000001:
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
