# Geomodels Web API Description

### Proxy WMS

/api/{model}?service=WMS&STYLES=default&wmsurl={WMS-url}

e.g. http://geomodels.auscope.org/api/tas?service=WMS&STYLES=default&wmsurl=http://services.ga.gov.au/gis/services/GA_Surface_Geology/MapServer/WMSServer?SERVICE=WMS&REQUEST=GetMap&LAYERS=AUS_GA_2500k_GUPoly_Lithostratigraphy&VERSION=1.3.0&STYLES=&FORMAT=image/png&TRANSPARENT=true&BBOX=15643630.04,-4922659.97,16190610.51,-4400163.46&CRS=EPSG:3857&WIDTH=256&HEIGHT=256


### WFS

/api/{model}?service=WFS&version=2.0&request=GetPropertyValue&exceptions={exc}&outputFormat={outf}&typeName={typeN}&valueReference={valRef}

e.g. http://geomodels.auscope.org/api/rosebery?service=WFS&version=2.0&request=GetPropertyValue&exceptions=application%2Fjson&outputFormat=application%2Fjson&typeName=boreholes&valueReference=borehole%3Aid

### 3DPS

/api/{model}?service=3DPS&version=1.0&request=GetResourceById&outputFormat=model%2Fgltf%2Bjson%3Bcharset%3DUTF-8&resourceId={resource-id}

e.g. http://geomodels.auscope.org/api/rosebery?service=3DPS&version=1.0&request=GetResourceById&outputFormat=model%2Fgltf%2Bjson%3Bcharset%3DUTF-8&resourceId=10026

### Import GOCAD .TS file

/api/{model}?service=IMPORT&id={identifier}

e.g. http://geomodels.auscope.org/api/rosebery?service=IMPORT&id=f0f071bd63bdc621

### Export DXF file

/api/{model}?service=EXPORT&filename={model-part-filename}&format={format}


### Download blob file 

/api/{model}/$blobfile.bin?id={identifier}

e.g. http://geomodels.auscope.org/api/rosebery/$blobfile.bin?id=drag_and_drop_f0f071bd63bdc621
