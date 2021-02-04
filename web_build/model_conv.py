#!/usr/bin/env python3

import os
import shutil
import subprocess
import sys
import time


''' Converts a geological model by forking 'conv_webasset.py' as a shell executable script

:param modelsSrcDir: model source directory - where all the models are kept
:param geomodelsDir: output directory
:param urlStr: path name for this model in website
:param modelDirName: directory name for model in the website's internal directory structure
:param inConvFile: input parameter file for model conversion
:param srcSubDir: source subdirectory for model files - where this model can be found within 'modelSrcDir'
'''
def convert_model(modelsSrcDir, geomodelsDir, urlStr, modelDirName, inConvFile, srcSubDir):
    # Check source dir
    srcDir = os.path.join(modelsSrcDir, srcSubDir)
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
    print("Executing: ", execList, flush=True)
    # Flag: display output as process runs or not
    interactive = True
    if not interactive:
        # Only displays output if there's an error
        cmdProc = subprocess.run(execList, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        print("Returned:", cmdProc.returncode, flush=True)
        if cmdProc.returncode != 0:
            print("Conversion returned an error")
            print("Returned - stdout:", cmdProc.stdout)
            print("           stderr:", cmdProc.stderr)
            sys.exit(1)
    else:
        # Displays output as process runs
        with subprocess.Popen(execList, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              encoding='utf-8', errors='ignore') as proc:
            while proc.poll() is None:
                line = 'X'
                while line != '':
                    line = proc.stdout.readline()
                    if line != '':
                        print(line, flush=True, end='')
                line = 'X'
                while line != '':
                    line = proc.stderr.readline()
                    if line != []:
                        print(line, flush=True, end='')
                time.sleep(1)
            print("Returned:", proc.returncode, flush=True)
            if proc.returncode != 0:
                sys.exit(1)

    # Copy results to models dir
    modelDir = os.path.join(geomodelsDir, modelDirName)
    print("Copying results from ", outDir, " -> ", modelDir)
    shutil.copytree(outDir, modelDir)

    # Move config file up to models dir
    config_file = os.path.join(modelDir, 'output_config.json')
    model_config = os.path.join(geomodelsDir, modelDirName+'_new.json')
    if os.path.exists(config_file):
        print("Copying ", config_file, " to ", model_config)
        shutil.copyfile(config_file, model_config)
