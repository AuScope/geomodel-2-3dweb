#!/bin/bash

# NB: Assumes we're in the 'test' dir

# Remove old venv
pdm venv remove -y for-test
# Create new venv
pdm venv create --with-pip --name for-test 3.10
eval $(pdm venv activate for-test)
pdm install --venv for-test

# Install assimp
if [ ! -d assimp-5.2.5 ]; then
wget https://github.com/assimp/assimp/archive/v5.2.5.tar.gz
tar xf v5.2.5.tar.gz

# Assumes 'sudo apt install cmake' 
pushd assimp-5.2.5 && cmake CMakeLists.txt -G 'Unix Makefiles' && make && popd
fi
export LD_LIBRARY_PATH=$LD_LIBRARY_PATH:$PWD/assimp-5.2.5/bin
echo $LD_LIBRARY_PATH

# Install coverage
python3 -m pip install coverage

# Test GOCAD import & conversion
pushd unit/gocad_import > /dev/null
coverage erase
python3 -m coverage run gocad_importer_test.py
[ $? -ne 0 ] && exit 1
popd > /dev/null

## Test assimp_kit
## FIXME: Version incompatibility problems
#pushd unit/assimp_kit > /dev/null
#coverage erase
#coverage run test_assimp_kit.py
#[ $? -ne 0 ] && exit 1
#popd > /dev/null

# Test webapi
# Avoid running webapi tests in gitlab
## FIXME: Version incompatibility problems
#python3 -m pip install pytest httpx
#hostname -f | egrep '\.au$' > /dev/null 2>&1
#if [ $? -eq 0 ]; then
#pushd unit/webapi > /dev/null
#coverage erase
#coverage run --source webapi -m pytest
#[ $? -ne 0 ] && exit 1
#popd > /dev/null
#fi

# Test regresssion
pushd regression > /dev/null
./reg_run.sh
[ $? -ne 0 ] && exit 1
popd > /dev/null

# Test db
pushd ../scripts/lib/db > /dev/null
coverage erase
coverage run db_tables.py
popd > /dev/null

coverage combine unit/gocad_import/.coverage # unit/assimp_kit/.coverage unit/webapi/.coverage ../scripts/.coverage ../scripts/lib/db/.coverage
coverage report --omit '*/geomodel-2-3dweb/scripts/lib/exports/print_assimp.py'

deactivate
