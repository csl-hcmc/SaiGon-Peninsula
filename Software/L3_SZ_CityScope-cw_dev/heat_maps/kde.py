import os, sys, json, time, argparse
import pandas as pd
import numpy as np
import geopandas as gpd
from utils import get_epsg

from shapely.geometry.polygon import Polygon
from shapely.geometry.multipolygon import MultiPolygon

from scipy import stats

def get_kde(grid_file_path, target_file_name_list, target_folder, 
    save_path='same', save_flag=True, print_flag=True, 
    bandwidth_method=None, bandwidth_multiplier=None):
    """
    target features should be points
    """
    ta = time.time()
    cells_full_content = json.load(open(grid_file_path, encoding='utf-8'))
    cells = cells_full_content['features']
    cell_epsg = get_epsg(cells_full_content)
    tb = time.time()
    
    for target_file_name in target_file_name_list:
        t1 = time.time()
        target_full_path = os.path.join(target_folder, target_file_name+'.geojson')
        attr = 'kde_of_' + target_file_name
        targets_full_content = json.load(open(target_full_path, encoding='utf-8'))
        targets = targets_full_content['features']
        # hack: considering too few points:
        real_points = [target['geometry']['coordinates'] for target in targets]
        if len(targets) <= 3:
            print(f'Warning: too few points (len={len(targets)}), generate 3 fake unrelated points.')
            fake_points = [[491000+np.random.rand(), 2500000+np.random.rand()] for i in range(3)]
        else:
            fake_points = []
        points = np.asarray(real_points + fake_points).T
        kernel = stats.gaussian_kde(points, bandwidth_method)
        if bandwidth_multiplier is not None:
            kernel.set_bandwidth(bw_method = kernel.factor * bandwidth_multiplier)
        targets_epsg = get_epsg(targets_full_content)
        if cell_epsg != targets_epsg or targets_epsg=='unknown':
            print('CRS of cells and targets do not match, might need to check it again.')
            print(f'CRS of cells: epsg {cell_epsg}\nCRS of targets ({target_file_name}): epsg {targets_epsg}\n')
    
        for cell in cells:
            cell['properties'] = {'centroid_x': cell['properties']['centroid_x'], 'centroid_y': cell['properties']['centroid_y']}   # speed up saving
            cell_coord = [cell['properties']['centroid_x'], cell['properties']['centroid_y']]
            cell['properties'][attr] = kernel(cell_coord)[0]
        t2 = time.time()
        if print_flag: print('{:4.4f} seconds elasped for generating {}'.format(t2-t1, attr))
    
    tc = time.time()
    cells_full_content['features'] = cells
    if save_flag:
        if save_path == 'same':
            save_path = grid_file_path
        else:
            dir_path = os.path.dirname(os.path.abspath(save_path))
            if not os.path.exists(dir_path):
                os.makedirs(dir_path)
        json.dump(cells_full_content, open(os.path.abspath(save_path), 'w'), indent=4)
        if print_flag: print(f'Cells with kernel density of {target_file_name_list} has been saved to:\n{save_path}')
    td = time.time()
    if print_flag: 
        print('{:4.4f} seconds in total (kde.py): {:4.4f} for preparing, {:4.4f} for calculation, {:4.4f} for saving'.format(
            td-ta, tb-ta, tc-tb, td-tc))
    return cells_full_content
    
    
def main():
    # print('kde starts at: ', time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time())))
    parser = argparse.ArgumentParser()
    parser.add_argument('-gfp', default='../data/grid.geojson', help='''grid file path''')
    parser.add_argument('-tfd', default='../tmp/emap_poi_epsg4547', help='''target folder''')
    parser.add_argument('-tfn', default=[], nargs='+', type=str, help='''target file name withOUT extention name (.geojson), 
        use space to seperate multiple file names''')
    parser.add_argument('-sp', default='same', help='''save path, default="same", i.e., overwrite the original cell file''')
    parser.add_argument('-bw', default=None, help='''bandwidth method, default=None, i.e., using scott estimator, 
        could be scott, silverman, or a scalar. If scalar is provided, it would be used as kde.factor, lower value will 
        lead to more local estimation''')
    parser.add_argument('-bwm', default=None, help='''bandwidth multiplier, deafult=None,
        if not None, this number will be multiplied with current kde.factor.
        if you find kde is too global, use a <1 multiplier, vice versa
        (1~0.01 seems to be good)''')
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
    if args.bw in [None, 'scott', 'silverman']:
        bandwidth_method = args.bw
    else:
        try:
            bandwidth_method = float(args.bw)
        except:
            print('Warning: invalid -bw argument, use default=None instead')
            bandwidth_method = None
    bandwidth_multiplier = args.bwm if args.bwm is None else float(args.bwm)
    print_flag = args.pf == 't'
    
    if print_flag:
        print(f'\ngrid_file_path = {grid_file_path}\ntarget_folder = {target_folder}')
        print(f'target_file_name_list = {target_file_name_list}\nsave_path = {save_path}')
        print(f'bandwidth_method = {bandwidth_method}\nbandwidth_multiplier = {bandwidth_multiplier}\n')
    # print('kde analysis starts at: ', time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time())))
    get_kde(grid_file_path, target_file_name_list, target_folder, save_path, save_flag=True, 
        bandwidth_method=bandwidth_method, bandwidth_multiplier=bandwidth_multiplier)
    # print('kde analysis finishes at: ', time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time())))
     
    
if __name__ == "__main__":
    main()