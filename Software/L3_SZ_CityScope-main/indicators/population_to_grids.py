import os, time, json, sys
sys.path.append('../heat_maps')
sys.path.append('../utils')
from simple_count import get_simple_count
from scipy.spatial.distance import cdist
from general import NpEncoder
from convert_coords import *
import numpy as np



grid_file_folder = '../data/jw_grid'
grid_fnames = ['grid1_4326.geojson', 'grid2_4326.geojson']
# grid_fnames = ['grid2_4326.geojson']

population_source_folder = '../tmp/pop_data_wgs84_jw_grid_extent_valid'
population_fnames = [x.split('.')[0] for x in os.listdir(population_source_folder)]

for grid_fname in grid_fnames:
    grid_file_path = os.path.join(grid_file_folder, grid_fname)
    grid_save_path = os.path.join(grid_file_folder, grid_fname.split('.')[0]+'_with_population.geojson')
    grid_with_pop, rest_pop_points = get_simple_count(grid_file_path, population_fnames,
                                                      population_source_folder,
                                                      save_flag=False, print_flag=True,
                                                      return_rest_points=True)

    # assign each person to a grid even though he/she is actually not in any grid as space exists among grids
    grid_list = grid_with_pop['features']
    grid_centroid_list = [[g['properties']['centroid_x'], g['properties']['centroid_y']] for g in grid_list]
    for attr, points in rest_pop_points.items():
        # points are (lng, lat) but centroids are (x,y)
        points = convert_pure_coords_from_crs_to_crs(points, 4326, 4547)
        dist_from_rest_pop_to_grids = cdist(points, np.asarray(grid_centroid_list))
        grid_idx_with_min_dist_list = np.argmin(dist_from_rest_pop_to_grids, axis=-1)
        grid_idx_list, pop_count_list = np.unique(grid_idx_with_min_dist_list, return_counts=True)
        for grid_idx, pop_count in zip(grid_idx_list, pop_count_list):
            grid_list[grid_idx]['properties'][attr] += pop_count
    for grid in grid_list:
        grid['properties']['tt_pop'] = np.sum([grid['properties']['count_of_' + x] for x in population_fnames])
    grid_with_pop['features'] = grid_list

    # save epsg-4326 (lng, lat) grid with population
    json.dump(grid_with_pop, open(os.path.join(
        grid_file_folder, 'population', grid_fname.split('.')[0]+'_with_pop.geojson'),'w'),
              indent=4, cls=NpEncoder)

    # save epsg-4547 (x, y) grid with population
    this_save_path = os.path.join(
        grid_file_folder, 'population',
        grid_fname.split('.')[0].split('_')[0] + '_4547_with_pop.geojson'
    )
    convert_coords_from_crs_to_crs(grid_with_pop, 4326, 4547,
                                   save_path=this_save_path, crs_header=crs_header_4547)

