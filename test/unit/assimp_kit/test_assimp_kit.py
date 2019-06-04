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
        if bcd_bytes == b'{\n    "asset": {\n        "version": "2.0",\n        "generator": "Open Asset Import Library (assimp v4.1.942628830)"\n    },\n    "accessors": [\n        {\n            "bufferView": 0,\n            "byteOffset": 0,\n            "componentType": 5126,\n            "count": 49,\n            "type": "VEC3",\n            "max": [\n                547548.25,\n                5828591.5,\n                150.1703338623047\n            ],\n            "min": [\n                534302.625,\n                5814851.0,\n                -12376.2041015625\n            ]\n        },\n        {\n            "bufferView": 1,\n            "byteOffset": 0,\n            "componentType": 5125,\n            "count": 165,\n            "type": "SCALAR",\n            "max": [\n                26.0\n            ],\n            "min": [\n                0.0\n            ]\n        }\n    ],\n    "buffers": [\n        {\n            "byteLength": 1248,\n            "uri": "$blobfile.bin"\n        }\n    ],\n    "bufferViews": [\n        {\n            "buffer": 0,\n            "byteOffset": 0,\n            "byteLength": 588,\n            "target": 34962\n        },\n        {\n            "buffer": 0,\n            "byteOffset": 588,\n            "byteLength": 660,\n            "target": 34963\n        }\n    ],\n    "materials": [\n        {\n            "name": "material",\n            "pbrMetallicRoughness": {\n                "baseColorFactor": [\n                    1.0,\n                    0.6470588445663452,\n                    0.0,\n                    1.0\n                ],\n                "metallicFactor": 0.0\n            },\n            "doubleSided": true\n        }\n    ],\n    "meshes": [\n        {\n            "name": "FLT_UN48",\n            "primitives": [\n                {\n                    "mode": 4,\n                    "material": 0,\n                    "indices": 1,\n                    "attributes": {\n                        "POSITION": 0\n                    }\n                }\n            ]\n        }\n    ],\n    "nodes": [\n        {\n            "name": "root_node",\n            "children": [\n                1\n            ]\n        },\n        {\n            "name": "FLT_UN48_0",\n            "mesh": 0\n        }\n    ],\n    "scenes": [\n        {\n            "nodes": [\n                0\n            ]\n        }\n    ],\n    "scene": 0\n}':
            print(MSG, "PASS")
            sys.exit(0)
    print(MSG, "FAIL!!")
    sys.exit(1)
