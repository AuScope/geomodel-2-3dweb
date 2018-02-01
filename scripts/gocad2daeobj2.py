#!/usr/bin/env python3
#
# I am writing this because the current library (LaGrit) used to read  GOCAD *.ts
# is buggy (seg faults a lot) and does not read the 'ZPOSITIVE', so some parts of models are displayed 
# upside down
#
from collada import *
import numpy
import PIL
import sys
import os
import glob
import struct
import array

CONVERT_COLLADA = True
COLLADA2GLTF_BIN = os.path.join(os.environ['HOME'], 'github', 'COLLADA2GLTF', 'build')

def parse_XYZ(is_float, x_str, y_str, z_str):
  ''' Helpful function to read XYZ cooordinates
      x_str, y_str, z_str - X,Y,Z coordinates in string form
      Returns four parameters: success  - true if could convert the strings to floats
                               x,y,z - floating point values
  '''
  x = y = z = None 
  if is_float:  
    try:
      x = float(x_str)
      y = float(y_str)
      z = float(z_str)
    except (OverflowError, ValueError):
      return False, None, None, None
  else:
    try:
      x = int(x_str)
      y = int(y_str)
      z = int(z_str)
    except (OverflowError, ValueError):
      return False, None, None, None
  return True, x, y, z



def interpolate(x_flt, xmin_flt, xmax_flt, ymin_flt, ymax_flt):
  ''' Interpolates a floating point number 
      x_flt - floating point number to be interpolated
      xmin_flt - minimum value within x_flt's range
      xmax_flt - maximum value within x_flt's range
      ymin_flt - minimum possible value to output 
      ymax_flt - maximum possible value to output
      Returns interpolated value
  '''
  return (x_flt - xmin_flt) / (xmax_flt - xmin_flt) * (ymax_flt - ymin_flt) + ymin_flt

def colour_map(i_flt, imin_flt, imax_flt):
  ''' This creates a false colour map, returns an RGBA tuple. A is set to the "SAT" global var.
      Maps a floating point value that varies between a min and max value to an RGBA tuple
      i_flt - floating point value to be mapped
      imax_flt - maximum range of the floating point value
      imin_flt - minimum range of the floating point value
      Returns an RGBA tuple
  '''
  SAT = 0.8
  hue_flt = (i_flt - imin_flt)/ (imax_flt - imin_flt)
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
   


class GOCAD_KIT:
  ''' Class used to read gocad files and output them to Wavefront OBJ and COLLADA files
  '''

  GOCAD_HEADERS = { 
               'TS':['GOCAD TSURF 1'],
               'VS':['GOCAD VSET 1'],
               'PL':['GOCAD PLINE 1'],
               'GP':['GOCAD HETEROGENEOUSGROUP 1', 'GOCAD HOMOGENEOUSGROUP 1'],
               'VO':['GOCAD VOXET 1'],
  }
  ''' Constant assigns possible headers to each flename extension'''

  SUPPORTED_EXTS = [
                 'TS',
                 'VS',
                  'PL',
                  'GP',
                  'VO',
  ]
  ''' List of file extensions to search for '''

  def __init__(self, base_xyz=(0.0, 0.0, 0.0)):
    ''' Initialise class
        base_xyz - optional (x,y,z) floating point tuple, base_xyz is subtracted from all coordinates
                   before they are output
    '''
    self.base_xyz = base_xyz
    print("self.base_xyz = ", self.base_xyz)

    self.vrtx_arr = []
    '''Array to store vertice data'''

    self.trgl_arr = []
    '''Array to store triangle face data'''

    self.seg_arr = []
    '''Array to store line segment data'''

    self.invert_zaxis = False
    '''Set to true if z-axis inversion is turned on in this GOCAD file'''

    self.rgba_tup = (1.0, 1.0, 1.0, 1.0)
    '''If one colour is specified in the file it is stored here'''

    self.prop_dict = {}
    '''Property dictionary'''

    self.is_ts = False
    '''True iff it is a GOCAD TSURF file'''

    self.is_vs = False
    '''True iff it is a GOCAD VSET file'''

    self.is_pl = False
    '''True iff it is a GOCAD PLINE file'''

    self.is_vo = False
    '''True iff it is a GOCAD VOXEL file'''

    self.prop_meta = {}
    '''Property metadata '''

    self.voxel_file = ""
    '''Name of binary file associated with VOXEL file'''

    self.axis_origin = None
    '''Origin of XYZ axis'''

    self.axis_u = None
    '''Length of u-axis'''

    self.axis_v = None
    '''Length of v-axis'''

    self.axis_w = None
    '''Length of w-axis'''

    self.vol_dims = None
    '''3 dimensional size of voxel volume'''

    self.axis_min = None
    '''3 dimensional minimum point of voxel volume '''

    self.axis_max = None
    '''3 dimensional maximum point of voxel volume '''

    self.voxel_data = numpy.zeros((1,1,1))
    '''Voxel data collected from binary file, stored as a 3d numpy array'''

    self.voxel_data_stats = { 'min': sys.float_info.max , 'max': -sys.float_info.max }
    '''Voxel data statistics: min & max'''

    self.colour_map = {}
    '''If colour map was specified, then it is stored here'''

    self.colourmap_name = ""
    '''Name of colour map'''



  def __repr__(self):
    ''' A very basic print friendly representation
    '''
    return "is_ts {0} is_vs {1} is_pl {2} is_vo {3} len(vrtx_arr)={4}\n".format(self.is_ts, self.is_vs, self.is_pl, self.is_vo, len(self.vrtx_arr))


    
  def setType(self, fileExt, firstLineStr):
    ''' Sets the type of GOCAD file: TSURF, VOXEL, PLINE etc.
        fileExt - the file extension 
        firstLineStr - first line in the file
        Returns True if it could determine the type of file
    '''
    print("setType(", fileExt, firstLineStr, ")")
    ext_str = fileExt.lstrip('.').upper()
    if ext_str=='GP':
      found = False
      for key in self.GOCAD_HEADERS:
        if key!='GP' and firstLineStr in self.GOCAD_HEADERS[key]:
          ext_str = key
          found = True
          break
      if not found:
        return False
        
    if ext_str in self.GOCAD_HEADERS:
      if ext_str=='TS' and firstLineStr in self.GOCAD_HEADERS['TS']:
        self.is_ts = True
        return True
      elif ext_str=='VS' and firstLineStr in self.GOCAD_HEADERS['VS']:
        self.is_vs = True
        return True
      elif ext_str=='PL' and firstLineStr in self.GOCAD_HEADERS['PL']:
        self.is_pl = True
        return True
      elif ext_str=='VO' and firstLineStr in self.GOCAD_HEADERS['VO']:
        self.is_vo = True
        return True

    return False


  def write_OBJ(self, fileName, src_file_str):
    ''' Writes out an OBJ file 
        fileName - filename of OBJ file, without extension
        src_file_str - filename of gocad file

        NOTES:
        OBJ is very simple, and has shortcomings:
        1. Does not include annotations (only comments and a group name) 
        2. Lines and points do not have a colour

        I am only using it here because GOCAD VOXEL files are too big for collada format
    '''
    # Output to OBJ file
    print("Writing ",fileName+".OBJ")
    out_fp = open(fileName+".OBJ", 'w')
    out_fp.write("# Wavefront OBJ file converted from '{0}'\n\n".format(src_file_str))
    ct_done = False
    if self.is_ts:
      if len(self.rgba_tup)==4:
        out_fp.write("mtllib "+fileName+".MTL\n")
    if self.is_ts or self.is_pl or self.is_vs:
      for v in self.vrtx_arr:
        bv = (v[0]-self.base_xyz[0], v[1]-self.base_xyz[1], v[2]-self.base_xyz[2]) 
        out_fp.write("v {0:f} {1:f} {2:f}\n".format(bv[0],bv[1],bv[2]))
    out_fp.write("g main\n")
    if self.is_ts:
      out_fp.write("usemtl colouring\n")
      for f in self.trgl_arr:
        out_fp.write("f {0:d} {1:d} {2:d}\n".format(f[0],f[1],f[2]))
  
    elif self.is_pl:
      for s in self.seg_arr:
        out_fp.write("l {0:d} {1:d}\n".format(s[0],s[1]))
  
    elif self.is_vs:
      out_fp.write("p");
      for p in range(len(self.vrtx_arr)):
        out_fp.write(" {0:d}".format(p+1))
      out_fp.write("\n")
  
    elif self.is_vo:
      ct_done=self.write_voxel_obj(out_fp, fileName, src_file_str, 64, False)      
    out_fp.close() 
    
    # Create an MTL file for the colour
    if len(self.rgba_tup)==4 and not ct_done:
      out_fp = open(fileName+".MTL", 'w')
      out_fp.write("# Wavefront MTL file converted from  '{0}'\n\n".format(src_file_str))
      out_fp.write("newmtl colouring\n")
      out_fp.write("Ka {0:.3f} {1:.3f} {2:.3f}\n".format(self.rgba_tup[0], self.rgba_tup[1], self.rgba_tup[2]))
      out_fp.write("Kd {0:.3f} {1:.3f} {2:.3f}\n".format(self.rgba_tup[0], self.rgba_tup[1], self.rgba_tup[2]))
      out_fp.write("Ks 0.000 0.000 0.000\n")
      out_fp.write("d 1.0\n")
      out_fp.close()


  def write_voxel_png(self, src_dir, fileName, src_file_str):
    ''' Writes out a PNG file of the top layer of the voxel data
        fileName - filename of OBJ file, without extension
        src_filen_str - filename of source gocad file
    '''
    colour_arr = array.array("B")
    z = self.vol_dims[2]-1
    pixel_cnt = 0
    for x in range(0, self.vol_dims[0]):
      for y in range(0, self.vol_dims[1]):
        (r,g,b) = self.colour_map[int(self.voxel_data[x][y][z])]
        colour_arr.append(int(r*255.0))
        colour_arr.append(int(g*255.0))
        colour_arr.append(int(b*255.0))
        pixel_cnt += 1
    img = PIL.Image.frombytes('RGB', (self.vol_dims[1], self.vol_dims[0]), colour_arr.tobytes()) 
    print(img)
    img.save(os.path.join(src_dir, fileName+".PNG"))
  

    
  def write_voxel_obj(self, out_fp, fileName, src_file_str, step_sz, use_full_cubes):
    ''' Writes out voxel data to Wavefront OBJ and MTL files
        out_fp - open file handle of OBJ file
        fileName - filename of OBJ file without the 'OBJ' extension
        src_file_str - filename of gocad file
        step_sz  - when stepping through the voxel block this is the step size
        use_full_cubes - will write out full cubes to file if true, else will remove non-visible faces
    '''
    # Limit to 256 colours
    mtl_fp = open(fileName+".MTL", 'w')
    for colour_idx in range(256):
      diffuse_colour = colour_map(float(colour_idx), 0.0, 255.0)
      mtl_fp.write("# Wavefront MTL file converted from  '{0}'\n\n".format(src_file_str))
      mtl_fp.write("newmtl colouring-{0:03d}\n".format(colour_idx))
      mtl_fp.write("Ka {0:.3f} {1:.3f} {2:.3f}\n".format(diffuse_colour[0], diffuse_colour[1], diffuse_colour[2]))
      mtl_fp.write("Kd {0:.3f} {1:.3f} {2:.3f}\n".format(diffuse_colour[0], diffuse_colour[1], diffuse_colour[2]))
      mtl_fp.write("Ks 0.000 0.000 0.000\n")
      mtl_fp.write("d 1.0\n")
    mtl_fp.close()
    ct_done = True
    out_fp.write("mtllib "+fileName+".MTL\n")
    vert_idx = 0
    breakOut = False
    for z in range(0,self.vol_dims[2],step_sz):
      for y in range(0,self.vol_dims[1],step_sz):
        for x in range(0,self.vol_dims[0],step_sz):
          colour_num = int(255.0*(self.voxel_data[x][y][z] - self.voxel_data_stats['min'])/(self.voxel_data_stats['max'] - self.voxel_data_stats['min']))
          # NB: Assumes AXIS_MIN = 0, and AXIS_MAX = 1
          u_offset = self.axis_origin[0]+ float(x)/self.vol_dims[0]*self.axis_u[0]
          v_offset = self.axis_origin[1]+ float(y)/self.vol_dims[1]*self.axis_v[1]
          w_offset = self.axis_origin[2]+ float(z)/self.vol_dims[2]*self.axis_w[2]
          v = (u_offset, v_offset, w_offset)
          pt_size = (step_sz*self.axis_u[0]/self.vol_dims[0]/2, step_sz*self.axis_v[1]/self.vol_dims[1]/2, step_sz*self.axis_w[2]/self.vol_dims[2]/2)
          vert_list = [ (v[0]-pt_size[0], v[1]-pt_size[1], v[2]+pt_size[2]),
                        (v[0]-pt_size[0], v[1]-pt_size[1], v[2]-pt_size[2]),
                        (v[0]-pt_size[0], v[1]+pt_size[1], v[2]-pt_size[2]),
                        (v[0]-pt_size[0], v[1]+pt_size[1], v[2]+pt_size[2]),
                        (v[0]+pt_size[0], v[1]-pt_size[1], v[2]+pt_size[2]),
                        (v[0]+pt_size[0], v[1]-pt_size[1], v[2]-pt_size[2]),
                        (v[0]+pt_size[0], v[1]+pt_size[1], v[2]-pt_size[2]),
                        (v[0]+pt_size[0], v[1]+pt_size[1], v[2]+pt_size[2]),
                      ]
          indice_list = []
  
          # Create a full cube for each voxel
          if use_full_cubes:
            indice_list = [ (4, 3, 2, 1), # WEST
                            (2, 6, 5, 1), # SOUTH
                            (3, 7, 6, 2), # BOTTOM
                            (8, 7, 3, 4), # NORTH
                            (5, 8, 4, 1), # TOP
                            (6, 7, 8, 5), # EAST
                          ]
          # To save space, only create surfaces at the edges, assuming a block shape (valid??)
          else:
            # BOTTOM FACE
            if z==0:
              indice_list.append((3, 7, 6, 2))
            # TOP FACE
            if z==self.vol_dims[2]-1:
              indice_list.append((5, 8, 4, 1))
            # SOUTH FACE
            if y==0:
              indice_list.append((2, 6, 5, 1))
            # NORTH FACE
            if y==self.vol_dims[1]:
              indice_list.append((8, 7, 3, 4))
            # EAST FACE 
            if x==0:
              indice_list.append((6, 7, 8, 5))
            # WEST FACE
            if x==self.vol_dims[0]:
              indice_list.append((4, 3, 2, 1))
  
          # Only write if there are indices to write
          if len(indice_list)>0:
            for vert in vert_list:
              bvert = (vert[0]-self.base_xyz[0], vert[1]-self.base_xyz[1], vert[2]-self.base_xyz[2]) 
              out_fp.write("v {0:f} {1:f} {2:f}\n".format(bvert[0],bvert[1],bvert[2]))
            out_fp.write("g main-{0:010d}\n".format(vert_idx))
            out_fp.write("usemtl colouring-{0:03d}\n".format(colour_num))
            for ind in indice_list:
              out_fp.write("f {0:d} {1:d} {2:d} {3:d}\n".format(ind[0]+vert_idx, ind[1]+vert_idx, ind[2]+vert_idx, ind[3]+vert_idx))
            out_fp.write("\n")
            vert_idx += len(vert_list)
            if vert_idx > 99999999999:
              breakOut = True
              break
        if breakOut:
          break
      if breakOut:
        break
    return ct_done
       
  #
  # COLLADA is better than OBJ, but very bulky
  #
  def write_collada(self, fileName):
    ''' Write out a COLLADA file
        fileName - filename of COLLADA file, without extension
    '''
    mesh = Collada()
    if self.is_ts:
      if len(self.rgba_tup)==4:
        effect = material.Effect("effect0", [], "phong", emission=(0,0,0,1), ambient=(0,0,0,1), diffuse=self.rgba_tup, specular=(0.5, 0.5, 0.5, 1), shininess=16.0, double_sided=True)
      else:
        effect = material.Effect("effect0", [], "phong", diffuse=(1,0,0), specular=(0,1,0), double_sided=True)
      mat = material.Material("material0", "mymaterial", effect)
      mesh.effects.append(effect)
      mesh.materials.append(mat)
      vert_floats = []
      for v in self.vrtx_arr:
        vert_floats += [v[0]-self.base_xyz[0], v[1]-self.base_xyz[1], v[2]-self.base_xyz[2]] 
      vert_src = source.FloatSource("triverts-array", numpy.array(vert_floats), ('X', 'Y', 'Z'))
      geom = geometry.Geometry(mesh, "geometry0", "mycube", [vert_src])
      input_list = source.InputList()
      input_list.addInput(0, 'VERTEX', "#triverts-array")
  
      indices = []
      for t in self.trgl_arr:
        indices += [t[0]-1, t[1]-1, t[2]-1]
  
      triset = geom.createTriangleSet(numpy.array(indices), input_list, "materialref")
      geom.primitives.append(triset)
      mesh.geometries.append(geom)
  
      matnode = scene.MaterialNode("materialref", mat, inputs=[])
      geomnode = scene.GeometryNode(geom, [matnode])
      node = scene.Node("node0", children=[geomnode])
  
      myscene = scene.Scene("myscene", [node])
      mesh.scenes.append(myscene)
      mesh.scene = myscene

    elif self.is_pl:
      LINE_WIDTH = 1000
      point_cnt = 0
      node_list = []
      yellow_colour = (1,1,0,1)
      effect = material.Effect("effect0", [], "phong", emission=(0,0,0,1), ambient=(0,0,0,1), diffuse=yellow_colour, specular=(0.7, 0.7, 0.7, 1), shininess=50.0, double_sided=True)
      mat = material.Material("material0", "mymaterial0", effect)
      mesh.effects.append(effect)
      mesh.materials.append(mat)
      matnode = scene.MaterialNode("materialref-0", mat, inputs=[])
      
      for l in self.seg_arr:
        v0 = self.vrtx_arr[l[0]-1]
        v1 = self.vrtx_arr[l[1]-1]
        bv0 = (v0[0]-self.base_xyz[0], v0[1]-self.base_xyz[1], v0[2]-self.base_xyz[2]) 
        bv1 = (v1[0]-self.base_xyz[0], v1[1]-self.base_xyz[1], v1[2]-self.base_xyz[2])
        print("PL: bv0=", bv0, "bv1=", bv1)        
        vert_floats = list(bv0) + [bv0[0], bv0[1], bv0[2]+LINE_WIDTH] + list(bv1) + [bv1[0], bv1[1], bv1[2]+LINE_WIDTH]
        print("vert_floats=", vert_floats)
        vert_src = source.FloatSource("lineverts-array-{0:010d}".format(point_cnt), numpy.array(vert_floats), ('X', 'Y', 'Z'))
        geom = geometry.Geometry(mesh, "geometry{0:010d}".format(point_cnt), "line-{0:010d}".format(point_cnt), [vert_src])
   
        input_list = source.InputList()
        input_list.addInput(0, 'VERTEX', "#lineverts-array-{0:010d}".format(point_cnt))
  
        indices = [0, 2, 3,
                   3, 1, 0]
        print("indices=", indices)
  
        triset = geom.createTriangleSet(numpy.array(indices), input_list, "materialref-0")
         
        geom.primitives.append(triset)
        mesh.geometries.append(geom)
        geomnode_list = []
        geomnode_list.append(scene.GeometryNode(geom, [matnode]))
        
        node = scene.Node("node{0:010d}".format(point_cnt), children=geomnode_list)
        node_list.append(node)
        point_cnt += 1
   
      myscene = scene.Scene("myscene", node_list)
      mesh.scenes.append(myscene)
      mesh.scene = myscene
  
  
    elif self.is_vs:
      POINT_SIZE = 1000
      point_cnt = 0
      print(len(self.rgba_tup), self.rgba_tup)
      node_list = []
      prop_str = list(self.prop_dict.keys())[0]
      for v in self.vrtx_arr:
        diffuse_colour = colour_map(self.prop_dict[prop_str][v], self.prop_meta[prop_str]['min'], self.prop_meta[prop_str]['max'])
        effect = material.Effect("effect{0:010d}".format(point_cnt), [], "phong", emission=(0,0,0,1), ambient=(0,0,0,1), diffuse=diffuse_colour, specular=(0.7, 0.7, 0.7, 1), shininess=50.0)
        mat = material.Material("material{0:010d}".format(point_cnt), "mymaterial{0:010d}".format(point_cnt), effect)
        mesh.effects.append(effect)
        mesh.materials.append(mat)
        bv = (v[0]-self.base_xyz[0], v[1]-self.base_xyz[1], v[2]-self.base_xyz[2]) 
        if True:
          vert_floats = list(bv) + [bv[0]+POINT_SIZE, bv[1], bv[2]] + [bv[0], bv[1]+POINT_SIZE, bv[2]] + [bv[0], bv[1], bv[2]+POINT_SIZE]
          vert_src = source.FloatSource("pointverts-array-{0:010d}".format(point_cnt), numpy.array(vert_floats), ('X', 'Y', 'Z'))
          geom = geometry.Geometry(mesh, "geometry{0:010d}".format(point_cnt), "mycube-{0:010d}".format(point_cnt), [vert_src])
          input_list = source.InputList()
          input_list.addInput(0, 'VERTEX', "#pointverts-array-{0:010d}".format(point_cnt))
  
          indices = [0, 2, 1,
                   3, 0, 1,
                   3, 2, 0,
                   3, 1, 2]
  
          triset = geom.createTriangleSet(numpy.array(indices), input_list, "materialref-{0:010d}".format(point_cnt))
        else:
          # Tried to do points as lines, but so far failed
          vert_floats = list(bv) + [bv[0], bv[1], bv[2]+1000]
          vert_src = source.FloatSource("pointverts-array-{0:010d}".format(point_cnt), numpy.array(vert_floats), ('X', 'Y', 'Z'))
          geom = geometry.Geometry(mesh, "geometry{0:010d}".format(point_cnt), "mycube-{0:010d}".format(point_cnt), [vert_src])
          input_list = source.InputList()
          input_list.addInput(0, 'VERTEX', "#pointverts-array-{0:010d}".format(point_cnt))
  
          indices = [0,1] 
          triset = geom.createLineSet(numpy.array(indices), input_list, "materialref-{0:010d}".format(point_cnt))
          
        geom.primitives.append(triset)
        mesh.geometries.append(geom)

        matnode = scene.MaterialNode("materialref-{0:010d}".format(point_cnt), mat, inputs=[])
        geomnode_list = [scene.GeometryNode(geom, [matnode])]
        
        node = scene.Node("node{0:010d}".format(point_cnt), children=geomnode_list)
        node_list.append(node)
        point_cnt += 1

      myscene = scene.Scene("myscene", node_list)
      mesh.scenes.append(myscene)
      mesh.scene = myscene
        
    elif self.is_vo:
      # Limit to 256 colours, only does tetrahedrons to save space 
      for colour_idx in range(256):
        diffuse_colour = colour_map(float(colour_idx), 0.0, 255.0)
        effect = material.Effect("effect{0:010d}".format(colour_idx), [], "phong", emission=(0,0,0,1), ambient=(0,0,0,1), diffuse=diffuse_colour, specular=(0.7, 0.7, 0.7, 1), shininess=50.0)
        mat = material.Material("material{0:010d}".format(colour_idx), "mymaterial{0:010d}".format(colour_idx), effect)
        mesh.effects.append(effect)
        mesh.materials.append(mat)
      
      node_list = []
      point_cnt = 0
      done = False
      for z in range(self.vol_dims[2]):
        for y in range(self.vol_dims[1]):
          for x in range(self.vol_dims[0]):
            if (self.voxel_data_stats['max'] - self.voxel_data_stats['min'])>0.0:
              colour_num = int(255.0*(self.voxel_data[x][y][z] - self.voxel_data_stats['min'])/(self.voxel_data_stats['max'] - self.voxel_data_stats['min']))
            else:
              colour_num = 0
            # NB: Assumes AXIS_MIN = 0, and AXIS_MAX = 1
            u_offset = self.axis_origin[0]+ float(x)/self.vol_dims[0]*self.axis_u[0]
            v_offset = self.axis_origin[1]+ float(y)/self.vol_dims[1]*self.axis_v[1]
            w_offset = self.axis_origin[2]+ float(z)/self.vol_dims[2]*self.axis_w[2]
            v = (u_offset-self.base_xyz[0], v_offset-self.base_xyz[1], w_offset-self.base_xyz[2])
            pt_size = (self.axis_u[0]/self.vol_dims[0], self.axis_v[1]/self.vol_dims[1], self.axis_w[2]/self.vol_dims[2])
            geomnode_list = []
            vert_floats = list(v) + [v[0]+pt_size[0], v[1], v[2]] + [v[0], v[1]+pt_size[1], v[2]] + [v[0], v[1], v[2]+pt_size[2]]
            vert_src = source.FloatSource("cubeverts-array-{0:010d}".format(point_cnt), numpy.array(vert_floats), ('X', 'Y', 'Z'))
            geom = geometry.Geometry(mesh, "geometry{0:010d}".format(point_cnt), "mycube-{0:010d}".format(point_cnt), [vert_src])
            input_list = source.InputList()
            input_list.addInput(0, 'VERTEX', "#cubeverts-array-{0:010d}".format(point_cnt))
  
            indices = [0, 2, 1,
                       3, 0, 1,
                       3, 2, 0,
                       3, 1, 2]
  
            triset = geom.createTriangleSet(numpy.array(indices), input_list, "materialref-{0:010d}".format(colour_num))
            geom.primitives.append(triset)
            mesh.geometries.append(geom)
            matnode = scene.MaterialNode("materialref-{0:010d}".format(colour_num), mesh.materials[colour_num], inputs=[])
            geomnode_list.append(scene.GeometryNode(geom, [matnode]))
        
            node = scene.Node("node{0:010d}".format(point_cnt), children=geomnode_list)
            node_list.append(node)
            point_cnt += 1
            
            if (point_cnt>999000000):
              print("Stop - too much!")
              done = True 
              break
          if done:
            break
        if done:
          break       
  
      print("Creating scene")
      myscene = scene.Scene("myscene", node_list)
      mesh.scenes.append(myscene)
      mesh.scene = myscene
    
    print("Writing mesh")
    mesh.write(fileName+'.dae')
    
    

  def process_gocad(self, src_dir, filename_str, file_lines):
    ''' Extracts details from gocad file
        filename_str - filename of gocad file
        file_lines - array of strings of lines from gocad file
    '''
    print("process_gocad(", filename_str, len(file_lines), ")")
   
    firstLine = True
    inHeader = False
    inPropClassHeader = False
    v_idx = 0
    properties_list = []
    fileName, fileExt = os.path.splitext(filename_str)
    for line in file_lines:
      line_str = line.rstrip(' \n\r').upper()
      splitstr_arr_raw = line.rstrip(' \n\r').split(' ')
      splitstr_arr = line_str.split(' ')
      
      # Check that we have a GOCAD file
      if firstLine:
        firstLine = False
        if not self.setType(fileExt, line_str):
          print("SORRY - not a GOCAD file", line_str)
          sys.exit(1)
        
      splitstr_arr = line_str.split(' ')
  
      # Get the colour
      if splitstr_arr[0] == "HEADER":
        inHeader = True
  
      if splitstr_arr[0] == "PROPERTY_CLASS_HEADER":
        self.prop_class_name = splitstr_arr[2]
        inPropClassHeader = True
  
      elif inHeader and splitstr_arr[0] == "}":
        inHeader = False
  
      elif inPropClassHeader and splitstr_arr[0] == "}":
        inPropClassHeader = False
  
      if inHeader:
        name_str, sep, value_str = line_str.partition(':')
        if name_str=='*SOLID*COLOR':
          rgbsplit_arr = value_str.split(' ')
          try:
            self.rgba_tup = (float(rgbsplit_arr[0]), float(rgbsplit_arr[1]), float(rgbsplit_arr[2]), float(rgbsplit_arr[3]))
          except (ValueError, OverflowError):
            self.rgba_tup = (1.0, 1.0, 1.0, 1.0)
      if inPropClassHeader:
        name_str, sep, value_str = line_str.partition(':')
        if name_str=='*COLORMAP*SIZE':
          print("colourmap-size", value_str)
        elif name_str=='*COLORMAP*NBCOLORS':
          print("numcolours", value_str)
        elif name_str=='HIGH_CLIP':
          print("highclip", value_str)
        elif name_str=='LOW_CLIP':
          print("lowclip", value_str)
        elif name_str=='COLORMAP':
          print("colourmap id", value_str)
          self.colourmap_name = value_str
        elif hasattr(self, 'colourmap_name') and name_str=='*COLORMAP*'+self.colourmap_name+'*COLORS':
          lut_arr = value_str.split(' ')
          for idx in range(0, len(lut_arr), 4):
            try:
              self.colour_map[int(lut_arr[idx])] = (float(lut_arr[idx+1]), float(lut_arr[idx+2]), float(lut_arr[idx+3]))
            except (OverflowError, ValueError):
              pass
  
      # If depth is positive, them must invert the z-axis
      if splitstr_arr[0].upper() == "ZPOSITIVE" and splitstr_arr[1].upper() == "DEPTH":
        self.invert_zaxis=True
  
      # Property names
      elif splitstr_arr[0].upper() == "PROPERTIES":
        properties_list = splitstr_arr[1:]

      # Grab the vertices and properties
      # NB: Assumes vertices are numbered sequentially, will stop if they are not
      elif splitstr_arr[0] == "PVRTX" or  splitstr_arr[0] == "VRTX":
        is_ok, x_flt, y_flt, z_flt = parse_XYZ(True, splitstr_arr[2], splitstr_arr[3], splitstr_arr[4])
        if is_ok:
          if self.invert_zaxis:
            z_flt = -z_flt
          self.vrtx_arr.append((x_flt, y_flt, z_flt))
          v_idx += 1
          if (int(splitstr_arr[1]))!=v_idx:
            print("ERROR - vertex ", splitstr_arr[0], " out of sequence in ", filename_str)
            sys.exit(1)
          if splitstr_arr[0] == "PVRTX":
            for p_idx in range(len(splitstr_arr[5:])):
              property_name = properties_list[p_idx]
              self.prop_dict.setdefault(property_name, {})
              try:
                self.prop_dict[property_name][(x_flt, y_flt, z_flt)] = float(splitstr_arr[p_idx+5])
              except (OverflowError, ValueError):
                pass
             
      # Grab the triangular edges
      elif splitstr_arr[0] == "TRGL":
        is_ok, a_int, b_int, c_int = parse_XYZ(False, splitstr_arr[1], splitstr_arr[2], splitstr_arr[3])
        if is_ok:
          self.trgl_arr.append((a_int, b_int, c_int))
  
      # Grab the segments
      elif splitstr_arr[0] == "SEG":
        try:
          a_int = int(splitstr_arr[1])
          b_int = int(splitstr_arr[2])
        except ValueError:
          pass
        else:
          self.seg_arr.append((a_int, b_int))
      
      # Voxel file attributes
      elif splitstr_arr[0] == "PROP_FILE":
        self.voxel_file = os.path.join(src_dir, splitstr_arr_raw[2])
      
      elif splitstr_arr[0] == "AXIS_O":
        is_ok, x_flt, y_flt, z_flt = parse_XYZ(True, splitstr_arr[1], splitstr_arr[2], splitstr_arr[3])
        if is_ok:
          self.axis_origin = (x_flt, y_flt, z_flt)
          
      elif splitstr_arr[0] == "AXIS_U":
        is_ok, x_flt, y_flt, z_flt = parse_XYZ(True, splitstr_arr[1], splitstr_arr[2], splitstr_arr[3])
        if is_ok:
          self.axis_u = (x_flt, y_flt, z_flt)
  
      elif splitstr_arr[0] == "AXIS_V":
        is_ok, x_flt, y_flt, z_flt = parse_XYZ(True, splitstr_arr[1], splitstr_arr[2], splitstr_arr[3])
        if is_ok:
          self.axis_v = (x_flt, y_flt, z_flt)
  
      elif splitstr_arr[0] == "AXIS_W":
        is_ok, x_flt, y_flt, z_flt = parse_XYZ(True, splitstr_arr[1], splitstr_arr[2], splitstr_arr[3])
        if is_ok:
          self.axis_w = (x_flt, y_flt, z_flt)
          
      elif splitstr_arr[0] == "AXIS_N":
        is_ok, x_int, y_int, z_int = parse_XYZ(False, splitstr_arr[1], splitstr_arr[2], splitstr_arr[3])
        if is_ok:
          self.vol_dims = (x_int, y_int, z_int)
          
      elif splitstr_arr[0] == "AXIS_MIN":
        is_ok, x_int, y_int, z_int = parse_XYZ(False, splitstr_arr[1], splitstr_arr[2], splitstr_arr[3])
        if is_ok:
          self.axis_min = (x_int, y_int, z_int)
          
      elif splitstr_arr[0] == "AXIS_MAX":
        is_ok, x_int, y_int, z_int = parse_XYZ(False, splitstr_arr[1], splitstr_arr[2], splitstr_arr[3])
        if is_ok:
          self.axis_max = (x_int, y_int, z_int)
    
    # Calculate max and min of properties rather than read them from file
    for prop_str in self.prop_dict:
      self.prop_meta.setdefault(prop_str,{})
      self.prop_meta[prop_str]['max'] = max(list(self.prop_dict[prop_str].values()))
      self.prop_meta[prop_str]['min'] = min(list(self.prop_dict[prop_str].values()))
  
     
    # Open up and read voxel file   
    if self.is_vo and len(self.voxel_file)>0:
      print("VOXEL FILE=", self.voxel_file)
      try:
        # Check file size first
        file_sz = os.path.getsize(self.voxel_file)
        num_voxels = 4*self.vol_dims[0]*self.vol_dims[1]*self.vol_dims[2]
        if file_sz != num_voxels:
          print("SORRY - Cannot process voxel file - length is not correct", filename_str)
          sys.exit(1)
        self.voxel_data = numpy.zeros((self.vol_dims[0], self.vol_dims[1], self.vol_dims[2]))
        fp = open(self.voxel_file, 'rb')
        for z in range(self.vol_dims[2]):
          for y in range(self.vol_dims[1]):
            for x in range(self.vol_dims[0]):
              binData = fp.read(4)
              val = struct.unpack(">f", binData)[0] # It's big endian!
              if (val > self.voxel_data_stats['max']):
                self.voxel_data_stats['max'] = val
              if (val < self.voxel_data_stats['min']):
                self.voxel_data_stats['min'] = val
              self.voxel_data[x][y][z] = val
        fp.close()
        print("min=", self.voxel_data_stats['min'], "max=", self.voxel_data_stats['max'])
      except IOError as e:
          print("SORRY - Cannot process voxel file IOError", filename_str, str(e), e.args)
          sys.exit(1)


#  END OF GOCAD_KIT CLASS


def extract_gocad(src_dir, filename_str, file_lines, base_xyz):
  ''' Extracts gocad files from a gocad group file
      filename_str - filename of gocad file
      file_lines - lines extracted from gocad group file
      Returns a list of GOCAD_KIT objects
  '''
  print("extract_gocad(", filename_str, ")")
  gs_list = []
  firstLine = True
  inMember = False
  inGoCAD = False
  gocad_lines = []
  fileName, fileExt = os.path.splitext(filename_str)
  for line in file_lines:
    
    line_str = line.rstrip(' \n\r').upper()
    splitstr_arr = line_str.split(' ')
    if firstLine:
      firstLine = False
      if fileExt.upper() != '.GP' or line_str not in GOCAD_KIT.GOCAD_HEADERS['GP']:
        print("SORRY - not a GOCAD GP file", repr(line_str))
        sys.exit(1)
    if line_str == "BEGIN_MEMBERS":
      inMember = True
      print("inMember = True")
    elif line_str == "END_MEMBERS":
      inMember = False
      print("inMember = False")
    elif inMember and splitstr_arr[0]=="GOCAD":
      inGoCAD = True
      print("START gathering")
    elif inMember and line_str == "END":
      inGoCAD = False
      print("END gathering")
      gs = GOCAD_KIT(base_xyz)
      gs.process_gocad(src_dir, filename_str, gocad_lines)
      gs_list.append(gs)
      gocad_lines = []
    if inMember and inGoCAD:
      gocad_lines.append(line)
      
  return gs_list
  
  
  

def find_and_process(gocad_src_dir, base_x, base_y, base_z):
  ''' Searches for gocad files and processes them
  '''
  for ext_str in GOCAD_KIT.SUPPORTED_EXTS:
    wildcard_str = os.path.join(gocad_src_dir, "*."+ext_str.lower())
    file_list = glob.glob(wildcard_str)
    for filename_str in file_list:
      fileName, fileExt = os.path.splitext(filename_str)
      try:
        fp = open(filename_str,'r')
        file_lines = fp.readlines()
      except(Exception):
        print("Can't open or read - skipping file", filename_str)
        continue

      if ext_str in ['TS', 'PL', 'VS', 'VO']:
        gs = GOCAD_KIT((base_x, base_y, base_z))
        gs.process_gocad(gocad_src_dir, filename_str, file_lines)

        # Check that conversion worked and write out files
        if ext_str == 'TS' and len(gs.vrtx_arr) > 0 and len(gs.trgl_arr) > 0:
          gs.write_collada(fileName)
        
        elif ext_str == 'PL' and len(gs.vrtx_arr) > 0 and len(gs.seg_arr) > 0:
          gs.write_collada(fileName)

        elif ext_str == 'VS' and len(gs.vrtx_arr) > 0:
          gs.write_collada(fileName)
      
        elif ext_str == 'VO' and gs.voxel_data.shape[0] > 1:
          # Must use PNG because some files are too large
          #gs.write_collada(fileName, gs)
          #gs.write_OBJ(fileName, filename_str)
          gs.write_voxel_png(gocad_src_dir, fileName, filename_str)
          
      elif ext_str == 'GP':
        gs_list=extract_gocad(gocad_src_dir, filename_str, file_lines, (base_x, base_y, base_z))
        file_idx=0
        for gs in gs_list:
          gs.write_collada("{0}_{1:d}".format(fileName, file_idx))
          file_idx += 1
      
      fp.close()
        
  # Convert from collada to GLTF v2
  if CONVERT_COLLADA:
    wildcard_str = os.path.join(gocad_src_dir, "*.dae")
    daefile_list = glob.glob(wildcard_str)
    for daefile_str in daefile_list:
      fileName, fileExt = os.path.splitext(daefile_str)
      cmd_str = os.path.join(COLLADA2GLTF_BIN, "COLLADA2GLTF-bin -i "+daefile_str+" -o "+fileName+".gltf")
      print(cmd_str)
      os.system(cmd_str)
      
  

if __name__ == "__main__":
    if len(sys.argv) > 1:
      gocad_src_dir = sys.argv[1]
      if os.path.isdir(gocad_src_dir):
        find_and_process(gocad_src_dir, 0.0,0.0,0.0)
      else:
        print("Dir "+gocad_src_dir+"does not exist")
    else:
      print("Command line parameter is a source dir of gocad files")

