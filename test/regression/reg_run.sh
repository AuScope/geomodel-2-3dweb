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
./gocad2collada.py -g -f $CWD/output "$CWD/input/${i}Test.$i" input/NorthGawlerConvParam.json >/dev/null 2>&1
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
./gocad2collada.py -g -f $CWD/output $CWD/input/PNGTest.vo input/NorthGawlerConvParam.json >/dev/null 2>&1
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

# Clear output directory
\rm -f $CWD/output/*

echo -n "Recursion test: "

# Try converting all files at once
./gocad2collada.py -g -r -f $CWD/output $CWD/input input/NorthGawlerConvParam.json >/dev/null 2>&1
[ $? -ne 0 ] && echo "FAILED - conversion returned False" && exit 1

# Check that all files were converted
for f in PNGTest_0.PNG gpTest.dae plTest.dae tsTest.dae vsTest.dae; do
[ ! -e $CWD/output/$f ] && echo "FAILED - $f" && exit 1
done
echo "PASSED"

## Remove output dir
#\rm -rf $CWD/output


exit 0
