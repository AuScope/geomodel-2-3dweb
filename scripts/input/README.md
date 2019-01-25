## JSON Input Parameter File

The conversion process uses an input parameter file to convert the GOCAD files and
create the model input file that enables the geomodelportal website (https://github.com/AuScope/geomodelportal/tree/dev/ui) display the converted files.

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
        "modelUrlPath": "tamworth",
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
      ],
      "VoxetColourTables": [
        {
                "filename": "3D_geology_Lithology@@",
                "colour_table": "3D_geology_lithology_colours.csv"
        }
      ]
}
```

There are 4 sections:

### 1. BoreholeData

The "BoreholeData" section is optional and used to create borehole GLTF objects and metadata. It has a number of elements:

* "BBOX"  - bounding box coordinates. All NVCL boreholes within this bounding box will be converted to GLTF files
* "EXTERNAL_LINK" - this is a link to an external website (e.g. AuScope website). When the user clicks on the borehole object in the browser, a popup window will appear with the 'URL' labelled with 'label'. Typically 'URL' would be a permanent link to the same set of boreholes in the AuScope website.
* "MODEL_CRS" The model CRS, this ensures that the borehole objects are generated with the same coordinates as the model itself. It would normally be the same as the 'crs' in the 'ModelProperties' section.
* "WFS_URL" The WFS URL for the NVCL boreholes service
* "WFS_VERSION" The version number passed to the WFS service
    
### 2. ModelProperties

The "ModelProperties" section is compulsory and contains the following:

* "crs" - this is the coordinate reference system of x,y,z coordinates that are contained in all the GOCAD files
* "init_cam_dist" - this is the initial camera distance to the model (used by the geomodelportal website)
* "name" - name of model for display purposes (used by the geomodelportal website)
* "modelUrlPath" - name of model in the website URL (should be the same as in https://github.com/AuScope/geomodelportal/blob/dev/ui/src/assets/geomodels/ProviderModelInfo.json)
* "proj4_defn" - (optional) if the CRS is not common, a 'proj4' definition may be necessary (http://proj4js.org/)


### 3. CoordOffsets

The "CoordOffsets" section is an optional coordinate offset that is added to all model parts from a particular file. For example, using the input parameter file above, if a GOCAD VSet object in "Hellyer.vs" is at (1000.0, 1000.0, 2500.0), its model part in the website would be placed at (1000.0, 1000.0, 500.0)

### 4. VoxetColourTables

When displaying volume data, an optional colour table can be specified so that a data value can have a certain colour
* "filename" - name of binary volume data file (same format as GOCAD VOXET data http://paulbourke.net/dataformats/gocad/gocad.pdf)
* "colour_table" - name of colour table file. Its format is CSV: _index_, _rock_label_, _red_, _green_, _blue_ where _index_ is the data value, and _red_, _green_, _blue_ are floats e.g.

```1,"RockySupersuite",0.968627,0.505882,0.705882```
