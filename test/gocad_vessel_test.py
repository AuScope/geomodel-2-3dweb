#!/usr/bin/env python3

import sys
import logging
import os

sys.path.append('../scripts')

from imports.gocad.gocad_vessel import GOCAD_VESSEL

INPUT_DIR = 'input'

def test_this(msg, test_file, assert_str, stop_on_exc=True, should_fail=False):
    ''' Function used to run a little test of GOCAD_VESSEL class
        msg - name of test
        test_file - name of GOCAD file
        assert_str - string of python code used to evaluate success of test
        stop_on_exc - set to False when you have some code that causes an exception
    '''
    split_str = []
    try:
        fp = open(os.path.join(INPUT_DIR, test_file))
        split_str = fp.readlines()
        fp.close()
    except FileNotFoundError:
        print("Cannot find file: '"+test_file+"' in '"+INPUT_DIR+"' directory")
        sys.exit(1)
    if stop_on_exc == False:
        gv = GOCAD_VESSEL(logging.ERROR, stop_on_exc=False)
    else:
        gv = GOCAD_VESSEL(logging.ERROR, stop_on_exc=True) # logging.DEBUG or logging.ERROR
    is_ok, gsm_list = gv.process_gocad(".", test_file, split_str)
    #print("gv=", repr(gv))
    #print("gsm_list=", repr(gsm_list))
    if not is_ok and not should_fail:
        print(msg, ": FAIL !!")
        sys.exit(1)
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
Control nodes in vertices and atoms with and without properties
"""
   
# MAIN PART OF PROGRAMME
if __name__ == "__main__":
    print("GOCAD_VESSEL Regression Test")


    #
    # Recognise file types - VOXET
    #
    test_this("Recognise VOXET file", "test001.vo", "gsm_list[0][0].is_volume() == True")

    #
    # Recognise file types - TSURF
    #
    test_this("Recognise TSURF file", "test002.ts", "gsm_list[0][0].is_trgl() == True")

    #
    # Recognise file types - PLINE
    #
    test_this("Recognise PLINE file", "test003.pl", "gsm_list[0][0].is_line() == True")


    #
    # Recognise file types - VSET
    #
    test_this("Recognise VSET file", "test004.vs", "gsm_list[0][0].is_point() == True")

    #
    # Double quoted strings
    #
    test_this("Double quoted strings", "test005.vo", 'gv.xyz_unit == ["M","M","M"]')

    #
    # Non-inverted z-axis
    #
    test_this("Recognise non-inverted z-axis", "test006.vo", "gv.invert_zaxis == False")

    #
    # Inverted z-axis
    #
    test_this("Recognise inverted z-axis", "test007.vo", "gv.invert_zaxis == True")


    #
    # Default coord system name
    #
    test_this("Default coord sys name", "test008.vo", "gv.coord_sys_name == 'DEFAULT' and gv.usesDefaultCoords == True")

    #
    # Non-default coord system name
    #
    test_this("Non-default coord sys name", "test009.vo", "gv.coord_sys_name == 'GDA94_MGA_ZONE54' and gv.usesDefaultCoords == False", should_fail=True)


    #
    # Solid colours: 3 floats
    #
    test_this("Colour floats*3 test", "test010.ts", "gsm_list[0][1].rgba_tup == (0.0,0.5,1.0,1.0)")

    #
    # Solid colours: 4 floats
    #
    test_this("Colour floats*4 test", "test011.ts", "gsm_list[0][1].rgba_tup == (0.486275,0.596078,0.827451,0.9)")

    #
    # Solid colours: hex
    #
    test_this("Colour hex test", "test012.ts", "gsm_list[0][1].rgba_tup == (0.5019607843137255,0.5019607843137255,0.5019607843137255,1.0)")


    #
    # Recognise header name, including forward slash
    #
    test_this("Recognise header name, including forward slash", "test013.ts", "gsm_list[0][2].name == 'TESTING12-3'")


    #
    # Convert kilometres to metres, inverts z-values, parse XYZ
    #
    test_this("Converts kilometres to metres, invert z-values, parse XYZ", "test014.ts", "gsm_list[0][0].vrtx_arr[0].xyz == (868218.75,6936609.375,354.82565307617187)")


    #
    # Parse infinity floats
    #
    test_this("Reads plus infinity (linux)", "test015.ts", "gsm_list[0][0].vrtx_arr[0].xyz[0] == sys.float_info.max")
    test_this("Reads minus infinity (linux)", "test016.ts", "gsm_list[0][0].vrtx_arr[0].xyz[0] == -sys.float_info.max")
    test_this("Reads plus infinity (windows)", "test017.ts", "gsm_list[0][0].vrtx_arr[0].xyz[0] == sys.float_info.max")
    test_this("Reads minus infinity (windows)", "test018.ts", "gsm_list[0][0].vrtx_arr[0].xyz[0] == -sys.float_info.max")


    #
    # Ignore bad value in XYZ
    #
    test_this("Ignore bad value in XYZ", "test019.ts", "gsm_list[0][0].vrtx_arr == []", stop_on_exc=False)


    #
    # Local property classes and no data marker
    #
    test_this("Parse property classes and no data marker", "test020.vs", "'AA' in gv.local_props and 'BB' in gv.local_props and 'CC' in gv.local_props and gv.local_props['CC'].no_data_marker == -99998.0")


    #
    # Parse properties and esizes
    #
    test_this("Parse properties and esizes", "test021.vs", "'AA' in gv.local_props and 'BB' in gv.local_props and 'CC' in gv.local_props and gv.local_props['BB'].data_sz == 1")


    #
    # Read local property values
    #
    test_this("Read local property values", "test022.vs", "'AA' in gv.local_props and gv.local_props['AA'].data_xyz[(641092.75, 6983354.125, 6304.10595703125)] == -110.087890625")


    #
    #  Voxet properties and dimensions
    #
    test_this("Voxet properties and dimensions", "test023.vo", 
          """'1' in gv.prop_dict and \
gv.prop_dict['1'].no_data_marker == -9999.0 and \
gv.prop_dict['1'].signed_int == True and \
gv.prop_dict['1'].data_type == 'h' and \
gv.prop_dict['1'].file_name == './tiny_voxet_test_file@@' and \
gv.prop_dict['1'].data_sz == 2 and \
gsm_list[0][0].vol_origin == (696000.0, 6863000.0, -40000.0) and \
gsm_list[0][0].vol_axis_u == (51000.0, 0.0, 0.0) and \
gsm_list[0][0].vol_axis_v == (0.0, 87000.0, 0.0) and \
gsm_list[0][0].vol_axis_w == (0.0, 0.0, 51000.0) and \
gsm_list[0][0].vol_sz == (1.0, 1.0, 1.0) """)

    #
    # Voxet flags file
    #
    test_this("Voxet flags", "test024.vo", "gv.flags_array_length ==  1856575 and gv.flags_bit_length == 27 and gv.flags_bit_size == 4 and gv.flags_offset == 0 and gv.flags_file == './3D_geology_flags@@'")


    #
    # Voxet rock table and color table
    #
    test_this("Voxet rock table and color table", "test025.vo", "gv.prop_dict['1'].is_index_data and gv.rock_label_idx['1'][2] == 'LLEWELLYN_REPEAT' and  gv.rock_label_idx['1'][13] == 'DOUBLECROSSING' and gv.prop_dict['1'].colourmap_name == 'ROCKCODE' and gv.prop_dict['1'].colour_map[9]==(0.909804,0.564706,0.203922)")

    #
    # Voxet data
    #
    test_this("Voxet data", "test025.vo", "gsm_list[0][0].vol_data[0][0][0] == 1.0")

    #
    # Max & min of XYZ values
    #
    test_this("Max & min of XYZ values", "test026.ts", "gsm_list[0][0].max_X ==868218.75 and gsm_list[0][0].min_X == 868000.0 and gsm_list[0][0].max_Y == 6936.765625 and gsm_list[0][0].min_Y == 6934.1875 and gsm_list[0][0].max_Z == -352.19583129882812 and gsm_list[0][0].min_Z == -354.82565307617187")


    #
    # Max and min of property values
    #
    test_this("Max & min of property values", "test027.vs", "gv.local_props['HRZR'].data_stats == {'min': -110.087890625, 'max': 23.025390625}")

    #
    # Two sets of property values
    #
    test_this("Two sets of vertex properties", "test028.ts", "len(gsm_list)==2")

    #
    # Names of objects and properties 
    #
    test_this("Names of objects and properties", "test028.ts", "gsm_list[0][2].name == 'BASE' and gsm_list[0][2].property_name == 'I' and gsm_list[1][2].name == 'BASE' and gsm_list[1][2].property_name == 'J'")

    #
    # Values of properties
    #
    test_this("Values of properties", "test028.ts", "gsm_list[0][0].xyz_data[(459395.951171875, 8241423.6875, -475.7239685058594)] == 1057.0 and gsm_list[1][0].xyz_data[(459395.951171875, 8241423.6875, -475.7239685058594)] == 927.0")

    #
    # Renumber skipped vertex ids, recognise TRGL keyword
    #
    test_this("Renumber skipped vertex ids, recognise TRGL keyword", "test028.ts", "gsm_list[0][0].vrtx_arr[5].n == 6 and gsm_list[0][0].trgl_arr[2].abc == (4, 5, 6)")

    #
    # Recognise SEG keyword
    #
    test_this("Recognise SEG keyword", "test003.pl", "gsm_list[0][0].seg_arr[0].ab == (1,2)")

    #
    # Spaces in fields
    #
    test_this("Spaces in fields", "test029.ts", "gsm_list[0][0].trgl_arr[0].abc == (1,2,3)")

    #
    # Labels with spaces in quotes
    #
    test_this("Labels with spaces in quotes", "test029.ts", "gsm_list[0][2].name == 'BLAH_1_2'")

    #
    # Region data in voxet file
    #
    test_this("Region data in voxet file", "test030.vo", "gv.region_colour_dict['QUARTZ'] == (0.641993, 0.756863, 0.629236, 1.0) and gv.region_colour_dict['SLATE'] == (0.25, 0.25, 0.25, 1.0) and gv.region_dict['8'] == 'QUARTZ' and gv.region_dict['9'] == 'SLATE'")

    #
    # Handle control nodes
    #
    test_this("Handle control nodes", "test031.ts", "gsm_list[0][0].xyz_data[(459395.951171875, 8241423.6875, -475.7239685058594)] == 1057.0 and gsm_list[1][0].xyz_data[(459395.951171875, 8241423.6875, -475.7239685058594)] == 927.0")

