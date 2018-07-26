#!/usr/bin/env python3

import sys
import logging

sys.path.append('../scripts')

from gocad_vessel import GOCAD_VESSEL

def test_this(msg, test_str, test_file, assert_str):

    split_str = test_str.split('\n')
    gv = GOCAD_VESSEL(logging.CRITICAL) # DEBUG or NOTSET
    gv.process_gocad(".", test_file, split_str)
    try:
        assert(eval(assert_str))
    except AssertionError:
        print(msg, ": FAIL !!")
        sys.exit(1) 
    print(msg, ": PASS")
    
   
# MAIN PART OF PROGRAMME
if __name__ == "__main__":
    print("GOCAD_VESSEL Regression Test")
    test_this("Recognise VOXEL file",  "GOCAD Voxet 1 \n", "test.vo", "gv.is_vo == True")
    test_this("Recognise TSURF file",  "GOCAD TSurf 1 \n", "test.ts", "gv.is_ts == True")
    test_this("Recognise PLINE file",  "GOCAD PLine 1 \n", "test.pl", "gv.is_pl == True")
    test_this("Recognise VSET file",  "GOCAD VSet 1 \n", "test.vs", "gv.is_vs == True")
    test_this("Double quoted strings", 'GOCAD Voxet 1 \n AXIS_UNIT " m " " m " " m "', "test.vo", 'gv.xyz_unit == ["M","M","M"]')
    test_this("Recognise non-inverted z-axis", "GOCAD Voxet 1 \nGOCAD_ORIGINAL_COORDINATE_SYSTEM\nZPOSITIVE Elevation\n", "test.vo", "gv.invert_zaxis == False")
    test_this("Recognise inverted z-axis", "GOCAD Voxet 1 \nGOCAD_ORIGINAL_COORDINATE_SYSTEM\nZPOSITIVE Depth\n", "test.vo", "gv.invert_zaxis == True")
    test_this("Default coord sys name", "GOCAD Voxet 1 \nGOCAD_ORIGINAL_COORDINATE_SYSTEM\nNAME Default\n", "test.vo", "gv.coord_sys_name == 'DEFAULT' and gv.usesDefaultCoords == True")
    test_this("Non-default coord sys name", "GOCAD Voxet 1 \nGOCAD_ORIGINAL_COORDINATE_SYSTEM\nNAME GDA94_MGA_Zone54\n", "test.vo", "gv.coord_sys_name == 'GDA94_MGA_ZONE54' and gv.usesDefaultCoords == False")
    test_this("Colour floats*3 test", "GOCAD TSurf 1 \nHEADER {\n*solid*color:0 0.5 1\n}\n", "test.ts", "gv.rgba_tup == (0.0,0.5,1.0,1.0)")
    test_this("Colour floats*4 test", "GOCAD TSurf 1 \nHEADER {\n*solid*color:0.486275 0.596078 0.827451 0.9\n}\n", "test.ts", "gv.rgba_tup == (0.486275,0.596078,0.827451,0.9)")
    test_this("Colour hex test", "GOCAD TSurf 1 \nHEADER {\n*solid*color:#808080\n}\n", "test.ts", "gv.rgba_tup == (0.5019607843137255,0.5019607843137255,0.5019607843137255,1.0)")
    test_this("Recognise header name", "GOCAD TSurf 1 \nHEADER {\nNAME:Testing12/3\n}\n", "test.ts", "gv.header_name == 'TESTING12-3'")
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
    test_this("Converts metres to kms & invert z-values", test_str, "test.ts", "gv.get_vrtx_arr()[0].xyz == (868218.75,6936609.375,354.82565307617187)")
    
