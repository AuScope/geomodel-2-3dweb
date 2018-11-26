# geomodel-2-3dweb

The aim is to generate 3D web versions of geological models

**NOTE:** This is still being developed. It is far from complete.

### To configure

1. Install Python v3 (https://www.python.org/) and these python library dependencies:
+ OWSLib (https://github.com/geopython/OWSLib)
+ pyassimp (https://github.com/assimp/assimp/tree/master/port/PyAssimp)
+ SQLAlchemy (https://www.sqlalchemy.org/)
+ pyproj (https://github.com/jswhit/pyproj)
+ Pillow (https://github.com/python-pillow/Pillow)
+ pycollada (https://github.com/pycollada/pycollada)
+ numpy (http://www.numpy.org/)
2. Clone and compile collada2gltf (https://github.com/KhronosGroup/COLLADA2GLTF)
3. Clone this repository
4. Edit 'lib/exports/collada2gltf.py', change 'COLLADA2GLTF_BIN' to point to the path where 'COLLADA2GLTF-bin' resides

### To convert some GOCAD files to GLTF

Run 'gocad2collada.py' (in 'scripts' dir). You must give it the directory where the GOCAD files reside, or a GOCAD file and an input file. Sample input files are in the 'scripts/input' directory. 

```
usage: gocad2collada.py [-h] [--output_config OUTPUT_CONFIG] [--recursive]
                        [--debug] [--nondefault_coord] [--output_folder OUTPUT_FOLDER] [--no_gltf]
                        GOCAD source dir/file JSON input param file

Convert GOCAD files into files used to display a geological model

positional arguments:

   GOCAD source dir/file
                        GOCAD source directory or source file  
   JSON input param file
                        Input parameters in JSON format  

optional arguments:

   -h, --help            show this help message and exit
  
   --output_config OUTPUT_CONFIG, -o OUTPUT_CONFIG
                         Output JSON config file
                        
   --recursive, -r       Recursively search directories for files
  
   --debug, -d           Print debug statements during execution
  
   --nondefault_coord, -x
                         Tolerate non-default GOCAD coordinate system  
                        
   --output_folder OUTPUT_FOLDER, -f OUTPUT_FOLDER
                         Output folder for graphics files  
                        
   --no_gltf, -g         Create COLLADA files, but do not convert to GLTF  
 ```
  


### TravisCI Status

[![Build Status](https://travis-ci.com/AuScope/geomodel-2-3dweb.svg?branch=master)](https://travis-ci.com/AuScope/geomodel-2-3dweb)

