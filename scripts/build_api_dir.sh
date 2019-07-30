#!/bin/sh
#
# This script creates the 'api' directory for the geomodels website
# It must be run from the 'scripts' directory and needs the sqlite db as command line parameter
#
# Use the 'make_boreholes.py' script to create the sqlite db
#
test "$1" = "" && echo "Usage: `basename $0` <db file>"  && exit 1
API_TAR=`date +%Y%m%d`-api.tar

# Create data dir and copy in db
\rm -rf api
mkdir -p api/data/cache
cp $1 api/data

# Assemble archive
git archive -o $API_TAR --prefix=./api/ HEAD ./lib ./make_boreholes.py ./index.py ./input
test $? -ne 0 && exit 1

# Add in data
tar uf $API_TAR ./api
\rm -rf api

# Strip out gitignore files
tar vf $API_TAR --delete `tar tvf $API_TAR | grep gitignore | awk '{ printf("%s ", $6); }'`
test $? -ne 0 && exit 1

# Remove README.md
tar vf $API_TAR --delete ./api/input/README.md
test $? -ne 0 && exit 1

echo "Done. Results are in: $API_TAR"
