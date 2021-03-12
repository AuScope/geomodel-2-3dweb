''' This class is used to build the config file for each model within the website
'''
import logging
import sys
import os
import json
from collections import defaultdict

# Set up debugging
LOCAL_LOGGER = logging.getLogger(__name__)

# Create console handler
LOCAL_HANDLER = logging.StreamHandler(sys.stdout)

# Create formatter
LOCAL_FORMATTER = logging.Formatter('%(asctime)s -- %(name)s -- %(levelname)s - %(message)s')

# Add formatter to ch
LOCAL_HANDLER.setFormatter(LOCAL_FORMATTER)

# Add handler to logger
LOCAL_LOGGER.addHandler(LOCAL_HANDLER)

LOCAL_LOGGER.setLevel(logging.INFO)  # logging.DEBUG

class ConfigBuilder():


    def __init__(self, debug_level=logging.INFO):
        '''
        A list of geographical extents [ [min_x, max_x, min_y, max_y], ... ]
        NB: An extent is a list of coords defining boundaries of model
        '''
        self.extent_list = []

        '''
        A list of model config dicts
        '''
        self.config_list = []


    def add_config_list(self, config_list):
        ''' Add model config dict to internal list
            :param config_list: list of model config dicts
        ''' 
        self.config_list += config_list 


    def has_output(self):
        '''
            Returns True iff there are model config dicts that can be written
            out to a config file
        ''' 
        return len(self.config_list) > 0


    def add_ext(self, ext):
        ''' Adds an extent to this instance's internal extent list
            :param ext: single extent [min_x, max_x, min_y, max_y]
        '''
        self.extent_list.append(ext)


    def reduce_extents(self):
        ''' Reduces the internal list of extents to just one extent
            :returns: single extent [min_x, max_x, min_y, max_y]
        '''
        LOCAL_LOGGER.debug("reduce_extents()")

        out_extent = [sys.float_info.max, -sys.float_info.max, sys.float_info.max, -sys.float_info.max]
        for extent in self.extent_list:
            if len(extent) < 4:
                continue
            if extent[0] < out_extent[0]:
                out_extent[0] = float(extent[0])
            if extent[1] > out_extent[1]:
                out_extent[1] = float(extent[1])
            if extent[2] < out_extent[2]:
                out_extent[2] = float(extent[2])
            if extent[3] > out_extent[3]:
                out_extent[3] = float(extent[3])
        return out_extent


    def create_json_config(self, output_filename, dest_dir, params):
        ''' Creates a JSON file for the website, specifying webasset objects to display in 3D

        :param output_filename: name of file containing created config file
        :param dest_dir: destination directory for output file
        :param params: model input parameters, SimpleNamespace() object,
                      keys are: 'name' 'crs' 'init_cam_dist' and optional 'proj4_defn'
        '''
        LOCAL_LOGGER.debug("create_json_config(%s)", output_filename)

        # Sort by display name before saving to file, sort by display name, then model URL
        sorted_model_dict_list = sorted(self.config_list,
                                    key=lambda x: (x['display_name'], x['model_url']))
        config_dict = {"properties": {"crs": params.crs, "extent": self.reduce_extents(),
                                      "name": params.name,
                                      "init_cam_dist": params.init_cam_dist
                                     },
                       "type": "GeologicalModel",
                      "version": 1.0
                      }
        # Are there any sidebar group labels that we can use?
        # If not, then put them in "Not Grouped"
        if hasattr(params, 'grp_struct_dict'):
            config_dict['groups'] = defaultdict(list)
            for model in sorted_model_dict_list:
                model_file = model['model_url']
                if model_file in params.grp_struct_dict:
                    group_name = params.grp_struct_dict[model_file][0]
                    config_dict["groups"][group_name].append(model)
                else:
                    config_dict["groups"]["Not Grouped"].append(model)

            # Are there WMS layers?
            if hasattr(params, 'wms_services'):
                for layer in params.wms_services:
                    config_dict['groups']['WMS Layers'].append({ **layer,
                                                                "type": "WMSLayer",
                                                                "displayed": True,
                                                                "include": True})

        # Is there a proj4 definition?
        if hasattr(params, 'proj4_defn'):
            config_dict["properties"]["proj4_defn"] = params.proj4_defn
        try:
            # Save out web asset JSON config file
            out_file = os.path.join(dest_dir, os.path.basename(output_filename))
            with open(out_file, "w") as file_p:
                json.dump(config_dict, file_p, indent=4, sort_keys=True)
        except OSError as os_exc:
            LOCAL_LOGGER.error(f"Cannot open file {output_filename}, {os_exc}")
            return

        # Optionally create the 'GroupStructure' section of model conversion JSON config file
        # This can be added to the model conv file to make it easy to categorise
        # the model parts in the website's sidebar
        conv_part_list = []
        if len(config_dict['groups']['Not Grouped']) > 0:
            for part in config_dict['groups']['Not Grouped']:
                conv_part = {'FileNameKey': part['model_url'], "Insert": { 'display_name': part['display_name'] }}
                if 'popups' in part:
                    conv_part['Insert']['popups'] = part['popups']
                conv_part_list.append(conv_part)

            try:
                # Save model conversion file
                out_file = os.path.join(dest_dir, "conv_group_struct.json")
                with open(out_file, 'w') as out_fp:
                    json.dump({'GroupStructure': {"Not Grouped": conv_part_list}}, out_fp, indent=4, sort_keys=True)
            except OSError as os_exc:
                LOCAL_LOGGER.error(f"Cannot save file {out_file}, {os_exc}")


    def add_config(self, gs_dict, label_str, popup_dict, file_name, outsrc_filename,
                   model_name, file_ext='.gltf', position=[0.0, 0.0, 0.0], styling={}):
        ''' Adds more config information to popup dictionary

        :param gs_dict: group structure dictionary (group struct dict format: \
        { filename: ( group_name, { insert_key1: val, insert_key2: val } } )
        :param label_str: string to use as a display name for this part of the \
        model, if none available in group struct dict
        :param popup_dict: information to display in popup window \
        ( popup dict format: { object_name: { 'attr_name': attr_val, ... } } where 'attr_name' is one of: 'name', 'title', 'href')
        :param file_name:  file and path (without extension) of model part source file
        :param outsrc_filename: file & path of source file when copied to output dir
        :param model_name: model name
        :param file_ext: optional file extension of 'file_name', defaults to '.gltf'
        :param position: optional [x,y,z] position of model part
        :param styling: optional dict of styling parameters e.g. \
                        { "labels": [  \
                            { \
                                "display_name": "MARKER_TOPMOROAKVELKERRI_GRP", \
                                "position": [ \
                                    425500.0, \
                                    8028000.0, \
                                    228.699997 \
                                ] \
                            }, \
                          ] \
                        }
        :returns: a dict of model configuration info, which includes the popup dict
        '''
        LOCAL_LOGGER.debug("add_config(%s, %s, %s, %s)", label_str, file_name, model_name, file_ext)
        np_filename = os.path.basename(file_name)
        modelconf_dict = {}
        modelconf_dict['styling'] = styling
        model_url = np_filename + file_ext
        modelconf_dict['model_url'] = model_url
        if outsrc_filename is not None:
            modelconf_dict['src_filename'] = os.path.basename(outsrc_filename)
        if file_ext.upper() == ".PNG":
            # PNG files do not have any coordinates, so they must be supplied
            modelconf_dict['type'] = 'ImagePlane'
            modelconf_dict['position'] = position
        elif file_ext.upper() == '.GZSON':
            modelconf_dict['type'] = 'GZSON'
        else:
            modelconf_dict['type'] = 'GLTFObject'
        modelconf_dict['popups'] = popup_dict

        self.add_inserts(gs_dict, model_url, modelconf_dict, label_str.replace('_', ' '))

        modelconf_dict['include'] = True
        modelconf_dict['displayed'] = True
        self.config_list.append(modelconf_dict)


    def add_inserts(self, gs_dict, model_part_key, modelconf_dict, alt_name):
        ''' Sets the 'display_name' and other inserts from the group structure dictionary

        :param gs_dict: group structure dictionary (group struct dict format: \
        { filename: ( group_name, { insert_key1: val, insert_key2: val } } ))
        :param model_part_key: model part key in 'gs_dict'
        :param modelconf_dict: dictionary of model information
        :param alt_name: alternative 'display_name' when not supplied in 'gs_dict'
        '''
        # Include inserts from group struct dict
        if model_part_key in gs_dict and len(gs_dict[model_part_key]) > 1:
            for ins_k, ins_v in gs_dict[model_part_key][1].items():
                modelconf_dict[ins_k] = ins_v

        # If display name not in group structure dict, use alt name string
        if 'display_name' not in modelconf_dict:
            modelconf_dict['display_name'] = alt_name


    def add_vol_config(self, gs_dict, geom_obj, style_obj, meta_obj):
        ''' Create a dictionary containing volume configuration data
        :param gs_dict: group structure dictionary (group struct dict format: \
        { filename: ( group_name, { insert_key1: val, insert_key2: val } } ))
        :param geom_obj: ModelGeometries object
        :param style_obj: STYLE object
        :param meta_obj: METADATA object
        :returns: a dict of volume config data
        '''
        model_url = os.path.basename(meta_obj.src_filename)+'.gz'
        modelconf_dict = {'model_url': model_url, 'type': '3DVolume',
                          'include': True, 'displayed': False}
        self.add_inserts(gs_dict, model_url, modelconf_dict, meta_obj.name)
        modelconf_dict['volumeData'] = {'dataType': geom_obj.vol_data_type,
                                        'dataDims': geom_obj.vol_sz,
                                        'origin': geom_obj.vol_origin,
                                        'size': geom_obj.get_vol_side_lengths(),
                                        'maxVal': geom_obj.get_max_data(),
                                        'minVal': geom_obj.get_min_data(),
                                        'rotation': geom_obj.get_rotation()}
        if style_obj.get_colour_table():
            modelconf_dict['volumeData']['colourLookup'] = style_obj.get_colour_table()
        if style_obj.get_label_table():
            modelconf_dict['volumeData']['labelLookup'] = style_obj.get_label_table()
        self.config_list.append(modelconf_dict)

