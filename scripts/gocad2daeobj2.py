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
import json

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
      gs = GOCAD_KIT(base_xyz, os.path.basename(fileName).upper())
      gs.process_gocad(src_dir, filename_str, gocad_lines)
      gs_list.append(gs)
      gocad_lines = []
    if inMember and inGoCAD:
      gocad_lines.append(line)
      
  return gs_list
  
  
  

def find_and_process(gocad_src_dir, base_x=0.0, base_y=0.0, base_z=0.0):
  ''' Searches for gocad files and processes them
      gocad_src_dir - source directory where there are gocad files
      base_x, base_y, base_z - 3D coordinate offset, this is added to all 
                               coordinates
  '''
  ret_list = []
  for ext_str in GOCAD_KIT.SUPPORTED_EXTS:
    wildcard_str = os.path.join(gocad_src_dir, "*."+ext_str.lower())
    file_list = glob.glob(wildcard_str)
    for filename_str in file_list:
      popup_dict_list = process(filename_str, base_x, base_y, base_z)
      ret_list += popup_dict_list
  return ret_list

def process(filename_str, base_x=0.0, base_y=0.0, base_z=0.0):
  ''' Processes a GOCAD file
      filename_str - filename of GOCAD file
      base_x, base_y, base_z - 3D coordinate offset, this is added to all 
                               coordinates
  '''
  popup_dict_list = []
  popup_dict = None
  fileName, fileExt = os.path.splitext(filename_str)
  ext_str = fileExt.lstrip('.').upper()
  gocad_src_dir = os.path.dirname(filename_str)
  try:
    fp = open(filename_str,'r')
    file_lines = fp.readlines()
  except(Exception):
    print("Can't open or read - skipping file", filename_str)
    return 

  if ext_str in ['TS', 'PL', 'VS', 'VO']:
    gs = GOCAD_KIT((base_x, base_y, base_z))
    gs.process_gocad(gocad_src_dir, filename_str, file_lines)

    # Check that conversion worked and write out files
    if ext_str == 'TS' and len(gs.vrtx_arr) > 0 and len(gs.trgl_arr) > 0:
      popup_dict = gs.write_collada(fileName)
    
    elif ext_str == 'PL' and len(gs.vrtx_arr) > 0 and len(gs.seg_arr) > 0:
      popup_dict= gs.write_collada(fileName)

    elif ext_str == 'VS' and len(gs.vrtx_arr) > 0:
      popup_dict = gs.write_collada(fileName)
  
    elif ext_str == 'VO' and gs.voxel_data.shape[0] > 1:
      # Must use PNG because some files are too large
      #popup_dict = gs.write_collada(fileName, gs)
      #gs.write_OBJ(fileName, filename_str)
      gs.write_voxel_png(gocad_src_dir, fileName, filename_str)
      
  elif ext_str == 'GP':
    gs_list=extract_gocad(gocad_src_dir, filename_str, file_lines, (base_x, base_y, base_z))
    file_idx = 0
    for gs in gs_list:
      out_filename = "{0}_{1:d}".format(fileName, file_idx)
      p_dict = gs.write_collada(out_filename)
      popup_dict_list.append(add_info2popup(p_dict, out_filename))
      popup_dict = None
      file_idx += 1

  fp.close()

  if popup_dict != None:
    popup_dict_list = [add_info2popup(popup_dict, fileName)]

  return popup_dict_list


        
def add_info2popup(popup_dict, fileName):
  ''' Adds more information to popup dictionary
      popup_dict - information to display in popup window
      fileName - file and path without extension of source file
  '''
  np_filename = os.path.basename(fileName)
  j_dict = {}
  j_dict['popups'] = popup_dict
  j_dict['type'] = 'GLTFObject'
  j_dict['model_url'] = np_filename+".gltf"
  j_dict['display_name'] = np_filename.replace('_',' ')
  j_dict['include'] = True
  j_dict['displayed'] = True
  return j_dict


      
def make_json_config(popup_dict_list, file_name):
  ''' Writes a JSON file of GLTF objects to display in 3D
      popup_dict_list - list to write to JSON file
  '''
  fp = open(file_name, "w")
  config_dict = read_json_config('NorthGawlerInput.json')
  groups_obj = config_dict['groups']
  for group_name, part_list in groups_obj.items():
    for part in part_list:
      for popup_dict in popup_dict_list:
        if part['model_url'] == popup_dict['model_url']:
          part['popups'] = popup_dict['popups']
          for label, p_dict in part['popups'].items():
            p_dict['title'] = group_name + '-' + part['display_name']
          break
  json.dump(config_dict, fp, indent=4, sort_keys=True)
  fp.close()


def read_json_config(file_name):
  '''
  '''
  fp = open(file_name, "r")
  config_dict = json.load(fp)
  fp.close()
  return config_dict
  

if __name__ == "__main__":
    if len(sys.argv) > 1:
      gocad_src = sys.argv[1]
      if os.path.isdir(gocad_src):
        popup_dict_list = find_and_process(gocad_src)
        # Convert all files from collada to GLTF v2
        if CONVERT_COLLADA:
          collada2gltf.convert_dir(gocad_src)
        make_json_config(popup_dict_list, os.path.join(gocad_src, "NorthGawlerOutput.json"))

      elif os.path.isfile(gocad_src):
        popup_dict_list = process(gocad_src)
        # Convert all files from collada to GLTF v2
        if CONVERT_COLLADA:
          file_name, file_ext = os.path.splitext(gocad_src)
          collada2gltf.convert_file(file_name+".dae")
        make_json_config(popup_dict_list, file_name+".json")
      else:
        print(gocad_src, "does not exist")
    else:
      print("Command line parameter is a source dir of gocad files")


