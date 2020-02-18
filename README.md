# geomodel-2-3dweb

Generates 3D web versions of geological models primarily for geomodelportal website (https://github.com/AuScope/geomodelportal)

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
+ diskcache (http://www.grantjenks.com/docs/diskcache/)
+ nvcl_kit (https://pypi.org/project/nvcl-kit/)
2. Clone and compile collada2gltf (https://github.com/KhronosGroup/COLLADA2GLTF)
3. Set 'COLLADA2GLTF_BIN' environment variable to point to the path where 'COLLADA2GLTF-bin' resides, e.g.
```
export COLLADA2GLTF_BIN=/home/fred/github/COLLADA2GLTF/build/
```
4. Clone this repository (i.e. geomodel-2-3dweb)


NB: pyassimp requires the assimp shared library which may need to be compiled and installed separately

### To convert some GOCAD *.ts *.vs *.pl files to GLTF or COLLADA

Run [gocad2collada.py](scripts/gocad2collada.py). You must give it either the directory where the GOCAD files reside, or a GOCAD file plus a conversion parameter file. This [README](scripts/input/README.md) explains the format of the conversion parameter file.   

e.g.
```
./gocad2collada.py gocad.ts config.json

```

where _config.json_ looks like this:

```
{
    "ModelProperties": {
        "crs": "EPSG:28352",
        "name": "Any Name",
        "modelUrlPath": "path",
        "init_cam_dist": 0.0,
        "proj4_defn": "+proj=utm +zone=52 +south +ellps=GRS80 +towgs84=0,0,0,0,0,0,0 +units=m +no_defs"
    },
    "GroupStructure": {}
}

```

Use the '-g' flag to generate COLLADA files

  
### Converting GOCAD models for use in geomodelportal website

[batch_proc.py](scripts/batch_proc.py) is a simple batch script used to convert the GOCAD models for the website.


### Building a borehole database

[make_boreholes.py](scripts/make_boreholes.py) is a script to create a database of NVCL borehole objects to display within the model. See this [README](scripts/README.md) for more information.

### Code Documentation

In the 'docs' directory, documentation can be generated for the Python scripts using [Sphinx](http://www.sphinx-doc.org/en/master/index.html). Please see local [README](docs/README) file for details.

### TravisCI Test Status

[![Test Status](https://travis-ci.com/AuScope/geomodel-2-3dweb.svg?branch=master)](https://travis-ci.com/AuScope/geomodel-2-3dweb)

