#!/bin/sh
#
# Basic regression test script. Run from the 'regression' directory
#
# Acknowledgements:
# 1) Some of the files for tests derived from these models:
#    http://www.energymining.sa.gov.au/minerals/geoscience/geoscientific_data/3d_geological_models (North Gawler model)
#    https://dasc.dmp.wa.gov.au/dasc/ (Sandstone model)
# 2) SKUA/GOCAD software from the "Paradigm Academic Software Program" (http://www.pdgm.com/affiliations/academic-software-programs/)
#    was used to view and produce VOXET and SGRID GOCAD object file samples used for testing
#


# Function to compare two files, print result and clear output dir. Exits if bad.
compare_and_print() {
    cmp $1 $2 >/dev/null 2>&1
    case $? in
    "0")
        echo "PASSED"
        ;;
    "1")
        echo "FAILED"
        diff $1 $2
        exit 1
        ;;
    *)
        echo "FAILED - file could not be compared"
        exit 1
        ;;
    esac

    # Clear output directory
    \rm -f $CWD/output/*

}


##########################################################################################
# Main part starts here
##########################################################################################

echo "\n\nGOCAD to COLLADA, GZIP and PNG conversion regression test"
CWD=`pwd`

# Conversion script
CONV_SCRIPT="conv_webasset.py"

# Model conversion parameter input file directory
MODEL_INDIR="../web_build/input"

# Make the output directory
[ ! -e output ] && mkdir output
cd ../../scripts


##########################################################################################
# Convert various file types
##########################################################################################

coverage erase

# Loop around processing different GOCAD objects
for i in 'pl' 'ts' 'vs' 'gp' 'wl'; do

echo -n "$i File test: "

# Convert GOCAD to COLLADA
python3 -m coverage run -a $CONV_SCRIPT -g -f $CWD/output "$CWD/input/${i}Test.$i" $MODEL_INDIR/NorthGawlerConvParam.json >/dev/null 2>&1
[ $? -ne 0 ] && echo "FAILED - conversion returned False" && exit 1

# Remove date stamps from file
egrep -v '(<created>|<modified>)' "$CWD/output/${i}Test.dae" > "$CWD/output/${i}Test2.dae"
[ $? -ne 0 ] && echo "FAILED" && exit 1

# Check that conversion was correct
compare_and_print "$CWD/output/${i}Test2.dae" "$CWD/golden/${i}Test.dae"

done

# Test second type of well file
echo -n "wl Type 2 File test: "
python3 -m coverage run -a $CONV_SCRIPT -g -f $CWD/output "$CWD/input/wl2Test.wl" $MODEL_INDIR/NorthGawlerConvParam.json >/dev/null 2>&1
[ $? -ne 0 ] && echo "FAILED - conversion returned False" && exit 1
egrep -v '(<created>|<modified>)' "$CWD/output/wl2Test.dae" > "$CWD/output/wl2Test2.dae"
[ $? -ne 0 ] && echo "FAILED" && exit 1
compare_and_print "$CWD/output/wl2Test2.dae" "$CWD/golden/wl2Test.dae"




##########################################################################################
# Convert objects nested within 2 levels of group files
##########################################################################################

echo -n "Convert objects nested within 2 levels of group files: "
python3 -m coverage run -a $CONV_SCRIPT -g -f $CWD/output $CWD/input/2layer.gp $MODEL_INDIR/TasConvParam.json >/dev/null 2>&1
[ $? -ne 0 ] && echo "FAILED - 2 layer gp conversion returned False" && exit 1

# Remove date stamps from file
egrep -v '(<created>|<modified>)' "$CWD/output/2layer.dae" > "$CWD/output/2layer2.dae"
[ $? -ne 0 ] && echo "FAILED" && exit 1

# Check that conversion was correct
compare_and_print "$CWD/output/2layer2.dae" "$CWD/golden/2layer.dae"


##########################################################################################
# Inherit colour from group file
##########################################################################################

echo -n "Inherit colour from group file: "
python3 -m coverage run -a $CONV_SCRIPT -g -f $CWD/output $CWD/input/gpColour.gp $MODEL_INDIR/TasConvParam.json >/dev/null 2>&1
[ $? -ne 0 ] && echo "FAILED - inherit colour from gp returned False" && exit 1

# Remove date stamps from file
egrep -v '(<created>|<modified>)' "$CWD/output/gpColour_0.dae" > "$CWD/output/gpColour.dae"
[ $? -ne 0 ] && echo "FAILED" && exit 1

# Check that conversion was correct
compare_and_print "$CWD/output/gpColour.dae" "$CWD/golden/gpColour.dae"


##########################################################################################
# Convert single layer VOXET to PNG test, with and without colour table
##########################################################################################

echo -n "Convert single layer VOXET to PNG test, with colour table: "

# Convert GOCAD to PNG with colour table
python3 -m coverage run -a $CONV_SCRIPT -g -f $CWD/output $CWD/input/PNGTest.vo $MODEL_INDIR/NorthGawlerConvParam.json >/dev/null 2>&1
[ $? -ne 0 ] && echo "FAILED - ct conversion returned False" && exit 1

# Check that conversion was correct
compare_and_print "$CWD/output/PNGTest@@.PNG" "$CWD/golden/PNGTest.PNG"


echo -n "Convert single layer VOXET to PNG test, without colour table: "

# Convert GOCAD to PNG without colour table
python3 -m coverage run -a $CONV_SCRIPT -g -f $CWD/output $CWD/input/PNGTestNoCT.vo $MODEL_INDIR/NorthGawlerConvParam.json >/dev/null 2>&1
[ $? -ne 0 ] && echo "FAILED - ct conversion returned False" && exit 1

# Check that conversion was correct
compare_and_print "$CWD/output/PNGTestNoCT@@.PNG" "$CWD/golden/PNGTestNoCT.PNG"



##########################################################################################
# Voxet with single layer RGBA values convert to PNG test
##########################################################################################

echo -n "Convert single layer RGBA voxet to PNG test: "

python3 -m coverage run -a $CONV_SCRIPT -g -f $CWD/output $CWD/input/RGBA_voxet.vo $MODEL_INDIR/NorthGawlerConvParam.json >/dev/null 2>&1
[ $? -ne 0 ] && echo "FAILED - ct conversion returned False" && exit 1

# Check that conversion was correct
compare_and_print "$CWD/output/RGBA_voxet@@.PNG" "$CWD/golden/RGBA_voxet.PNG"


##########################################################################################
# Voxet with 3 binary files conversion & output config test
##########################################################################################

echo -n "Voxet with 3 binary files conversion & output config test: "

python3 -m coverage run -a $CONV_SCRIPT -g -f $CWD/output -o smallConf.json $CWD/input/small_voxet/small.vo $CWD/input/small_voxet/small.json >/dev/null 2>&1
[ $? -ne 0 ] && echo "FAILED - conversion returned False" && exit 1

# Check that conversion was correct
for f in small_lithology@@.gz small_density@@.gz small_susceptibility@@.gz; do

# Crudely removing the MTIME from gzip header to allow comparison
od -c "$CWD/golden/$f" | tail -n +2 > $CWD/output/gold.gz
od -c "$CWD/output/$f" | tail -n +2 > $CWD/output/out.gz
cmp "$CWD/output/gold.gz" "$CWD/output/out.gz" >/dev/null 2>&1
[ $? -ne 0 ] && echo "FAILED - comparison of $f returned False" && exit 1

done

# Compare the output config file
compare_and_print "$CWD/output/smallConf.json" "$CWD/golden/smallConf.json"


##########################################################################################
# Directory recursion test
##########################################################################################

echo -n "Directory recursion test: "

# Try converting all files at once
python3 -m coverage run -a $CONV_SCRIPT -g -r -f $CWD/output $CWD/input $MODEL_INDIR/NorthGawlerConvParam.json
#  >/dev/null 2>&1
[ $? -ne 0 ] && echo "FAILED - conversion returned False" && exit 1

# Check that all files were converted
for f in PNGTest@@.PNG gpTest.dae plTest.dae tsTest.dae vsTest.dae small_lithology@@.gz small_density@@.gz small_susceptibility@@.gz; do
[ ! -e $CWD/output/$f ] && echo "FAILED - $f" && exit 1
done

echo "PASSED"

##########################################################################################
# File output exception handling tests
##########################################################################################

echo -n "File output exception handling tests: "

# Make output directory read-only to test exception handling for various file types
\rm -rf $CWD/output
mkdir $CWD/output
chmod a-w $CWD/output
for f in tsTest.ts PNGTest.vo gpTest.gp vsTest.vs RGBA_voxet.vo wlTest.wl; do
python3 -m coverage run -a $CONV_SCRIPT -g -r -f $CWD/output $CWD/input/$f $MODEL_INDIR/NorthGawlerConvParam.json > output.txt 2>&1
[ $? -ne 0 ] && echo "FAILED - test returned False $f" && exit 1
grep 'ERROR - Cannot open file' output.txt >/dev/null 2>&1 && [ $? -ne 0 ] && echo "FAILED - $f" && exit 1
done
\rm output.txt
chmod a+w $CWD/output
echo "PASSED"


# Remove output dir
\rm -rf $CWD/output

exit 0
