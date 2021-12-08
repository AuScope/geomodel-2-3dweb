#!/bin/bash

pushd unit/gocad_import > /dev/null
coverage erase
coverage run gocad_importer_test.py
[ $? -ne 0 ] && exit 1
popd > /dev/null

pushd unit/assimp_kit > /dev/null
coverage erase
coverage run test_assimp_kit.py
[ $? -ne 0 ] && exit 1
popd > /dev/null

# Avoid running in gitlab
hostname -f | egrep '\.au$' > /dev/null 2>&1
if [ $? -eq 0 ]; then
pushd unit/webapi > /dev/null
coverage erase
coverage run --source webapi -m pytest
[ $? -ne 0 ] && exit 1
popd > /dev/null
fi

pushd regression > /dev/null
./reg_run.sh
[ $? -ne 0 ] && exit 1
popd > /dev/null

pushd ../scripts/lib/db > /dev/null
coverage erase
coverage run db_tables.py
popd > /dev/null

coverage combine unit/gocad_import/.coverage unit/assimp_kit/.coverage unit/webapi/.coverage ../scripts/.coverage ../scripts/lib/db/.coverage
coverage report --omit '*/geomodel-2-3dweb/scripts/lib/exports/print_assimp.py'

