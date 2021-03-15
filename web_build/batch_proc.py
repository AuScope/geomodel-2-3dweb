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
under the name '<model_name>.json'

The model source directory is set via GEOMODELS_HOME environment var or the command line
"""

import os
import shutil
import sys
import argparse
from multiprocessing import Pool

from model_conv import convert_model

# Optional destination directory for web asset files
DEST_DIR = ''

# Number of processes running in parallel
POOL_SZ = 3

# Directory where all the converted web asset files are kept
GEOMODELS_DIR = os.path.join(os.path.join(DEST_DIR), 'geomodels')

# Directory where all the model source files are kept
MODELS_SRC_DIR = None
if 'GEOMODELS_HOME' in os.environ:
    MODELS_SRC_DIR = os.environ['GEOMODELS_HOME']

# Prevents NetCDF file locking errors on NFS mounts
os.environ['HDF5_USE_FILE_LOCKING'] = 'FALSE'

# This is the list of models to be converted. 'URL string' is for future use.
# Format:
# [ (MODELS_SRC_DIR, GEOMODELS_DIR, <URL string>, <model_name>, <model input file>, <src_sub_dir>, <recreate_outdir> ), ... ]
#
# <src_sub_dir> is the subdirectory within 'MODELS_SRC_DIR' where the models source files live
# <URL string> is the name of the model as part of the model's URL
# <recreate_outdir> if True then will remove current output dir, if False then will skip processing if
#                   output dir exists
#
MODEL_DATA = [
    # Vic - Bendigo
    (MODELS_SRC_DIR, GEOMODELS_DIR, "bendigo", "Bendigo", "input/BendigoConvParam.json", "Victoria/Bendigo/3D_model_attributes", True),

    # Vic - Otway
    (MODELS_SRC_DIR, GEOMODELS_DIR, "otway", "Otway", "input/OtwayConvParam.json", "Victoria/otway", True),

    # Vic - Stavely
    (MODELS_SRC_DIR, GEOMODELS_DIR, "stavely", "Stavely", "input/StavelyConvParam.json", "Victoria/G154990_Stavely_3D_model_datapack/stavely_3D_model_datapack/GOCAD", True),

    # WA - Windimurra
    (MODELS_SRC_DIR, GEOMODELS_DIR, "windimurra", "Windimurra", "input/WindimurraConvParam.json",
     "WesternAust/Windimurra/3D_Windimurra_GOCAD/3D_Windimurra_GOCAD/GOCAD", True),

    # WA - Sandstone
    (MODELS_SRC_DIR, GEOMODELS_DIR, "sandstone", "Sandstone", "input/SandstoneConvParam.json", "WesternAust/Sandstone/3D_Sandstone_GOCAD/GOCAD", True),


    # SA - Cariewerloo
    (MODELS_SRC_DIR, GEOMODELS_DIR, "cariewerloo", "Cariewerloo", "input/CariewerlooConvParam.json", "SouthAust/GDP00005", True),

    # SA - Emmie Bluff
    (MODELS_SRC_DIR, GEOMODELS_DIR, "emmiebluff", "EmmieBluff", "input/EmmieBluffConvParam.json", "SouthAust/GDP00006/GocadObjects", True),

    # SA - Burra Mine
    (MODELS_SRC_DIR, GEOMODELS_DIR, "burramine", "BurraMine", "input/BurraMineConvParam.json", "SouthAust/GDP0008/BurraMineDVD/3D Models/Gocad", True),

    # SA - Central Flinders
    (MODELS_SRC_DIR, GEOMODELS_DIR, "centralflinders", "CentralFlinders", "input/CentralFlindersConvParam.json", "SouthAust/GDP00024", True),

    # SA - North Flinders
    (MODELS_SRC_DIR, GEOMODELS_DIR, "northflinders", "NorthFlinders", "input/NorthFlindersConvParam.json", "SouthAust/GDP00025", True),

    # SA - North Gawler
    (MODELS_SRC_DIR, GEOMODELS_DIR, "ngawler", "NorthGawler", "input/NorthGawlerConvParam.json", "SouthAust/GDP00026", True),

    # SA - Curnamona Sedimentary Basins
    (MODELS_SRC_DIR, GEOMODELS_DIR, "curnamonased", "CurnamonaSed", "input/CurnamonaSedConvParam.json", "SouthAust/GDP00033/CurnamonaSedimentaryBasins/Gocad", True),

    # SA - Western Gawler
    (MODELS_SRC_DIR, GEOMODELS_DIR, "westerngawler", "WesternGawler", "input/WesternGawlerConvParam.json", "SouthAust/GDP00067/Gocad objects", True),


    # Tas - Rosebery Lyell
    (MODELS_SRC_DIR, GEOMODELS_DIR, "rosebery", "RoseberyLyell", "input/RoseberyLyellConvParam.json", "Tasmania/RoseberyLyell", True),


    # QLD - Quamby
    (MODELS_SRC_DIR, GEOMODELS_DIR, "quamby", "Quamby", "input/QuambyConvParam.json", "Queensland/Quamby/Quamby/TSurf", True),

    # QLD - MtDore
    (MODELS_SRC_DIR, GEOMODELS_DIR, "mtdore", "MtDore", "input/MtDoreConvParam.json", "Queensland/MtDore/Model Objects", True),

    

    # NSW - "Western Tamworth Belt"
    (MODELS_SRC_DIR, GEOMODELS_DIR, "tamworth", "Tamworth", "input/WestTamworthConvParam.json", "NewSouthWales/WesternTamworth", True),

    # NSW - "Cobar geological and fault model package"
    (MODELS_SRC_DIR, GEOMODELS_DIR, "cobar", "Cobar", "input/CobarConvParam.json", "NewSouthWales/Cobar_GM_gocad_May18/Cobar_GM_gocad_May18", True),

    # NSW - "Curnamona Province and Delamerian Orogen 3D fault model"
    (MODELS_SRC_DIR, GEOMODELS_DIR, "curnamona", "Curnamona", "input/CurnamonaConvParam.json", "NewSouthWales/Curnamona_Delamerian_GDA94_Z54_GOCAD", True),

    # NSW - "Eastern Lachlan Orogen 3D fault model"
    (MODELS_SRC_DIR, GEOMODELS_DIR, "eastlachlan", "EastLachlan", "input/EastLachlanConvParam.json", "NewSouthWales/E_Lachlan_Orogen_GDA94_Z55_GOCAD", True),

    # NSW - "Western Lachlan Orogen and southern Thomson Orogen 3D fault model"
    (MODELS_SRC_DIR, GEOMODELS_DIR, "westlachlan", "WestLachlan", "input/WestLachlanConvParam.json", "NewSouthWales/W_Lachlan_Orogen_GDA94_Z55_GOCAD", True),

    # NSW - Southern New England Deep Crustal
    (MODELS_SRC_DIR, GEOMODELS_DIR, "sthnewengland", "SthNewEngland", "input/SthNewEnglandConvParam.json", "NewSouthWales/20150626_SNEO_Deep_Struture_SKUA", True),

    # NSW - "New England Orogen 3D fault model"
    (MODELS_SRC_DIR, GEOMODELS_DIR, "newengland", "NewEngland", "input/NewEnglandConvParam.json", "NewSouthWales/NEO_GDA94_Z56_GOCAD", True),

    # NT - McArthur Basin
    (MODELS_SRC_DIR, GEOMODELS_DIR, "mcarthur", "McArthurBasin", "input/McArthurBasinConvParam.json",
     "NorthernTerritory/McArthurBasin/DIP012/Digital_Data/REGIONAL_MODEL", True),


    # GA - North Qld
    (MODELS_SRC_DIR, GEOMODELS_DIR, "nqueensland", "NorthQueensland", "input/NorthQueenslandConvParam.json", "GA/North-Queensland", True),

    # GA - Tasmania
    (MODELS_SRC_DIR, GEOMODELS_DIR, "tas", "Tas", "input/TasConvParam.json", "GA/Tas", True),

    # GA - Yilgarn
    (MODELS_SRC_DIR, GEOMODELS_DIR, "yilgarn", "Yilgarn", "input/YilgarnConvParam.json", "GA/Yilgarn-NWS", True),


    # CSIRO - RockLea Dome
    (MODELS_SRC_DIR, GEOMODELS_DIR, "rocklea", "RockleaDome", "input/RockleaConvParam.json", "CSIRO/RockleaDome", True),

    # GA/NCI Stuart Shelf MT model
    (MODELS_SRC_DIR, GEOMODELS_DIR, "stuartshelf", "StuartShelf", "input/StuartShelfConvParam.json", "NCI/MT", True)
]


# MAIN PART OF PROGRAMME
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--model', nargs=6, dest="model", help='MODELS_SRC_DIR, GEOMODELS_DIR, urlStr, modelDirName, inConvFile, sDir')
    args = parser.parse_args()
    if args.model is None:
        if MODELS_SRC_DIR is None:
            print("Please set 'GEOMODELS_HOME' env var or use --models command line parameter")
            sys.exit(1)
        try:
            # Remove and recreate models dir
            if os.path.exists(GEOMODELS_DIR):
                print("Removing", GEOMODELS_DIR)
                shutil.rmtree(GEOMODELS_DIR)
            os.mkdir(GEOMODELS_DIR)

            # Run each conversion in parallel, number of parallel processes = POOL_SZ
            with Pool(POOL_SZ) as pool:
                print(pool.starmap(convert_model, MODEL_DATA))

        except OSError as exc:
            print("ERROR - ", repr(exc))
            sys.exit(1)
    else:
        MODELS_SRC_DIR, GEOMODELS_DIR, urlStr, modelDirName, inConvFile, srcSubDir = args.model
        # Run model conversion as a separate process
        convert_model(MODELS_SRC_DIR, GEOMODELS_DIR, urlStr, modelDirName, inConvFile, srcSubDir)

