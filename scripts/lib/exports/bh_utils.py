'''
 A collection of Python functions used to create clean, consistent borehole labels and filenames
'''

import logging, sys


LOG_LVL = logging.INFO
''' Initialise debug level to minimal debugging
'''

# Set up debugging
LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(LOG_LVL)

if not LOGGER.hasHandlers():

    # Create logging console handler
    HANDLER = logging.StreamHandler(sys.stdout)

    # Create logging formatter
    FORMATTER = logging.Formatter('%(name)s -- %(levelname)s - %(message)s')

    # Add formatter to ch
    HANDLER.setFormatter(FORMATTER)

    # Add handler to LOGGER and set level
    LOGGER.addHandler(HANDLER)



def make_borehole_label(borehole_name, depth):
    ''' Makes a consistent and space-free label for borehole sections

    :param borehole_name: name of borehole
    :param depth: depth of section
    :returns: byte string label
    '''
    return bytes(clean(borehole_name)+"_"+str(int(depth)), encoding='utf=8')


def make_borehole_filename(borehole_name):
    ''' Returns a string, formatted borehole file name with no filename extension

    :param borehole_name: borehole identifier used to make file name
    '''
    return "Borehole_"+clean(borehole_name)


def clean(borehole_name):
    ''' Returns a clean version of the borehole name or id

    :param borehole_name: borehole identifier or name
    '''
    return borehole_name.replace(' ', '_').replace('/', '_').replace(':', '_')
