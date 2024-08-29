#!/bin/bash

# NB: Assumes we're in the 'test' dir

# Install patched version of assimp, will try github released version once relevant PRs are merged
ASSIMP_VER=5.2.5
if [ ! -d assimp-$ASSIMP_VER ]; then
#wget https://github.com/assimp/assimp/archive/v$ASSIMP_VER.tar.gz
#wget https://github.com/assimp/assimp/archive/refs/tags/v$ASSIMP_VER.tar.gz
tar xvfz v$ASSIMP_VER.tar.gz

# NB: Assumes 'sudo apt install cmake' 
#pushd assimp-$ASSIMP_VER && cmake CMakeLists.txt -G 'Unix Makefiles' -DCMAKE_BUILD_TYPE=Debug && make && popd
pushd assimp-$ASSIMP_VER && cmake CMakeLists.txt -G 'Unix Makefiles' && make && popd
fi
export LD_LIBRARY_PATH=$LD_LIBRARY_PATH:$PWD/assimp-$ASSIMP_VER/bin
echo "LD_LIBRARY_PATH=$LD_LIBRARY_PATH"
