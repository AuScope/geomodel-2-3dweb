from pyproj import Transformer

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
    :returns: converted coordinates [x,y], [math.inf, math.inf] upon error
    '''
    transformer = Transformer.from_crs(__clean_crs(input_crs), __clean_crs(output_crs), always_xy=True)
    return transformer.transform(x_y[0], x_y[1])

