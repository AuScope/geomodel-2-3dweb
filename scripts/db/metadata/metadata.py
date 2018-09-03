class METADATA():
    def __init__(self):
        self.name = ''
        ''' Taken from GOCAD object name ??
        '''

        self.property_name = ''
        ''' Taken from 'PROPERTY_CLASS_HEADER' e.g. PROPERTY_CLASS_HEADER c1 {
        '''

        self.is_index_data = False
        ''' Does the volume data just point to a rock/colour table, or is it measurement data?
        '''

        self.rock_label_table = {}
        ''' Table specifying names of rocks , key is an integer, value is the label
        '''

    def __repr__(self):
        return("METADATA(): name={0} property_name={1} is_index_data={2} rock_label_table={3}".format(self.name, self.property_name, str(self.is_index_data), str(self.rock_label_table)))

