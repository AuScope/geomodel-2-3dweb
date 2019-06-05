#!/usr/bin/env python3
import sys
import os
import ctypes
from logging import ERROR

# Add in path to local library files
sys.path.append(os.path.join('..', '..', '..', 'scripts'))

from lib.imports.gocad.gocad_importer import GocadImporter
from lib.exports.assimp_kit import AssimpKit

import lib.exports.print_assimp as pa

if __name__ == "__main__":
    MSG = "\nTest assimp_kit GOCAD TS file conversion:"
    gocad_obj = GocadImporter(ERROR, base_xyz=(0.0, 0.0, 0.0),
                              nondefault_coords=False)
    src_dir = 'drag_and_drop'
    filename_str = 'otway_test.ts'
    with open(filename_str) as file_p:
        file_lines = file_p.readlines()

    # First convert GOCAD to GSM
    is_ok, gsm_list = gocad_obj.process_gocad(src_dir, filename_str, file_lines)
    if is_ok and gsm_list:
        # Then, output GSM as GLTF ...
        gsm_obj = gsm_list[0]
        geom_obj, style_obj, metadata_obj = gsm_obj
        assimp_obj = AssimpKit(ERROR)
        assimp_obj.start_scene()
        assimp_obj.add_geom(geom_obj, style_obj, metadata_obj)
        blob_obj = assimp_obj.end_scene("")
        bcd = ctypes.cast(blob_obj.contents.data, ctypes.POINTER(blob_obj.contents.size * ctypes.c_char))
        bcd_bytes = b''
        for byt in bcd.contents:
            bcd_bytes += byt
        test_str = bcd_bytes.decode('utf-8')
        with open('golden.v4.1.0.json') as fp:
            golden_lines = fp.readlines()
        golden_str = ''.join(golden_lines)
        if golden_str.rstrip('\n') == test_str.rstrip('\n'):
            print(MSG, "PASS")
            sys.exit(0)
    print(test_str)
    print()
    print(golden_str)
    print(MSG, "FAIL!!")
    sys.exit(1)
