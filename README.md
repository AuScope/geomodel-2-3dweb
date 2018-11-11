# geomodel-2-3dweb

The aim is to generate 3D web versions of geological models

**NOTE:** This is still being developed. It is far from complete.

### To configure

1. Install python library dependencies:
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

### TravisCI Status

[![Build Status](https://travis-ci.com/AuScope/geomodel-2-3dweb.svg?branch=master)](https://travis-ci.com/AuScope/geomodel-2-3dweb)

