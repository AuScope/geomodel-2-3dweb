from pyproj import Proj, transform

def __clean_crs(crs):
    ''' Removes namespace prefixes from a CRS: \
        e.g. 'urn:x-ogc:def:crs:EPSG:4326' becomes 'EPSG:4326'

    :param crs: crs string to be cleaned
    :returns: cleaned crs string
    '''
    pair = crs.split(':')[-2:]
    return pair[0]+':'+pair[1]


def convert_coords(input_crs, output_crs, x_y):
    ''' Converts coordinate systems

    :param input_crs: coordinate reference system of input coordinates
    :param output_crs: coordinate reference system of output coordinates
    :param x_y: input coordinates in [x,y] format
    :returns: converted coordinates [x,y]
    '''
    p_in = Proj(__clean_crs(input_crs))
    p_out = Proj(__clean_crs(output_crs))
    return transform(p_in, p_out, x_y[0], x_y[1])

