#!/bin/bash

# NB: Assumes we're in the 'test' dir

# Fetch assimp release
ASSIMP_VER=5.4.3
if [ ! -d assimp-$ASSIMP_VER ]; then
wget https://github.com/assimp/assimp/archive/refs/tags/v$ASSIMP_VER.tar.gz
tar xfz v$ASSIMP_VER.tar.gz

# NB: Assumes 'sudo apt install cmake' 
#pushd assimp-$ASSIMP_VER && cmake CMakeLists.txt -G 'Unix Makefiles' -DCMAKE_BUILD_TYPE=Debug && make && popd
pushd assimp-$ASSIMP_VER && cmake CMakeLists.txt -G 'Unix Makefiles' && make && popd
fi
export LD_LIBRARY_PATH=$LD_LIBRARY_PATH:$PWD/assimp-$ASSIMP_VER/bin
echo "LD_LIBRARY_PATH=$LD_LIBRARY_PATH"
