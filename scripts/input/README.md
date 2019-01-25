JSON Input Parameter File

The conversion process uses an input parameter file to convert the models and
create the model input file for the geomodels website.

NB: The 'BoreholeData' and 'CoordOffsets' sections are optional.

Here is an example JSON input parameter file

```
{
    "BoreholeData": {
        "BBOX": { "west": 149, "south": -33, "east": 153.67, "north": -28 },
        "EXTERNAL_LINK": { "label": "AUSCOPE_PORTAL_URL",
                           "URL": ""
                         },
        "MODEL_CRS": "EPSG:20356",
        "WFS_URL": "http://auscope.dpi.nsw.gov.au:80/geoserver/wfs",
        "BOREHOLE_CRS": "urn:x-ogc:def:crs:EPSG:4326",
        "WFS_VERSION": "1.1.0"
     },
     "ModelProperties": {
        "crs": "EPSG:20356",
        "init_cam_dist": 900000.0,
        "name": "West Tamworth Belt", 
        "proj4_defn": "+proj=utm +zone=52 +south +ellps=GRS80 +towgs84=0,0,0,0,0,0,0 +units=m +no_defs"
      },
      "CoordOffsets": [
         {
             "filename": "Avebury.vs",
             "offset": [0.0, 0.0, -2250.0]
         },
         {
             "filename": "Hellyer.vs",
             "offset": [0.0, 0.0, -2000.0]
         }
      ]
}
```

There are 3 sections:

The "BoreholeData" section is used to create borehole GLTF objects. It has a number of elements:

    "BBOX"  - bounding box coordinates. All NVCL boreholes within this bounding box will be converted to GLTF files
    "EXTERNAL_LINK" - this is a link to an external website (e.g. AuScope website). When the user clicks on the borehole object in the browser, a popup window will appear with the 'URL' labelled with 'label'.
    Typically 'URL' would be a permanent link to the same set of boreholes in the AuScope website.
    "MODEL_CRS" The model CRS, this ensures that the borehole objects are generated with the same coordinates as the model itself. It would normally be the same as the 'crs' in the 'ModelProperties' section.
    "WFS_URL" The WFS URL for the NVCL boreholes service
    "WFS_VERSION" The version number passed to the WFS service

The "ModelProperties" section contains the following:

    "crs"- this is the coordinate reference system of x,y,z coordinates that are contained in all the GOCAD files
    "name" - name of model for display purposes (used by the geomodels website)
    "proj4_defn" - if the CRS is not common, a 'proj4' definition may be necessary (http://proj4js.org/)
    "init_cam_dist" - this is the initial camera distance to the model (used by the geomodelportal website)


The "CoordOffsets" section is a coordinate offset that is added to all model parts from a particular file. For example, using the input parameter file above, if a GOCAD VSet object in "Hellyer.vs" is at (1000.0, 1000.0, 2500.0), its model part in the website would be placed at (1000.0, 1000.0, 500.0)


