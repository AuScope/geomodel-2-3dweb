from enum import Enum

class MapFeat(Enum):
    UNKNOWN = 1
    SHEAR_DISP_STRUCT = 2
    GEOLOGICAL_UNIT = 3
    CONTACT = 4

class METADATA():
    ''' Storage for metadata attributes extracted from GOCAD that can be assigned directly to GeoSciML 
    '''
    def __init__(self):
        self.name = ''
        ''' Taken from GOCAD object name ??
        '''

        self._property_name = []
        ''' Taken from 'PROPERTY_CLASS_HEADER' e.g. PROPERTY_CLASS_HEADER c1 {
        '''

        self.is_index_data = False
        ''' Does the volume data just point to a rock/colour table, or is it measurement data?
        '''

        self.rock_label_table = {}
        ''' Table specifying names of rocks, key is an integer, value is the label
        '''

        self.src_filename = ''
        ''' Volume data source file
        '''

        self.geofeat_name = ''
        ''' Copied from GOCAD "STRATIGRAPHIC_POSITION" (1st val) or from GOCAD "GEOLOGICAL_FEATURE"
            to GeoSciML v4 GeologicFeature::GeologicUnit gml:name or
            GeologicFeature::GeologicStructure::ShearDisplacementStructure gml:name or
            GeologicFeature::GeologicStructure::Contact gml:name
        '''

        self.geoevent_numeric_age_range = 0
        ''' Copied from GOCAD "STRATIGRAPHIC_POSITION" (2nd val) to GeoSciML v4 GeologicEvent
            gsmlb:numericAgeRange
        '''

        self.mapped_feat = MapFeat.UNKNOWN
        ''' Copied from GOCAD "GEOLOGICAL_TYPE" which can have values: top, intraformational, 
           fault, unconformity, intrusive, topography, boundary, and ghost
           'fault' maps to "GeologicFeature::GeologicStructure::ShearDisplacementStructure"
           'intrusive' - many kinds of igneous formations, maps to 'GeologicFeature::GeologicUnit'
           'unconformity' - (gaps in the geologic record within a stratigraphic unit) and
           'intraformational' and 'boundary' map to 'GeologicFeature::GeologicStructure::Contact'
           'top', 'topography' maybe map to 'MappedFeature' fields
        '''

    def __repr__(self):
        ''' A basic print friendly representation
        '''
        ret_str = 'METADATA():'
        for field in dir(self):
            if '__' != field[-2:] and not callable(getattr(self,field)):
                ret_str += field + ": " + repr(getattr(self, field))[:200] + "\n"
        return ret_str

    def add_property_name(self, name):
        ''' Adds a property name
        :name: property name, string
        '''
        self._property_name.append(name)


    def get_property_name(self, idx=0):
        ''' Retrieve property name
        :idx: index used when point in space has multiple properties, omit for volumes
        :returns: property name, string
        '''
        if len(self._property_name) > idx:
            return self._property_name[idx]
        return ''

