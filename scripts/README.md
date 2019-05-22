## Creating a borehole database 

To create a borehole database, run [make_boreholes.py](make_boreholes.py)

e.g. from Linux bash shell:

_./make_boreholes.py -b batch.txt -d query_data.db output_dir_

where: 

  "batch.txt" contains a list of model input conversion files

  "output_dir/query_data.db" is the output borehole database used to serve up NVCL boreholes

It also creates GLTF or COLLADA borehole files which are not used.

