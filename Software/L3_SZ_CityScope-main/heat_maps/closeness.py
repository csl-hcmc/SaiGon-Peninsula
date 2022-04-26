import os, sys, json, time, argparse
import pandas as pd
import numpy as np
import geopandas as gpd
from utils import distance_from_centroid, get_epsg
from scipy.spatial.distance import cdist

from shapely.geometry.polygon import Polygon
from shapely.geometry.multipolygon import MultiPolygon

# @profile
def get_closeness(grid_file_path, target_file_name_list, target_folder, 
    nearest_n=None, max_considering_dist=15000,
    save_path='same', save_flag=True, print_flag=True):

    cells_full_content = json.load(open(grid_file_path, encoding='utf-8'))
    cells = cells_full_content['features']
    cell_centroids = np.asarray([[cell['properties']['centroid_x'], cell['properties']['centroid_y']] for cell in cells])
    cell_epsg = get_epsg(cells_full_content)
    
    for target_file_name in target_file_name_list:
        t1 = time.time()
        target_full_path = os.path.join(target_folder, target_file_name+'.geojson')
        attr = 'closeness_to_' + target_file_name
        targets_full_content = json.load(open(target_full_path, encoding='utf-8'))
        targets = targets_full_content['features']
        
        if len(targets) > 0:
            target_centroids = np.asarray([point_feature['geometry']['coordinates'] for point_feature in targets])
            dist_from_cells_to_targets = cdist(cell_centroids, target_centroids)
        else:
            dist_from_cells_to_targets = []
            
        targets_epsg = get_epsg(targets_full_content)
        if cell_epsg != targets_epsg or targets_epsg=='unknown':
            print('CRS of cells and targets do not match, might need to check it again.')
            print(f'CRS of cells: epsg {cell_epsg}\nCRS of targets ({target_file_name}): epsg {targets_epsg}\n')
    
        # generate a distance lookup table from all cells to all targets
        cells_to_targets_dist_lookup = {}
        targets_to_cells_dist_lookup = {}
        # cells_id_lookup = {serial_idx: cell['id'] for serial_idx, cell in enumerate(cells)}
        # targets_id_lookup = {serial_idx: target['properties']['OBJECTID'] for serial_idx, target in enumerate(targets)}
        t4 = time.time()
        
        # # Too slow
        # for cell in cells:
            # cell_idx = cell['id']
            # cell_coord = [cell['properties']['centroid_x'], cell['properties']['centroid_y']]
            # if cell_idx not in cells_to_targets_dist_lookup:
                # cells_to_targets_dist_lookup[cell_idx] = {}
            # for target in targets:
                # if target['properties']['OBJECTID'] not in targets_to_cells_dist_lookup:
                    # targets_to_cells_dist_lookup[target['properties']['OBJECTID']] = {}
                # this_dist = distance_from_centroid(cell_coord, target)
                # cells_to_targets_dist_lookup[cell_idx][target['properties']['OBJECTID']] = this_dist
                # targets_to_cells_dist_lookup[target['properties']['OBJECTID']][cell_idx] = this_dist 
        
        for cell_serial_idx, cell in enumerate(cells):
            cells_to_targets_dist_lookup[cell_serial_idx] = {
                target_serial_idx: dist_from_cells_to_targets[cell_serial_idx, target_serial_idx] 
                    for target_serial_idx, target in enumerate(targets)
            }
            
        for target_serial_idx, target in enumerate(targets):
            targets_to_cells_dist_lookup[target_serial_idx] = {
                cell_serial_idx: dist_from_cells_to_targets[cell_serial_idx, target_serial_idx] 
                    for cell_serial_idx, cell in enumerate(cells)
            }
                
        if max_considering_dist is not None:
            targets_considered = [
                target_serial_idx for target_serial_idx, dist_list in targets_to_cells_dist_lookup.items()
                    if min(list(dist_list.values())) <= max_considering_dist
            ]
        else:
            targets_considered = [target_serial_idx for target_serial_idx, target in enumerate(targets)]
            
        if nearest_n and nearest_n >= len(targets_considered):
            nearest_n = None    # too many nearest_n, use all targets_considered instead
            
        # print(f'len(targets) = {len(targets)}, len(targets_considered) = {len(targets_considered)}, nearest_n = {nearest_n}\n\n')
        
        for cell_serial_idx, cell in enumerate(cells):
            dist_to_all_targets = cells_to_targets_dist_lookup[cell_serial_idx]
            dist_to_considered_targets = [dist_to_all_targets[target_serial_idx] for target_serial_idx in targets_considered]
            if nearest_n is not None:
                valid_dist = sorted(dist_to_considered_targets)[:nearest_n]
            else:
                valid_dist = dist_to_considered_targets
            if len(valid_dist) == 0:
                closeness = 0
            else:
                closeness = sum([1000/max(0.1, dist) for dist in valid_dist]) / len(valid_dist)  # 1000 to convert from m to km
            cell['properties'][attr] = closeness
        t2 = time.time()
        if print_flag: print('{:4.4f} seconds elasped for generating {}'.format(t2-t1, attr))
        
    cells_full_content['features'] = cells
    if save_flag:
        if save_path == 'same':
            save_path = grid_file_path
        else:
            dir_path = os.path.dirname(os.path.abspath(save_path))
            if not os.path.exists(dir_path):
                os.makedirs(dir_path)
        json.dump(cells_full_content, open(os.path.abspath(save_path), 'w'), indent=4)
        if print_flag: print(f'Cells with closeness to {target_file_name_list} has been saved to:\n{save_path}')
    return cells_full_content
    
    
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-gfp', default='../data/grid.geojson', help='''grid file path''')
    parser.add_argument('-tfd', default='../tmp/emap_poi_epsg4547', help='''target folder''')
    parser.add_argument('-tfn', default=[], nargs='+', type=str, help='''target file name withOUT extention name (.geojson), 
        use space to seperate multiple file names''')
    parser.add_argument('-sp', default='same', help='''save path, default="same", i.e., overwrite the original cell file''')
    parser.add_argument('-nn', default=None, help='''only considering nearest n targets''')
    parser.add_argument('-mcd', default=15000, help='''only considering targets whose minimum distance to any of cells is less than this distance (in meters)''')
    parser.add_argument('-pf', default='t', help='''print_flag, default="t"''')
    
    
    args = parser.parse_args()
    grid_file_path = args.gfp
    if not os.path.exists(grid_file_path):
        print(f'Error: grid_file_path ({grid_file_path}) does not exist')
        return
    target_folder = args.tfd
    target_file_name_list = args.tfn
    for fname in target_file_name_list:
        fpath = os.path.join(target_folder, fname+'.geojson')
        if not os.path.exists(fpath):
            print(f'Error: target_file_name ({fpath}) does not exists')
            return
    save_path = args.sp
    nearest_n = args.nn if args.nn is None else int(args.nn)
    max_considering_dist = args.mcd if args.mcd is None else float(args.mcd)
    print_flag = args.pf == 't'
    
    if print_flag:
        print(f'\ngrid_file_path = {grid_file_path}\ntarget_folder = {target_folder}')
        print(f'target_file_name_list = {target_file_name_list}\nsave_path = {save_path}')
        print(f'nearest_n = {nearest_n}\nmax_considering_dist = {max_considering_dist}\n')
        
    get_closeness(grid_file_path, target_file_name_list, target_folder, save_path=save_path, 
        nearest_n=nearest_n, max_considering_dist=max_considering_dist, save_flag=False)
     
    
if __name__ == "__main__":
    main()