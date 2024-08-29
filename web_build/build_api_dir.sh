#!/bin/sh
#
# This script creates the 'api' directory for the geomodels website
# It must be run from the 'scripts' directory and needs the sqlite db as command line parameter
#
# Use the 'make_boreholes.py' script to create the sqlite db
#
test "$1" = "" && echo "Usage: `basename $0` <db file>"  && exit 1
API_TAR=api.tar.gz
\rm -f $API_TAR

# Create data dir and copy in db
[ -d api ] && \rm -rf api
mkdir -p api/data/cache
cp $1 api/data || exit 1

# Assemble api files
cp make_boreholes.py api
cp -r ../scripts/lib api
cp ../scripts/webapi/webapi.py api
cp -r ./input api

# Remove unwanted files
find api/lib -type f |  egrep -v ".*py$" | xargs -iX \rm -f X
find api/lib -type d | grep __pycache__ | xargs -iX \rm -rf X

# Add in data
tar cfvz $API_TAR ./api
\rm -rf api

echo "Done. Results are in: $API_TAR"
