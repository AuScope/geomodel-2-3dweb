#!/bin/sh
#
# Basic regression test script. Run from the 'regression' directory
#
# Acknowledgements:
# 1) Files for tests derived from: http://www.energymining.sa.gov.au/minerals/geoscience/geoscientific_data/3d_geological_models
# 2) SKUA/GOCAD software from the "Paradigm Academic Software Program" (http://www.pdgm.com/affiliations/academic-software-programs/) was used to produce and view the voxet files
#

echo "\n\nGOCAD to COLLADA and PNG conversion regresssion test"
CWD=`pwd`

# Make the output directory
[ ! -e output ] && mkdir output 
cd ../../scripts

# Loop around processing different GOCAD objects
for i in 'pl' 'ts' 'vs' 'gp'; do

# Clear output directory
\rm -f $CWD/output/*

echo -n "$i File test: "

# Convert GOCAD to COLLADA
./gocad2collada.py "$CWD/input/${i}Test.$i" -g --output_folder $CWD/output --create -o "$CWD/output/${i}Test.json" input/NorthGawlerConvParam.json  >/dev/null 2>&1
[ $? -ne 0 ] && echo "FAILED - conversion returned False" && exit 1

# Remove date stamps from file
egrep -v '(<created>|<modified>)' "$CWD/output/${i}Test.dae" > "$CWD/output/${i}Test2.dae" 
[ $? -ne 0 ] && echo "FAILED" && exit 1

# Check that conversion was correct
cmp "$CWD/output/${i}Test2.dae" "$CWD/golden/${i}Test.dae" >/dev/null 2>&1
case $? in
"0")
    echo "PASSED"
    ;;
"1")
    echo "FAILED"
    exit 1
    ;;
*)
    echo "FAILED - file could not be compared"
    exit 1
    ;;
esac

done

# Clear output directory
\rm -f $CWD/output/*

echo -n "Convert single layer VOXET to PNG test: "

# Convert GOCAD to PNG 
./gocad2collada.py "$CWD/input/PNGTest.vo" -g --output_folder $CWD/output --create -o "$CWD/output/PNGTest.json" input/NorthGawlerConvParam.json >/dev/null 2>&1
[ $? -ne 0 ] && echo "FAILED - conversion returned False" && exit 1

# Check that conversion was correct
cmp "$CWD/output/PNGTest_0.PNG" "$CWD/golden/PNGTest.PNG" >/dev/null 2>&1
case $? in
"0")
    echo "PASSED"
    ;;
"1")
    echo "FAILED"
    exit 1
    ;;
*)
    echo "FAILED - file could not be compared"
    exit 1
    ;;
esac

# Remove output dir
\rm -rf $CWD/output
exit 0
