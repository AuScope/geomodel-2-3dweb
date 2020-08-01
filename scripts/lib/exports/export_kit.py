"""
Parent class for all '_kit' classes
"""
import logging
import sys

class ExportKit:

    def __init__(self, debug_level):
        ''' Initialise class
        :param debug_level: debug level taken from python's 'logging' module
        '''
        # Set up logging, use an attribute of class name so it is only called once
        if not hasattr(ExportKit, 'logger'):
            ExportKit.logger = logging.getLogger(__name__)

            # Create console handler
            handler = logging.StreamHandler(sys.stdout)

            # Create formatter
            formatter = logging.Formatter('%(asctime)s -- %(name)s -- %(levelname)s - %(message)s')

            # Add formatter to ch
            handler.setFormatter(formatter)

            # Add handler to logger and set level
            ExportKit.logger.addHandler(handler)

        # Finally, set debug level
        ExportKit.logger.setLevel(debug_level)
        self.logger = ExportKit.logger

    def start_write(self):
        ''' Generic routine to start the process write out multiple GSM objects 
        '''
        raise NotImplementedError("Subclass must implement abstract method")


    def add_geom(self, geom_obj, style_obj, meta_obj):
        ''' Generic routine to add GSM objects to be written out in future

        :param geom_obj: MODEL_GEOMETRY object that hold geometry and text
        :param style_obj: STYLE object containing colour info
        :param meta_obj: METADATA object, used for labelling
        '''
        raise NotImplementedError("Subclass must implement abstract method")


    def end_write(self):
        ''' Generic routine to write out the accumulated GSM objects
        '''
        raise NotImplementedError("Subclass must implement abstract method")


    def write(self, geom_obj, style_obj, meta_obj, file_name):
        ''' Generic routine to write out a single GSM object

        :param geom_obj: MODEL_GEOMETRY object that hold geometry and text
        :param style_obj: STYLE object containing colour info
        :param meta_obj: METADATA object, used for labelling
        :param out_filename: path & filename file to output
        '''
        raise NotImplementedError("Subclass must implement abstract method")
