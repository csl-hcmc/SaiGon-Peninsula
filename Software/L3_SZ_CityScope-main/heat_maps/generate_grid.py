import os, sys, json, time
import pandas as pd
import numpy as np
import geopandas as gpd

from shapely.geometry.polygon import Polygon
from shapely.geometry.multipolygon import MultiPolygon

from utils import euclidean_distance

  
def save_grid_geojson(X, Y, save_path, crs, mask=None, min_area_intersect_with_mask=0):
    name = os.path.basename(save_path).split('.')[0]
    content = {
        "type": "FeatureCollection",
        "name": name,
        "crs": crs,
    }
    nrow, ncol = X.shape
    features = []
    idx = 0
    for row_idx in range(nrow-1):
        for col_idx in range(ncol-1):
            this_cell_coords = [
                [X[row_idx, col_idx], Y[row_idx, col_idx]],
                [X[row_idx+1, col_idx], Y[row_idx+1, col_idx]],
                [X[row_idx+1, col_idx+1], Y[row_idx+1, col_idx+1]],
                [X[row_idx, col_idx+1], Y[row_idx, col_idx+1]],
                [X[row_idx, col_idx], Y[row_idx, col_idx]]
            ]
            if mask is not None:
                cell = Polygon(this_cell_coords)
                if not ((mask.contains(cell)) or (mask.intersection(cell).area>min_area_intersect_with_mask)):
                    continue
            features.append({
                "type": "Feature",
                "id": idx,
                "properties": {
                    'row_idx': row_idx, 'col_idx': col_idx,
                    'centroid_x': np.mean([coord[0] for coord in this_cell_coords[:-1]]),
                    'centroid_y': np.mean([coord[1] for coord in this_cell_coords[:-1]])
                 }, 
                "geometry": {"type": "Polygon", "coordinates": [this_cell_coords]} 
            })
            idx += 1
    content['features'] = features
    json.dump(content, open(os.path.abspath(save_path), 'w'), indent=4)
  
def get_meshgrid(resolution, ombb_long_edge_length, ombb_short_edge_length, ombb_angle, ombb_bottom_left):
    x, y = [], []
    this_x, this_y = -resolution, -resolution
    while this_x <= ombb_long_edge_length:
        x.append(this_x)
        this_x += resolution
    x.append(this_x)
    while this_y <= ombb_short_edge_length:
        y.append(this_y)
        this_y += resolution
    y.append(this_y)
    X, Y = np.meshgrid(x, y)
    rot = (ombb_angle - 90) * np.pi / 180
    Xr =  np.cos(rot)*X + np.sin(rot)*Y  
    Yr = -np.sin(rot)*X + np.cos(rot)*Y
    Xr += (ombb_bottom_left[0] - Xr[0][0])
    Yr += (ombb_bottom_left[1] - Yr[0][0])
    return Xr, Yr
    
     
def main():
    base_file = '../data/border_RA_epsg4547.geojson'
    base_ombb_file = '../data/border_RA_ombb.geojson'
    grid_file = '../data/grid.geojson'
    resolution = 80
    
    ombb = json.load(open(base_ombb_file))['features'][0]
    ombb_coords = ombb['geometry']['coordinates'][0]
    ombb_angle = ombb['properties']['angle']
    ombb_bottom_left = ombb_coords[3]
    ombb_long_edge_length = euclidean_distance(ombb_coords[0], ombb_coords[3])
    ombb_short_edge_length = euclidean_distance(ombb_coords[0], ombb_coords[1])
    crs = json.load(open(base_file))['crs']
    
    X, Y = get_meshgrid(resolution, ombb_long_edge_length, ombb_short_edge_length, ombb_angle, ombb_bottom_left)
    mask = json.load(open(base_file))['features'][0]
    if mask['geometry']['type'] == 'MultiPolygon':
        mask = Polygon(mask['geometry']['coordinates'][0][0])
    elif mask['geometry']['type'] == 'Polygon':
        mask = Polygon(mask['geometry']['coordinates'][0])
    min_area_intersect_with_mask = 0.2 * resolution ** 2
    
    save_grid_geojson(X, Y, grid_file, crs, mask, min_area_intersect_with_mask)
    
if __name__ == '__main__':
    main()