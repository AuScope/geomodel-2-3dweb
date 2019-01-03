# Convert files from collada to GLTF v2
# by calling 'COLLADA2GLTF-bin' which is assumed to be available locally
# See https://github.com/KhronosGroup/COLLADA2GLTF/ for more information
#
import os
import glob

COLLADA2GLTF_BIN = os.path.join(os.environ['HOME'], 'github', 'COLLADA2GLTF', 'build')
''' Path where 'COLLADA2GLTF-bin' is located '''

REMOVE_COLLADA = True
''' Removes COLLADA file after conversion '''


def convert_dir(src_dir, file_mask="*.dae"):
    ''' Converts a directory of files from COLLADA to GLTF

    :param src_dir: directory of COLLADA files to be converted
    :param file_mask: optional file mask of files
    '''
    wildcard_str = os.path.join(src_dir, file_mask)
    daefile_list = glob.glob(wildcard_str)
    for daefile_str in daefile_list:
        convert_file(daefile_str)

def convert_file(daefile_str):
    ''' Converts a COLLADA file to GLTF
        will convert <file>_0 <file>_1 etc. if <file> does not exist

    :param daefile_str: filename to be converted
    '''
    if os.path.exists(daefile_str):
        convert_one_file(daefile_str)
    else:
        src_dir = os.path.dirname(daefile_str)
        fileName, fileExt = os.path.splitext(daefile_str)
        wildcard_str = os.path.join(src_dir, fileName+"_*.dae")
        collfile_list = glob.glob(wildcard_str)
        for collfile_str in collfile_list:
            convert_one_file(collfile_str)

def convert_one_file(daefile_str): 
    ''' Converts a COLLADA file to GLTF

    :param daefile_str: filename to be converted
    '''
    fileName, fileExt = os.path.splitext(daefile_str)
    cmd_str = os.path.join(COLLADA2GLTF_BIN, "COLLADA2GLTF-bin -i '"+daefile_str+"' -o '"+fileName+".gltf'")
    print(cmd_str)
    os.system(cmd_str)
    if REMOVE_COLLADA:
        print("Deleting ", daefile_str)
        os.remove(daefile_str)

