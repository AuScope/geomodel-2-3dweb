"""
A collection GOCAD helper functions
"""
import logging
import sys

from lib.imports.gocad.gocad_filestr_types import GocadFileDataStrMap

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


def split_gocad_objs(filename_lines):
    ''' Separates joined GOCAD entries within a file

    :param filename_lines: lines from concatenated GOCAD file
    '''
    gocad_headers = GocadFileDataStrMap.GOCAD_HEADERS
    file_lines_list = []
    part_list = []
    in_file = False
    for line in filename_lines:
        line_str = line.rstrip(' \n\r').upper()
        if not in_file:
            for marker in gocad_headers.values():
                if line_str == marker[0]:
                    in_file = True
                    part_list.append(line)
                    break
        elif in_file:
            part_list.append(line)
            if line_str == 'END':
                in_file = False
                part_list.append(line)
                file_lines_list.append(part_list)
                part_list = []
    return file_lines_list

def check_vertex(num, vrtx_arr):
    ''' If vertex exists in vertex array then returns True else False

    :param num: vertex number to search for
    :param vrtx_arr: vertex array
    '''
    for vrtx in vrtx_arr:
        if vrtx.n == num:
            return True
    return False


def _parse_quoted_labels(line_str):
    ''' Look out for double-quoted label strings and substitute underscores

    :param line_str: line string
    :reurns: all double-quoted labels with spaces now have double quotes removed and underscores
             substituted for labels
    '''
    while line_str.count('"') >= 2:
        before_tup = line_str.partition('"')
        after_tup = before_tup[2].partition('"')
        line_str = before_tup[0] + " " + after_tup[0].strip(' ').replace(' ', '_') \
                   + " " + after_tup[2]
    return line_str


def _parse_quoted_filename(line):
    ''' Split up the string, correctly parsing a quoted filename

    :param line: a line of input file
    :returns: array of tokens, split up version of line, token separator is a space
    '''
    if line.count('"') < 2:
        return line.split()
    if line.count('"') >= 2:
        before_tup = line.partition('"')
        after_tup = before_tup[2].partition('"')
    return before_tup[0].split() + [after_tup[0]] + after_tup[2].split()


def make_line_gen(file_lines):
    ''' This is a Python generator function that processes lines of the GOCAD object file
        and returns each line in various forms, from quite unprocessed to fully processed

    :param filename_str: filename of gocad file
    :param file_lines: array of strings of lines from gocad file
    :returns: array of field strings in upper case with double quotes removed from strings,
             array of field string in original case without double quotes removed,
             line of GOCAD file in upper case,
             boolean, True iff it is the last line of the file
    '''
    for line in file_lines:
        line_str = line.rstrip(' \n\r').upper()

        # Split up the string, substituting underscores for spaces in doubled quoted labels
        line_str = _parse_quoted_labels(line_str)
        splitstr_arr = line_str.split()

        # Split up the string, correctly parsing quoted filename
        splitstr_arr_raw = _parse_quoted_filename(line.rstrip(' \n\r'))

        # Skip blank lines
        if not splitstr_arr:
            continue
        yield splitstr_arr, splitstr_arr_raw, line_str, line == file_lines[-1:][0]
    yield [], [], '', True
