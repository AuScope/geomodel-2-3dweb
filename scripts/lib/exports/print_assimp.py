'''
Functions used to print out "assimp" (https://github.com/assimp/assimp) data structures,
used for debugging purposes
'''
import ctypes
# from pyassimp import *

def print_scene(scene):
    ''' Prints out the entire scene contained in the assimp data structure
        :param scene: assimp scene object
    '''
    print("\nSCENE START:", repr(scene))
    field_list = ['mNumAnimations', 'mAnimations', 'mNumCameras', 'mCameras', 'mFlags',
                  'mNumLights', 'mLights', 'mNumMaterials', 'mMaterials', 'mNumMeshes',
                  'mMeshes', 'mNumTextures', 'mTextures', 'mRootNode']
    for field in field_list:
        if getattr(scene, field, False) is not False:
            print(field, ':', getattr(scene, field))
            if field == 'mRootNode':
                print_node(scene.mRootNode.contents)
            elif field == 'mMeshes':
                for m_idx in range(scene.mNumMeshes):
                    print_mesh(scene.mMeshes[m_idx].contents)
            elif field == 'mMaterials':
                for m_idx in range(scene.mNumMaterials):
                    print_materials(scene.mMaterials[m_idx].contents)
        else:
            print("field ?", field)
    print("SCENE END\n")


def print_mesh(mesh):
    ''' Prints out an assimp mesh object
        :param mesh: assimp mesh object
    '''
    print("\nMESH START :", repr(mesh))
    field_list = ['mBitangents', 'mBones', 'mColors', 'mFaces', 'mMaterialIndex', 'mName',
                  'mNormals', 'mNumAnimMeshes', 'mNumBones', 'mNumFaces', 'mNumUVComponents',
                  'mNumVertices', 'mPrimitiveTypes', 'mTangents', 'mTextureCoords', 'mVertices',
                  'mTextureCoordsNames']
    for field in field_list:
        if getattr(mesh, field, False) is not False:
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
            elif field == 'mTextureCoordsNames':
                print("IF NULL should be false: ", bool(mesh.mTextureCoordsNames))

    print("MESH END\n")


def print_faces(face):
    ''' Prints out an assimp face object
        :param face: assimp face object
    '''
    print("\nFACE START:")
    for i_idx in range(face.mNumIndices):
        print(i_idx, ':  ', face.mIndices[i_idx])
    print("FACE END\n")


def print_vertices(vert):
    ''' Prints out the XYZ coords of a vertex object
    '''
    print("x:", vert.x, "y:", vert.y, "z:", vert.z)


def print_colours(col_list):
    ''' Prints out the RGBA colours in a colour list
        :param col_list: list of eight colours
    '''
    print("\nCOLOURS START")
    for idx in range(8):
        if col_list[idx]:
            print(col_list[idx].contents.r, col_list[idx].contents.g, col_list[idx].contents.b,
                  col_list[idx].contents.a)
    print("COLOURS END\n")


def print_texture(texture):
    ''' Prints out an assimp texture object
        :param texture: texture object
    '''
    print("\nTEXTURES START")
    for idx in range(8):
        if texture[idx]:
            print(texture[idx].contents.x, texture[idx].contents.y, texture[idx].contents.z)
    print("TEXTURES END\n")


def print_uvcomponents(comp):
    ''' Prints out a list of eight assimp UV component objects
        :param comp: UV component object
    '''
    print("\nNUM UV COMPONENTS")
    for idx in range(8):
        print(idx, ':  ', comp[idx])
    print("END NUM UV COMPONENTS")


def print_node(node):
    ''' Prints out an assimp node object
        :param node: assimp node object
    '''
    print("\nNODE START:", repr(node))
    field_list = ['mChildren', 'mMeshes', 'mName', 'mNumChildren',
                  'mNumMeshes', 'mParent', 'mTransformation']
    for field in field_list:
        if getattr(node, field, False) is not False:
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
                    print_node(node.mChildren[ch_idx].contents)
                print("CHILDREN END\n")
    print("NODE END\n")


def print_materials(mat):
    ''' Prints out an assimp materials object
        :param mat: assimp materials object
    '''
    print('\nMATERIALS START:', repr(mat))
    field_list = ['mNumAllocated', 'mNumProperties', 'mProperties']
    for field in field_list:
        if getattr(mat, field, False) is not False:
            print(field, ':', getattr(mat, field))
            if field == 'mProperties':
                for m_idx in range(mat.mNumProperties):
                    print_properties(mat.mProperties[m_idx].contents)
    print("MATERIALS END\n")


def print_properties(prop):
    ''' Prints out assimp properties
        :param prop: assimp properties object
    '''
    print('\nPROPERTIES START:', repr(prop))
    field_list = ['mDataLength', 'mIndex', 'mKey', 'mSemantic', 'mType']
    for field in field_list:
        if field == 'mKey':
            print('mKey: ', prop.mKey.data)
        elif getattr(prop, field, False) is not False:
            print(field, ':', getattr(prop, field))
    # Float
    if prop.mType == 1:
        arr_len = int(prop.mDataLength/4)
        flt_ptr = ctypes.cast(prop.mData, ctypes.POINTER(ctypes.c_float * arr_len))
        print("Values: ", end='')
        for idx in range(arr_len):
            print(flt_ptr.contents[idx], ' ', end='')
        print()

    # Double
    elif prop.mType == 2:
        arr_len = int(prop.mDataLength/8)
        dbl_ptr = ctypes.cast(prop.mData, ctypes.POINTER(ctypes.c_double * arr_len))
        print("Values: ", end='')
        for idx in range(arr_len):
            print(dbl_ptr.contents[idx], ' ', end='')
        print()

    # String
    elif prop.mType == 3:
        # pylint: disable=C0111, R0903
        class StringTyp(ctypes.Structure):
            _fields_ = [("len", ctypes.c_int), ("value", ctypes.c_char * prop.mDataLength)]
        str_ptr = ctypes.cast(prop.mData, ctypes.POINTER(StringTyp))
        print("Values", str_ptr.contents.len, str_ptr.contents.value)

    # 32-bit integer
    elif prop.mType == 4:
        arr_len = int(prop.mDataLength/4)
        int_ptr = ctypes.cast(prop.mData, ctypes.POINTER(ctypes.c_uint * arr_len))
        print("Values: ", end='')
        for idx in range(arr_len):
            print(int_ptr.contents[idx], ' ', end='')
        print()

    # Binary buffer
    elif prop.mType == 5:
        bstr_ptr = ctypes.cast(prop.mData, ctypes.POINTER(ctypes.c_char * prop.mDataLength))
        print("Values: ", end='')
        for idx in range(prop.mDataLength):
            print(bstr_ptr.contents[idx], ' ', end='')
        print()

    # Unknown
    else:
        print("WARNING: Unknown property type")
    print('PROPERTIES END\n')


def print_matrix4x4(matrix):
    ''' Prints out a 4x4 matrix
        :param matrix: matrix object with attributes a1,a2,a3,a4, b1,b2 ...
    '''
    print('    ', matrix.a1, matrix.a2, matrix.a3, matrix.a4)
    print('    ', matrix.b1, matrix.b2, matrix.b3, matrix.b4)
    print('    ', matrix.c1, matrix.c2, matrix.c3, matrix.c4)
    print('    ', matrix.d1, matrix.d2, matrix.d3, matrix.d4)

def print_blob(blob):
    ''' Prints a binary blob object
        :param blob: binary blob object
    '''
    cntr = 0
    while cntr < 10000:
        print("blob =", blob)
        print("blob.contents =", blob.contents)
        print("blob.contents.size =", blob.contents.size)
        bcd = ctypes.cast(blob.contents.data, ctypes.POINTER(blob.contents.size * ctypes.c_char))
        bcd_bytes = b''
        for byt in bcd.contents:
            bcd_bytes += byt
        print("blob.contents.data = ", bcd_bytes)
        print("blob.contents.name.data =", blob.contents.name.data)
        print("blob.contents.next =", blob.contents.next)
        if not blob.contents.next:
            break
        blob = blob.contents.next
        cntr += 1
    print()
