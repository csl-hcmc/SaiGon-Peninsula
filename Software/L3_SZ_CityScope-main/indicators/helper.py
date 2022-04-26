import os, time, json, sys
sys.path.append('../heat_maps')
sys.path.append('../utils')
from convert_coords import *


# change coordinates from 4236 to 4547
def convert_coordinates_from_4236_to_4547():
    source_dir_list = [
        '../tmp/physical_data_wgs84_jw_grid_extent_buffered',
    ]
    save_dir_list = [
        '../tmp/physical_data_epsg4547_jw_grid_extent_buffered',
    ]
    for source_dir, save_dir in zip(source_dir_list, save_dir_list):
        if not os.path.exists(os.path.abspath(save_dir)):
            os.makedirs(os.path.abspath(save_dir))
        for fname in os.listdir(source_dir):
            source_fpath = os.path.join(source_dir, fname)
            save_fpath = os.path.join(save_dir, fname)
            convert_coords_from_crs_to_crs(
                source_fpath, 4326,
                4547, save_fpath,
                crs_header=crs_header_4547
            )


if __name__ == '__main__':
    convert_coordinates_from_4236_to_4547()