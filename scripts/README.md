## Creating a borehole database 

To create a borehole database, run [make_boreholes.py](make_boreholes.py)

e.g. from Linux bash shell, in "scripts" directory:

_./make_boreholes.py -b batch.txt -d query_data.db output_dir_

where: 

  "batch.txt" contains a list of model input conversion files

  "output_dir/query_data.db" is the output borehole database used to serve up NVCL boreholes

NB: It also creates GLTF or COLLADA borehole files which are not used.


## Creating 'api' directory

To create a 'api' directory run [build_api_dir.sh](build_api_dir.sh)

e.g. from Linux bash shell, in "scripts" directory:

_./build_api_dir.sh output_dir/query_data.db_

This will produce a tar file with today's date which can be copied to website

