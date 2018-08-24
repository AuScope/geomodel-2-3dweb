#!/usr/bin/env python3

from pyassimp import *
import ctypes


def print_scene(scene):
    print("\nSCENE START:", repr(scene))
    field_list = ['mAnimations', 'mCameras', 'mFlags', 'mLights', 'mMaterials', 'mMeshes', 'mNumAnimations', 'mNumCameras', 'mNumLights', 'mNumMaterials', 'mNumMeshes', 'mNumTextures', 'mRootNode', 'mTextures']
    for field in field_list:
        if getattr(scene, field, False):
            print(field, ':', getattr(scene, field))
            if field == 'mRootNode':
                print_node(scene.mRootNode.contents)
            elif field == 'mMeshes':
                for m_idx in range(scene.mNumMeshes):
                    print_mesh(scene.mMeshes[0][m_idx])
            elif field == 'mMaterials':
                for m_idx in range(scene.mNumMaterials):
                    print_materials(scene.mMaterials[0][m_idx])
    print("SCENE END\n")


def print_mesh(mesh):
    print("\nMESH START :", repr(mesh))
    field_list = ['mBitangents', 'mBones', 'mColors', 'mFaces', 'mMaterialIndex', 'mName', 'mNormals', 'mNumAnimMeshes', 'mNumBones', 'mNumFaces', 'mNumUVComponents', 'mNumVertices', 'mPrimitiveTypes', 'mTangents', 'mTextureCoords', 'mVertices']
    for field in field_list:
        if getattr(mesh, field, False):
            print(field, ':', getattr(mesh, field))
            if field == 'mFaces':
                for f_idx in range(mesh.mNumFaces):
                    print_faces(mesh.mFaces[f_idx])
            elif field == 'mVertices':
                print("\nVERTICES START")
                for v_idx in range(mesh.mNumVertices):
                    print_vertices(mesh.mVertices[v_idx])
                print("VERTICES END\n")
            elif field == 'mName':
                print("name:", mesh.mName.data)
            elif field == 'mColors':
                print_colours(mesh.mColors)
            elif field == 'mTextureCoords':
                print_texture(mesh.mTextureCoords)
            elif field == 'mNumUVComponents':
                print_uvcomponents(mesh.mNumUVComponents)

    print("MESH END\n")


def print_faces(face):
    print("\nFACE START:")
    for i_idx in range(face.mNumIndices):
        print(i_idx, ':  ', face.mIndices[i_idx])
    print("FACE END\n")


def print_vertices(vert):
    print("x:", vert.x, "y:", vert.y, "z:", vert.z)


def print_colours(col):
    print("\nCOLOURS START")
    for idx in range(8):
        if col[idx]:
            print(col[idx].contents.r, col[idx].contents.g, col[idx].contents.b, col[idx].contents.a)
    print("COLOURS END\n")


def print_texture(texture):
    print("\nTEXTURES START")
    for idx in range(8):
        if texture[idx]:
            print(texture[idx].contents.x, texture[idx].contents.y, texture[idx].contents.z)
    print("TEXTURES END\n")


def print_uvcomponents(comp):
    print("\nNUM UV COMPONENTS")
    for idx in range(8):
        print(idx, ':  ', comp[idx])
    print("END NUM UV COMPONENTS")

 
def print_node(node):
    print("\nNODE START:", repr(node))
    field_list = ['mChildren', 'mMeshes', 'mName', 'mNumChildren', 'mNumMeshes', 'mParent', 'mTransformation']
    for field in field_list:
        if getattr(node, field, False):
            print(field, ':', getattr(node, field))
            if field == 'mMeshes':
                for m_idx in range(node.mNumMeshes):
                    print("Mesh index: ", node.mMeshes[m_idx])
            elif field == 'mName':
                print("name: ", node.mName.data)
            elif field == 'mTransformation':
                print("transformation: ")
                print_matrix4x4(node.mTransformation)
            elif field == 'mChildren':
                print("CHILDREN START:")
                for ch_idx in range(node.mNumChildren):
                    print_node(node.mChildren[0][ch_idx])
                print("CHILDREN END\n")
    print("NODE END\n")


def print_materials(mat):
    print('\nMATERIALS START:', repr(mat))
    field_list = ['mNumAllocated', 'mNumProperties', 'mProperties']
    for field in field_list:
        if getattr(mat, field, False):
            print(field, ':', getattr(mat, field))
            if field == 'mProperties':
                for m_idx in range(mat.mNumProperties):
                    print_properties(mat.mProperties[0][m_idx])
    print("MATERIALS END\n")


def print_properties(prop):
    print('\nPROPERTIES START:', repr(prop))
    field_list = ['mData', 'mDataLength', 'mIndex', 'mKey', 'mSemantic', 'mType']
    for field in field_list:
        if getattr(prop, field, False):
            print(field, ':', getattr(prop, field))
            # if field == 'mData':
            #print('mData: ', prop.mData.contents.value)
    print('PROPERTIES END\n')


def print_matrix4x4(matrix):
    print('    ', matrix.a1, matrix.a2, matrix.a3, matrix.a4)
    print('    ', matrix.b1, matrix.b2, matrix.b3, matrix.b4)
    print('    ', matrix.c1, matrix.c2, matrix.c3, matrix.c4)
    print('    ', matrix.d1, matrix.d2, matrix.d3, matrix.d4)

