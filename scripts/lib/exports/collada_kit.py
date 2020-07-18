"""
Contains the ColladaKit class
"""

import sys
import logging
from collections import defaultdict
import numpy
import collada as Collada

from lib.exports.collada_out import ColladaOut
# from lib.exports.obj_out import ObjKit
from lib.exports.bh_utils import make_borehole_label
from lib.exports.export_kit import ExportKit
from lib.db.style.false_colour import calculate_false_colour_num, make_false_colour_tup

class ColladaKit(ExportKit):
    ''' Class used to output COLLADA files, given geometry, style and metadata data structures
    '''

    EMISSION = (0, 0, 0, 1)
    ''' Emission parameter for pycollada material effect '''

    AMBIENT = (0, 0, 0, 1)
    ''' Ambient parameter for pycollada material effect '''

    SPECULAR = (0.7, 0.7, 0.7, 1)
    ''' Specular parameter for pycollada material effect '''

    SHININESS = 50.0
    ''' Shininess parameter for pycollada material effect '''

    SHADING = "phong"
    ''' Shading parameter for pycollada material effect '''

    MAX_COLOURS = 256.0
    ''' Maximum number of colours displayed in one COLLADA file '''

    POINT_SIZE = 300
    ''' Size of object used to represent point data '''

    def __init__(self, debug_level):
        ''' Initialise class

        :param debug_level: debug level taken from python's 'logging' module
        '''
        # Call parent class
        ExportKit.__init__(self, debug_level)

        # Pycollada objects used to create a single COLLADA file using multiple input files
        self.mesh_obj = None
        self.geomnode_list = []
        self.obj_cnt = 0

        self.collout_obj = ColladaOut(debug_level)
        #self.objoout_obj = ObjKit(debug_level)


    def start_collada(self):
        ''' Initiate creation of a COLLADA file
        '''
        self.logger.debug("start_collada()")
        self.mesh_obj = Collada.Collada()
        self.geomnode_list = []


    def add_geom_to_collada(self, geom_obj, style_obj, meta_obj):
        ''' Adds a vessel object to the pycollada mesh object
            NB: Does not accept GOCAD vertex or volume files as they usually have
            (too) many node objects

        :param geom_obj: MODEL_GEOMETRY object
        :param style_obj: STYLE object containing colour info
        :param meta_obj: METADATA object
        :returns: a popup info dict or exits if you try to add a GOCAD VS (vertex)
            or VO (volume) file
            popup info dict format: { object_name: { 'attr_name': attr_val, ... } }
            and a node label string
        '''
        self.logger.debug("add_geom_to_collada()")

        # Cannot do volumes using this function
        if geom_obj.is_volume():
            self.logger.error("Cannot process volume file from here, internal error")
            sys.exit(1)

        geometry_name = meta_obj.name
        popup_dict = {}
        node_label = ''

        # Triangles
        if geom_obj.is_trgl():
            effect = Collada.material.Effect("effect-{0:05d}".format(self.obj_cnt), [],
                                             self.SHADING, emission=self.EMISSION,
                                             ambient=self.AMBIENT,
                                             diffuse=style_obj.get_rgba_tup(),
                                             specular=self.SPECULAR,
                                             shininess=self.SHININESS,
                                             double_sided=True)
            mat = Collada.material.Material("material-{0:05d}".format(self.obj_cnt),
                                            "mymaterial-{0:05d}".format(self.obj_cnt),
                                            effect)
            self.mesh_obj.effects.append(effect)
            self.mesh_obj.materials.append(mat)
            matnode = Collada.scene.MaterialNode("materialref-{0:05d}".format(self.obj_cnt),
                                                 mat, inputs=[])
            # Make floats array for inclusion in COLLADA file
            vert_floats = []
            for vrtx in geom_obj.vrtx_arr:
                vert_floats += [vrtx.xyz[0], vrtx.xyz[1], vrtx.xyz[2]]

            vert_src = Collada.source.FloatSource("triverts-array-{0:05d}".format(self.obj_cnt),
                                                  numpy.array(vert_floats), ('X', 'Y', 'Z'))
            geom = Collada.geometry.Geometry(self.mesh_obj, "geometry-{0:05d}".format(self.obj_cnt),
                                             geometry_name, [vert_src])
            input_list = Collada.source.InputList()
            input_list.addInput(0, 'VERTEX', "#triverts-array-{0:05d}".format(self.obj_cnt))

            indices = []
            for tri in geom_obj.trgl_arr:
                indices += [tri.abc[0]-1, tri.abc[1]-1, tri.abc[2]-1]

            triset = geom.createTriangleSet(numpy.array(indices), input_list,
                                            "materialref-{0:05d}".format(self.obj_cnt))

            geom.primitives.append(triset)
            self.mesh_obj.geometries.append(geom)
            self.geomnode_list.append(Collada.scene.GeometryNode(geom, [matnode]))

            popup_dict[geometry_name] = {'title': meta_obj.name, 'name': meta_obj.name}
            node_label = geometry_name

        # Lines
        elif geom_obj.is_line():
            effect = Collada.material.Effect("effect-{0:05d}".format(self.obj_cnt), [],
                                             self.SHADING,
                                             emission=self.EMISSION,
                                             ambient=self.AMBIENT,
                                             diffuse=style_obj.get_rgba_tup(),
                                             specular=self.SPECULAR,
                                             shininess=self.SHININESS,
                                             double_sided=True)
            mat = Collada.material.Material("material-{0:05d}".format(self.obj_cnt),
                                            "mymaterial-{0:05d}".format(self.obj_cnt), effect)
            self.mesh_obj.effects.append(effect)
            self.mesh_obj.materials.append(mat)

            geom_label_list = self.collout_obj.make_line(self.mesh_obj, geometry_name,
                                                         self.geomnode_list, geom_obj.seg_arr,
                                                         geom_obj.vrtx_arr, self.obj_cnt,
                                                         geom_obj.line_width, not geom_obj.is_vert_line)
            for geom_label in geom_label_list:
                popup_dict[geom_label] = {'title': meta_obj.name, 'name': meta_obj.name}
                node_label = geom_label

        # Points
        elif geom_obj.is_point():
            geometry_name = meta_obj.name
            prop_dict = geom_obj.get_loose_3d_data(True)
            colour_num = 0

            # If there are many colours, make MAX_COLORS materials
            if not style_obj.has_single_colour():
                self.make_false_colour_materials(self.mesh_obj, self.MAX_COLOURS)
                max_v = geom_obj.get_max_data()
                min_v = geom_obj.get_min_data()

            # If there is only one colour
            else:
                self.make_colour_material(self.mesh_obj, style_obj.get_rgba_tup(), colour_num)
                min_v = 0.0
                max_v = 0.0

            # Draw vertices as pyramids
            for vrtx in geom_obj.vrtx_arr:
                # Lookup the colour table
                if not style_obj.has_single_colour() and vrtx.xyz in prop_dict:
                    colour_num = calculate_false_colour_num(prop_dict[vrtx.xyz], max_v, min_v,
                                                            self.MAX_COLOURS)
                geom_label = self.collout_obj.make_pyramid(self.mesh_obj, geometry_name,
                                                           self.geomnode_list, vrtx, self.obj_cnt,
                                                           self.POINT_SIZE, colour_num)

                popup_dict[geom_label] = {'name': meta_obj.get_property_name(),
                                          'val': prop_dict[vrtx.xyz],
                                          'title': geometry_name.replace('_', ' ')}
                node_label = geom_label


        self.obj_cnt += 1
        return popup_dict, node_label



    def end_collada(self, out_filename, node_label):
        ''' Close out a COLLADA, writing the mesh object to file

        :param out_filename: path & filename of COLLADA file to output, without extension
        :param node_label: label for the COLLADA "Node" object
                           (used by the website to recognise model parts)
        '''
        self.logger.debug("end_collada(%s, %s)", out_filename, node_label)

        node = Collada.scene.Node(node_label, children=self.geomnode_list)
        myscene = Collada.scene.Scene("myscene", [node])
        self.mesh_obj.scenes.append(myscene)
        self.mesh_obj.scene = myscene
        dest_path = out_filename + '.dae'
        self.logger.info("end_collada() Writing COLLADA file: %s", dest_path)
        try:
            self.mesh_obj.write(dest_path)
        except OSError as os_exc:
            self.logger.error("ERROR - Cannot write file %s: %s", dest_path, repr(os_exc))


    def write_collada(self, geom_obj, style_obj, meta_obj, out_filename):
        ''' Write out a COLLADA file

        :param geom_obj: MODEL_GEOMETRY object that geometry and text
        :param style_obj: STYLE object containing colour info
        :param meta_obj: METADATA object, used for labelling
        :param out_filename: path & filename of COLLADA file to output, without extension
        :returns: a dictionary of popup info objects
            popup info dict format: { object_name: { 'attr_name': attr_val, ... } }
        '''
        self.logger.debug("write_collada(%s)", out_filename)
        self.logger.debug("write_collada() geom_obj=%s", repr(geom_obj))
        p_dict = {}
        if geom_obj.is_point():
            p_dict = self.write_point_collada(geom_obj, style_obj, meta_obj, out_filename)
        elif geom_obj.is_volume():
            self.logger.error("Cannot use write_collada for volumes?")
            sys.exit(1)
        else:
            self.start_collada()
            p_dict, node_label = self.add_geom_to_collada(geom_obj, style_obj, meta_obj)
            self.end_collada(out_filename, node_label)
        return p_dict


    def write_point_collada(self, geom_obj, style_obj, meta_obj, out_filename):
        ''' Write out a COLLADA file from a point geometry file

        :param geom_obj: MODEL_GEOMETRY object that hold geometry and text
        :param style_obj: STYLE object containing colour info
        :param meta_obj: METADATA object, used for labelling
        :param out_filename: path & filename of COLLADA file to output, without extension
        '''
        self.logger.debug("write_point_collada(%s)", out_filename)
        self.logger.debug("write_point_collada() geom_obj=%s", repr(geom_obj))

        if not geom_obj.is_point():
            self.logger.error("Cannot use write_point_collada for line, triangle or volume")
            sys.exit(1)

        mesh = Collada.Collada()
        popup_dict = {}
        geometry_name = meta_obj.name

        node_list = []
        geomnode_list = []
        colour_num = 0
        # If there are many colours, make MAX_COLORS materials
        prop_dict = geom_obj.get_loose_3d_data(True)
        if not style_obj.has_single_colour():
            self.make_false_colour_materials(mesh, self.MAX_COLOURS)
            max_v = geom_obj.get_max_data()
            min_v = geom_obj.get_min_data()

        # If there is only one colour
        else:
            self.make_colour_material(mesh, style_obj.get_rgba_tup(), colour_num)

        # Draw vertices as pyramids
        geom_label=''
        for point_cnt, vrtx in enumerate(geom_obj.vrtx_arr):
            # If there's a colour table calculate colour, but if no data at that point
            # then skip this vertex
            if not style_obj.has_single_colour():
                if vrtx.xyz not in prop_dict:
                    continue
                colour_num = calculate_false_colour_num(prop_dict[vrtx.xyz], max_v, min_v,
                                                        self.MAX_COLOURS)

            # Create coloured pyramid
            geom_label = self.collout_obj.make_pyramid(mesh, geometry_name, geomnode_list, vrtx,
                                                       point_cnt, self.POINT_SIZE, colour_num)

            # Create popup info
            popup_dict[geom_label] = {'name': meta_obj.get_property_name(),
                                      'title': geometry_name.replace('_', ' ')}
            if vrtx.xyz in prop_dict:
                popup_dict[geom_label]['val'] = prop_dict[vrtx.xyz]

        # Create a node using the geometry list
        node = Collada.scene.Node(geom_label, children=geomnode_list)
        node_list.append(node)

        # Add nodes to scene, add scene to mesh
        myscene = Collada.scene.Scene("myscene", node_list)
        mesh.scenes.append(myscene)
        mesh.scene = myscene

        # Write mesh to file
        dest_path = out_filename+'.dae'
        self.logger.info("write_point_collada() Writing COLLADA file: %s", dest_path)
        try:
            mesh.write(dest_path)
        except OSError as os_exc:
            self.logger.error("ERROR - Cannot write file %s: %s", dest_path, repr(os_exc))
            return {}

        return popup_dict


    def compute_neighbours(self, xyz_list, step):
        ''' Counts the number of neighbours of each point in a 3d array

        :params xyz_listr: list of (X,Y,Z) coordinates
        :returns: dictionary: key is (X,Y,Z), value is number of neighbours
        '''
        ret = {}
        for xyz in xyz_list:
            cnt = 0
            for x_val, y_val, z_val in xyz_list:
                if xyz != (x_val, y_val, z_val):
                    if self.next_to(xyz[0], x_val, step) and self.next_to(xyz[1], y_val, step) \
                                                         and self.next_to(xyz[2], z_val, step):
                        cnt += 1
            ret[xyz] = cnt
        #self.logger.debug("compute_neighbours(%s) returns %s", repr(xyz_list), repr(ret))
        return ret


    def next_to(self, a_val, b_val, step):
        ''' Returns True iff a equals b or if a is exactly 'step' units away from b
        '''
        return a_val == b_val or a_val == b_val + step or a_val == b_val - step

    def calc_step_sz(self, geom_obj, limit):
        ''' With many voxets being so large, we have to increase sample size so we don't
            create too much data, to be improved later on.

        :params geom_obj: MODEL_GEOMETRY object
        :params limit: the higher this number the more cubes will be used to
                       represent the voxet data
        :returns: step size as an integer, point (sample) size as list of 3 integers [X,Y,Z]
        '''
        step = 1
        n_elems3 = geom_obj.vol_sz[0] * geom_obj.vol_sz[1] * geom_obj.vol_sz[2]
        while n_elems3/(step*step*step) > limit:
            step += 1
        pt_size = [(abs(geom_obj.vol_axis_u[0])*step)/(geom_obj.vol_sz[0]*2),
                   (abs(geom_obj.vol_axis_v[1])*step)/(geom_obj.vol_sz[1]*2),
                   (abs(geom_obj.vol_axis_w[2])*step)/(geom_obj.vol_sz[2]*2)]
        return step, pt_size



    def write_vol_collada(self, geom_obj, style_obj, meta_obj, out_filename):
        ''' Write out a COLLADA file from a vo file

        :param geom_obj: MODEL_GEOMETRY object that geometry and text
        :param style_obj: STYLE object containing colour info
        :param meta_obj: METADATA object, used for labelling
        :param out_filename: path & filename of COLLADA file to output, without extension
        '''
        self.logger.debug("write_vol_collada(%s)", out_filename)
        self.logger.debug("write_vol_collada() geom_obj=%s", repr(geom_obj))

        if not geom_obj.is_volume():
            self.logger.error("Cannot use write_vo_collada for non-volume file, internal error")
            sys.exit(1)

        geometry_name = meta_obj.name
        popup_list = []
        popup_dict = {}

        # There are two kinds of voxel object
        # One has index values that refer to rock types or colours, the other
        # has values that refer to physical measurements
        if meta_obj.is_index_data:
            # Calculate size of each voxet cube
            step, pt_size = self.calc_step_sz(geom_obj, 50000)
            self.logger.debug("step = %d", step)

            # Take the index data found in the voxel file and group it together
            bucket = defaultdict(list)
            for z_val in range(0, geom_obj.vol_sz[2], step):
                for y_val in range(0, geom_obj.vol_sz[1], step):
                    for x_val in range(0, geom_obj.vol_sz[0], step):
                        if geom_obj.vol_data[x_val][y_val][z_val] != geom_obj.get_no_data_marker():
                            key = int(geom_obj.vol_data[x_val][y_val][z_val])
                            bucket[key].append((x_val, y_val, z_val))

            self.logger.debug("Computed buckets")

            # Computing neighbours
            num_neighbours = {}
            for data_val, coord_list in bucket.items():
                num_neighbours[data_val] = self.compute_neighbours(coord_list, step)

            self.logger.debug("Computed neighbours")

            # For each index value (usually rock type)
            for file_cnt, (data_val, coord_list) in enumerate(bucket.items(), 1):
                self.logger.debug("Writing coords %s for key %s", repr(coord_list[:6]),
                                  repr(data_val))
                mesh = Collada.Collada()
                self.make_mapped_colour_materials(mesh, style_obj.colour_map)
                point_cnt = 0
                node_list = []
                colour_num = data_val - int(geom_obj.get_min_data())
                data_val_label = style_obj.get_rock_label_table().get(colour_num,
                                                                      meta_obj.get_property_name())
                geom_label_stub = geometry_name+"-"+data_val_label
                for x_val, y_val, z_val in coord_list:
                    # self.logger.debug("%d %d %d data_val = %s num_neighbours = %d",
                    # x_val,y_val,z_val, repr(data_val),
                    # num_neighbours[data_val][(x_val,y_val,z_val)])
                    # If surrounded by other cubes, you can't see it, so omit
                    if num_neighbours[data_val][(x_val, y_val, z_val)] < 26:
                        geomnode_list = []
                        geom_label = self.collout_obj.make_cube(mesh, colour_num, x_val, y_val,
                                                                z_val, geom_obj, pt_size,
                                                                geom_label_stub, file_cnt,
                                                                point_cnt, geomnode_list)
                        node = Collada.scene.Node("node{0:010d}".format(point_cnt),
                                                  children=geomnode_list)
                        node_list.append(node)
                        point_cnt += 1

                # Use a key with a regular expression to save writing thousands of properties
                # to config file
                popup_dict["^" + geom_label_stub] = {'title': meta_obj.name,
                                                     'property name': meta_obj.get_property_name(),
                                                     'property value': data_val_label}

                myscene = Collada.scene.Scene("myscene", node_list)
                mesh.scenes.append(myscene)
                mesh.scene = myscene

                # If there are unique labels, then use these, else use the filename
                if data_val_label != meta_obj.get_property_name():
                    popup_dict_key = data_val_label
                else:
                    popup_dict_key = out_filename + '_' + str(file_cnt)

                # Write out COLLADA file
                out_filepath = out_filename + '_' +str(file_cnt)
                self.logger.info("write_vol_collada() Writing COLLADA file: %s.dae", out_filepath)
                try:
                    mesh.write(out_filepath+'.dae')
                except OSError as os_exc:
                    self.logger.error("ERROR - Cannot write file %s.dae: %s", out_filepath, repr(os_exc))
                else:
                    popup_list.append((popup_dict_key, popup_dict, out_filename))
                    popup_dict = {}

        # The physical measurements kind uses a false colourmap, and written as one big file
        else:
            mesh = Collada.Collada()
            # Limit to 256 colours
            self.make_false_colour_materials(mesh, self.MAX_COLOURS)
            point_cnt = 0
            node_list = []

            # Calculate size of each voxet cube
            step, pt_size = self.calc_step_sz(geom_obj, 100000)
            self.logger.debug("step = %d", step)

            for z_val in range(0, geom_obj.vol_sz[2], step):
                for y_val in range(0, geom_obj.vol_sz[1], step):
                    for x_val in range(0, geom_obj.vol_sz[0], step):
                        if geom_obj.vol_data[x_val][y_val][z_val] !=  \
                                 geom_obj.get_no_data_marker() and \
                                 (z_val == 0 or y_val == 0 or x_val == 0 or \
                                 z_val == geom_obj.vol_sz[2]-1 or \
                                 y_val == geom_obj.vol_sz[1]-1 or x_val == geom_obj.vol_sz[0]-1):
                            colour_num = calculate_false_colour_num(geom_obj.vol_data[x_val][y_val][z_val],
                                                                    geom_obj.get_max_data(),
                                                                    geom_obj.get_min_data(),
                                                                    self.MAX_COLOURS)
                            geomnode_list = []
                            geom_label = self.collout_obj.make_cube(mesh, colour_num, x_val,
                                                                    y_val, z_val, geom_obj,
                                                                    pt_size, geometry_name,
                                                                    1, point_cnt, geomnode_list)
                            node = Collada.scene.Node("node{0:010d}".format(point_cnt),
                                                      children=geomnode_list)
                            val_str = "{:.3f}".format(geom_obj.vol_data[x_val][y_val][z_val])
                            popup_dict[geom_label] = {'title': meta_obj.name,
                                                      'name': meta_obj.get_property_name(),
                                                      'value': val_str}
                            node_list.append(node)
                            point_cnt += 1
                        elif geom_obj.vol_data[x_val][y_val][z_val] == geom_obj.get_no_data_marker():
                            self.logger.debug("%d %d %d no data", x_val, y_val, z_val)

            myscene = Collada.scene.Scene("myscene", node_list)
            mesh.scenes.append(myscene)
            mesh.scene = myscene

            dest_path = out_filename+'.dae'
            self.logger.info("write_vol_collada() Writing COLLADA file: %s", dest_path)
            try:
                mesh.write(dest_path)
            except OSError as os_exc:
                self.logger.error("ERROR - Cannot write file %s: %s", dest_path, repr(os_exc))
            else:
                popup_list.append((meta_obj.get_property_name(), popup_dict, out_filename))

        return popup_list


    def write_borehole(self, base_vrtx, borehole_name, colour_info_dict, height_reso, out_filename):
        ''' Write out a COLLADA file of a borehole stick

        :param base_vrtx: base vertex, position of the object within the model [x,y,z]
        :param borehole_name: name of borehole
        :param colour_info_dict: dict of colour info; key - depth, float,
                                val - { 'colour' : (R,B,G,A), 'classText' : mineral name }
                                where R,G,B,A are floats
        :param height_reso: height resolution for colour info dict
        :param out_filename: path & filename of COLLADA file to output, without extension
        '''
        self.logger.debug("write_borehole(%s, %s, colour_info_dict = %s, %s)", repr(base_vrtx),
                          repr(borehole_name), repr(colour_info_dict), repr(out_filename))

        mesh = Collada.Collada()
        node_list = []

        for depth, colour_info in colour_info_dict.items():
            effect = Collada.material.Effect("effect_{:d}".format(int(depth)), [], "phong",
                                             emission=(0, 0, 0, 1), ambient=(0, 0, 0, 1),
                                             diffuse=colour_info['colour'],
                                             specular=(0.7, 0.7, 0.7, 1), shininess=50.0)
            mat = Collada.material.Material("material_{:d}".format(int(depth)),
                                            "mymaterial_{:d}".format(int(depth)), effect)
            mesh.effects.append(effect)
            mesh.materials.append(mat)

        geomnode_list = []
        borehole_label = make_borehole_label(borehole_name, 0)
        self.collout_obj.make_colour_borehole_marker(mesh, base_vrtx, borehole_label,
                                                     geomnode_list,
                                                     colour_info_dict, height_reso)
        node = Collada.scene.Node(borehole_label, children=geomnode_list)
        node_list.append(node)

        myscene = Collada.scene.Scene("myscene", node_list)
        mesh.scenes.append(myscene)
        mesh.scene = myscene

        try:
            mesh.write(out_filename+'.dae')
        except OSError as os_exc:
            self.logger.error("ERROR - Cannot write file %s.dae: %s", out_filename, repr(os_exc))




    def make_false_colour_materials(self, mesh, max_colours_flt):
        ''' Adds a list of coloured materials to COLLADA object using a false colour map

        :params mesh: pycollada 'collada' object
        :params max_colours_flt: number of colours to add, float
        '''
        for colour_idx in range(int(max_colours_flt)):
            diffuse_colour = make_false_colour_tup(float(colour_idx), 0.0, max_colours_flt - 1.0)
            effect = Collada.material.Effect("effect{0:010d}".format(colour_idx), [], self.SHADING,
                                             emission=self.EMISSION, ambient=self.AMBIENT,
                                             diffuse=diffuse_colour, specular=self.SPECULAR,
                                             shininess=self.SHININESS)
            mat = Collada.material.Material("material{0:010d}".format(colour_idx),
                                            "mymaterial{0:010d}".format(colour_idx), effect)
            mesh.effects.append(effect)
            mesh.materials.append(mat)


    def make_colour_material(self, mesh, colour_tup, colour_idx):
        ''' Adds a colour material to COLLADA object

        :params mesh: pycollada 'collada' object
        :params colour_tup: tuple of floats (R,G,B,A)
        :params colour_idx: integer index, used to refer to the material
        '''
        self.logger.debug("make_colour_material(%s, %s, %s)", repr(mesh), repr(colour_tup),
                          repr(colour_idx))
        effect = Collada.material.Effect("effect{0:010d}".format(colour_idx), [], self.SHADING,
                                         emission=self.EMISSION, ambient=self.AMBIENT,
                                         diffuse=colour_tup, specular=self.SPECULAR,
                                         shininess=self.SHININESS)
        mat = Collada.material.Material("material{0:010d}".format(colour_idx),
                                        "mymaterial{0:010d}".format(colour_idx), effect)
        mesh.effects.append(effect)
        mesh.materials.append(mat)


    def make_mapped_colour_materials(self, mesh, colour_map):
        ''' Adds a list of coloured materials to COLLADA object using supplied colour_map

        :params mesh: COLLADA object
        :params colour_map: dict of colours, key is integer, value is RGBA tuple of 4 floats
        '''
        for key in colour_map:
            self.make_colour_material(mesh, colour_map[key], key)



#  END OF ColladaKit CLASS
