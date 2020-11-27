import sys
import os
import logging
import gzip
import shutil
from shutil import SameFileError
import zipfile

from lib.exports.png_kit import PngKit
from lib.exports.collada_kit import ColladaKit
from lib.exports.netcdf_kit import NetCDFKit
from lib.imports.gocad.gocad_importer import GocadImporter, extract_from_grp
from lib.imports.gocad.gocad_filestr_types import GocadFileDataStrMap
from lib.imports.gocad.helpers import split_gocad_objs
from lib.file_processing import is_only_small
import lib.exports.collada2gltf as collada2gltf
from lib.config_builder import ConfigBuilder

from converters.converter import Converter

GROUP_LIMIT = 8
''' If there are more than GROUP_LIMIT number of GOCAD objects in a group file
    then use one COLLADA file else put use separate COLLADA files for each object
'''

VOL_SLICER = True
''' If 'True', it will create a volume slicer for voxet files
    else will create cubes, which will only work for smaller volumes
'''


NETCDF_THRESHOLD = 3000
''' Threshold at which VS & PL files will revert to writing a NetCDF file instead of making GLTF
'''


class Gocad2WebAsset(Converter):
    """ Converts some GOCAD files to COLLADA, then GLTFs, others are converted to GZIP or NetCDF

        TS -> COLLADA -> GLTF
        PL -> COLLADA -> GLTF
        PL -> NETCDF (larger number of lines)
        VO -> GZIP
        SG -> GZIP (only if there are no faults)
        VS -> COLLADA -> GLTF (small number of points)
        VS -> NETCDF (larger number of points)
        WL -> GLTF

        NB: GP object files are split up and each sub object converted

        This creates the classes to parse the GOCAD object file, and the classes to output the web asset files
    """

    def __init__(self, debug_lvl, params_obj, model_url_path, coord_offset, ct_file_dict, nondef_coords):
        """ Constructor for 'Gocad2Collada' class

        :param debug_lvl: debug level e.g. 'logging.DEBUG'
        :param params_obj: model parameter object
        :param model_url_path: model URL path
        :param coord_offset: (X,Y,Z) floats; objects are generated with constant offset to their 3d coords
        :param ct_file_dict: colour table file dictionary
        :param nondef_coords: if True then will not stop if encounters non-default GOCAD coordinates
        """

        # Create logging console handler
        handler = logging.StreamHandler(sys.stdout)

        # Create logging formatter
        formatter = logging.Formatter('%(asctime)s -- %(name)s -- %(levelname)s - %(message)s')

        # Add formatter to ch
        handler.setFormatter(formatter)

        # Set up debugging
        self.logger = logging.getLogger(__name__)

        # Add handler to LOGGER and set level
        self.logger.addHandler(handler)
        self.logger.setLevel(debug_lvl)
        self.debug_lvl = debug_lvl

        # If true will not stop if a file has non default coordinates
        self.nondef_coords = nondef_coords

        # Coordinate Offsets are stored here, key is filename, value is (x,y,z)
        self.coord_offset = coord_offset

        # Colour table files: key is GOCAD filename, value is a tuple: (CSV colour table filename (w/o path),
        #                     list of values to be rendered as transparent)
        self.ct_file_dict = ct_file_dict

        # Name of model as specified in its URL
        self.model_url_path = model_url_path

        # Process the parameter file
        self.params = params_obj

        # Config Builder object
        self.config_build_obj = ConfigBuilder()

        # Output kits
        self.coll_kit_obj = ColladaKit(self.debug_lvl)
        self.png_kit_obj = PngKit(self.debug_lvl)
        self.netcdf_kit_obj = NetCDFKit(self.debug_lvl)

        self.file_datastr_map = GocadFileDataStrMap()


    def get_supported_exts(self):
        ''' Returns a list of file extensions which can be converted

        :returns: a list of file extensions which can be converted
        '''
        return GocadImporter.SUPPORTED_EXTS


    def process_points(self, whole_file_lines, dest_dir, file_name, base_xyz, filename_str, src_dir):
        ''' Takes in GOCAD lines and converts to a COLLADA file if less than 3000 points,
            else converts to a NetCDF file.

        :param whole_file_lines: list of strings taken from file's lines
        :param dest_dir: destination directory
        :param file_name: source file name with path but without extension
        :param base_xyz: [x,y,z] offset for writing out coordinates
        :param filename_str: source file name with path and extension
        :param src_dir: source directory

        '''
        self.logger.debug("process_points(%s, %s, %s, %s, %s)", repr(dest_dir), repr(file_name), repr(base_xyz), repr(filename_str), repr(src_dir))
        file_lines_list = split_gocad_objs(whole_file_lines)
        out_filename = os.path.join(dest_dir, os.path.basename(file_name))
        file_ext='.gltf'
        for mask_idx, file_lines in enumerate(file_lines_list):
            if len(file_lines_list) > 1:
                o_fname = os.path.join(dest_dir, os.path.basename(file_name))
                out_filename = "{0}_{1:d}".format(o_fname, mask_idx)
            gocad_obj = GocadImporter(self.debug_lvl, base_xyz=base_xyz,
                                      nondefault_coords=self.nondef_coords,
                                      ct_file_dict=self.ct_file_dict)

            # Check that conversion worked
            is_ok, gsm_list = gocad_obj.process_gocad(src_dir, filename_str, file_lines)
            if not is_ok:
                self.logger.warning("Could not process %s", filename_str)
                continue

            # Write out files
            prop_filename = out_filename
            if len(gsm_list) > 1:
                prop_filename += "_0"
            # Loop around when several properties in one GOCAD object
            for prop_idx, (geom_obj, style_obj, meta_obj) in enumerate(gsm_list):
                if prop_idx > 0:
                    prop_filename = "{0}_{1:d}".format(out_filename, prop_idx)
                # If too many points then output a point cloud
                # TODO: Can't handle mixtures of GLTF and NC
                if len(geom_obj.vrtx_arr) < NETCDF_THRESHOLD:
                    popup_dict = self.coll_kit_obj.write_collada(geom_obj,
                                                                 style_obj,
                                                                 meta_obj,
                                                                 prop_filename)
                else:
                    popup_dict = self.netcdf_kit_obj.write_points(geom_obj,
                                                                  style_obj,
                                                                  meta_obj,
                                                                  prop_filename)
                    file_ext='.nc'
 
                src_filename = self.copy_source(filename_str, dest_dir)
                self.config_build_obj.add_config(self.params.grp_struct_dict,
                                            meta_obj.name, popup_dict,
                                            prop_filename, src_filename,
                                            self.model_url_path, file_ext=file_ext)
                self.config_build_obj.add_ext(geom_obj.get_extent())
        return True


    def process_volumes(self, whole_file_lines, dest_dir, file_name, base_xyz, filename_str, src_dir): 
        """ Process file that contains a 3D volume

        :param whole_file_lines: list of strings taken from file's lines
        :param dest_dir: destination directory
        :param file_name: source file name with path but without extension
        :param base_xyz: [x,y,z] offset for writing out coordinates
        :param file_name_str: source file name with path and extension
        :param src_dir: source directory
        """
        self.logger.debug("process_volumes("+file_name+")")
        file_lines_list = split_gocad_objs(whole_file_lines)
        has_result = False
        for mask_idx, file_lines in enumerate(file_lines_list):
            if len(file_lines_list) > 1:
                out_filename = "{0}_{1:d}".format(os.path.join(dest_dir,
                                                               os.path.basename(file_name)),
                                                  mask_idx)
            gocad_obj = GocadImporter(self.debug_lvl, base_xyz=base_xyz,
                                      nondefault_coords=self.nondef_coords,
                                      ct_file_dict=self.ct_file_dict)

            # Check that conversion worked
            is_ok, gsm_list = gocad_obj.process_gocad(src_dir, filename_str, file_lines)
            if not is_ok:
                self.logger.warning("Could not process %s", filename_str)
                continue

            # Loop around when several binary files in one GOCAD VOXET object
            for prop_idx, (geom_obj, style_obj, meta_obj) in enumerate(gsm_list):
                out_filename = os.path.join(dest_dir, os.path.basename(meta_obj.src_filename))
                self.write_single_volume((geom_obj, style_obj, meta_obj),
                                         src_dir, out_filename, prop_idx)
                self.config_build_obj.add_ext(geom_obj.get_extent())
            has_result = True
        return has_result


    def process_others(self, whole_file_lines, dest_dir, file_name, base_xyz, filename_str, src_dir, ext_str, out_filename):
        """ Process other kinds of file, e.g. faults

        :param whole_file_lines: list of strings taken from file's lines
        :param dest_dir: destination directory
        :param file_name: source file name with path but without extension
        :param base_xyz: [x,y,z] offset for writing out coordinates
        :param filename_str: source file name with path and extension
        :param src_dir: source directory
        :param ext_str: file extent string
        :param out_filename: output filename
        """
        file_lines_list = split_gocad_objs(whole_file_lines)
        self.coll_kit_obj.start_collada()
        popup_dict = {}
        node_label = ''
        has_result = False
        file_ext='.gltf'
        for file_lines in file_lines_list:
            gocad_obj = GocadImporter(self.debug_lvl, base_xyz=base_xyz,
                                      nondefault_coords=self.nondef_coords)
            is_ok, gsm_list = gocad_obj.process_gocad(src_dir, filename_str, file_lines)
            if not is_ok:
                self.logger.warning("WARNING - could not process %s", filename_str)
                continue
            for geom_obj, style_obj, meta_obj in gsm_list:

                # Check that conversion worked and write out files
                if ext_str == 'TS' and geom_obj.vrtx_arr and geom_obj.trgl_arr \
                           or (ext_str in ['PL', 'WL']) and geom_obj.vrtx_arr  \
                           and geom_obj.seg_arr:
                    # If there are too many lines, write out NetCDF
                    # TODO: Can't handle mixtures of GLTF and NC
                    if ext_str == 'PL' and len(geom_obj.seg_arr) > NETCDF_THRESHOLD:
                        popup_dict = self.netcdf_kit_obj.write_lines(geom_obj,
                                                                      style_obj,
                                                                      meta_obj,
                                                                      out_filename)
                        file_ext='.nc'
                        self.make_config(meta_obj, filename_str, dest_dir, file_name, popup_dict, file_ext)
                    # Else write out as COLLADA
                    else: 
                        p_dict, node_label = self.coll_kit_obj.add_geom_to_collada(geom_obj,
                                                                          style_obj, meta_obj)
                        popup_dict.update(p_dict)
                        has_result = True
                    self.config_build_obj.add_ext(geom_obj.get_extent())

        # If COLLADA object was added
        if has_result:
            self.make_config(meta_obj, filename_str, dest_dir, file_name, popup_dict, file_ext)
            self.coll_kit_obj.end_collada(out_filename, node_label)
        return True


    def make_config(self, meta_obj, filename_str, dest_dir, file_name, popup_dict, file_ext):
        '''
        Make configuration data for model part

        :param filename_str: source file name with path and extension
        :param dest_dir: destination directory
        :param file_name: source file name with path but without extension
        :param popup_dict: dict of values displayed when model part is clicked on
        :param file_ext: file extension
        '''
        # Add in any labels, if they were generated
        s_dict = {}
        if meta_obj.label_list:
            s_dict = { "labels": [] }
            for labl in meta_obj.label_list:
                s_dict["labels"].append({"display_name": labl['name'],
                                         "position": labl['position'] })
        src_filename = self.copy_source(filename_str, dest_dir)
        self.config_build_obj.add_config(self.params.grp_struct_dict,
                                         os.path.basename(file_name),
                                         popup_dict, file_name, src_filename,
                                          self.model_url_path, styling=s_dict, file_ext=file_ext)

    def copy_source(self, src_filename, dest_dir):
        '''
        Compress (using ZIP compression) and copy model source files

        :param src_filename: source filename (with path and extension)
        :param dest_dir: destination directory
        :returns path & filename of destination file or None upon error
        '''
        # First, copy source file to destination directory
        copy_filename = os.path.join(dest_dir, os.path.basename(src_filename))
        try:
            shutil.copyfile(src_filename, copy_filename)
        except SameFileError:
            pass
        except OSError as exc:
            self.logger.error("Cannot copy file %s to %s: %s", src_filename, dest_filename, str(exc))
            return None

        # Then create a compressed ZIP file, relative to destination directory
        noext_src_filename = os.path.splitext(src_filename)[0]
        zip_filename = os.path.basename(noext_src_filename) + '.zip'
        try:
            cwd = os.getcwd()
            os.chdir(dest_dir)
            with zipfile.ZipFile(zip_filename, mode="w", compression=zipfile.ZIP_DEFLATED) as z_obj:
                z_obj.write(os.path.basename(copy_filename)) 
            os.chdir(cwd)
            # Remove copy file
            os.remove(copy_filename)
        except OSError as exc:
            self.logger.error("Cannot compress file %s into %s: %s", src_filename, zip_filename, str(exc))
            os.chdir(cwd)
            return None

        return zip_filename

    def process_groups(self, whole_file_lines, dest_dir, file_name, base_xyz, filename_str, src_dir, out_filename):
        ''' Process GOCAD group file

        :param whole_file_lines: list of strings taken from file's lines
        :param dest_dir: destination directory
        :param file_name: source file name with path but without file extension
        :param base_xyz: [x,y,z] offset for writing out coordinates
        :param filename_str: source file name with path and file extension
        :param src_dir: source directory
        :param out_filename: output path and filename but without file extension
        '''
        gsm_list = extract_from_grp(src_dir, filename_str, whole_file_lines, base_xyz,
                                    self.debug_lvl, self.nondef_coords, self.ct_file_dict)

        # If there are too many entries in the GP file, then use one COLLADA file only
        has_result = False
        if len(gsm_list) > GROUP_LIMIT or is_only_small(gsm_list):
            self.logger.debug("All group objects in one COLLADA file")
            self.coll_kit_obj.start_collada()
            popup_dict = {}
            node_label = ''
            has_geom = False
            for file_idx, (geom_obj, style_obj, meta_obj) in enumerate(gsm_list):
                # Any single layer volumes are still written out to separate image files
                if geom_obj.is_single_layer_vo():
                    out_filename = os.path.join(dest_dir,
                                                os.path.basename(meta_obj.src_filename))
                    self.write_single_volume((geom_obj, style_obj, meta_obj),
                                             src_dir, out_filename, file_idx)
                else:
                    p_dict, node_label = self.coll_kit_obj.add_geom_to_collada(geom_obj, style_obj,
                                                                  meta_obj)
                    popup_dict.update(p_dict)
                    has_geom = True
                self.config_build_obj.add_ext(geom_obj.get_extent())
                has_result = True
            # Only write out the COLLADA file if there were geometries included
            if has_geom and has_result:
                src_filename = self.copy_source(filename_str, dest_dir)
                self.config_build_obj.add_config(self.params.grp_struct_dict,
                                            os.path.basename(file_name), popup_dict,
                                            file_name, src_filename, self.model_url_path)
                self.coll_kit_obj.end_collada(out_filename, node_label)
                

        # Else place each GOCAD object in its own COLLADA file
        else:
            for file_idx, (geom_obj, style_obj, meta_obj) in enumerate(gsm_list):
                if geom_obj.is_volume():
                    out_filename = os.path.join(dest_dir,
                                                os.path.basename(meta_obj.src_filename))
                    self.write_single_volume((geom_obj, style_obj, meta_obj),
                                             src_dir, out_filename, file_idx)
                else:
                    prop_filename = "{0}_{1:d}".format(out_filename, file_idx)
                    p_dict = self.coll_kit_obj.write_collada(geom_obj, style_obj, meta_obj,
                                                        prop_filename)
                    src_filename = self.copy_source(filename_str, dest_dir)
                    self.config_build_obj.add_config(self.params.grp_struct_dict,
                                                meta_obj.name, p_dict,
                                                prop_filename, src_filename,
                                                self.model_url_path)
                self.config_build_obj.add_ext(geom_obj.get_extent())
                has_result = True
        return has_result


    def process(self, filename_str, dest_dir):
        ''' Processes a GOCAD file. This one GOCAD file can contain many parts and produce many
            output files

        :param filename_str: filename of GOCAD file, including path
        :param dest_dir: destination directory
        '''
        self.logger.info("\nProcessing %s", filename_str)
        # If there is an offset from the input parameter file, then apply it
        base_xyz = (0.0, 0.0, 0.0)
        basefile = os.path.basename(filename_str)
        if basefile in self.coord_offset:
            base_xyz = self.coord_offset[basefile]
        file_name, file_ext = os.path.splitext(filename_str)
        ext_str = file_ext.lstrip('.').upper()
        out_filename = os.path.join(dest_dir, os.path.basename(file_name))
        src_dir = os.path.dirname(filename_str)

        # Open GOCAD file and read all its contents, assume it fits in memory
        try:
            file_d = open(filename_str, 'r')
            whole_file_lines = file_d.readlines()
        except OSError as os_exc:
            self.logger.error("Can't open or read - skipping file %s %s", filename_str, os_exc)
            return False, [], []
        ok = False

        # VS files usually have lots of data points and thus one COLLADA file for each GOCAD file
        # If the VS file has too many points, then output as NetCDF4 file
        if self.file_datastr_map.is_points(filename_str):
            ok = self.process_points(whole_file_lines, dest_dir, file_name, base_xyz, filename_str, src_dir)

        # One VO or SG file can produce many other files
        elif self.file_datastr_map.is_volume(filename_str):
            ok = self.process_volumes(whole_file_lines, dest_dir, file_name, base_xyz, filename_str, src_dir)

        # For triangles, wells and lines, place multiple GOCAD objects in one COLLADA file
        elif self.file_datastr_map.is_borehole(filename_str) or self.file_datastr_map.is_flat_shape(filename_str):
            ok = self.process_others(whole_file_lines, dest_dir, file_name, base_xyz, filename_str, src_dir, ext_str, out_filename)

        # Process group files, depending on the number of GOCAD objects inside
        elif self.file_datastr_map.is_mixture(filename_str):
            ok = self.process_groups(whole_file_lines, dest_dir, file_name, base_xyz, filename_str, src_dir, out_filename)

        file_d.close()
        if ok:
            self.logger.debug("process() returns True")
            return True

        self.logger.debug("process() returns False, no result")
        return False


    def write_single_volume(self, gsm_obj, src_dir, out_filename, prop_idx):
        ''' Write a single volume to disk
        :param gsm_obj: (MODEL_GEOMETRY, STYLE, METADATA) tuple, contains the geometry of the
                        volume, the volume's style & metadata
        :param src_dir: source directory where there are 3rd party model files
        :param out_filename: output filename without extension
        :param prop_idx: property index of volume's properties, integer
        '''
        geom_obj, style_obj, meta_obj = gsm_obj
        self.logger.debug("write_single_volume(geom_obj=%s, style_obj=%s, meta_obj=%s)",
                          repr(geom_obj), repr(style_obj), repr(meta_obj))
        self.logger.debug("src_dir=%s, out_filename=%s, prop_idx=%d)", src_dir, out_filename,
                          prop_idx)

        if geom_obj.vol_data is not None:
            if not geom_obj.is_single_layer_vo():
                if VOL_SLICER:
                    in_filename = os.path.join(src_dir, os.path.basename(out_filename))
                    # Compress volume data and save to file
                    with open(in_filename, 'rb') as fp_in:
                        with gzip.open(out_filename + '.gz', 'wb') as fp_out:
                            shutil.copyfileobj(fp_in, fp_out)
                            self.config_build_obj.add_vol_config(self.params.grp_struct_dict,
                                                            geom_obj, style_obj, meta_obj)

                else:
                    # Produce GLTFs from voxet file
                    popup_list = self.coll_kit_obj.write_vol_collada(geom_obj, style_obj, meta_obj,
                                                                out_filename)
                    for popup_dict_key, popup_dict, out_file in popup_list:
                        # NB: No source file available for volumes yet
                        self.config_build_obj.add_config(self.params.grp_struct_dict,
                                                    popup_dict_key, popup_dict,
                                                    out_file, None, self.model_url_path)

            # Produce a PNG file from voxet file
            else:
                popup_dict = self.png_kit_obj.write_single_voxel_png(geom_obj, style_obj, meta_obj,
                                                                out_filename)
                # Just supply the PNG file as the downloadable source for single layer volumes
                src_filename = out_filename + '.PNG'
                self.config_build_obj.add_config(self.params.grp_struct_dict,
                                            "{0}_{1}".format(meta_obj.name, prop_idx+1),
                                            popup_dict, out_filename, src_filename,
                                            self.model_url_path, file_ext='.PNG',
                                            position=geom_obj.vol_origin)
