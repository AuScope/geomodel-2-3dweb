# Development Notes

## To configure

1. Install Python v3.10 or higher (https://www.python.org/)
2. Install PDM (https://pdm.fming.dev/latest/) and jq (https://jqlang.github.io/jq/)

NB: pyassimp requires the assimp shared library which may need to be compiled and installed separately

3. Clone and compile collada2gltf (https://github.com/KhronosGroup/COLLADA2GLTF)
4. Set 'COLLADA2GLTF_BIN' environment variable to point to the path where 'COLLADA2GLTF-bin' resides, e.g.
```
export COLLADA2GLTF_BIN=/home/fred/github/COLLADA2GLTF/build/
```
5. Clone this repository (i.e. geomodel-2-3dweb)
6. 'pdm install' will install the python library dependencies
  * 'eval $(pdm venv activate)' will start a Python env, 'deactivate' to exit
  * 'pdm run $SHELL' will run the Python env in a new shell

## Converting files

#### To convert one file or a folder of files to GLTF or COLLADA or GZIP (geophysics volumes)

* Accepted formats:
     * GOCAD (*.ts *.pl *.vs *.wl *.vo *.sg *.gp)
     * XYZV (X-coord Y-coord Z-coord value, space separated, one quadtuple per line, used for geophysics volumes)
  
Run [conv_webasset.py](scripts/conv_webasset.py). You must give it either a GOCAD file or the directory where the GOCAD files reside, plus a conversion parameter file. This [README](web_build/input/README.md) explains the format of the conversion parameter file.

e.g.
```
pdm run $SHELL
cd scripts
./conv_webasset.py gocad.ts config.json

```

where a simple _config.json_ could look like this:

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

#### Converting directories of files (e.g. GOCAD) for use in AuScope geomodels website

[batch_proc.py](web_build/batch_proc.py) is a simple batch script used to convert the GOCAD models for the website.

#### Building a borehole database

[make_boreholes.py](web_build/make_boreholes.py) is a script to create a database of NVCL borehole objects to display within the model. See this [README](web_build/README.md) for more information.



Regression tests
```
pdm run $SHELL
cd test/regression
./run_reg.sh
```
