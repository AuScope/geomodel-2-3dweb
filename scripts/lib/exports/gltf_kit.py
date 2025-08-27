"""
Contains the GltfKit class
"""

import sys
import logging
import ctypes

import numpy as np
np.set_printoptions(threshold=sys.maxsize)

import pygltflib
from pygltflib import BufferFormat

from lib.exports.geometry_gen import colour_borehole_gen, tri_gen
from lib.exports.export_kit import ExportKit


class GltfKit(ExportKit):
    ''' Class used to export geometries
    '''

    FILE_EXT = '.gltf'
    ''' Extension of file
    '''

    def __init__(self, debug_level):
        ''' Initialise class

        :param debug_level: debug level taken from python's 'logging' module
        '''
        # Call parent class
        ExportKit.__init__(self, debug_level)

        # Initialise
        self.start_scene()


    def start_scene(self):
        ''' Initiate scene creation, only one scene can be created at a time
        '''
        self.logger.debug("\n\nstart_scene() !!")
        self.nodes = []
        self.meshes =  []
        self.accessors = []
        self.bufferViews = []
        self.materials = []
        self.mesh_cnt = 0
        self.max_ind = -1
        self.binary_blob = b''     
        self.first_accessor = False

    def add_mesh(self, points: list[list[int]], triangles: list[list[float]], colour: list[float]):
        '''
        :param points: list of points [x, y, z] - short int
        :param triangles: list of triangles [v1, v2, v3] - floats
        :param colour: [red, green, blue, alpha] - floats
        '''
        # Calculate current max index
        for triples in triangles:
            for idx in triples:
                if self.max_ind < idx:
                    self.max_ind = idx
        self.logger.debug(f"{self.max_ind=}")

        np_triangles = np.array(triangles, dtype="uint16")
        triangles_binary_blob = np_triangles.flatten().tobytes()
        np_points = np.array(points, dtype="float32")
        points_binary_blob = np_points.tobytes()
        self.logger.debug(f"@@ {np_triangles=}")
        self.logger.debug(f"@@ {np_points=}")
        self.logger.debug(f"@@ {colour=}")

        self.nodes.append(pygltflib.Node(mesh=self.mesh_cnt))
        self.meshes.append(
            pygltflib.Mesh(
                primitives=[
                    pygltflib.Primitive(
                        attributes=pygltflib.Attributes(POSITION=self.mesh_cnt + 1), # Positions are at this accessor 
                        mode=pygltflib.TRIANGLES, # Expect triangles
                        indices=0, # Indices are at this accessor
                        material=self.mesh_cnt # Index to material
                    )
                ]
            )
        )
        if not self.first_accessor:
            # Only need one of these
            self.accessors.append(
                pygltflib.Accessor(
                    bufferView=0,
                    componentType=pygltflib.UNSIGNED_SHORT,
                    count=np_triangles.size,
                    type=pygltflib.SCALAR,
                    max=[int(np_triangles.max())],
                    min=[int(np_triangles.min())],
                )
            )

        self.accessors.append(
            pygltflib.Accessor(
                bufferView=self.mesh_cnt + 1,
                componentType=pygltflib.FLOAT,
                count=len(np_points),
                type=pygltflib.VEC3,
                max=np_points.max(axis=0).tolist(),
                min=np_points.min(axis=0).tolist(),
           )
        )
        if not self.first_accessor:
            # Only need one of these
            self.bufferViews.append(
                # Buffer of indices that form triangles
                pygltflib.BufferView(
                    buffer=0, # Only one buffer
                    byteOffset=len(self.binary_blob),
                    byteLength=len(triangles_binary_blob),
                    target=pygltflib.ELEMENT_ARRAY_BUFFER,
                )
            )
            self.first_accessor = True

        self.binary_blob += triangles_binary_blob
        self.bufferViews.append(
            # Buffer of 3d points
            pygltflib.BufferView(
                buffer=0, # Only one buffer
                byteOffset=len(self.binary_blob),
                byteLength=len(points_binary_blob),
                target=pygltflib.ARRAY_BUFFER,
            )
        )
        self.binary_blob += points_binary_blob

        # Add coloured material
        self.materials.append(
            pygltflib.Material(
                pbrMetallicRoughness = pygltflib.PbrMetallicRoughness(
                    # Set colour
                    baseColorFactor = colour,
                    # Set up for no hard reflections
                    metallicFactor = 0.0,
                    roughnessFactor = 1.0
                ),
                emissiveFactor = [0.0, 0.0, 0.0],
                alphaMode = None,
                alphaCutoff = None,
                # Double sided
                doubleSided = True
            )
        )
        self.mesh_cnt += 1
         

    def add_geom(self, geom_obj, style_obj, meta_obj):
        ''' Add a geometry to the scene. It only does triangular meshes for the moment.
        Will be expanded to include other types.

        :param geom_obj: ModelGeometries object
        :param style_obj: STYLE object
        :param meta_obj: METADATA object
        '''
        if geom_obj.is_trgl():
            rgba_colour = style_obj.get_rgba_tup(def_rand=True)
            mesh_gen = tri_gen(geom_obj.trgl_arr, geom_obj.vrtx_arr, meta_obj.name)
            for vert_list, indices, mesh_name in mesh_gen:
                indices = [[idx+self.max_ind+1 for idx in triples] for triples in indices]
                self.add_mesh(vert_list, indices, rgba_colour)
        else:
            self.logger.warning('GltfKit cannot convert point or line geometries')


    def end_scene(self, out_filename: str) -> object | bool:
        ''' Called after geometries have all been added to scene and a file or blob should be created

        :param out_filename: filename and path of output file, without file extension \
                             if an empty string, then a blob is returned and a file is not created
        :returns: True if file was written out, else returns the GLTF as a blob object
        '''
        gltf = pygltflib.GLTF2(
            scene=0,
            scenes=[pygltflib.Scene(nodes=list(range(len(self.nodes))))],
            nodes=self.nodes,
            meshes=self.meshes,
            accessors=self.accessors,
            bufferViews=self.bufferViews,
            buffers=[
                pygltflib.Buffer(
                    byteLength=len(self.binary_blob)
                )
            ],
            materials=self.materials,
        )
        gltf.set_binary_blob(self.binary_blob)
        gltf.convert_buffers(BufferFormat.DATAURI)   # Save buffers inside GLTF
        if out_filename != '':
            gltf.save(out_filename + ".gltf")
            return True
        return gltf.gltf_to_json()


    def write_borehole(self, base_vrtx: list[float], borehole_name: str, colour_info_dict, height_reso: float,
                             out_filename=''):
        ''' Write out a file or blob of a borehole stick
            if 'out_filename' is supplied then writes a file and returns True/False
            else returns a pointer to a 'structs.ExportDataBlob' object

        :param base_vrtx: base vertex, position of the object within the model [x,y,z]
        :param borehole_name: name of borehole
        :param colour_info_dict: dict of colour info; key - depth, float, val {'colour':(R,B,G,A), \
                                            'classText': mineral name }, where R,G,B,A are floats
        :param height_reso: height resolution for colour info dict
        :param out_filename: optional destination directory+file (without extension), \
                             where file is written
        '''
        self.logger.debug(f"write_borehole({base_vrtx=}, {out_filename=}, {borehole_name=}, {colour_info_dict=})")

        self.start_scene()

        cb_gen = colour_borehole_gen(base_vrtx, borehole_name, colour_info_dict, height_reso)
        for vert_list, indices, colour_idx, depth, rgba_colour, class_dict, mesh_name in cb_gen:
            self.logger.debug(f"{vert_list=}")
            self.logger.debug(f"{rgba_colour=}")
            self.logger.debug(f"adding 1+{self.max_ind=}")
            # Add max index + 1  to current set of indices
            indices = [[idx+self.max_ind+1 for idx in triples] for triples in indices]
            self.add_mesh(vert_list, indices, rgba_colour)
        self.logger.debug(f"... write_borehole({borehole_name=}) DONE")
        return self.end_scene(out_filename)


#  END OF GltfKit CLASS
