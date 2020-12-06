from enum import Enum

from converters.gocad2webasset import Gocad2WebAsset
from converters.xyzv2webasset import XYZV2WebAsset

class FileType(Enum):
    ''' Enum class enumerating types of file to be converted
        used by 'get_converter' method
    '''
    GOCAD = 1
    XYZV = 2


def get_converter(file_type):
    ''' Used to retrieve converter

    :param type: file type e.g. FileType.GOCAD
    :return: 'Converter' object, or None if not found
    '''
    if file_type==FileType.GOCAD:
        return Gocad2WebAsset
    if file_type==FileType.XYZV:
        return XYZV2WebAsset
    return None
