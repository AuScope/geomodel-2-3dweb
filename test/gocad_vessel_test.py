#!/usr/bin/env python3

import sys
import logging

sys.path.append('../scripts')

from gocad_vessel import GOCAD_VESSEL

def test_this(msg, test_str, test_file, assert_str, stop_on_exc=True):
    ''' Function used to run a little test of GOCAD_VESSEL class
        msg - name of test
        test_str - lines of GOCAD file to test
        test_file - name of GOCAD file
        assert_str - string of python code used to evaluate success of test
        stop_on_exc - set to False when you have some code that causes an exception
    '''
    split_str = test_str.split('\n')
    if stop_on_exc == False:
        gv = GOCAD_VESSEL(logging.ERROR, stop_on_exc=False)
    else:
        gv = GOCAD_VESSEL(logging.ERROR, stop_on_exc=True) # DEBUG or ERROR
    gv.process_gocad(".", test_file, split_str)
    try:
        assert(eval(assert_str))
    except AssertionError:
        print(msg, ": FAIL !!")
        sys.exit(1) 
    print(msg, ": PASS")
    
"""
TODO List:

Using GOCAD_KIT:
----------------
Multiple GOCAD entries in GROUP and TSURF files
Parsing directories to find GOCAD files, parsing single files

Using GOCAD_VESSEL:
-------------------
Multiple whitespace in field separators
Spaces in filenames and paths
Control nodes in vertices and atoms with and without properties
Property vertices and atoms (PATOM, PVRTX)
Skipped vertex ids
Colour maps
REGION keyword
SEG
TRGL
property class header: COLOURMAP
Max and min of properties
Max and min of XYZ coords
"""
   
# MAIN PART OF PROGRAMME
if __name__ == "__main__":
    print("GOCAD_VESSEL Regression Test")


    #
    # Recognise file types
    #
    test_this("Recognise VOXEL file",  "GOCAD Voxet 1 \n", "test.vo", "gv.is_vo == True")
    test_this("Recognise TSURF file",  "GOCAD TSurf 1 \n", "test.ts", "gv.is_ts == True")
    test_this("Recognise PLINE file",  "GOCAD PLine 1 \n", "test.pl", "gv.is_pl == True")
    test_this("Recognise VSET file",  "GOCAD VSet 1 \n", "test.vs", "gv.is_vs == True")


    #
    # Double quoted strings
    #
    test_this("Double quoted strings", 'GOCAD Voxet 1 \n AXIS_UNIT " m " " m " " m "', "test.vo", 'gv.xyz_unit == ["M","M","M"]')


    #
    # Inverted z-axis
    #
    test_this("Recognise non-inverted z-axis", "GOCAD Voxet 1 \nGOCAD_ORIGINAL_COORDINATE_SYSTEM\nZPOSITIVE Elevation\n", "test.vo", "gv.invert_zaxis == False")
    test_this("Recognise inverted z-axis", "GOCAD Voxet 1 \nGOCAD_ORIGINAL_COORDINATE_SYSTEM\nZPOSITIVE Depth\n", "test.vo", "gv.invert_zaxis == True")


    #
    # Coord system name
    #
    test_this("Default coord sys name", "GOCAD Voxet 1 \nGOCAD_ORIGINAL_COORDINATE_SYSTEM\nNAME Default\n", "test.vo", "gv.coord_sys_name == 'DEFAULT' and gv.usesDefaultCoords == True")
    test_this("Non-default coord sys name", "GOCAD Voxet 1 \nGOCAD_ORIGINAL_COORDINATE_SYSTEM\nNAME GDA94_MGA_Zone54\n", "test.vo", "gv.coord_sys_name == 'GDA94_MGA_ZONE54' and gv.usesDefaultCoords == False")


    #
    # Solid colours
    #
    test_this("Colour floats*3 test", "GOCAD TSurf 1 \nHEADER {\n*solid*color:0 0.5 1\n}\n", "test.ts", "gv.rgba_tup == (0.0,0.5,1.0,1.0)")
    test_this("Colour floats*4 test", "GOCAD TSurf 1 \nHEADER {\n*solid*color:0.486275 0.596078 0.827451 0.9\n}\n", "test.ts", "gv.rgba_tup == (0.486275,0.596078,0.827451,0.9)")
    test_this("Colour hex test", "GOCAD TSurf 1 \nHEADER {\n*solid*color:#808080\n}\n", "test.ts", "gv.rgba_tup == (0.5019607843137255,0.5019607843137255,0.5019607843137255,1.0)")


    #
    # Header name
    #
    test_this("Recognise header name", "GOCAD TSurf 1 \nHEADER {\nNAME:Testing12/3\n}\n", "test.ts", "gv.header_name == 'TESTING12-3'")


    #
    # Convert kilometres to metres, inverts z-values, parse XYZ
    #
    test_str = """GOCAD TSurf 1
GOCAD_ORIGINAL_COORDINATE_SYSTEM
NAME Default
AXIS_NAME "X" "Y" "Z"
AXIS_UNIT "km" "km" "m"
ZPOSITIVE Depth
END_ORIGINAL_COORDINATE_SYSTEM
TFACE
VRTX 1 868.21875 6936.609375 -354.82565307617187
VRTX 2 868 6936.765625 -354.44522094726562
VRTX 3 868 6934.1875 -352.19583129882812
TRGL 1 2 3
    """
    test_this("Converts kilometres to metres, invert z-values, parse XYZ", test_str, "test.ts", "gv.get_vrtx_arr()[0].xyz == (868218.75,6936609.375,354.82565307617187)")


    #
    # Parse infinity floats
    #
    test_this("Reads plus infinity (linux)", "GOCAD TSurf 1\nVRTX 1 inf 6936.609375 -354.82565307617187", "test.ts", "gv.get_vrtx_arr()[0].xyz[0] == sys.float_info.max")
    test_this("Reads minus infinity (linux)", "GOCAD TSurf 1\nVRTX 1 -inf 6936.609375 -354.82565307617187", "test.ts", "gv.get_vrtx_arr()[0].xyz[0] == -sys.float_info.max")
    test_this("Reads plus infinity (windows)", "GOCAD TSurf 1\nVRTX 1 1.#INF 6936.609375 -354.82565307617187", "test.ts", "gv.get_vrtx_arr()[0].xyz[0] == sys.float_info.max")
    test_this("Reads minus infinity (windows)", "GOCAD TSurf 1\nVRTX 1 -1.#INF 6936.609375 -354.82565307617187", "test.ts", "gv.get_vrtx_arr()[0].xyz[0] == -sys.float_info.max")


    #
    # Ignore bad value in XYZ
    #
    test_this("Ignore bad value in XYZ", "GOCAD TSurf 1\nVRTX 1 blah 6936.609375 -354.82565307617187", "test.ts", "gv.get_vrtx_arr() == []", stop_on_exc=False)


    #
    # Local property classes and no data marker
    #
    test_str = """GOCAD VSet 1
PROPERTY_CLASSES AA BB CC
NO_DATA_VALUES -99999 -99999 -99998
ESIZES 1 1 1 
    """
    test_this("Parse property classes and no data marker", test_str, "test.vs", "'AA' in gv.local_props and 'BB' in gv.local_props and 'CC' in gv.local_props and gv.local_props['CC'].no_data_marker == -99998.0")


    #
    # Parse properties and esizes
    #
    test_str = """GOCAD VSet 1
PROPERTIES AA BB CC
NO_DATA_VALUES -99999 -99999 -99999
ESIZES 1 1 1 
    """
    test_this("Parse properties and esizes", test_str, "test.vs", "'AA' in gv.local_props and 'BB' in gv.local_props and 'CC' in gv.local_props and gv.local_props['BB'].data_sz == 1")


    #
    # Read local property values
    #
    test_str = """GOCAD VSet 1
PROPERTIES AA BB CC
NO_DATA_VALUES -99999 -99999 -99998
PROPERTY_CLASSES AA BB CC
ESIZES 1 1 1 
PVRTX 1 641092.75 6983354.125 6304.10595703125 -110.087890625 -123.456 12.3456
    """
    test_this("Read local property values", test_str, "test.vs", "'AA' in gv.local_props and gv.local_props['AA'].data[(641092.75, 6983354.125, 6304.10595703125)] == -110.087890625")


    #
    #  Voxet properties and dimensions
    #
    test_str = """GOCAD Voxet 1
PROPERTY 1 "Lithology"
PROPERTY_CLASS 1 "lithologies"
INTERPOLATION_METHOD  Block
PROPERTY_KIND 1 "lithologies"
PROPERTY_CLASS_HEADER 1 "lithologies" {
colormap:lithologies
*colormap*size:21
*colormap*nbcolors:21
low_clip:1
high_clip:21
*colormap*nodata:true
*colormap*ndtransparency:1
}
AXIS_O 696000 6863000 -40000 
AXIS_U 51000 0 0 
AXIS_V 0 87000 0 
AXIS_W 0 0 51000 
AXIS_MIN 0 0 0 
AXIS_MAX 1 1 1 
AXIS_N 0 0 0
AXIS_NAME "axis-1" "axis-2" "axis-3"
AXIS_UNIT " number" " number" " number" 
AXIS_TYPE even even even
PROPERTY_SUBCLASS 1 ROCK "lithologies"
PROP_NO_DATA_VALUE 1 -9999
PROP_STORAGE_TYPE 1 Short
PROP_ESIZE 1 2
PROP_SIGNED 1 1
PROP_ETYPE 1  IEEE
PROP_FORMAT 1 RAW
PROP_OFFSET 1 0
PROP_FILE 1 empty_voxet_test_file@@
    """
    test_this("Voxet properties and dimensions", test_str, "test.vo", 
          """'1' in gv.prop_dict and \
gv.prop_dict['1'].no_data_marker == -9999.0 and \
gv.prop_dict['1'].signed_int == True and \
gv.prop_dict['1'].data_type == 'h' and \
gv.prop_dict['1'].file_name == './empty_voxet_test_file@@' and \
gv.prop_dict['1'].data_sz == 2 and \
gv.axis_origin == (696000.0, 6863000.0, -40000.0) and \
gv.axis_u == (51000.0, 0.0, 0.0) and \
gv.axis_v == (0.0, 87000.0, 0.0) and \
gv.axis_w == (0.0, 0.0, 51000.0) and \
gv.axis_min == (0.0, 0.0, 0.0) and \
gv.axis_max == (1.0, 1.0, 1.0) """)

    #
    # Voxet flags file
    #
    test_str = """GOCAD Voxet 1
FLAGS_ARRAY_LENGTH 1856575 
FLAGS_BIT_LENGTH 27 
FLAGS_ESIZE 4 
FLAGS_OFFSET 0 
FLAGS_FILE 3D_geology_flags@@
    """
    test_this("Voxet flags", test_str, "test.vo", "gv.flags_array_length ==  1856575 and gv.flags_bit_length == 27 and gv.flags_bit_size == 4 and gv.flags_offset == 0 and gv.flags_file == './3D_geology_flags@@'")



