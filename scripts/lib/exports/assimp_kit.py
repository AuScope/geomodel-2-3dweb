"""
Contains the AssimpKit class
"""

import sys
import logging
import ctypes
from ctypes import POINTER
from pyassimp import structs, export, export_blob

from lib.exports.geometry_gen import colour_borehole_gen, tri_gen

# import lib.exports.print_assimp as pa


class AssimpKit:
    ''' Class used to export geometries to assimp lib
    '''

    FILE_EXT = '.gltf'
    ''' Extension of file
    '''

    EXPORT_TYPE = 'gltf2'
    ''' Export type for assimp API
    '''

    def __init__(self, debug_level):
        ''' Initialise class

        :param debug_level: debug level taken from python's 'logging' module
        '''
        # Set up logging, use an attribute of class name so it is only called once
        if not hasattr(AssimpKit, 'logger'):
            AssimpKit.logger = logging.getLogger(__name__)

            # Create console handler
            handler = logging.StreamHandler(sys.stdout)

            # Create formatter
            formatter = logging.Formatter('%(asctime)s -- %(name)s -- %(levelname)s - %(message)s')

            # Add formatter to ch
            handler.setFormatter(formatter)

            # Add handler to logger and set level
            AssimpKit.logger.addHandler(handler)

        AssimpKit.logger.setLevel(debug_level)
        self.logger = AssimpKit.logger

        self.scn = None
        ''' Assimp scene object
        '''


    def start_scene(self):
        ''' Initiate scene creation, only one scene can be created at a time
        '''
        self.scn = structs.Scene()
        self.scn.mMetadata = None
        self.scn.mPrivate = 0


    def add_geom(self, geom_obj, style_obj, meta_obj):
        ''' Add a geometry ot the scene. It only does triangular meshes for the moment.
        Will be expanded to include other types.
        :param geom_obj: ModelGeometries object
        :param style_obj: STYLE object
        :param meta_obj: METADATA object
        '''
        if geom_obj.is_trgl():

            # Set up a mesh
            mesh_p_arr = (POINTER(structs.Mesh) * 1)()
            mesh_arr_pp = ctypes.cast(mesh_p_arr, POINTER(POINTER(structs.Mesh)))
            self.scn.mMeshes = mesh_arr_pp
            self.scn.mNumMeshes = 1

            # Put the mesh name in the mesh's parents, because GLTFLoader
            # copies this into the mesh name
            self.make_nodes(b'root_node', meta_obj.name+b'_0', 1)

            # Set up materials
            mat_p_arr = (POINTER(structs.Material) * 1)()
            mat_arr_pp = ctypes.cast(mat_p_arr, POINTER(POINTER(structs.Material)))
            self.scn.mMaterials = mat_arr_pp
            self.scn.mNumMaterials = 1

            mesh_gen = tri_gen(geom_obj.trgl_arr, geom_obj.vtrx_arr, meta_obj.name)
            for vert_list, indices, mesh_name in mesh_gen:
                mesh_obj = self.make_a_mesh(mesh_name, indices, 0)
                mesh_p_arr[0] = ctypes.pointer(mesh_obj)
                self.add_vertices_to_mesh(mesh_obj, vert_list)
                mat_obj = self.make_material(style_obj.rgba_tup)
                mat_p_arr[0] = ctypes.pointer(mat_obj)
        else:
            self.logger.warning('AssimpKit cannot convert point or line geometries')


    def end_scene(self, out_filename):
        ''' Called after geometries have all been added to scene and a file or blob
        should be created
        :param out_filename: filename and path of output file, without file extension
                             if an empty string, then a blob is returned and a file is not created
        :returns: True if file was written out, else returns the GLTF as an assimp blob object
        '''

        #pa.print_scene(self.scn)
        #sys.stdout.flush()

        # Create a file
        if out_filename != '':
            self.logger.info("Writing GLTF: %s", out_filename + self.FILE_EXT)
            export(self.scn, out_filename + self.FILE_EXT, self.EXPORT_TYPE)
            self.logger.info(" DONE.")
            sys.stdout.flush()
            return True

        # Return a blob
        exp_blob = export_blob(self.scn, self.EXPORT_TYPE, processing=None)
        #pa.print_blob(exp_blob)
        return exp_blob


    def write_borehole(self, base_vrtx, borehole_name, colour_info_dict, height_reso,
                       out_filename=''):
        ''' Write out a file or blob of a borehole stick
            if 'out_filename' is supplied then writes a file and returns True/False
            else returns a pointer to a 'structs.ExportDataBlob' object

        :param base_vrtx: base vertex, position of the object within the model [x,y,z]
        :param borehole_name: name of borehole
        :param colour_info_dict: dict of colour info; key - depth, float, val {'colour':(R,B,G,A),
                                            'classText': mineral name }, where R,G,B,A are floats
        :param height_reso: height resolution for colour info dict
        :param out_filename: optional destination directory+file (without extension),
                             where file is written
        '''
        self.logger.debug("write_borehole(%s, %s, %s, colour_info_dict = %s)",
                          repr(base_vrtx), repr(out_filename), repr(borehole_name),
                          repr(colour_info_dict))

        self.start_scene()

        bh_size = len(colour_info_dict)

        # Set up meshes
        mesh_p_arr = (POINTER(structs.Mesh) * bh_size)()
        mesh_arr_pp = ctypes.cast(mesh_p_arr, POINTER(POINTER(structs.Mesh)))
        self.scn.mMeshes = mesh_arr_pp
        self.scn.mNumMeshes = bh_size
        gen = colour_borehole_gen(base_vrtx, borehole_name, colour_info_dict, height_reso)
        # Test to see if there is only one mesh
        # pylint: disable=W0612
        *first, mesh_name = next(gen)
        one_only = False
        try:
            next(gen)
        except StopIteration:
            one_only = True

        # Put the mesh name in the mesh's parents, because GLTFLoader
        # copies this into the mesh name
        self.make_nodes(b'root_node', mesh_name+b'_0', bh_size)

        # Set up materials
        mat_p_arr = (POINTER(structs.Material) * bh_size)()
        mat_arr_pp = ctypes.cast(mat_p_arr, POINTER(POINTER(structs.Material)))
        self.scn.mMaterials = mat_arr_pp
        self.scn.mNumMaterials = bh_size

        cb_gen = colour_borehole_gen(base_vrtx, borehole_name, colour_info_dict, height_reso)
        for vert_list, indices, colour_idx, depth, colour_info, mesh_name in cb_gen:
            # If there is only one mesh, then GLTFLoader does not append a '_0' to the name,
            # so we must do so, to be consistent with the database
            if one_only:
                mesh_name += b'_0'
            mesh_obj = self.make_a_mesh(mesh_name, indices, colour_idx)
            mesh_p_arr[colour_idx] = ctypes.pointer(mesh_obj)
            self.add_vertices_to_mesh(mesh_obj, vert_list)
            mat_obj = self.make_material(colour_info['colour'])
            mat_p_arr[colour_idx] = ctypes.pointer(mat_obj)

        return self.end_scene(out_filename)


    def make_empty_node(self, node_name):
        ''' Makes an empty node with a supplied name
        :param node_name: name of node to be created
        :returns: pyassimp 'Node' object
        '''
        node = structs.Node()
        node.mName.data = node_name
        node.mName.length = len(node_name)
        node.mTransformation = structs.Matrix4x4(1.0, 0.0, 0.0, 0.0,
                                                 0.0, 1.0, 0.0, 0.0,
                                                 0.0, 0.0, 1.0, 0.0,
                                                 0.0, 0.0, 0.0, 1.0)
        node.mParent = None
        node.mNumChildren = 0
        node.mChildren = None
        node.mNumMeshes = 0
        node.mMeshes = None
        node.mMetadata = None
        return node


    def make_nodes(self, root_node_name, child_node_name, num_meshes):
        ''' Make the scene's root node and a child node

        :param root_node_name: bytes object, name of root node
        :param child_node_name: bytes object, name of child of root node
        '''
        # Make a root node
        parent_n = self.make_empty_node(root_node_name)
        parent_n.mNumChildren = 1

        # Make a child node
        child_n = self.make_empty_node(child_node_name)
        child_n.mParent = ctypes.pointer(parent_n)

        # Integer index to meshes
        mesh_idx_arr = (ctypes.c_uint * num_meshes)()
        for i in range(num_meshes):
            mesh_idx_arr[i] = i
        child_n.mMeshes = ctypes.cast(ctypes.pointer(mesh_idx_arr), POINTER(ctypes.c_uint))
        child_n.mNumMeshes = num_meshes

        ch_n_p = ctypes.pointer(child_n)
        ch_n_pp = ctypes.pointer(ch_n_p)
        parent_n.mChildren = ch_n_pp
        self.scn.mRootNode = ctypes.pointer(parent_n)


    def make_a_mesh(self, mesh_name, index_list, material_index):
        ''' Creates a mesh object

        :param mesh_name: name of mesh object, bytes object
        :param index_list: list of integers, indexes into a vertex list
        :param material_index: index into scene's array of materials
        :returns: pyassimp 'Mesh' object
        '''
        msh = structs.Mesh()
        num_faces = len(index_list)//3

        f_arr = (structs.Face * num_faces)()
        msh.mFaces = ctypes.cast(f_arr, POINTER(structs.Face))
        msh.mNumFaces = num_faces
        msh.mPrimitiveTypes = 4  # Triangle
        msh.mName.length = len(mesh_name)
        msh.mName.data = mesh_name
        msh.mMaterialIndex = material_index

        for f_idx, i_idx  in enumerate(range(0, len(index_list), 3)):
            i_arr = (ctypes.c_uint * 3)()
            i_arr[0] = index_list[i_idx]
            i_arr[1] = index_list[1+i_idx]
            i_arr[2] = index_list[2+i_idx]
            i_arr_p = ctypes.cast(i_arr, POINTER(ctypes.c_uint))
            f_arr[f_idx].mIndices = i_arr_p
            f_arr[f_idx].mNumIndices = 3
        return msh


    def add_vertices_to_mesh(self, mesh, vertex_list):
        ''' Adds the vertices to a mesh

        :param mesh: pyassimp 'Mesh' object
        :param vertex_list: list of floats, (x,y,z) coords of vertices
        '''
        num_vertices = len(vertex_list)//3
        v_arr = (structs.Vector3D * num_vertices)()
        v_arr_p = ctypes.cast(v_arr, POINTER(structs.Vector3D))
        mesh.mVertices = v_arr_p
        mesh.mNumVertices = num_vertices
        for varr_idx, v_idx in enumerate(range(0, len(vertex_list), 3)):
            v_arr[varr_idx] = structs.Vector3D(vertex_list[v_idx], vertex_list[v_idx+1],
                                               vertex_list[v_idx+2])


    def make_colour(self, key, r_val, g_val, b_val, a_val):
        ''' Makes a pyassimp 'MaterialProperty' object for colour

        :param key: bytes object with name of key
        :param r,g,b,a: floating point values of RGBA colours
        '''
        mat_prop = structs.MaterialProperty()
        mat_prop.mSemantic = 0
        mat_prop.mIndex = 0
        mat_prop.mType = 1
        mat_prop.mDataLength = 16
        rgba_type = (ctypes.c_float * 4)
        col = rgba_type(r_val, g_val, b_val, a_val)
        mat_prop.mData = ctypes.cast(col, POINTER(ctypes.c_char))
        mat_prop.mKey = structs.String(len(key), key) # b'$clr.diffuse'
        return mat_prop


    def make_material(self, diffuse_colour):
        ''' Makes a material object with a certain diffuse colour
        :param diffuse_colour: tuple of floating point values (R,G,B,A)
        :returns pyassimp 'Material' object
        '''
        mat = structs.Material()
        mat.mNumProperties = 1
        mat.mNumAllocated = 1
        col_p = self.make_colour(b'$clr.diffuse', *diffuse_colour)
        col_pp = ctypes.pointer(col_p)
        col_ppp = ctypes.pointer(col_pp)
        mat.mProperties = col_ppp
        return mat

#  END OF AssimpKit CLASS
