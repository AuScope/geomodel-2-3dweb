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

### To convert some GOCAD *.ts *.vs *.pl files to GLTF

Run 'gocad2collada.py' (in 'scripts' dir). You must give it either the directory where the GOCAD files reside, or a GOCAD file plus an input file. Sample input files are in the 'scripts/input' directory. This [README](scripts/input/README.md) explains their format.

e.g.
```
./gocad2collada.py gocad.ts config.json
```

```
usage: gocad2collada.py [-h] [-o OUTPUT_CONFIG] [-r] [-d] [-x]
                        [-f OUTPUT_FOLDER] [-g]
                        GOCAD source dir/file JSON input param file

Convert GOCAD files into files used to display a geological model

positional arguments:
  GOCAD source dir/file
                        GOCAD source directory or source file
  JSON input param file
                        Input parameters in JSON format

optional arguments:
  -h, --help            show this help message and exit
  -o OUTPUT_CONFIG, --output_config OUTPUT_CONFIG
                        Output JSON config file
  -r, --recursive       Recursively search directories for files
  -d, --debug           Print debug statements during execution
  -x, --nondefault_coord
                        Tolerate non-default GOCAD coordinate system
  -f OUTPUT_FOLDER, --output_folder OUTPUT_FOLDER
                        Output folder for graphics files
  -g, --no_gltf         Create COLLADA files, but do not convert to GLTF
 ```

  
### To convert GOCAD models for use in websites, use the 'batch_proc.py' script

### TravisCI Status

[![Build Status](https://travis-ci.com/AuScope/geomodel-2-3dweb.svg?branch=master)](https://travis-ci.com/AuScope/geomodel-2-3dweb)

