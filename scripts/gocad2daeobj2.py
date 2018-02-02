#!/usr/bin/env python3
#
# I am writing this because the current library (LaGrit) used to read  GOCAD *.ts
# is buggy (seg faults a lot) and does not read the 'ZPOSITIVE', so some parts of models are displayed 
# upside down.
#
# Eventually this will accept all types of GOCAD files and support colours and 'ZPOSITIVE' flag etc.
#
import sys
import os
import glob

from gocad_kit import GOCAD_KIT
import collada2gltf

CONVERT_COLLADA = True


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
        
  # Convert all files from collada to GLTF v2
  if CONVERT_COLLADA:
    collada2gltf.convert(gocad_src_dir, "*.dae")
      
  

if __name__ == "__main__":
    if len(sys.argv) > 1:
      gocad_src_dir = sys.argv[1]
      if os.path.isdir(gocad_src_dir):
        find_and_process(gocad_src_dir, 0.0,0.0,0.0)
      else:
        print("Dir "+gocad_src_dir+"does not exist")
    else:
      print("Command line parameter is a source dir of gocad files")

