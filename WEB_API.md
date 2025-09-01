# Geomodels Web API Description

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

/api/{model}?service=3DPS&version=1.0&request=GetResourceById&outputFormat=model%2Fgltf%2Bjson%3Bcharset%3DUTF-8&resourceId={resource-id}

#### Purpose 

* Retrieves GLTF representations of NVCL (National Virtual Core Library) boreholes that are in the immediate vicinity of the 3D model

e.g. https://geomodels.auscope.org.au/api/rosebery?service=3DPS&version=1.0&request=GetResourceById&outputFormat=model%2Fgltf%2Bjson%3Bcharset%3DUTF-8&resourceId=10026

## Import GOCAD .TS file

/api/{model}?service=IMPORT&id={identifier}

e.g. https://geomodels.auscope.org.au/api/rosebery?service=IMPORT&id=f0f071bd63bdc621

#### Purpose 

* Allows the user to drag and drop a .TS file into the 3D scene

## Export DXF file (experimental)

/api/{model}?service=EXPORT&filename={model-part-filename}&format={format}

* This exports a model part in the form of a DXF file, but because it uses 'assimp' (https://github.com/assimp/assimp) it could export other formats
* This requires installation of 'pyassimp' python package ('experimental' group in 'pyproject.yaml') and installation and compilation of 'assimmp' shared library

