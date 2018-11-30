class METADATA():
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
        ''' Table specifying names of rocks , key is an integer, value is the label
        '''

        self.src_filename = ''
        ''' Volume data source file
        '''



    def __repr__(self):
        return("METADATA(): name={0} property_name={1} is_index_data={2}".format(self.name, self._property_name, str(self.is_index_data)))

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

