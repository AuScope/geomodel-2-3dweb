#!/usr/bin/env python3

import os
import shutil
import subprocess
import sys

#
# A simple program to run conversions from GOCAD to GLTF, PNG etc. 
# for a number of models. 
#
# Each model has a source dir (MODELS_SRC_DIR + <src_dir>), where the
# GOCAD files reside. Within the source dir there is an 'output' dir
# which holds the converted files.
# Once the conversion of a model is complete, the files in the 'output' dir
# are copied to the 'geomodels' directory in DEST_DIR, into a <model_name>
# directory. The model's config file is copied to the 'geomodels' directory,
# under the name '<model_name>_new.json'
#
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
("windimurra", "Windimurra", "input/WindimurraConvParam.json", "WesternAust/Windimurra/3D_Windimurra_GOCAD/3D_Windimurra_GOCAD/GOCAD"),

# WA - Sandstone 
("sandstone", "Sandstone", "input/SandstoneConvParam.json", "WesternAust/Sandstone/3D_Sandstone_GOCAD/GOCAD"),

# SA - North Gawler
("ngawler", "NorthGawler", "input/NorthGawlerConvParam.json", "SouthAust/GDP00026"),

# Tas - Rosebery Lyell
("rosebery", "RoseberyLyell", "input/RoseberyLyellConvParam.json", "Tasmania/RoseberyLyell"),

# QLD - Quamby
("quamby", "Quamby", "input/QuambyConvParam.json", "Queensland/Quamby/Quamby/TSurf"),

# NSW - West Tamworth
("tamworth", "Tamworth", "input/WestTamworthConvParam.json", "NewSouthWales/WesternTamworth"),

# NT - McArthur Basin
("mcarthur", "McArthurBasin", "input/McArthurBasinConvParam.json", "NorthernTerritory/McArthurBasin/DIP012/Digital_Data/REGIONAL_MODEL"),

# GA - North Qld
("nqueensland", "NorthQueensland", "input/NorthQueenslandConvParam.json", "GA/North-Queensland"),

# GA - Tasmania
("tas", "Tas", "input/TasConvParam.json", "GA/Tas"),

# GA - Yilgarn
("yilgarn", "Yilgarn", "input/YilgarnConvParam.json", "GA/Yilgarn-NWS")

]           


# MAIN PART OF PROGRAMME
if __name__ == "__main__":
    try:
        geomodelsDir = os.path.join(os.path.join(DEST_DIR), 'geomodels') 

        # Remove and recreate models dir
        if os.path.exists(geomodelsDir):
            print("Removing", geomodelsDir)
            shutil.rmtree(geomodelsDir)
        os.mkdir(geomodelsDir)

        for urlStr, modelDirName, inConvFile, sDir in MODELS:
            # Check source dir
            srcDir = os.path.join(MODELS_SRC_DIR, sDir)
            if not os.path.exists(srcDir):
                print("ERROR - source directory does not exist", srcDir)
                sys.exit(1)

            # Remove and recreate output dir
            outDir = os.path.join(srcDir, 'output')
            if os.path.exists(outDir):
                print("Removing", outDir)
                shutil.rmtree(outDir)
            os.mkdir(outDir)

            # Run model conversion
            execList = ["./gocad2collada.py", "-x", "-r", "-f", outDir, srcDir, inConvFile]
            print("Executing: ", execList)
            cmdProc = subprocess.run(execList)
            print("Returned: ", cmdProc)
            if cmdProc.returncode != 0:
                print("Conversion returned an error")
                sys.exit(1)

            # Copy results to models dir
            modelDir =  os.path.join(geomodelsDir, modelDirName)
            print("Copying results from ", outDir, " -> ", modelDir)
            shutil.copytree(outDir, modelDir)

            # Move config file up to models dir
            config_file = os.path.join(modelDir, 'output_config.json')
            model_config = os.path.join(geomodelsDir, modelDirName+'_new.json')
            if os.path.exists(config_file):
                print("Moving ", config_file, " to ", model_config)
                os.rename(config_file, model_config)

    except Exception as e:
        print("ERROR - ", repr(e))
        sys.exit(1)
