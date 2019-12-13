''' Converts files from collada to GLTF v2
   by calling 'COLLADA2GLTF-bin' which is assumed to be available locally
   See https://github.com/KhronosGroup/COLLADA2GLTF/ for more information
'''
import os
import glob
import subprocess

''' Path where 'COLLADA2GLTF-bin' is located '''
if 'COLLADA2GLTF_BIN' in os.environ:
    COLLADA2GLTF_BIN = os.environ['COLLADA2GLTF_BIN']
elif 'HOME' in os.environ:
    COLLADA2GLTF_BIN = os.path.join(os.environ['HOME'], 'github', 'COLLADA2GLTF', 'build')
else:
    COLLADA2GLTF_BIN = "."

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
        # pylint:disable=W0612
        file_name, file_ext = os.path.splitext(daefile_str)
        wildcard_str = os.path.join(src_dir, file_name+"_*.dae")
        collfile_list = glob.glob(wildcard_str)
        for collfile_str in collfile_list:
            convert_one_file(collfile_str)

def convert_one_file(daefile_str):
    ''' Converts a COLLADA file to GLTF

    :param daefile_str: filename to be converted
    '''
    collada_bin = os.path.join(COLLADA2GLTF_BIN, "COLLADA2GLTF-bin")
    if not os.path.exists(collada_bin):
        print("Cannot convert to .dae: 'COLLADA2GLTF_BIN' is not set correctly in", __name__, " nor as env var")
        return

    # pylint:disable=W0612
    file_name, file_ext = os.path.splitext(daefile_str)
    # COLLADA2GLTF does not like single filename without path as -o parameter
    file_name = os.path.abspath(file_name)
    cmd_list = [collada_bin, "-i", daefile_str, "-o", file_name+".gltf"]
    try:
        cmd_proc = subprocess.run(cmd_list)
    except OSError as os_exc:
        print("Cannot execute COLLADA2GLTF: ", os_exc)
    else:
        if cmd_proc.returncode != 0:
            print("Conversion from COLLADA to GLTF failed: return code=", str(cmd_proc.returncode))
        elif REMOVE_COLLADA:
            print("Deleting ", daefile_str)
        os.remove(daefile_str)
