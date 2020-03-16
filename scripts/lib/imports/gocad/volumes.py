import os
import numpy as np

def read_volume_binary_files(self):
    ''' Open up and read binary volume file, could be from VOXET or SGRID

        :returns: False upon error
    '''
    if not self.vol_sz:
        self.logger.error("Cannot process voxel file, cube size is not defined, " \
                          "missing 'AXIS_N'")
        return False

    # pylint: disable=W0612
    for file_idx, prop_obj in self.prop_dict.items():
        # Sometimes filename needs a .vo on the end
        if not os.path.isfile(prop_obj.file_name) and prop_obj.file_name[-2:] == "@@" and \
                                      os.path.isfile(prop_obj.file_name+".vo"):
            prop_obj.file_name += ".vo"

        # If there is a colour table in CSV file then read it
        bin_file = os.path.basename(prop_obj.file_name)
        if bin_file in self.ct_file_dict:
            csv_file_path = os.path.join(os.path.dirname(prop_obj.file_name),
                                         self.ct_file_dict[bin_file][0])
            prop_obj.read_colour_table_csv(csv_file_path, self.ct_file_dict[bin_file][1])
            self.logger.debug("prop_obj.colour_map = %s", repr(prop_obj.colour_map))
            self.logger.debug("prop_obj.rock_label_table = %s", repr(prop_obj.rock_label_table))

        # Read and process binary file
        try:
            # Check file size first
            file_sz = os.path.getsize(prop_obj.file_name)
            num_voxels = self.vol_sz[0]*self.vol_sz[1]*self.vol_sz[2]
            self.logger.debug("num_voxels = %s", repr(num_voxels))
            est_sz = prop_obj.data_sz*num_voxels+prop_obj.offset
            if file_sz < est_sz:
                self.logger.error("SORRY - Cannot process VOXET/SGRID file - length (%d)" \
                                  " is less than estimated size (%d): %s",
                                  file_sz, est_sz, prop_obj.file_name)
                return False

            # Initialise data array to zeros
            prop_obj.data_3d = np.zeros((self.vol_sz[0], self.vol_sz[1], self.vol_sz[2]))

            # Prepare 'numpy' dtype object for binary float, integer signed/unsigned data types
            d_typ = prop_obj.make_numpy_dtype()

            # Read entire file, assumes file small enough to store in memory
            self.logger.info("Reading binary file: %s", prop_obj.file_name)
            elem_offset = prop_obj.offset//prop_obj.data_sz
            self.logger.debug("elem_offset = %s", repr(elem_offset))
            fp_arr = np.fromfile(prop_obj.file_name, dtype=d_typ, count=num_voxels+elem_offset)
            fp_idx = elem_offset
            # If VOXET
            if self._is_vo:
                # Calculate geometries of VOXET
                mult = [(self.axis_max[0]-self.axis_min[0])/self.vol_sz[0],
                        (self.axis_max[1]-self.axis_min[1])/self.vol_sz[1],
                        (self.axis_max[2]-self.axis_min[2])/self.vol_sz[2]]
                # Loop over points in volume
                for z_val in range(self.vol_sz[2]):
                    for y_val in range(self.vol_sz[1]):
                        for x_val in range(self.vol_sz[0]):

                            x_coord, y_coord, z_coord = self.calc_vo_xyz(x_val, y_val, z_val, mult)
                            # If numeric VOXET
                            if prop_obj.data_type != 'rgba':
                                converted, data_val = self.parse_float(fp_arr[fp_idx],
                                                           prop_obj.no_data_marker)
                                if not converted:
                                    continue
                                prop_obj.assign_to_3d(x_val, y_val, z_val, data_val)
                            # If RGBA VOXET
                            else:
                                data_val = fp_arr[fp_idx]
                                prop_obj.assign_to_xyz((x_coord, y_coord, z_coord), data_val)
                                prop_obj.assign_to_ijk((x_val, y_val, z_val), data_val)

                            fp_idx += 1
            # If SGRID
            elif self._is_sg:
                # SGRID gets its coordinates from a points file
                if self.sgrid_cell_align:
                    pt_arr_sz = (self.vol_sz[0]+1) * (self.vol_sz[1]+1) * (self.vol_sz[2]+1)
                else:
                    pt_arr_sz = self.vol_sz[0] * self.vol_sz[1] * self.vol_sz[2]

                points_offset = pt_arr_sz + self.points_offset//12 # 3 * 4-byte floats
                dt = np.dtype([('x', '>f4'), ('y', '>f4'), ('z', '>f4')])
                pt_arr = np.fromfile(self.points_file, dtype=dt, count=points_offset)
                self.logger.debug("pt_arr = %s", repr(pt_arr))
                self.logger.debug("pt_arr.shape = %s", repr(pt_arr.shape))
                try:
                    pt_arr = pt_arr.reshape(self.vol_sz[0]+1, self.vol_sz[1]+1, self.vol_sz[2]+1)
                except ValueError:
                    self.logger.error("Cannot process SGRID file, incorrect array dimensions")
                    return False

                self.logger.debug("pt_arr.shape = %s", repr(pt_arr.shape))

                # Loop over points in 3d SGRID
                for z_val in range(self.vol_sz[2]):
                    for y_val in range(self.vol_sz[1]):
                        for x_val in range(self.vol_sz[0]):
                            x_coord, y_coord, z_coord = self.calc_sg_xyz(x_val, y_val, z_val, pt_arr)
                            data_val = fp_arr[fp_idx]
                            prop_obj.assign_to_xyz((x_coord, y_coord, z_coord), data_val)
                            prop_obj.assign_to_ijk((x_val, y_val, z_val), data_val)
                            fp_idx += 1

                            # self.logger.debug("fp[%d, %d, %d] = %s", x_val, y_val, z_val, repr(data_val))
                            # self.logger.debug("x,y,z=[%f, %f, %f]", x_coord, y_coord, z_coord)


        except IOError as io_exc:
            self.logger.error("SORRY - Cannot process voxel file IOError %s %s %s",
                              prop_obj.file_name, str(io_exc), io_exc.args)
            return False

    self.logger.debug("Done looping")

    # Process flags file if desired
    if not self.SKIP_FLAGS_FILE:
        # Read VOXET flags file
        if self.flags_file != '' and self._is_vo:
            self.read_region_flags_file(self.flags_array_length,
                                          self.flags_file,
                                          self.flags_bit_size,
                                          self.flags_offset)

        # SGRID also has a flags file, but uses different markers
        elif self.region_flags_file != '' and self._is_sg:
            self.read_region_flags_file(self.region_flags_array_length,
                                          self.region_flags_file,
                                          self.region_flags_bit_size,
                                          self.region_flags_offset)
     
        else:
            self.logger.warning("SKIP_FLAGS_FILE = True  => Skipping flags file %s",
                                self.flags_file)
    self.logger.debug("Return True")
    return True


def calc_vo_xyz(self, x_idx, y_idx, z_idx, mult):
    # Calculate the XYZ coords and their maxs & mins
    x_coord = self.axis_o[0]+ \
      (float(x_idx)*self.axis_u[0]*mult[0] + \
      float(y_idx)*self.axis_u[1]*mult[1] + \
      float(z_idx)*self.axis_u[2]*mult[2])
    y_coord = self.axis_o[1]+ \
      (float(x_idx)*self.axis_v[0]*mult[0] + \
      float(y_idx)*self.axis_v[1]*mult[1] + \
      float(z_idx)*self.axis_v[2]*mult[2])
    z_coord = self.axis_o[2]+ \
      (float(x_idx)*self.axis_w[0]*mult[0] + \
      float(y_idx)*self.axis_w[1]*mult[1] + \
      float(z_idx)*self.axis_w[2]*mult[2])
    self.geom_obj.calc_minmax(x_coord, y_coord, z_coord)
    return x_coord, y_coord, z_coord


def calc_sg_xyz(self, x_idx, y_idx, z_idx, fp_arr):
    # SGRID has coordinates in points file
    x_coord, y_coord, z_coord = fp_arr[x_idx][y_idx][z_idx]
    self.geom_obj.calc_minmax(x_coord, y_coord, z_coord)
    return x_coord, y_coord, z_coord


def read_region_flags_file(self, flags_array_len, flags_file,
                             flags_bit_sz, flags_offset):
    ''' Reads the flags file and looks for regions for a VOXET or SGRID file.
    :param flags_array_len: length of flags array
    :param flags_file: filename of flags file
    :param flags_bit_sz: mumber of bits in each element of flags array
    :param flags_offset: pointer to start of flags data within flags file
    '''
    if flags_array_len != self.vol_sz[0]*self.vol_sz[1]*self.vol_sz[2]:
        self.logger.warning("SORRY - Cannot process voxel flags file, inconsistent size" \
                            " between data file and flag file")
        self.logger.debug("read_region_flags_file() return False")
        return False
    # Check file does not exist, sometimes needs a '.vo' on the end
    if not os.path.isfile(flags_file) and flags_file[-2:] == "@@" and \
                                         os.path.isfile(flags_file+".vo"):
        flags_file += ".vo"

    try:
        # Check file size first
        file_sz = os.path.getsize(flags_file)
        num_voxels = self.vol_sz[0]*self.vol_sz[1]*self.vol_sz[2]
        est_sz = flags_bit_sz*num_voxels+flags_offset
        if file_sz < est_sz:
            self.logger.error("SORRY - Cannot process voxel flags file %s - length (%d) " \
                              "is less than calculated size (%d)",
                              flags_file, file_sz, est_sz)
            sys.exit(1)

        # Initialise data array to zeros
        np.zeros((self.vol_sz[0], self.vol_sz[1], self.vol_sz[2]))

        # Prepare 'numpy' dtype object for binary float, integer signed/unsigned data types
        d_typ = np.dtype(('B', (flags_bit_sz)))

        # Read entire file, assumes file small enough to store in memory
        self.logger.info("Reading binary flags file: %s", flags_file)
        f_arr = np.fromfile(flags_file, dtype=d_typ)
        f_idx = flags_offset//flags_bit_sz
        self.flags_prop = PROPS(flags_file, self.logger.getEffectiveLevel())
        # self.debug('self.region_dict.keys() = %s', self.region_dict.keys())
        for z_val in range(0, self.vol_sz[2]):
            for y_val in range(0, self.vol_sz[1]):
                for x_val in range(0, self.vol_sz[0]):
                    # self.logger.debug("%d %d %d %d => %s", x, y, z, f_idx, repr(f_arr[f_idx]))
                    # convert floating point number to a bit mask
                    bit_mask = ''
                    # NB: Single bytes are not returned as arrays
                    if flags_bit_sz == 1:
                        bit_mask = '{0:08b}'.format(f_arr[f_idx])
                    else:
                        for bit in range(flags_bit_sz-1, -1, -1):
                            bit_mask += '{0:08b}'.format(f_arr[f_idx][bit])
                    # self.logger.debug('bit_mask= %s', bit_mask)
                    # self.logger.debug('self.region_dict = %s', repr(self.region_dict))
                    cnt = flags_bit_sz*8-1
                    # Examine the bit mask one bit at a time, starting at the highest bit
                    for bit in bit_mask:
                        if str(cnt) in self.region_dict and bit == '1':
                            key = self.region_dict[str(cnt)]
                            # self.logger.debug('cnt = %d bit = %d', cnt, bit)
                            # self.logger.debug('key = %s', key)
                            self.flags_prop.append_to_ijk((x_val, y_val, z_val), key)
                        cnt -= 1
                    f_idx += 1

    except IOError as io_exc:
        self.logger.error("SORRY - Cannot process voxel flags file, IOError %s %s %s",
                          flags_file, str(io_exc), io_exc.args)
        self.logger.debug("read_region_flags_file() return False")
        return False

    return True

