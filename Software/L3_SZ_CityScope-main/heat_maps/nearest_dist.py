import os, sys, json, time, argparse
import pandas as pd
import numpy as np
import geopandas as gpd
from utils import distance_from_centroid, get_epsg
from scipy.spatial.distance import cdist

from shapely.geometry.polygon import Polygon
from shapely.geometry.multipolygon import MultiPolygon

def get_nearest_distance(grid_file_path, target_file_name_list, target_folder, 
    save_path='same', save_flag=True, print_flag=True):

    cells_full_content = json.load(open(grid_file_path, encoding='utf-8'))
    cells = cells_full_content['features']
    cell_centroids = np.asarray([[cell['properties']['centroid_x'], cell['properties']['centroid_y']] for cell in cells])
    cell_epsg = get_epsg(cells_full_content)
    
    for target_file_name in target_file_name_list:
        t1 = time.time()
        target_full_path = os.path.join(target_folder, target_file_name+'.geojson')
        attr = 'dist_to_' + target_file_name
        targets_full_content = json.load(open(target_full_path, encoding='utf-8'))
        targets = targets_full_content['features']
        
        if len(targets) > 0:
            target_centroids = np.asarray([point_feature['geometry']['coordinates'] for point_feature in targets])
            dist_from_cells_to_targets = cdist(cell_centroids, target_centroids)
            
        targets_epsg = get_epsg(targets_full_content)
        if cell_epsg != targets_epsg or targets_epsg=='unknown':
            print('CRS of cells and targets do not match, might need to check it again.')
            print(f'CRS of cells: epsg {cell_epsg}\nCRS of targets ({target_file_name}): epsg {targets_epsg}\n')
    
        for idx, cell in enumerate(cells):
            cell_coord = [cell['properties']['centroid_x'], cell['properties']['centroid_y']]
            if len(targets) > 0:
                # min_dist = min([distance_from_centroid(cell_coord, target) for target in targets])
                min_dist = min(dist_from_cells_to_targets[idx, :])
            else:
                min_dist = 0
            cell['properties'][attr] = min_dist
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
        if print_flag: print(f'Cells with nearest distance to {target_file_name_list} has been saved to:\n{save_path}')
    return cells_full_content
    
    
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-gfp', default='../data/grid.geojson', help='''grid file path''')
    parser.add_argument('-tfd', default='../tmp/emap_poi_epsg4547', help='''target folder''')
    parser.add_argument('-tfn', default=[], nargs='+', type=str, help='''target file name withOUT extention name (.geojson), 
        use space to seperate multiple file names''')
    parser.add_argument('-sp', default='same', help='''save path, default="same", i.e., overwrite the original cell file''')
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
    print_flag = args.pf == 't'
    
    if print_flag:
        print(f'\ngrid_file_path = {grid_file_path}\ntarget_folder = {target_folder}')
        print(f'target_file_name_list = {target_file_name_list}\nsave_path = {save_path}\n')
    get_nearest_distance(grid_file_path, target_file_name_list, target_folder, save_path, save_flag=True)
     
    
if __name__ == "__main__":
    main()