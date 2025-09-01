# Geomodels Web API Description

A basic implementation of a subset of the 3DPS standard V1.0 (http://docs.opengeospatial.org/is/15-001r4/15-001r4.html)
 and WFS v2.0 standards (http://www.opengeospatial.org/standards/wfs)


## Proxy WMS

/api/{model}?service=WMS&STYLES=default&wmsurl={WMS-url}

#### Purpose 

* Used to place a surface geology map onto the model using Geoscience Australia's surface geology WMS service (https://ecat.ga.gov.au/geonetwork/srv/eng/catalog.search#/metadata/101041)

e.g. https://geomodels.auscope.org.au/api/tas?service=WMS&STYLES=default&wmsurl=http://services.ga.gov.au/gis/services/GA_Surface_Geology/MapServer/WMSServer?SERVICE=WMS&REQUEST=GetMap&LAYERS=AUS_GA_2500k_GUPoly_Lithostratigraphy&VERSION=1.3.0&STYLES=&FORMAT=image/png&TRANSPARENT=true&BBOX=15643630.04,-4922659.97,16190610.51,-4400163.46&CRS=EPSG:3857&WIDTH=256&HEIGHT=256

## WFS

/api/{model}?service=WFS&version=2.0&request=GetPropertyValue&exceptions={exc}&outputFormat={outf}&typeName={typeN}&valueReference={valRef}

#### Purpose 

* Retrieves identifiers of NVCL (National Virtual Core Library) boreholes that are in the immediate vicinity of the 3D model

e.g. https://geomodels.auscope.org.au/api/rosebery?service=WFS&version=2.0&request=GetPropertyValue&exceptions=application%2Fjson&outputFormat=application%2Fjson&typeName=boreholes&valueReference=borehole%3Aid

## 3DPS 

### GetResourceById request

/api/{model}?service=3DPS&version=1.0&request=GetResourceById&outputFormat=model%2Fgltf%2Bjson%3Bcharset%3DUTF-8&resourceId={resource-id}

#### Purpose

* Retrieves GLTF representations of NVCL (National Virtual Core Library) boreholes that are in the immediate vicinity of the 3D model

e.g. https://geomodels.auscope.org.au/api/rosebery?service=3DPS&version=1.0&request=GetResourceById&outputFormat=model%2Fgltf%2Bjson%3Bcharset%3DUTF-8&resourceId=10026

### GetFeatureInfoById request

/api/{model}?service=3DPS&version=1.0&request=GetFeatureInfoByObjectId&objectId={object-id}&layers=boreholes&format=application%2Fjson

#### Purpose

* Retrieves information about an NVCL borehole

e.g. https://geomodels.auscope.org.au/api/NorthGawler?service=3DPS&version=1.0&request=GetFeatureInfoByObjectId&objectId=EWHDDH01_185_0&layers=boreholes&format=application%2Fjson

## Import GOCAD .TS file

/api/{model}?service=IMPORT&id={identifier}

e.g. https://geomodels.auscope.org.au/api/rosebery?service=IMPORT&id=f0f071bd63bdc621

#### Purpose 

* Allows the user to drag and drop a .TS file into the 3D scene
* Returns a GLTF file

## Export DXF file (experimental)

/api/{model}?service=EXPORT&filename={model-part-filename}&format={format}

#### Purpose

* This exports a model part in the form of a DXF file, but because it uses 'assimp' (https://github.com/assimp/assimp) it could export other formats
* This requires installation of 'pyassimp' python package ('experimental' group in 'pyproject.yaml') and installation and compilation of 'assimp' shared library

