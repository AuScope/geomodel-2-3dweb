## Creating a borehole database 

To create a borehole database, run [makeBoreholes.py](makeBoreholes.py)

e.g. from Linux bash shell:

./makeBoreholes.py -b batch.txt -d query_data.db output_dir

where "batch.txt" contains a list of model input conversion files

       "output_dir/query_data.db" is the output borehole database used to serve up NVCL boreholes

It also creates GLTF or COLLADA borehole files which are not used.

