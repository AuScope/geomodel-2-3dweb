from collections import namedtuple

VRTX = namedtuple('VRTX', 'n xyz')
''' Immutable named tuple which stores vertex data

:n: sequence number
:xyz: coordinates
'''

ATOM = namedtuple('ATOM', 'n v')
''' Immutable named tuple which stores atom data

:n: sequence number
:v: vertex it refers to
'''

TRGL = namedtuple('TRGL', 'n abc')
''' Immutable named tuple which stores triangle data

:n: sequence number
:abc: triangle vertices
'''

SEG = namedtuple('SEG', 'ab')
''' Immutable named tuple which stores segment data

:ab: segment vertices
'''
