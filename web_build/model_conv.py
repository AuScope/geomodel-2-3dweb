import os
import shutil
import subprocess
import sys
import time

def print_output(proc):
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


''' Converts a geological model by forking 'conv_webasset.py' as a shell executable script

:param modelsSrcDir: model source directory - where all the models are kept
:param geomodelsDir: output directory
:param urlStr: path name for this model in website
:param modelDirName: directory name for model in the website's internal directory structure
:param inConvFile: input parameter file for model conversion
:param srcSubDir: source subdirectory for model files - where this model can be found within 'modelSrcDir'
:param recreateOutDir: recreate output directory
'''
def convert_model(modelsSrcDir, geomodelsDir, urlStr, modelDirName, inConvFile, srcSubDir,
                 recreateOutDir=True):
    # Check source dir
    srcDir = os.path.join(modelsSrcDir, srcSubDir)
    if not os.path.exists(srcDir):
        print("ERROR - source directory does not exist", srcDir)
        return

    # Remove and recreate output dir
    skip_conversion = False
    outDir = os.path.join(srcDir, 'output')
    if os.path.exists(outDir):
        if not recreateOutDir:
            print("Skipping conversion", srcDir)
            skip_conversion = True
        else:
            print("Removing", outDir)
            shutil.rmtree(outDir)
            os.mkdir(outDir)
    else:
        os.mkdir(outDir)

    # Run model conversion
    # NB: Assumes 'conv_webasset.py' lives in ../scripts dir
    if not skip_conversion:
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
                return
        else:
            # Displays output as process runs
            with subprocess.Popen(execList, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                  encoding='utf-8', errors='ignore') as proc:
                while proc.poll() is None:
                    print_output(proc)
                    time.sleep(1)
                print("Returned:", proc.returncode, flush=True)
                if proc.returncode != 0:
                    print_output(proc)
                    print("Exiting")
                    return

    # Copy results to models dir
    modelDir = os.path.join(geomodelsDir, modelDirName)
    print("Copying results from ", outDir, " -> ", modelDir)
    shutil.copytree(outDir, modelDir)

    # Move config file up to models dir
    config_file = os.path.join(modelDir, 'output_config.json')
    model_config = os.path.join(geomodelsDir, modelDirName+'.json')
    if os.path.exists(model_config):
        print("Renaming ", model_config, " to ", model_config+'.old')
        os.rename(model_config, model_config+'.old')
    if os.path.exists(config_file):
        print("Copying ", config_file, " to ", model_config)
        shutil.copyfile(config_file, model_config)
