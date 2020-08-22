from abc import ABC, abstractmethod

class Converter:
    ''' Super class for implementing a file format converter
    '''

    @abstractmethod
    def __init__(self, debug_lvl, params_obj, model_url_path, coord_offset=(0.0,0.0,0.0), ct_file_dict={}, nondef_coords=True):
        """ Constructor for Converter class

        :param debug_lvl: debug level e.g. 'logging.DEBUG'
        :param params_obj: model parameter object
        :param model_url_path: model URL path
        :param coord_offset: (X,Y,Z) floats; objects are generated with constant offset to their 3d coords
        :param ct_file_dict: colour table file dictionary
        :param nondef_coords: if True then will ignore unknown coordinate systems
        """

        self.config_build_obj = None

        raise NotImplementedError


    @abstractmethod
    def process(filename_str, dest_dir):
        ''' Processes a file.

        :param filename_str: filename of file to be processed, including path
        :param dest_dir: output destination directory
        '''
        raise NotImplementedError


