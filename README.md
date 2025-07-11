[![pdm-managed](https://img.shields.io/badge/pdm-managed-blueviolet)](https://pdm.fming.dev)
![Test Status](https://github.com/AuScope/geomodel-2-3dweb/actions/workflows/tests.yml/badge.svg)
[![Coverage Status](https://raw.githubusercontent.com/AuScope/geomodel-2-3dweb/master/test/badge/coverage-badge.svg)]()

# AuScope Geomodels Portal back-end

Generates 3D web versions of geoscience models primarily for AuScope Geomodels website (https://geomodels.auscope.org.au)

The source code for the front-end of AuScope Geomodels is [here](https://github.com/AuScope/geomodelportal)

## Development

#### To configure

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

#### Run tests

All tests
```
cd test
./run_test.sh
```

Regression tests
```
pdm run $SHELL
cd test/regression
./run_reg.sh
```

## Workflows

### 'Build API Backend' Workflow

Triggers: manual dispatch, push to master

Function:
  - Make Python API directory
  - Make borehole database
  - Make Python package state files
  - All outputs are exported as artifacts

### 'Build Models Backend' Workflow

Triggers: push to master

Function:
  - Make models 3d web assets
  - Web assets are exported as artifacts

### 'Release API Backend' Workflow

Triggers: Push to a release tag

Function:
  - Creates a backend release
  - Adds the files from the latest successful 'Build API Backend' action to the release

**NB: After running this release the 'Release Models Backend' action (below) can be run to add 
model web assets to the release**

### 'Release Models Backend' Workflow

Triggers: Manual dispatch on provided tag

Function:
  - Add model web assets from the latest successful 'Build Models Backend' action to the release

### 'Pages Build Deployment' Workflow

Triggers: dynamic

Function:
  - Creates documentation deployed to https://auscope.github.io/geomodel-2-3dweb/

### 'Testing' Workflow

Triggers: Push to master, pull_request to master

Function:
  - Runs all the unit and regression tests


## Release Procedure

1. Tag with "PORTAL_RELEASE_YYYYMMDD" annotated tag
```
git tag -a PORTAL_RELEASE_20241223 -m "December 2024 Release"
git push --tags origin master
```
2. The 'Release API Backend' action will create a release at this tag
3. Once step 2 is complete, run the 'Release Models Backend' action inputting the tag name
4. The 'Release Models Backend' action will build all the model files and insert them into the release

## Code Documentation

Autogenerated Source Code Documentation is available [here](https://auscope.github.io/geomodel-2-3dweb/)

Please see [README](doc_src/README.md) file for documentation generation details.

## Acknowledgements

Funding provided by [AuScope Pty Ltd](https://www.auscope.org.au/)

SKUA/GOCAD software from the [Paradigm Academic Software Program](http://www.pdgm.com/affiliations/academic-software-programs/) was used to view some types of GOCAD object files and produce sample GOCAD OBJECT files used for testing

## Citation

Please cite as:

Fazio, Vincent; Woodcock, Robert (2024): AuScope 3D Geological Models Portal. v1. CSIRO. Service Collection. http://hdl.handle.net/102.100.100/609085?index=1
