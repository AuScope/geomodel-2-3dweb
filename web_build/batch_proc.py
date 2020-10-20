#!/usr/bin/env python3
"""
A simple program to run conversions from GOCAD to GLTF, PNG etc.
for a number of models.
Each model has a source dir (MODELS_SRC_DIR + <src_dir>), where the
GOCAD files reside. Within the source dir there is an 'output' dir
which holds the converted files.
Once the conversion of a model is complete, the files in the 'output' dir
are copied to the 'geomodels' directory in DEST_DIR, into a <model_name>
directory. The model's config file is copied to the 'geomodels' directory,
under the name '<model_name>_new.json'
"""

import os
import shutil
import sys
import argparse

from model_conv import convert_model

DEST_DIR = ''

MODELS_SRC_DIR = os.path.join(os.environ['HOME'], 'GEO_MODELS')

# This is the list of models to be converted. 'URL string' is for future use.
# Format:
# [ ( <URL string>, <model_name>, <model input file>, <src_dir> ), ... ]
#
MODELS = [
    # Vic - Otway
    ("otway", "Otway", "input/OtwayConvParam.json", "Victoria/otway"),

    # WA - Windimurra
    ("windimurra", "Windimurra", "input/WindimurraConvParam.json",
     "WesternAust/Windimurra/3D_Windimurra_GOCAD/3D_Windimurra_GOCAD/GOCAD"),

    # WA - Sandstone
    ("sandstone", "Sandstone", "input/SandstoneConvParam.json",
     "WesternAust/Sandstone/3D_Sandstone_GOCAD/GOCAD"),

    # SA - North Gawler
    ("ngawler", "NorthGawler", "input/NorthGawlerConvParam.json", "SouthAust/GDP00026"),

    # Tas - Rosebery Lyell
    ("rosebery", "RoseberyLyell", "input/RoseberyLyellConvParam.json", "Tasmania/RoseberyLyell"),

    # QLD - Quamby
    ("quamby", "Quamby", "input/QuambyConvParam.json", "Queensland/Quamby/Quamby/TSurf"),

    # NSW - West Tamworth
    ("tamworth", "Tamworth", "input/WestTamworthConvParam.json", "NewSouthWales/WesternTamworth"),

    # NT - McArthur Basin
    ("mcarthur", "McArthurBasin", "input/McArthurBasinConvParam.json",
     "NorthernTerritory/McArthurBasin/DIP012/Digital_Data/REGIONAL_MODEL"),

    # GA - North Qld
    ("nqueensland", "NorthQueensland", "input/NorthQueenslandConvParam.json",
     "GA/North-Queensland"),

    # GA - Tasmania
    ("tas", "Tas", "input/TasConvParam.json", "GA/Tas"),

    # GA - Yilgarn
    ("yilgarn", "Yilgarn", "input/YilgarnConvParam.json", "GA/Yilgarn-NWS"),

    ## CSIRO - RockLea Dome
    #("rocklea", "Rocklea Dome", "input/RockleaConvParam.json", "CSIRO/RockleaDome")
]


# MAIN PART OF PROGRAMME
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--model', nargs=6, dest="model", help='MODELS_SRC_DIR, GEOMODELS_DIR, urlStr, modelDirName, inConvFile, sDir')
    args = parser.parse_args()
    if args.model is None:
        try:
            GEOMODELS_DIR = os.path.join(os.path.join(DEST_DIR), 'geomodels')

            # Remove and recreate models dir
            if os.path.exists(GEOMODELS_DIR):
                print("Removing", GEOMODELS_DIR)
                shutil.rmtree(GEOMODELS_DIR)
            os.mkdir(GEOMODELS_DIR)

            for urlStr, modelDirName, inConvFile, sDir in MODELS:
                convert_model(MODELS_SRC_DIR, GEOMODELS_DIR, urlStr, modelDirName, inConvFile, sDir)

        except OSError as exc:
            print("ERROR - ", repr(exc))
            sys.exit(1)
    else:
        MODELS_SRC_DIR, GEOMODELS_DIR, urlStr, modelDirName, inConvFile, sDir = args.model
        convert_model(MODELS_SRC_DIR, GEOMODELS_DIR, urlStr, modelDirName, inConvFile, sDir)

