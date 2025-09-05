# Development Notes

## To configure development environment

1. Install Python v3.10 or higher (https://www.python.org/)
2. Install PDM (https://pdm.fming.dev/latest/) and jq (https://jqlang.github.io/jq/)


3. Clone and compile collada2gltf (https://github.com/KhronosGroup/COLLADA2GLTF)
4. Set 'COLLADA2GLTF_BIN' environment variable to point to the path where 'COLLADA2GLTF-bin' resides, e.g.
```
export COLLADA2GLTF_BIN=/home/fred/github/COLLADA2GLTF/build/
```
5. Clone this repository (i.e. geomodel-2-3dweb)
6. 'pdm install' will install the python library dependencies
  * 'eval $(pdm venv activate)' will start a Python env, 'deactivate' to exit
  * 'pdm run $SHELL' will run the Python env in a new shell

NB: pyassimp is only required for the experimental file export function. It requires the assimp shared library which may need to be compiled and installed separately


## Converting files

### To convert one file or a folder of files to GLTF or COLLADA or GZIP (geophysics volumes)

* Accepted formats:
     * GOCAD (*.ts *.pl *.vs *.wl *.vo *.sg *.gp)
     * XYZV (X-coord Y-coord Z-coord value, space separated, one quadtuple per line, used for geophysics volumes)
  
Run [conv_webasset.py](scripts/conv_webasset.py). You must give it either a GOCAD file or the directory where the GOCAD files reside, plus a conversion parameter file. This [README](web_build/input/README.md) explains the format of the conversion parameter file.

e.g.
```
cd scripts
pdm run ./conv_webasset.py gocad.ts config.json

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

### Converting directories of files (e.g. GOCAD) for use in AuScope geomodels website

[batch_proc.py](web_build/batch_proc.py) is a simple batch script used to convert the GOCAD models for the website.


## Creating a borehole database 

To create a borehole database, run [make_boreholes.py](make_boreholes.py)

e.g. from Linux bash shell, in "web_build" directory:

_pdm run ./make_boreholes.py -b batch.txt -d query_data.db output_dir_

where: 

  "batch.txt" contains a list of model input conversion files

  "output_dir/query_data.db" is the output borehole database used to serve up NVCL boreholes

NB: It also creates GLTF or COLLADA borehole files which are not used.


## Creating 'api' directory

To create a 'api' directory run [build_api_dir.sh](build_api_dir.sh)

e.g. from Linux bash shell, in "web_build" directory:

_pdm run ./build_api_dir.sh output_dir/query_data.db_

This will produce a tar file with today's date which can be copied to website

NB: If you aren't using a borehole database, substitute an empty file for _output_dir/query_data.db_
