'''
 A collection of Python functions for creating false colour representations of objects
'''
import sys 

def calculate_false_colour_num(val_flt, max_flt, min_flt, max_colours_flt):
    ''' Calculates a colour number via interpolation

    :param val_flt: value used to calculate colour number
    :param min_flt: lower bound of value
    :param max_flt: upper bound of value
    :param max_colours_flt: maximum number of colours
    :returns: integer colour number
    '''
    # Floating point arithmetic fails of the numbers are at limits
    if max_flt == abs(sys.float_info.max) or min_flt == abs(sys.float_info.max) or val_flt == abs(sys.float_info.max):
        return 0
    # Ensure denominator is not too large
    if (max_flt - min_flt) > 0.0000001:
        return int((max_colours_flt-1)*(val_flt - min_flt)/(max_flt - min_flt))
    return 0


def interpolate(x_flt, xmin_flt, xmax_flt, ymin_flt, ymax_flt):
    ''' Given x, linearly interpolates a y-value

    :param x_flt: floating point number to be interpolated
    :param xmin_flt: minimum value within x_flt's range
    :param xmax_flt: maximum value within x_flt's range
    :param ymin_flt: minimum possible value to output
    :param ymax_flt: maximum possible value to output
    :returns: interpolated y-value, float
    '''
    return (x_flt - xmin_flt) / (xmax_flt - xmin_flt) * (ymax_flt - ymin_flt) + ymin_flt


def make_false_colour_tup(i_flt, imin_flt, imax_flt):
    ''' This creates a false colour map, returns an RGBA tuple.
        Maps a floating point value that varies between a min and max value to an RGBA tuple

    :param i_flt: floating point value to be mapped
    :param imax_flt: maximum range of the floating point value
    :param imin_flt: minimum range of the floating point value
    :returns: returns an RGBA float tuple (R,G,B,A)
    '''
    if i_flt < imin_flt or i_flt > imax_flt:
        return (0.0, 0.0, 0.0, 0.0)
    SAT = 0.8
    hue_flt = (imax_flt - i_flt)/ (imax_flt - imin_flt)
    vmin_flt = SAT * (1 - SAT)
    pix = [0.0,0.0,0.0,1.0]

    if hue_flt < 0.25:
        pix[0] = SAT
        pix[1] = interpolate(hue_flt, 0.0, 0.25, vmin_flt, SAT)
        pix[2] = vmin_flt

    elif hue_flt < 0.5:
        pix[0] = interpolate(hue_flt, 0.25, 0.5, SAT, vmin_flt)
        pix[1] = SAT
        pix[2] = vmin_flt

    elif hue_flt < 0.75:
        pix[0] = vmin_flt
        pix[1] = SAT
        pix[2] = interpolate(hue_flt, 0.5, 0.75, vmin_flt, SAT)

    else:
        pix[0] = vmin_flt
        pix[1] = interpolate(hue_flt, 0.75, 1.0, SAT, vmin_flt)
        pix[2] = SAT
    return tuple(pix)

