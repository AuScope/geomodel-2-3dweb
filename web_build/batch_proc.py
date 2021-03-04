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

# Prevents NetCDF file locking errors on NFS mounts
os.environ['HDF5_USE_FILE_LOCKING'] = 'FALSE'

# This is the list of models to be converted. 'URL string' is for future use.
# Format:
# [ ( <URL string>, <model_name>, <model input file>, <src_sub_dir>, <recreate_outdir> ), ... ]
#
# <src_sub_dir> is the subdirectory within 'MODELS_SRC_DIR' where the models source files live
#
MODEL_DATA = [
    # Vic - Bendigo
    ("bendigo", "Bendigo", "input/BendigoConvParam.json", "Victoria/Bendigo/3D_model_attributes", False),

    # Vic - Otway
    ("otway", "Otway", "input/OtwayConvParam.json", "Victoria/otway", False),

    # Vic - Stavely
    ("stavely", "Stavely", "input/StavelyConvParam.json", "Victoria/G154990_Stavely_3D_model_datapack/stavely_3D_model_datapack/GOCAD", False),

    # WA - Windimurra
    ("windimurra", "Windimurra", "input/WindimurraConvParam.json",
     "WesternAust/Windimurra/3D_Windimurra_GOCAD/3D_Windimurra_GOCAD/GOCAD", False),

    # WA - Sandstone
    ("sandstone", "Sandstone", "input/SandstoneConvParam.json", "WesternAust/Sandstone/3D_Sandstone_GOCAD/GOCAD", False),


    # SA - Cariewerloo
    ("cariewerloo", "Cariewerloo", "input/CariewerlooConvParam.json", "SouthAust/GDP00005", False),

    # SA - Emmie Bluff
    ("emmiebluff", "EmmieBluff", "input/EmmieBluffConvParam.json", "SouthAust/GDP00006/GocadObjects", True),

    # SA - Burra Mine
    ("burramine", "BurraMine", "input/BurraMineConvParam.json", "SouthAust/GDP0008/BurraMineDVD/3D Models/Gocad", True),

    # SA - Central Flinders
    ("centralflinders", "CentralFlinders", "input/CentralFlindersConvParam.json", "SouthAust/GDP00024", True),

    # SA - North Flinders
    ("northflinders", "NorthFlinders", "input/NorthFlindersConvParam.json", "SouthAust/GDP00025", True),

    # SA - North Gawler
    ("ngawler", "NorthGawler", "input/NorthGawlerConvParam.json", "SouthAust/GDP00026", False),

    # SA - Curnamona Sedimentary Basins
    ("curnamonased", "CurnamonaSed", "input/CurnamonaSedConvParam.json", "SouthAust/GDP00033/CurnamonaSedimentaryBasins/Gocad", True),

    # SA - Western Gawler
    ("westerngawler", "WesternGawler", "input/WesternGawlerConvParam.json", "SouthAust/GDP00067/Gocad objects", True),


    # Tas - Rosebery Lyell
    ("rosebery", "RoseberyLyell", "input/RoseberyLyellConvParam.json", "Tasmania/RoseberyLyell", False),


    # QLD - Quamby
    ("quamby", "Quamby", "input/QuambyConvParam.json", "Queensland/Quamby/Quamby/TSurf", False),

    # QLD - MtDore
    ("mtdore", "MtDore", "input/MtDoreConvParam.json", "Queensland/MtDore/Model Objects", True),

    

    # NSW - "Western Tamworth Belt"
    ("tamworth", "Tamworth", "input/WestTamworthConvParam.json", "NewSouthWales/WesternTamworth", False),

    # NSW - "Cobar geological and fault model package"
    ("cobar", "Cobar", "input/CobarConvParam.json", "NewSouthWales/Cobar_GM_gocad_May18/Cobar_GM_gocad_May18", True),

    # NSW - "Curnamona Province and Delamerian Orogen 3D fault model"
    ("curnamona", "Curnamona", "input/CurnamonaConvParam.json", "NewSouthWales/Curnamona_Delamerian_GDA94_Z54_GOCAD", True),

    # NSW - "Eastern Lachlan Orogen 3D fault model"
    ("eastlachlan", "EastLachlan", "input/EastLachlanConvParam.json", "NewSouthWales/E_Lachlan_Orogen_GDA94_Z55_GOCAD", True),

    # NSW - "Western Lachlan Orogen and southern Thomson Orogen 3D fault model"
    ("westlachlan", "WestLachlan", "input/WestLachlanConvParam.json", "NewSouthWales/W_Lachlan_Orogen_GDA94_Z55_GOCAD", True),

    # NSW - Southern New England Deep Crustal
    ("sthnewengland", "SthNewEngland", "input/SthNewEnglandConvParam.json", "NewSouthWales/20150626_SNEO_Deep_Struture_SKUA", True),

    # NSW - "New England Orogen 3D fault model"
    ("newengland", "NewEngland", "input/NewEnglandConvParam.json", "NewSouthWales/NEO_GDA94_Z56_GOCAD", True),

    # NT - McArthur Basin
    ("mcarthur", "McArthurBasin", "input/McArthurBasinConvParam.json",
     "NorthernTerritory/McArthurBasin/DIP012/Digital_Data/REGIONAL_MODEL", False),


    # GA - North Qld
    ("nqueensland", "NorthQueensland", "input/NorthQueenslandConvParam.json", "GA/North-Queensland", False),

    # GA - Tasmania
    ("tas", "Tas", "input/TasConvParam.json", "GA/Tas", False),

    # GA - Yilgarn
    ("yilgarn", "Yilgarn", "input/YilgarnConvParam.json", "GA/Yilgarn-NWS", False),


    # CSIRO - RockLea Dome
    ("rocklea", "RockleaDome", "input/RockleaConvParam.json", "CSIRO/RockleaDome", True),

    # GA/NCI Stuart Shelf MT model
    ("stuartshelf", "StuartShelf", "input/StuartShelfConvParam.json", "NCI/MT", True)
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

            for urlStr, modelDirName, inConvFile, srcSubDir, recreateOutDir in MODEL_DATA:
                # Run model conversion as a separate process
                convert_model(MODELS_SRC_DIR, GEOMODELS_DIR, urlStr, modelDirName, inConvFile, srcSubDir, recreateOutDir)

        except OSError as exc:
            print("ERROR - ", repr(exc))
            sys.exit(1)
    else:
        MODELS_SRC_DIR, GEOMODELS_DIR, urlStr, modelDirName, inConvFile, srcSubDir = args.model
        # Run model conversion as a separate process
        convert_model(MODELS_SRC_DIR, GEOMODELS_DIR, urlStr, modelDirName, inConvFile, srcSubDir)

