#!/usr/bin/env python3
"""
Unit test for GocadImporter class
"""
import sys
import logging
import os

# Add in path to local library files
sys.path.append(os.path.join('..', '..', '..', 'scripts'))


from lib.imports.gocad.gocad_importer import GocadImporter, extract_from_grp

#pylint: disable=W0611
from lib.db.geometry.types import ATOM

# pylint: disable=W0611
from lib.db.metadata.metadata import MapFeat

INPUT_DIR = 'input'



def test_this(msg, test_file, assert_str, stop_on_exc=True, should_fail=False):
    ''' Function used to run a little test of GocadImporter class
        :param msg: name of test
        :param test_file: name of GOCAD file
        :param assert_str: string of python code used to evaluate success of test
        :param stop_on_exc: set to False when you have some code that causes an exception
        :param should_fail: optional, set to True if the test is meant to fail
    '''
    split_str = []
    try:
        test_path = os.path.join(INPUT_DIR, test_file)
        with open(test_path) as file_p:
            split_str = file_p.readlines()
    except OSError as os_exc:
        print("Cannot open or find file: {0}: {1}".format(test_path, repr(os_exc)))
        sys.exit(1)
    if not stop_on_exc:
        gocad_obj = GocadImporter(logging.ERROR, stop_on_exc=False)
    else:
        gocad_obj = GocadImporter(logging.ERROR, stop_on_exc=True) # logging.DEBUG or logging.ERROR
    # pylint: disable=W0612
    is_ok, gsm_list = gocad_obj.process_gocad(".", test_file, split_str)
    # print("is_ok = ", is_ok)
    # print("gsm_list=", repr(gsm_list))
    if not is_ok and not should_fail:
        print(msg, ": FAIL !!")
        sys.exit(1)
    try:
        # pylint: disable=W0123
        assert eval(assert_str)
    except (AssertionError, IndexError) as exc:
        print(msg, ": FAIL !!")
        sys.exit(1)
    print(msg, ": PASS")



def test_group(msg, test_file, assert_str):
    ''' Opens up and parses a GOCAD group file
        :param msg: name of test
        :test_file: name of GOCAD file
        :assert_str: string of python code used to evaluate success of test
    '''
    try:
        with open(os.path.join(INPUT_DIR, test_file)) as file_p:
            file_lines = file_p.readlines()
    except FileNotFoundError:
        print("Cannot find file: '"+test_file+"' in '"+INPUT_DIR+"' directory")
        sys.exit(1)
    # pylint: disable=W0612
    gsm_list = extract_from_grp(INPUT_DIR, test_file, file_lines, (0.0, 0.0, 0.0),
                                logging.ERROR, False, {})
    #print("gsm_list=", repr(gsm_list))
    try:
        # pylint: disable=W0123
        assert eval(assert_str)
    except AssertionError:
        print(msg, ": FAIL !!")
        sys.exit(1)
    print(msg, ": PASS")





# MAIN PART OF PROGRAMME
if __name__ == "__main__":
    print("GocadImporter Unit Test")


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
    test_this("Double quoted strings", "test005.vo", 'gocad_obj.xyz_unit == ["M","M","M"]')

    #
    # Non-inverted z-axis
    #
    test_this("Recognise non-inverted z-axis", "test006.vo", "gocad_obj.invert_zaxis == False")

    #
    # Inverted z-axis
    #
    test_this("Recognise inverted z-axis", "test007.vo", "gocad_obj.invert_zaxis == True")


    #
    # Default coord system name
    #
    test_this("Default coord sys name",
              "test008.vo", "gocad_obj.coord_sys_name == 'DEFAULT' and \
              gocad_obj.uses_default_coords == True")

    #
    # Non-default coord system name
    #
    test_this("Non-default coord sys name", "test009.vo",
              "gocad_obj.coord_sys_name == 'GDA94_MGA_ZONE54' and \
              gocad_obj.uses_default_coords == False",
              should_fail=True)


    #
    # Solid colours: 3 floats
    #
    test_this("Colour floats*3 test", "test010.ts",
              "gsm_list[0][1].get_rgba_tup() == (0.0,0.5,1.0,1.0)")

    #
    # Solid colours: 4 floats
    #
    test_this("Colour floats*4 test", "test011.ts",
              "gsm_list[0][1].get_rgba_tup() == (0.486275,0.596078,0.827451,0.9)")

    #
    # Solid colours: hex
    #
    test_this("Colour hex test", "test012.ts",
              """gsm_list[0][1].get_rgba_tup() == (0.5019607843137255,
                                                   0.5019607843137255,
                                                   0.5019607843137255,1.0)""")


    #
    # Recognise header name, including forward slash
    #
    test_this("Recognise header name, including forward slash",
              "test013.ts", "gsm_list[0][2].name == 'TESTING12-3'")


    #
    # Convert kilometres to metres, inverts z-values, parse XYZ
    #
    test_this("Converts kilometres to metres, invert z-values, parse XYZ", "test014.ts",
              "gsm_list[0][0].vrtx_arr[0].xyz == (868218.75,6936609.375,354.82565307617187)")


    #
    # Parse infinity floats
    #
    test_this("Reads plus infinity (linux)", "test015.ts",
              "gsm_list[0][0].vrtx_arr[0].xyz[0] == sys.float_info.max")
    test_this("Reads minus infinity (linux)", "test016.ts",
              "gsm_list[0][0].vrtx_arr[0].xyz[0] == -sys.float_info.max")
    test_this("Reads plus infinity (windows)", "test017.ts",
              "gsm_list[0][0].vrtx_arr[0].xyz[0] == sys.float_info.max")
    test_this("Reads minus infinity (windows)", "test018.ts",
              "gsm_list[0][0].vrtx_arr[0].xyz[0] == -sys.float_info.max")


    #
    # Ignore bad value in XYZ
    #
    test_this("Ignore bad value in XYZ", "test019.ts",
              "gsm_list[0][0].vrtx_arr == []", stop_on_exc=False)


    #
    # Local property classes and no data marker
    #
    test_this("Parse property classes and no data marker", "test020.vs",
              "'AA' in gocad_obj.local_props and 'BB' in gocad_obj.local_props and \
              'CC' in gocad_obj.local_props and \
              gocad_obj.local_props['CC'].no_data_marker == -99998.0")


    #
    # Parse properties and esizes
    #
    test_this("Parse properties and esizes", "test021.vs",
              "'AA' in gocad_obj.local_props and 'BB' in gocad_obj.local_props and \
              'CC' in gocad_obj.local_props and gocad_obj.local_props['BB'].data_sz == 1")


    #
    # Read local property values
    #
    test_this("Read local property values", "test022.vs",
              """'AA' in gocad_obj.local_props and \
gocad_obj.local_props['AA'].data_xyz[(641092.75, \
                                      6983354.125, \
                                      6304.10595703125)] == -110.087890625""")


    #
    #  Voxet properties and dimensions
    #
    test_this("Voxet properties and dimensions", "test023.vo",
              """'1' in gocad_obj.prop_dict and \
gocad_obj.prop_dict['1'].no_data_marker == -9999.0 and \
gocad_obj.prop_dict['1'].signed_int == True and \
gocad_obj.prop_dict['1'].data_type == 'h' and \
gocad_obj.prop_dict['1'].file_name == './tiny_voxet_test_file@@' and \
gocad_obj.prop_dict['1'].data_sz == 2 and \
gsm_list[0][0].vol_origin == (696000.0, 6863000.0, -40000.0) and \
gsm_list[0][0].vol_axis_u == (51000.0, 0.0, 0.0) and \
gsm_list[0][0].vol_axis_v == (0.0, 87000.0, 0.0) and \
gsm_list[0][0].vol_axis_w == (0.0, 0.0, 51000.0) and \
gsm_list[0][0].vol_sz == (1.0, 1.0, 1.0) """)

    #
    # Voxet flags file
    #
    test_this("Voxet flags", "test024.vo",
              """gocad_obj.flags_array_length ==  1856575 and \
gocad_obj.flags_bit_length == 27 and gocad_obj.flags_bit_size == 4 and \
gocad_obj.flags_offset == 0 and gocad_obj.flags_file == './3D_geology_flags@@'""")


    #
    # Voxet rock table and color table
    #
    test_this("Voxet rock table and color table", "test025.vo",
              """gocad_obj.prop_dict['1'].is_index_data and \
gocad_obj.rock_label_idx['1'][2] == 'LLEWELLYN_REPEAT' and \
gocad_obj.rock_label_idx['1'][13] == 'DOUBLECROSSING' and \
gocad_obj.prop_dict['1'].colourmap_name == 'ROCKCODE' and \
gocad_obj.prop_dict['1'].colour_map[9]==(0.909804,0.564706,0.203922,1.0)""")

    #
    # Voxet data
    #
    test_this("Voxet data", "test025.vo", "gsm_list[0][0].vol_data[0][0][0] == 1.0")

    #
    # Max & min of XYZ values
    #
    test_this("Max & min of XYZ values", "test026.ts",
              """gsm_list[0][0].max_x ==868218.75 and \
gsm_list[0][0].min_x == 868000.0 and gsm_list[0][0].max_y == 6936.765625 and \
gsm_list[0][0].min_y == 6934.1875 and gsm_list[0][0].max_z == -352.19583129882812 and \
gsm_list[0][0].min_z == -354.82565307617187""")


    #
    # Max and min of property values
    #
    test_this("Max & min of property values", "test027.vs",
              "gocad_obj.local_props['HRZR'].data_stats == {'min': -110.087890625, \
                                                            'max': 23.025390625}")

    #
    # Two sets of vertex property values
    #
    test_this("Two sets of vertex properties", "test028.ts", "len(gsm_list)==1")

    #
    # Names of objects and properties
    #
    test_this("Names of objects and properties", "test028.ts",
              """gsm_list[0][2].name == 'BASE' and \
gsm_list[0][2].get_property_name(0) == 'I' and \
gsm_list[0][2].get_property_name(1) == 'J'""")

    #
    # Values of properties
    #
    test_this("Values of properties", "test028.ts",
              """gsm_list[0][0].get_xyz_data(0)[(459395.951171875,
                                                 8241423.6875,
                                                 -475.7239685058594)] == 1057.0 \
and gsm_list[0][0].get_xyz_data(1)[(459395.951171875,
                                                 8241423.6875,
                                                 -475.7239685058594)] == 927.0""")

    #
    # Renumber skipped vertex ids, recognise TRGL keyword
    #
    test_this("Renumber skipped vertex ids, recognise TRGL keyword", "test028.ts",
              "gsm_list[0][0].vrtx_arr[5].n == 6 and gsm_list[0][0].trgl_arr[2].abc == (4, 5, 6)")

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
    test_this("Region data in voxet file", "test030.vo",
              """gocad_obj.region_colour_dict['QUARTZ'] == (0.641993, 0.756863, 0.629236, 1.0) and \
gocad_obj.region_colour_dict['SLATE'] == (0.25, 0.25, 0.25, 1.0) \
and gocad_obj.region_dict['8'] == 'QUARTZ' \
and gocad_obj.region_dict['9'] == 'SLATE'""")

    #
    # Handle control nodes
    #
    test_this("Handle control nodes", "test031.ts",
              """gsm_list[0][0].get_xyz_data(0)[(459395.951171875,
                                                 8241423.6875,
                                                 -475.7239685058594)] == 1057.0 \
             and gsm_list[0][0].get_xyz_data(1)[(459395.951171875,
                                                 8241423.6875,
                                                 -475.7239685058594)] == 927.0""")

    #
    # ATOMS with and without properties
    #
    test_this("ATOMS with and without properties", "test032.ts",
              """gsm_list[0][0].get_xyz_data()[(459876.3125,
                                                8241554.9453125,
                                                -485.6229248046875)] == 1050.0 \
and len(gsm_list[0][0].atom_arr)==4 and ATOM(6,6) in gsm_list[0][0].atom_arr""")

    #
    # Extract GOCAD objects from group file
    #
    test_group("Extract GOCAD objects from group file", "test033.gp",
               "len(gsm_list)==6 and \
gsm_list[0][0].vrtx_arr[0].xyz == (856665.6796875, 6091995.966796875, 77.90100860595703) \
and gsm_list[0][2].name == 'TEST033-TEST-1' and gsm_list[0][2].get_property_name() == 'OBJECTID' \
and gsm_list[0][0].get_xyz_data()[(856665.6796875, 6091995.966796875, 77.90100860595703)] == 10.0")

    #
    # Extraction of metadata
    #
    test_this("Extraction of GeoSciML MappedFeatures - part 1", "test034.ts",
              "gsm_list[0][2].geofeat_name == 'F123' and \
gsm_list[0][2].mapped_feat == MapFeat.SHEAR_DISP_STRUCT")

    test_this("Extraction of GeoSciML MappedFeatures - part 2", "test035.ts",
              "gsm_list[0][2].geofeat_name == 'MESOZOIC' and \
gsm_list[0][2].geoevent_numeric_age_range == 200 and \
gsm_list[0][2].mapped_feat == MapFeat.GEOLOGICAL_UNIT")

    test_this("Extraction of GeoSciML MappedFeatures - part 3", "test036.ts",
              "gsm_list[0][2].geofeat_name == 'VOI' and \
gsm_list[0][2].mapped_feat == MapFeat.CONTACT")
