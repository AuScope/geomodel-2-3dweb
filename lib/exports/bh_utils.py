'''
 A collection of Python functions used to create clean, consistent borehole labels and filenames
'''

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
    return borehole_name.replace(' ','_').replace('/','_').replace(':','_')


