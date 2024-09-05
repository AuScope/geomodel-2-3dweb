from lxml import etree
from io import StringIO
from pickle import PicklingError, UnpicklingError

"""
These functions are used to pickle and unpickle XML objects belonging to the lxml package
"""

def element_unpickler(xml: bytes) -> etree._Element:
    """ Unpickle etree._Element by parsing a byte string

    :param xml: bytes string containing XML for _Element
    :returns: _Element object
    """
    try:
        elem = etree.fromstring(element)
    except etree.LxmlError as le:
        raise UnpicklingError(f"Unpickle XML error: {le}")

def element_pickler(element_obj: etree._Element) -> (bytes):
    """ Pickle etree._Element object by converting to a byte string

    :param element_obj: etree._Element object
    :returns: Unpickle function and XML byte string
    """
    try:
        return element_unpickler, (etree.tostring(element_obj),)
    except etree.LxmlError as le:
        raise PicklingError(f"Pickle XML error: {le}")

def elementtree_unpickler(xml: bytes) -> etree._ElementTree:
    """ Unpickle etree._ElementTree by parsing a byte string

    :param xml: bytes string containing XML for _ElementTree
    :returns: _ElementTree object
    """
    try:
        data = StringIO(xml)
        return etree.parse(data)
    except etree.LxmlError as le:
        raise UnpicklingError(f"Unpickle XML error: {le}")
    except TypeError as te:
        raise UnpicklingError(f"String IO error: {te}")


def elementtree_pickler(elementtree: etree._ElementTree) -> (bytes):
    """ Pickle etree._ElementTree object by converting to a byte string

    :param element_obj: etree._ElementTree object
    :returns: Unpickle function and XML byte string
    """
    try:
        data = StringIO()
        tree.write(data)
        return elementtree_unpickler, (data.getvalue(),)
    except etree.LxmlError as le:
        raise PicklingError(f"Pickle XML error: {le}")
    except TypeError as te:
        raise PicklingError(f"String IO error: {te}")

