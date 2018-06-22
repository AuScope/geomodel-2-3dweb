import collada as Collada
import numpy
import PIL
import sys
import os
import array
import logging

class GOCAD_KIT:
    ''' Class used to output GOCAD files as Wavefront OBJ or COLLADA files
    '''

    EMISSION = (0,0,0,1)
    ''' Emission parameter for pycollada material effect '''

    AMBIENT = (0,0,0,1)
    ''' Ambient parameter for pycollada material effect '''

    SPECULAR=(0.7, 0.7, 0.7, 1)
    ''' Specular parameter for pycollada material effect '''

    SHININESS=50.0
    ''' Shininess parameter for pycollada material effect '''

    SHADING="phong"
    ''' Shading parameter for pycollada material effect '''

    MAX_COLOURS = 256.0
    ''' Maximum number of colours displayed in one COLLADA file '''

    LINE_WIDTH = 1000
    ''' Width of lines created for GOCAD PL files '''

    def __init__(self, debug_level):
        ''' Initialise class
        '''
        # Set up logging, use an attribute of class name so it is only called once
        if not hasattr(GOCAD_KIT, 'logger'):
            GOCAD_KIT.logger = logging.getLogger(__name__)

            # Create console handler
            handler = logging.StreamHandler(sys.stdout)

            # Create formatter
            formatter = logging.Formatter('%(asctime)s -- %(name)s -- %(levelname)s - %(message)s')

            # Add formatter to ch
            handler.setFormatter(formatter)

            # Add handler to logger and set level
            GOCAD_KIT.logger.addHandler(handler)
            GOCAD_KIT.logger.setLevel(debug_level)

        self.logger = GOCAD_KIT.logger

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
                bv = (v.xyz[0]-v_obj.base_xyz[0], v.xyz[1]-v_obj.base_xyz[1], v.xyz[2]-v_obj.base_xyz[2])
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


    def write_voxel_png(self, v_obj, src_dir, fileName):
        ''' Writes out PNG files from voxel data
            v_obj - vessel object that holds voxel data
            fileName - filename of OBJ file, without extension
            src_filen_str - filename of source gocad file
        '''
        popup_list = []
        self.logger.debug("write_voxel_png(%s,%s)", src_dir, fileName)
        if len(v_obj.prop_dict) > 0:
            print(v_obj.prop_dict)
            for map_idx in sorted(v_obj.prop_dict):
                popup_list.append(self.write_single_voxel_png(v_obj, src_dir, fileName, map_idx))
        return popup_list 


    def write_single_voxel_png(self, v_obj, src_dir, fileName, idx):
        ''' Writes out a PNG file of the top layer of the voxel data
            v_obj - vessel object that holds details of GOCAD file
            fileName - filename of OBJ file, without extension
            src_filen_str - filename of source gocad file
        '''
        self.logger.debug("write_single_voxel_png(%s, %s, %s)", src_dir, fileName, idx)
        colour_arr = array.array("B")
        z = v_obj.vol_dims[2]-1
        pixel_cnt = 0
        prop_obj = v_obj.prop_dict[idx]
        # If colour table is provided within source file, use it
        if len(prop_obj.colour_map) > 0:
            for x in range(0, v_obj.vol_dims[0]):
                for y in range(0, v_obj.vol_dims[1]):
                    try:
                        (r,g,b) = prop_obj.colour_map[int(prop_obj.data[x][y][z])]
                    except ValueError:
                        (r,g,b) = (0.0, 0.0, 0.0)
                    pixel_colour = [int(r*255.0), int(g*255.0), int(b*255.0)]
                    colour_arr.fromlist(pixel_colour)
                    pixel_cnt += 1
        # Else use a false colour map
        else:
            for x in range(0, v_obj.vol_dims[0]):
                for y in range(0, v_obj.vol_dims[1]):
                    try:
                        (r,g,b,a) = self.make_colour_map(prop_obj.data[x][y][z], prop_obj.data_stats['min'], prop_obj.data_stats['max'])      
                    except ValueError:
                        (r,g,b,a) = (0.0, 0.0, 0.0, 0.0) 
                    pixel_colour = [int(r*255.0), int(g*255.0), int(b*255.0)]
                    colour_arr.fromlist(pixel_colour)
                    pixel_cnt += 1
                    
        img = PIL.Image.frombytes('RGB', (v_obj.vol_dims[1], v_obj.vol_dims[0]), colour_arr.tobytes())
        print("Writing PNG file: ",fileName+"_"+idx+".PNG")
        img.save(os.path.join(src_dir, fileName+"_"+idx+".PNG"))
        if len(prop_obj.class_name) >0:
            label_str = prop_obj.class_name
        else:
            label_str = v_obj.header_name
        popup_dict = { os.path.basename(fileName+"_"+idx): { 'title': label_str, 'name': label_str } }
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
        self.logger.debug("start_collada()")
        self.mesh_obj = Collada.Collada()
        self.geomnode_list = []

        
    def add_v_to_collada(self, v_obj):
        ''' Adds a vessel object to the pycollada mesh object
            NB: Does not accept GOCAD vertex or volume files as they usually have (too) many node objects
            v_obj - GOCAD vessel object
            Returns a popup info dict or exits if you try to add a GOCAD VS (vertex) or VO (volume) file
            popup info dict format: { object_name: { 'attr_name': attr_val, ... } }
        '''
        self.logger.debug("add_v_to_collada()")

        # Cannot do vertices *.VS or volumes *.VO
        if v_obj.is_vs or v_obj.is_vo:
            print("ERROR - cannot process VS or VO file in a GP file?")
            sys.exit(1)

        group_name = ""
        if len(v_obj.group_name)>0:
            group_name = v_obj.group_name+"-"
        if len(v_obj.header_name)>0:
            geometry_name = group_name + v_obj.header_name
        else:
            geometry_name = group_name + "geometry"
        popup_dict = {}

        # Make a vertex dictionary to associate the vertex sequence number with its position in 'vrtx_arr'
        vert_dict = v_obj.make_vertex_dict()
 
        # Triangles
        if v_obj.is_ts:
            if len(v_obj.rgba_tup)!=4:
                v_obj.rgba_tup = (1,0,0,1.0)
            effect = Collada.material.Effect("effect-{0:05d}".format(self.vobj_cnt), [], self.SHADING, emission=self.EMISSION, ambient=self.AMBIENT, diffuse=v_obj.rgba_tup, specular=self.SPECULAR, shininess=self.SHININESS, double_sided=True)
            mat = Collada.material.Material("material-{0:05d}".format(self.vobj_cnt), "mymaterial-{0:05d}".format(self.vobj_cnt), effect)
            self.mesh_obj.effects.append(effect)
            self.mesh_obj.materials.append(mat)
            matnode = Collada.scene.MaterialNode("materialref-{0:05d}".format(self.vobj_cnt), mat, inputs=[])
            # Make floats array for inclusion in COLLADA file
            vert_floats = []
            for v in v_obj.get_vrtx_arr():
                vert_floats += [v.xyz[0]-v_obj.base_xyz[0], v.xyz[1]-v_obj.base_xyz[1], v.xyz[2]-v_obj.base_xyz[2]]

            vert_src = Collada.source.FloatSource("triverts-array-{0:05d}".format(self.vobj_cnt), numpy.array(vert_floats), ('X', 'Y', 'Z'))
            geom = Collada.geometry.Geometry(self.mesh_obj, "geometry-{0:05d}".format(self.vobj_cnt), geometry_name, [vert_src])
            input_list = Collada.source.InputList()
            input_list.addInput(0, 'VERTEX', "#triverts-array-{0:05d}".format(self.vobj_cnt))

            indices = []
            for t in v_obj.get_trgl_arr():
                indices += [vert_dict[t.abc[0]]-1, vert_dict[t.abc[1]]-1, vert_dict[t.abc[2]]-1]

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
            vrtx_arr = v_obj.get_vrtx_arr()
            for l in v_obj.get_seg_arr():
                v0 = vrtx_arr[vert_dict[l.ab[0]]-1]
                v1 = vrtx_arr[vert_dict[l.ab[1]]-1]
                bv0 = (v0.xyz[0]-v_obj.base_xyz[0], v0.xyz[1]-v_obj.base_xyz[1], v0.xyz[2]-v_obj.base_xyz[2])
                bv1 = (v1.xyz[0]-v_obj.base_xyz[0], v1.xyz[1]-v_obj.base_xyz[1], v1.xyz[2]-v_obj.base_xyz[2])
                vert_floats = list(bv0) + [bv0[0], bv0[1], bv0[2]+self.LINE_WIDTH] + list(bv1) + [bv1[0], bv1[1], bv1[2]+self.LINE_WIDTH]
                vert_src = Collada.source.FloatSource("lineverts-array-{0:010d}-{1:05d}".format(point_cnt, self.vobj_cnt), numpy.array(vert_floats), ('X', 'Y', 'Z'))
                geom_label = "line-{0}-{1:010d}".format(geometry_name, point_cnt)
                geom = Collada.geometry.Geometry(self.mesh_obj, "geometry{0:010d}-{1:05d}".format(point_cnt, self.vobj_cnt), geom_label, [vert_src])

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
        '''
        self.logger.debug("end_collada(%s)", fileName)

        node = Collada.scene.Node("node0", children=self.geomnode_list)
        myscene = Collada.scene.Scene("myscene", [node])
        self.mesh_obj.scenes.append(myscene)
        self.mesh_obj.scene = myscene
        print("2 Writing COLLADA file: ", fileName+'.dae')
        self.mesh_obj.write(fileName+'.dae')


    def write_collada(self, v_obj, fileName):
        ''' Write out a COLLADA file
            fileName - filename of COLLADA file, without extension
            v_obj - vessel object that holds details of GOCAD file
            Returns a dictionary of popup info objects
            popup info dict format: { object_name: { 'attr_name': attr_val, ... } }
        '''
        self.logger.debug("write_collada(%s)",  fileName)
        self.logger.debug("write_collada() v_obj=%s", repr(v_obj))
        p_dict = {}
        if v_obj.is_vs:
            p_dict = self.write_vs_collada(v_obj, fileName)
        elif v_obj.is_vo:
            print("ERROR - Cannot use write_collada for VO?")
            sys.exit(1)
        else:
            self.start_collada()
            p_dict = self.add_v_to_collada(v_obj)
            self.end_collada(fileName)
        return p_dict


    def write_vs_collada(self, v_obj, fileName):
        ''' Write out a COLLADA file from a vs file
            fileName - filename of COLLADA file, without extension
            v_obj - vessel object that holds details of GOCAD file
        '''
        self.logger.debug("write_vs_collada(%s)", fileName)
        self.logger.debug("write_vs_collada() v_obj=%s", repr(v_obj))
        
        if not v_obj.is_vs:
            print("ERROR - Cannot use write_single_collada for PL, TS, VO?")
            sys.exit(1)

        mesh = Collada.Collada()
        popup_dict = {}
        group_name = ""
        if len(v_obj.group_name)>0:
            group_name = v_obj.group_name+"-"
        if len(v_obj.header_name)>0:
            geometry_name = group_name + v_obj.header_name
        else:
            geometry_name = group_name + "geometry"
 
        # Make a vertex dictionary to associate the vertex sequence number with its position in 'vrtx_arr'
        vert_dict = v_obj.make_vertex_dict()

        POINT_SIZE = 1000
        point_cnt = 0
        node_list = []
        geomnode_list = []
        vert_floats = []
        matnode_list = []
        triset_list = []
        vert_src_list = []
        colour_num = 0
        # If there are many colours, make MAX_COLORS materials
        if len(v_obj.local_props.keys()) > 0:
            self.make_colour_materials(mesh, self.MAX_COLOURS)
            prop_str = list(v_obj.local_props.keys())[0]
            prop_dict = v_obj.local_props[prop_str].data
            max_v = v_obj.local_props[prop_str].data_stats['max']
            min_v = v_obj.local_props[prop_str].data_stats['min']
        elif len(v_obj.prop_dict.keys()) > 0:
            self.make_colour_materials(mesh, self.MAX_COLOURS)
            prop_str = list(v_obj.prop_dict.keys())[0]
            prop_dict = v_obj.prop_dict[prop_str]
            max_v = v_obj.prop_meta[prop_str]['max']
            min_v = v_obj.prop_meta[prop_str]['min']
        # If there is only one colour
        else:
            self.make_colour_material(mesh, v_obj.rgba_tup, colour_num)
            prop_str = ""
            prop_dict = {}
            min_v = 0.0
            max_v = 0.0

        # Draw vertices as pyramids
        for v in v_obj.get_vrtx_arr():
            # Lookup the colour table
            if prop_str!="":
                # If no data value for this vertex then skip to next one
                if v.xyz not in prop_dict:
                    continue               
                colour_num = self.calculate_colour_num(prop_dict[v.xyz], max_v, min_v, self.MAX_COLOURS)
            bv = (v.xyz[0]-v_obj.base_xyz[0], v.xyz[1]-v_obj.base_xyz[1], v.xyz[2]-v_obj.base_xyz[2])
            # Vertices of the pyramid
            vert_floats = [bv[0], bv[1], bv[2]+POINT_SIZE*2] + \
                          [bv[0]+POINT_SIZE, bv[1]+POINT_SIZE, bv[2]] + \
                          [bv[0]+POINT_SIZE, bv[1]-POINT_SIZE, bv[2]] + \
                          [bv[0]-POINT_SIZE, bv[1]-POINT_SIZE, bv[2]] + \
                          [bv[0]-POINT_SIZE, bv[1]+POINT_SIZE, bv[2]]
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

            if prop_str!="":
                popup_dict[geom_label] = { 'name': prop_str, 'val': prop_dict[v.xyz], 'title': geometry_name.replace('_',' ') }
            else:
                popup_dict[geom_label] = { 'name': geometry_name.replace('_',' '), 'title': geometry_name.replace('_',' ') }
            point_cnt += 1

        node = Collada.scene.Node("node0", children=geomnode_list)
        node_list.append(node)
        myscene = Collada.scene.Scene("myscene", node_list)
        mesh.scenes.append(myscene)
        mesh.scene = myscene

        # print('returning ', popup_dict)
        return popup_dict


    def write_vo_collada(self, v_obj, fileName):
        ''' Write out a COLLADA file from a vo file
            fileName - filename of COLLADA file, without extension
            v_obj - vessel object that holds details of GOCAD file
        '''
        self.logger.debug("write_vo_collada(%s)", fileName)
        self.logger.debug("write_vo_collada() v_obj=%s", repr(v_obj))
        
        if not v_obj.is_vo:
            print("ERROR - Cannot use write_collada_voxel for PL, TS, VO, VS?")
            sys.exit(1)

        mesh = Collada.Collada()
        group_name = ""
        if len(v_obj.group_name)>0:
            group_name = v_obj.group_name+"-"
        if len(v_obj.header_name)>0:
            geometry_name = group_name + v_obj.header_name
        else:
            geometry_name = group_name + "geometry"
 
        # Make a vertex dictionary to associate the vertex sequence number with its position in 'vrtx_arr'
        vert_dict = v_obj.make_vertex_dict()
        popup_list = []
        popup_dict = {}
        file_cnt = 1
        # Increase sample size so we don't create too much data, to be improved later on
        step = 1
        n_elems3 = v_obj.vol_dims[0] * v_obj.vol_dims[1] * v_obj.vol_dims[2]
        while n_elems3/(step*step*step) > 10000:
          step += 1
        print("step =", step)
        pt_size = [(v_obj.axis_u[0]*step)/(v_obj.vol_dims[0]*2), 
                   (v_obj.axis_v[1]*step)/(v_obj.vol_dims[1]*2),
                   (v_obj.axis_w[2]*step)/(v_obj.vol_dims[2]*2)]
        # FIXME: Only does first one!
        # print(v_obj.prop_dict)
        print('pt_size = ' , pt_size)
        # Put create a dict based on colour
        bucket = {}
        prop_obj = v_obj.prop_dict['1']
        for z in range(0, v_obj.vol_dims[2], step):
            for y in range(0, v_obj.vol_dims[1], step):
                for x in range(0, v_obj.vol_dims[0], step):
                    key = int(prop_obj.data[x][y][z])
                    bucket.setdefault(key, []) 
                    bucket[key].append((x,y,z))

        for data_val, coord_list in bucket.items():
            # Limit to 256 colours
            self.make_colour_materials(mesh, self.MAX_COLOURS)
            node_list = []
            point_cnt = 0
            for x,y,z in coord_list:
                # print(x,y,z,' data_val =', data_val )
                if prop_obj.data[x][y][z] != prop_obj.no_data_marker:
                    colour_num = self.calculate_colour_num(prop_obj.data[x][y][z], prop_obj.data_stats['max'], prop_obj.data_stats['min'], self.MAX_COLOURS)
                    # NB: Assumes AXIS_MIN = 0, and AXIS_MAX = 1
                    u_offset = v_obj.axis_origin[0]+ float(x)/v_obj.vol_dims[0]*v_obj.axis_u[0]
                    v_offset = v_obj.axis_origin[1]+ float(y)/v_obj.vol_dims[1]*v_obj.axis_v[1]
                    w_offset = v_obj.axis_origin[2]+ float(z)/v_obj.vol_dims[2]*v_obj.axis_w[2]
                    v = (u_offset-v_obj.base_xyz[0], v_offset-v_obj.base_xyz[1], w_offset-v_obj.base_xyz[2])
                        
                    geomnode_list = []
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

                    triset = geom.createTriangleSet(numpy.array(indices), input_list, "materialref-{0:010d}".format(colour_num))
                    geom.primitives.append(triset)
                    mesh.geometries.append(geom)
                    matnode = Collada.scene.MaterialNode("materialref-{0:010d}".format(colour_num), mesh.materials[colour_num], inputs=[])
                    geomnode_list.append(Collada.scene.GeometryNode(geom, [matnode]))

                    node = Collada.scene.Node("node{0:010d}".format(point_cnt), children=geomnode_list)
                    node_list.append(node)
                    if (x,y,z) in v_obj.flags_dict:
                        popup_name = v_obj.flags_dict[(x,y,z)]
                    else:
                        popup_name =  v_obj.header_name
                    popup_dict[geom_label] = { 'title': v_obj.header_name, 'name': popup_name }
                    point_cnt += 1
                else:
                    print(x,y,z, 'no data')

            myscene = Collada.scene.Scene("myscene", node_list)
            mesh.scenes.append(myscene)
            mesh.scene = myscene

            print("1 Writing COLLADA file: ", fileName+'.dae')
            out_filename = fileName+'_'+str(file_cnt)
            mesh.write(out_filename+'.dae')
            popup_list.append((popup_dict, out_filename))
            popup_dict = {}

            file_cnt += 1

            mesh = Collada.Collada()

 
        # print('returning ', popup_list)
        return popup_list





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


    def make_colour_material(self, mesh, colour_tup, colour_idx):
        ''' Adds a colour material to COLLADA object
            mash - Collada object
            colour_tup - tuple of floats (R,G,B,A)
            colour_idx - integer index, used to refer to the material
        '''
        effect = Collada.material.Effect("effect{0:010d}".format(colour_idx), [], self.SHADING, emission=self.EMISSION, ambient=self.AMBIENT, diffuse=colour_tup, specular=self.SPECULAR, shininess=self.SHININESS)
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
        ''' This creates a false colour map, returns an RGBA tuple.
            Maps a floating point value that varies between a min and max value to an RGBA tuple
            i_flt - floating point value to be mapped
            imax_flt - maximum range of the floating point value
            imin_flt - minimum range of the floating point value
            Returns an RGBA tuple
        '''
        if i_flt < imin_flt or i_flt > imax_flt:
            return (0.0, 0.0, 0.0, 0.0)
        SAT = 0.8
        hue_flt = (imax_flt - i_flt)/ (imax_flt - imin_flt)
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
