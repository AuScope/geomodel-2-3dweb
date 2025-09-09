import logging
import sys

from lib.db.style.style import STYLE
from lib.db.geometry.types import VRTX, ATOM, TRGL, SEG
from lib.db.geometry.model_geometries import ModelGeometries
from lib.db.metadata.metadata import METADATA

DEBUG_LVL = logging.INFO

# Set up debugging
LOGGER = logging.getLogger(__name__)

# Create console handler
LOCAL_HANDLER = logging.StreamHandler(sys.stdout)

# Create formatter
LOCAL_FORMATTER = logging.Formatter('%(asctime)s -- %(name)s -- %(levelname)s - %(message)s')

# Add formatter to ch
LOCAL_HANDLER.setFormatter(LOCAL_FORMATTER)

# Add handler to LOGGER
LOGGER.addHandler(LOCAL_HANDLER)

# Set debug level
LOGGER.setLevel(DEBUG_LVL)


def process_xyzv(file_lines, src_dir, filename, label, no_data_val=1e+10):
    LOGGER.debug("process_xyzv(file_lines[0]=%s)", file_lines[0])
    geom_obj = ModelGeometries()
    d_dict = {}
    (x_list, y_list, z_list) = ([], [], [])
    (min_v, max_v) = (sys.float_info.max, sys.float_info.min)
    for idx, l in enumerate(file_lines):
        try:
            (x, y, z, v) = (float(l[0]), float(l[1]), float(l[2]), float(l[3]))
        except ValueError:
            continue
        geom_obj.vrtx_arr.append(VRTX(idx+1, (x, y, z)))
        geom_obj.calc_minmax(x, y, z)
        if v != no_data_val:
            if v < min_v:
                min_v = v
            if v > max_v:
                max_v = v
        d_dict[x, y, z] = v

    geom_obj.add_loose_3d_data(True, d_dict)
    geom_obj.add_stats(min_v, max_v, no_data_val)
    meta_obj = METADATA()
    meta_obj.name = label
    style_obj = STYLE()
    return True, [(geom_obj, style_obj, meta_obj)]
