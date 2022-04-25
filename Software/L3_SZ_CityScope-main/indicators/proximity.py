import json, time, os
import numpy as np
from scipy.spatial.distance import cdist
from shapely.geometry import Polygon
import pandas as pd

# constants
grid_fpath = '../data/jw_grid/population/grid1_4547_with_pop.geojson'
from_geojson = json.load(open(grid_fpath, 'r', encoding='utf-8'))
from_obj_list = from_geojson['features']
from_obj_weight = [f['properties']['tt_pop'] for f in from_obj_list]
kpi_folder = '../tmp/kpi_epsg4547_confined'
poi_folder = '../tmp/emap_poi_epsg4547_confined'
landuse_fpath = '../tmp/physical_data_epsg4547_jw_grid_extent_buffered/current_landuse.geojson'
buildings_fpath = '../tmp/physical_data_epsg4547_jw_grid_extent_buffered/buildings.geojson'

def get_coords(obj_list):
    coords = []
    if type(obj_list[0]) == dict:
        if 'centroid_x' in obj_list[0]['properties']:
            coords = [[obj['properties']['centroid_x'],
                       obj['properties']['centroid_y']] for obj in obj_list]
        else:
            if obj_list[0]['geometry']['type'] == 'Polygon':
                coords = [
                    list(list(Polygon(obj['geometry']['coordinates'][0]).centroid.coords)[0])
                    for obj in obj_list
                ]
            elif obj_list[0]['geometry']['type'] == 'MultiPolygon':
                coords = [
                    list(list(Polygon(obj['geometry']['coordinates'][0][0]).centroid.coords)[0])
                    for obj in obj_list
                ]
            elif obj_list[0]['geometry']['type'] == 'Point':
                coords = [obj['geometry']['coordinates'] for obj in obj_list]
    elif type(obj_list[0]) in [list, tuple] and len(obj_list[0]) == 2:
        coords = obj_list
    else:
        raise TypeError('Element of obj_list must be dict, or list/tuple of coordinates with length=2')
    return coords


def calc_proximity(from_obj_list, to_obj_list, from_obj_weight=None,
                   dist_threshold=None, time_threshold=20, speed=1.2,
                   dist_matrix=None, kth=1, method='straight_line',
                   network_dist_multiplier=1, return_detailed_rst=False):
    if dist_matrix is None or len(dist_matrix) == 0:
        if len(to_obj_list) == 0:
            if return_detailed_rst:
                return {
                    'pass_ratio': 0,
                    'dist_matrix': np.asarray([]),
                    'weights': from_obj_weight,
                    'config': {'dist_threshold': dist_threshold,
                               'method': method, 'kth': kth,
                               'network_dist_multiplier': network_dist_multiplier}
                }
            else:
                return 0
        from_coords = np.asarray(get_coords(from_obj_list))
        to_coords = np.asarray(get_coords(to_obj_list))
        if method == 'straight_line':
            dist_matrix = cdist(from_coords, to_coords)
        elif method == 'network':
            # to do: network distance
            pass
    elif type(dist_matrix) == str and dist_matrix.endswith('.json'):
        dist_matrix = np.asarray(json.load(open(dist_matrix, encoding='utf-8')))
    elif type(dist_matrix) == np.ndarray:
        pass
    else:
        raise TypeError('If provided, dist_matrix must be a numpy.ndarray or a str for path of saved json file')

    if method == 'straight_line':
        dist_matrix = dist_matrix * network_dist_multiplier

    if dist_threshold is None:
        assert time_threshold is not None and speed is not None
        dist_threshold = time_threshold * speed * 60

    if kth == 1:
        kth_nearest_dist = np.min(dist_matrix, axis=-1)
    else:
        kth = min(kth, dist_matrix.shape[1]-1)
        kth_nearest_dist = np.sort(dist_matrix, axis=-1)[:, kth-1]
    nearest_dist_lt_threshold = kth_nearest_dist <= dist_threshold
    if from_obj_weight is None:
        pass_ratio = np.sum(nearest_dist_lt_threshold) / len(nearest_dist_lt_threshold)
    else:
        pass_ratio = np.sum(nearest_dist_lt_threshold * from_obj_weight) / np.sum(from_obj_weight)
    if return_detailed_rst:
        return {
                    'pass_ratio': pass_ratio,
                    'dist_matrix': dist_matrix,
                    'weights': from_obj_weight,
                    'config': {'dist_threshold': dist_threshold,
                               'method': method, 'kth': kth,
                               'network_dist_multiplier': network_dist_multiplier}
                }
    else:
        return pass_ratio


def calc_proximity_to_poi_kpi(points_name, points_type, dist_threshold,
                              method='straight_line', network_dist_multiplier=1,
                              kth=1, dist_matrix=None, print_flag=True):
    t0 = time.time()
    if points_type.upper() == 'POI':
        to_fpath = os.path.join(poi_folder, 'poi_'+points_name+'.geojson')
    elif points_type.upper() == 'KPI':
        to_fpath = os.path.join(kpi_folder, 'kpi_'+points_name+'.geojson')

    to_geojson = json.load(open(to_fpath, 'r', encoding='utf-8'))
    to_obj_list = to_geojson['features']
    rst = calc_proximity(from_obj_list, to_obj_list, from_obj_weight=from_obj_weight,
                         dist_threshold=dist_threshold, kth=kth,
                         dist_matrix=dist_matrix, method=method,
                         network_dist_multiplier=network_dist_multiplier,
                         return_detailed_rst=True)
    pass_ratio = rst['pass_ratio']
    t1 = time.time()

    if print_flag:
        print('\nProximity to {} of {}:\n'.format(points_type.upper(), points_name) + '='*40)
        print('{:4.2f}% of population can access {:d} of {} within {} meters'.format(
            pass_ratio * 100, kth, points_name, dist_threshold))
        print(f'Distance are calculated using {method} method, with network_dist_multiplier = {network_dist_multiplier}')
        print('Time cost of calculation = {:4.4f} seconds'.format(t1-t0))
    return rst


def batch_calc_proximity_to_poi_kpi(points_type, points_name_list='all',
                                    dist_threshold_list=[300], method='straight_line',
                                    network_dist_multiplier_list=[1],
                                    kth_list=[1], print_flag=False,
                                    csv_save_path=None):
    dist_matrix_lookup = {}
    rst = []
    if points_name_list == 'all':
        if points_type.upper() == 'POI':
            points_name_list = [f.split('.')[0][4:] for f in sorted(os.listdir(poi_folder)) if f.startswith('poi_')]
        elif points_type.upper() == 'KPI':
            points_name_list = [f.split('.')[0][4:] for f in sorted(os.listdir(kpi_folder)) if f.startswith('kpi_')]
    for points_name in points_name_list:
        for dist_threshold in dist_threshold_list:
            for network_dist_multiplier in network_dist_multiplier_list:
                for kth in kth_list:
                    dist_matrix = dist_matrix_lookup.get(points_name, None)
                    this_rst = calc_proximity_to_poi_kpi(points_name,
                                                         points_type,
                                                         dist_threshold,
                                                         method,
                                                         network_dist_multiplier,
                                                         kth, dist_matrix, print_flag)
                    if points_name not in dist_matrix_lookup:
                        dist_matrix_lookup[points_name] = this_rst['dist_matrix']
                    rst.append({
                        'destination': points_name,
                        'dist_threshold': dist_threshold,
                        'nearest_k': kth,
                        'network_dist_multiplier': network_dist_multiplier,
                        'accessible_ratio': this_rst['pass_ratio']
                    })
    if csv_save_path is not None:
        df = pd.DataFrame(rst)
        save_dirname = os.path.dirname(os.path.abspath(csv_save_path))
        if not os.path.exists(save_dirname):
            os.makedirs(save_dirname)
        df.to_csv(os.path.abspath(csv_save_path), encoding='utf-8', index=False)
    return rst


def batch_calc_proximity_to_lu_bldg(to_obj_type, usage_list='all',
                                    dist_threshold_list=[300], method='straight_line',
                                    network_dist_multiplier_list=[1],
                                    kth_list=[1], print_flag=False,
                                    csv_save_path=None):
    dist_matrix_lookup = {}
    rst = []
    if to_obj_type in ['lu', 'landuse']:
        to_geojson = json.load(open(landuse_fpath, 'r', encoding='utf-8'))
        usage_column = 'DETAIL_LU_NAME'
        to_obj_type = 'Land-use'
    elif to_obj_type in ['buildings', 'bldg']:
        to_geojson = json.load(open(buildings_fpath, 'r', encoding='utf-8'))
        usage_column = 'BLDG_USAGE'
        to_obj_type = 'Buildings'
    all_features = to_geojson['features']
    if type(usage_list) == str and usage_list == 'all':
        usage_list = np.unique([f['properties'][usage_column] for f in all_features])
    elif type(usage_list) == str:
        usage_list = [usage_list]
    elif type(usage_list) == list:
        pass
    else:
        raise TypeError('usage_list must be a list, or "all", or a string of usage name')

    for usage in usage_list:
        for dist_threshold in dist_threshold_list:
            for network_dist_multiplier in network_dist_multiplier_list:
                for kth in kth_list:
                    t0 = time.time()
                    dist_matrix = dist_matrix_lookup.get(usage, None)
                    to_obj_list = [f for f in all_features if f['properties'][usage_column]==usage]
                    this_rst = calc_proximity(
                        from_obj_list, to_obj_list, from_obj_weight=from_obj_weight,
                        dist_threshold=dist_threshold, kth=kth,
                        dist_matrix=dist_matrix, method=method,
                        network_dist_multiplier=network_dist_multiplier,
                        return_detailed_rst=True
                    )
                    pass_ratio = this_rst['pass_ratio']
                    t1 = time.time()
                    if print_flag:
                        print('\nProximity to {} with usage = {}:\n'.format(to_obj_type, usage) + '=' * 60)
                        print('{:4.2f}% of population can access {:d} of {} within {} meters'.format(
                            pass_ratio * 100, kth, usage, dist_threshold))
                        print(f'Distance are calculated using {method} method, with network_dist_multiplier = {network_dist_multiplier}')
                        print('Time cost of calculation = {:4.4f} seconds'.format(t1 - t0))
                    if usage not in dist_matrix_lookup:
                        dist_matrix_lookup[usage] = this_rst['dist_matrix']
                    rst.append({
                        'destination': usage,
                        'dist_threshold': dist_threshold,
                        'nearest_k': kth,
                        'network_dist_multiplier': network_dist_multiplier,
                        'accessible_ratio': this_rst['pass_ratio']
                    })
    if csv_save_path is not None:
        df = pd.DataFrame(rst)
        save_dirname = os.path.dirname(os.path.abspath(csv_save_path))
        if not os.path.exists(save_dirname):
            os.makedirs(save_dirname)
        df.to_csv(os.path.abspath(csv_save_path), encoding='utf-8', index=False)
    return rst


def main():
    batch_calc_proximity_to_poi_kpi('poi', csv_save_path='poi.csv', print_flag=True,
                                    dist_threshold_list=[300,400,500],
                                    kth_list=[1,3])
    batch_calc_proximity_to_poi_kpi('kpi', csv_save_path='kpi.csv', print_flag=True,
                                    dist_threshold_list=[300, 400, 500],
                                    kth_list=[1, 3])
    batch_calc_proximity_to_lu_bldg('landuse', 'all',
                                    csv_save_path='landuse.csv', print_flag=True,
                                    dist_threshold_list=[300,400,500])
    batch_calc_proximity_to_lu_bldg('buildings', 'all',
                                    csv_save_path='buildings.csv',
                                    print_flag=True,
                                    kth_list=[1, 2, 3],
                                    dist_threshold_list=[300, 400, 500])

if __name__ == '__main__':
    main()