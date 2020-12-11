import sys
import os
import logging
import gzip
import shutil
from shutil import SameFileError
import zipfile
import csv

from lib.exports.gzson_kit import GZSONKit
from lib.config_builder import ConfigBuilder

from lib.imports.xyzv.xyzv_importer import process_xyzv

from converters.converter import Converter

class XYZV2WebAsset(Converter):
    """ Converts some XYZV files to GEOJSON GZIP

        This parses the XYZ object file and calls the classes to output the web asset files
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
        self.gzson_kit_obj = GZSONKit(self.debug_lvl)

    def get_supported_exts(self):
        ''' Returns a list of file extensions which can be converted

        :returns: a list of file extensions which can be converted
        '''
        return ['XYZV']

    def process_points(self, points_list, dest_dir, noext_filename, base_xyz, filename, src_dir):
        ''' Takes in XYZV lines and converts to a GZipped GEOJSON file.

        :param points_list: list of [x,y,z,v] taken from file's lines
        :param dest_dir: destination directory
        :param noext_filename: source file name with path but without extension
        :param base_xyz: [x,y,z] offset for writing out coordinates
        :param filename: source file name with path and extension
        :param src_dir: source directory

        '''
        self.logger.debug("process_points(%s, %s, %s, %s, %s)", repr(dest_dir), repr(noext_filename), repr(base_xyz), repr(filename), repr(src_dir))
        base_filename = os.path.basename(noext_filename)
        out_filename = os.path.join(dest_dir, base_filename)
        file_ext=self.get_supported_exts()[0].lower()

        # Check that conversion worked
        is_ok, gsm_list = process_xyzv(points_list, src_dir, filename, base_filename)
        if not is_ok:
            self.logger.warning("Could not process %s", filename)
            return False

        # Write out files
        prop_filename = out_filename
        if len(gsm_list) > 1:
            prop_filename += "_0"
        # Loop around when several properties in one GOCAD object
        for prop_idx, (geom_obj, style_obj, meta_obj) in enumerate(gsm_list):
            if prop_idx > 0:
                prop_filename = "{0}_{1:d}".format(out_filename, prop_idx)
            popup_dict = self.gzson_kit_obj.write_points(geom_obj, style_obj, meta_obj, prop_filename)
 
            src_filename = self.copy_source(filename, dest_dir)
            self.config_build_obj.add_config(self.params.grp_struct_dict,
                                            meta_obj.name, popup_dict,
                                            prop_filename, src_filename,
                                            self.model_url_path, file_ext='.gzson')
            self.config_build_obj.add_ext(geom_obj.get_extent())
        return True


    def make_config(self, meta_obj, filename, dest_dir, noext_filename, popup_dict, file_ext):
        '''
        Make configuration data for model part

        :param filename: source file name with path and extension
        :param dest_dir: destination directory
        :param noext_filename: source file name with path but without extension
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
        src_filename = self.copy_source(filename, dest_dir)
        self.config_build_obj.add_config(self.params.grp_struct_dict,
                                         os.path.basename(noext_filename),
                                         popup_dict, noext_filename, src_filename,
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
            self.logger.error("Cannot copy file %s to %s: %s", src_filename, copy_filename, str(exc))
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


    def process(self, filename, dest_dir):
        ''' Processes an XYZV file.

        :param filename: filename of XYZV file, including path
        :param dest_dir: destination directory
        :returns True if successful
        '''
        self.logger.info("\nProcessing %s", filename)
        # If there is an offset from the input parameter file, then apply it
        base_xyz = (0.0, 0.0, 0.0)
        basefile = os.path.basename(filename)
        if basefile in self.coord_offset:
            base_xyz = self.coord_offset[basefile]
        noext_filename, file_ext = os.path.splitext(filename)
        ext_str = file_ext.lstrip('.').upper()
        if ext_str != self.get_supported_exts()[0]:
            self.logger.debug("Cannot process %s - wrong file extension", filename)
            return False 
        out_filename = os.path.join(dest_dir, os.path.basename(noext_filename))
        src_dir = os.path.dirname(filename)
        points_list = []

        # Open XYZV file and read all its contents, assume it fits in memory
        try:
            with open(filename, newline='') as csvfile:
                csvreader = csv.reader(csvfile, delimiter=' ', skipinitialspace=True)
                for xyzv_line in csvreader:
                    if len(xyzv_line) > 3:
                        points_list.append(xyzv_line)
                    else:
                        self.logger.info("Can't read %s - incorrect number of columns", filename)
                        return False

                ok = self.process_points(points_list, dest_dir, noext_filename, base_xyz, filename, src_dir)
                if ok:
                    self.logger.debug("process() returns True")
                    return True

        except (OSError, csv.Error) as exc:
            self.logger.info("Can't open or read - skipping file %s %s", filename, str(exc))
            return False

        self.logger.debug("process() returns False, no result")
        return False

