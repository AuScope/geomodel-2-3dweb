#!/bin/sh
#
# Basic regression test script. Run from the 'regression' directory
#
# Acknowledgements:
# 1) Some of the files for tests derived from these models:
#    http://www.energymining.sa.gov.au/minerals/geoscience/geoscientific_data/3d_geological_models (North Gawler model)
#    https://dasc.dmp.wa.gov.au/dasc/ (Sandstone model)
# 2) SKUA/GOCAD software from the "Paradigm Academic Software Program" (http://www.pdgm.com/affiliations/academic-software-programs/)
#    was used to produce and view the voxet files
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

# Make the output directory
[ ! -e output ] && mkdir output
cd ../../scripts


##########################################################################################
# Convert various file types
##########################################################################################

# Loop around processing different GOCAD objects
for i in 'pl' 'ts' 'vs' 'gp'; do

echo -n "$i File test: "

# Convert GOCAD to COLLADA
./gocad2collada.py -g -f $CWD/output "$CWD/input/${i}Test.$i" input/NorthGawlerConvParam.json >/dev/null 2>&1
[ $? -ne 0 ] && echo "FAILED - conversion returned False" && exit 1

# Remove date stamps from file
egrep -v '(<created>|<modified>)' "$CWD/output/${i}Test.dae" > "$CWD/output/${i}Test2.dae"
[ $? -ne 0 ] && echo "FAILED" && exit 1

# Check that conversion was correct
compare_and_print "$CWD/output/${i}Test2.dae" "$CWD/golden/${i}Test.dae"

done


##########################################################################################
# Convert single layer VOXET to PNG test, with and without colour table
##########################################################################################

echo -n "Convert single layer VOXET to PNG test, with colour table: "

# Convert GOCAD to PNG with colour table
./gocad2collada.py -g -f $CWD/output $CWD/input/PNGTest.vo input/NorthGawlerConvParam.json >/dev/null 2>&1
[ $? -ne 0 ] && echo "FAILED - ct conversion returned False" && exit 1

# Check that conversion was correct
compare_and_print "$CWD/output/PNGTest@@.PNG" "$CWD/golden/PNGTest.PNG"


echo -n "Convert single layer VOXET to PNG test, without colour table: "

# Convert GOCAD to PNG without colour table
./gocad2collada.py -g -f $CWD/output $CWD/input/PNGTestNoCT.vo input/NorthGawlerConvParam.json >/dev/null 2>&1
[ $? -ne 0 ] && echo "FAILED - ct conversion returned False" && exit 1

# Check that conversion was correct
compare_and_print "$CWD/output/PNGTestNoCT@@.PNG" "$CWD/golden/PNGTestNoCT.PNG"



##########################################################################################
# Voxet with single layer RGBA values convert to PNG test
##########################################################################################

echo -n "Convert single layer RGBA voxet to PNG test: "

./gocad2collada.py -g -f $CWD/output $CWD/input/RGBA_voxet.vo input/NorthGawlerConvParam.json >/dev/null 2>&1
[ $? -ne 0 ] && echo "FAILED - ct conversion returned False" && exit 1

# Check that conversion was correct
compare_and_print "$CWD/output/RGBA_voxet@@.PNG" "$CWD/golden/RGBA_voxet.PNG"


##########################################################################################
# Voxet with 3 binary files conversion & output config test
##########################################################################################

echo -n "Voxet with 3 binary files conversion & output config test: "

./gocad2collada.py -g -f $CWD/output -o smallConf.json $CWD/input/small_voxet/small.vo $CWD/input/small_voxet/small.json >/dev/null 2>&1
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
# Recursion test
##########################################################################################

echo -n "Recursion test: "

# Try converting all files at once
./gocad2collada.py -g -r -f $CWD/output $CWD/input input/NorthGawlerConvParam.json >/dev/null 2>&1
[ $? -ne 0 ] && echo "FAILED - conversion returned False" && exit 1

# Check that all files were converted
for f in PNGTest@@.PNG gpTest.dae plTest.dae tsTest.dae vsTest.dae small_lithology@@.gz small_density@@.gz small_susceptibility@@.gz; do
[ ! -e $CWD/output/$f ] && echo "FAILED - $f" && exit 1
done

echo "PASSED"


# Remove output dir
\rm -rf $CWD/output

exit 0
