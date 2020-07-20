import os

from lib.imports.data_str_types import FileDataStructMap


class GocadFileDataStrMap(FileDataStructMap):

    GOCAD_HEADERS = {
        'TS':['GOCAD TSURF 1'],
        'VS':['GOCAD VSET 1'],
        'PL':['GOCAD PLINE 1'],
        'GP':['GOCAD HETEROGENEOUSGROUP 1', 'GOCAD HOMOGENEOUSGROUP 1'],
        'VO':['GOCAD VOXET 1'],
        'WL':['GOCAD WELL 1'],
        'SG':['GOCAD SGRID 1'],
    }
    ''' Constant assigns possible headers to each filename extension
    '''

    def is_points(self, filename_str):
        ''' Routine to recognise a points file
        :param filename_str: filename (including path) of GOCAD object file
        :return: True if this file contains a points data structure
        '''
        return self.__get_ext(filename_str) == 'VS'


    def is_volume(self, filename_str):
        ''' Routine to recognise a volume file
        :param filename_str: filename (including path) of GOCAD object file
        :return: True if this file contains a volume data structure
        '''
        return self.__get_ext(filename_str) in ['VO', 'SG']


    def is_borehole(self, filename_str):
        ''' Routine to recognise a borehole file
        :param filename_str: filename (including path) of GOCAD object file
        :return: True if this file contains a borehole data structure
        '''
        return self.__get_ext(filename_str) == 'WL'


    def is_flat_shape(self, filename_str):
        ''' Routine to recognise a flat shape file e.g. triangles, planes in 3d
        :param filename_str: filename (including path) of GOCAD object file
        :return: True if this file contains a flat shape data structure
        '''
        return self.__get_ext(filename_str) in ['TS', 'PL']


    def is_mixture(self, filename_str):
        ''' Routine to recognise a file with a mixture of data structures
        :param filename_str: filename (including path) of GOCAD object file
        :return: True if this file contains a mixture of data structures
        '''
        return self.__get_ext(filename_str) == 'GP'


    def __get_ext(self, filename_str):
        file_name, file_ext = os.path.splitext(filename_str)
        ext_str = file_ext.lstrip('.').upper()
        return ext_str
