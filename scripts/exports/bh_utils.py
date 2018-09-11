def make_borehole_label(borehole_name):
    ''' Returns a label version of the borehole name or id

    :param borehole_name: borehole name or identifier
    '''
    return "borehole-{0}".format(clean_borehole_name(borehole_name))

def make_borehole_filename(borehole_name):
    ''' Returns a string, formatted borehole file name with no filename extension

    :param borehole_name: borehole identifier used to make file name
    '''
    return "Borehole_"+clean_borehole_name(borehole_name)


def clean_borehole_name(borehole_name):
    ''' Returns a clean version of the borehole name or id

    :param borehole_name: borehole identifier
    '''
    return borehole_name.replace(' ','_').replace('/','_').replace(':','_')


