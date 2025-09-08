#!/bin/bash

# NB: Assumes we're in the 'test' dir

# Remove old venv
pdm venv remove -y for-test
# Create new venv
pdm venv create --name for-test 3.10
eval $(pdm venv activate for-test)
pdm install -G test --venv for-test

# Test GOCAD import & conversion
pushd unit/gocad_import > /dev/null
coverage erase
python3 -m coverage run gocad_importer_test.py
[ $? -ne 0 ] && exit 1
popd > /dev/null

## Test assimp_kit
#pushd unit/assimp_kit > /dev/null
#coverage erase
#coverage run test_assimp_kit.py
#[ $? -ne 0 ] && exit 1
#popd > /dev/null

# Test webapi
pushd unit/webapi > /dev/null
coverage erase
coverage run --source webapi -m pytest
[ $? -ne 0 ] && exit 1
popd > /dev/null

# Test regresssion
pushd regression > /dev/null
./reg_run.sh
[ $? -ne 0 ] && exit 1
popd > /dev/null

# Test db
pushd ../scripts/lib/db > /dev/null
coverage erase
coverage run db_tables.py
[ $? -ne 0 ] && exit 1
popd > /dev/null

#coverage combine unit/gocad_import/.coverage ../scripts/lib/db/.coverage ../scripts/.coverage unit/assimp_kit/.coverage unit/webapi/.coverage
coverage combine unit/gocad_import/.coverage ../scripts/lib/db/.coverage unit/webapi/.coverage
coverage html
coverage xml
coverage report --omit '*/geomodel-2-3dweb/scripts/lib/exports/print_assimp.py'
genbadge coverage -i coverage.xml -o badge/coverage-badge.svg -v

deactivate
