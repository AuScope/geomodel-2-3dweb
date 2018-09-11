#!/usr/bin/env python3

from pyassimp import *
import ctypes

from db.geometry.model_geometries import *

import exports.print_assimp as pa


def make_nodes(s):
    n = structs.Node()
    n.mTransformation = structs.Matrix4x4(1.0, 0.0, 0.0, 0.0,  0.0, 1.0, 0.0, 0.0,  0.0, 0.0, 1.0, 0.0,  0.0, 0.0, 0.0, 1.0)
    n.mMetadata = None
    n.mName.data = b'defaultobject'
    n.mName.length = 13
    n_ch = structs.Node()
    n_ch.mTransformation = structs.Matrix4x4(1.0, 0.0, 0.0, 0.0,  0.0, 1.0, 0.0, 0.0,  0.0, 0.0, 1.0, 0.0,  0.0, 0.0, 0.0, 1.0)
    n_ch.mNumMeshes = 1
    n_ch.mMeshes = ctypes.pointer(ctypes.c_uint(0))
    n_ch.mName.length = 13
    n_ch.mName.data = b'defaultobject'
    n_ch.mParent = ctypes.pointer(n)
    
    n_ch_p = ctypes.pointer(n_ch)
    n_ch_pp = ctypes.pointer(n_ch_p)
    n.mChildren  = n_ch_pp
    n.mNumChildren = 1
    
    np = ctypes.pointer(n)
    s.mRootNode = np
    

def make_meshes(s):
    NUM_FACES = 3
    m = structs.Mesh()
    mp = ctypes.pointer(m)
    mpp = ctypes.pointer(mp)

    s.mMeshes = mpp
    s.mNumMeshes = 1

    f_arr = (structs.Face * NUM_FACES)()
    f_arr_p = ctypes.cast(f_arr, ctypes.POINTER(structs.Face))

    s.mMeshes[0][0].mNumFaces = NUM_FACES 
    s.mMeshes[0][0].mFaces = f_arr_p
    s.mMeshes[0][0].mPrimitiveTypes = 4  # Triangle
    s.mMeshes[0][0].mName.length = 13
    s.mMeshes[0][0].mName.data = b'defaultobject'

    for f_idx in range(NUM_FACES):
        i_arr = (ctypes.c_uint * NUM_FACES)()
        i_arr[0] = 0+NUM_FACES*f_idx
        i_arr[1] = 1+NUM_FACES*f_idx
        i_arr[2] = 2+NUM_FACES*f_idx
        i_arr_p = ctypes.cast(i_arr, ctypes.POINTER(ctypes.c_uint))
        f_arr[f_idx].mIndices = i_arr_p
        f_arr[f_idx].mNumIndices = 3


def make_vertices(s):
    NUM_VERTICES = 9
    v_arr = (structs.Vector3D * NUM_VERTICES)()
    v_arr_p = ctypes.cast(v_arr, ctypes.POINTER(structs.Vector3D))

    s.mMeshes[0][0].mVertices = v_arr_p

    v_arr_vals = [[0., 0., 0.], [0., 2., 0.], [2., 0., 0.], [0., 0., 0.], [2., 0., 0.], [0., 0., 2.],
                  [0., 0., 0.], [0., 0., 2.], [0., 2., 0.]]
    
    for v_idx in range(NUM_VERTICES):
        v_arr[v_idx] = structs.Vector3D(v_arr_vals[v_idx][0], v_arr_vals[v_idx][1], v_arr_vals[v_idx][2])

    s.mMeshes[0][0].mNumVertices = NUM_VERTICES


def make_materials(s):
    NUM_MATERIALS = 1
    NUM_PROPERTIES = 1

    m = structs.Material()
    mp = ctypes.pointer(m)
    mpp = ctypes.pointer(mp)
    s.mMaterials = mpp
    s.mNumMaterials = NUM_MATERIALS
    m.mNumProperties = NUM_PROPERTIES
    m.mNumAllocated = 0
    p = structs.MaterialProperty()
    pp = ctypes.pointer(p)
    ppp = ctypes.pointer(pp)
    m.mProperties = ppp

def init_scene(s):
    s.mMetadata = None
    
 
if __name__ == "__main__":

    s = structs.Scene()

    init_scene(s)

    make_meshes(s)
    make_vertices(s)
    make_nodes(s)
    make_materials(s)

    #pa.print_scene(s)


    print("\nCreating GLTF")
    export(s, "home_made_test.gltf", "gltf2")

    #scene = load('tetra.obj')
    pa.print_scene(scene)

    #assert len(scene.mMeshes)
    #mesh = scene.mMeshes[0]

    #assert len(mesh.vertices)
    #print(mesh.vertices[0])

    #export(scene, "tetra.gltf", "gltf2")

    ## don't forget this one, or you will leak!
    #release(scene)
