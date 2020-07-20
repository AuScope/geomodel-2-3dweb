class FileDataStructMap:


    def is_points(self, file_name):
        ''' Generic routine to recognise a points file
        '''
        raise NotImplementedError("Subclass must implement abstract method")


    def is_volume(self, file_name):
        ''' Generic routine to recognise a volume file
        '''
        raise NotImplementedError("Subclass must implement abstract method")


    def is_borehole(self, file_name):
        ''' Generic routine to recognise a volume file
        '''
        raise NotImplementedError("Subclass must implement abstract method")


    def is_flat_shape(self, file_name):
        ''' Generic routine to recognise a volume file
        '''
        raise NotImplementedError("Subclass must implement abstract method")


    def is_mixture(self, file_name):
        ''' Generic routine to recognise a file with a mixture 
        '''
        raise NotImplementedError("Subclass must implement abstract method")

