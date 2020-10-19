#!/usr/bin/env python3

import os
import shutil
import subprocess
import sys


def convert_model(modelsSrcDir, geomodelsDir, urlStr, modelDirName, inConvFile, sDir):
    # Check source dir
    srcDir = os.path.join(modelsSrcDir, sDir)
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
    # NB: Assumes 'conv_webasset.py' lives in ../scripts dir
    execList = [os.path.join(os.pardir,"scripts","conv_webasset.py"), "-x", "-r", "-f", outDir, srcDir, inConvFile]
    print("Executing: ", execList)
    cmdProc = subprocess.run(execList, capture_output=True)
    print("Returned:", cmdProc.returncode)
    if cmdProc.returncode != 0:
        print("Conversion returned an error")
        print("Returned - stdout:", cmdProc.stdout)
        print("           stderr:", cmdProc.stderr)
        sys.exit(1)

    # Copy results to models dir
    modelDir = os.path.join(geomodelsDir, modelDirName)
    print("Copying results from ", outDir, " -> ", modelDir)
    shutil.copytree(outDir, modelDir)

    # Move config file up to models dir
    config_file = os.path.join(modelDir, 'output_config.json')
    model_config = os.path.join(geomodelsDir, modelDirName+'_new.json')
    if os.path.exists(config_file):
        print("Moving ", config_file, " to ", model_config)
        os.rename(config_file, model_config)
