import os, sys, json
sys.path.append('../utils')
from shapely.geometry.polygon import Polygon

from convert_coords import convert_coords_from_crs_to_crs, crs_header_4326, crs_header_4547

def process_grid_from_jw(source_path, save_path=None, check_line=False, max_area=None):
    if save_path is None:
        save_path = source_path
    if not os.path.exists(os.path.dirname(save_path)):
        os.makedirs(os.path.dirname(save_path))
        
    print(f'\n\nProcess grid:\nsource from {os.path.abspath(source_path)}\nsave to {os.path.abspath(save_path)}')
    full_data = json.load(open(source_path, 'r'))
    features = full_data['features']
    features_new = []
    for idx, feature in enumerate(features):
        feature['id'] = idx
        coords = [coord[:2] for coord in feature['geometry']['coordinates']]
        if not check_line:
            if len(coords) <= 2:
                print(f'Skip lineString with id={idx}: length of coords is {len(coords)}')
                continue
            if coords[0] != coords[-1]:
                print(f'\n\nPolyline id={idx} not colosed, might be due to missing edge, force it to be closed')
                coords.append(coords[0].copy())  # subtle error. if not using copy, the same coord would be convert_coord twice!!
            feature['geometry']['coordinates'] = [coords]
            feature['geometry']['type'] = 'Polygon'
            this_polygon = Polygon(coords)
            if max_area is not None and this_polygon.area >= max_area:
                print(f'Skip polygon with id={idx}: too large area, area={this_polygon.area}')
                continue
            feature['properties'].update({
                'centroid_x': this_polygon.centroid.x,
                'centroid_y': this_polygon.centroid.y,
                'area': this_polygon.area
            })
        else:
            feature['geometry']['coordinates'] = coords
            feature['properties']['len_coords'] = len(coords)
            feature['properties']['closed'] = True if coords[0]==coords[-1] else False
            if len(coords) <= 2:
                print(f'Error at id={idx}: length of coords is {len(coords)}')
            if not feature['properties']['closed']:
                print(f'Error at id={idx}: polygon might be not closed')
        features_new.append(feature)
    full_data['features'] = features_new
    json.dump(full_data, open(save_path, 'w'), indent=4)
    return full_data
    
def save_grid_in_4326(full_data, save_path_4326):
    print(f'\nConvert grid CRS to 4326:\nsave to {os.path.abspath(save_path_4326)}')
    if full_data['crs'] == crs_header_4547:
        full_data = convert_coords_from_crs_to_crs(full_data, 4547, 4326, crs_header=crs_header_4326)
    json.dump(full_data, open(save_path_4326, 'w'), indent=4)
    

def main():
    check_line = False
    max_area = 4000000
    grid_folder = '../data/jw_grid'
    for grid_fname in ['grid2_raw_new']:
        source_path = os.path.join(grid_folder, grid_fname + '.geojson')
        save_path_4547 = os.path.join(grid_folder, grid_fname.split('_')[0] + '_4547.geojson')
        save_path_4326 = os.path.join(grid_folder, grid_fname.split('_')[0] + '_4326.geojson')
        full_data = process_grid_from_jw(source_path, save_path_4547, check_line, max_area)        
        if not check_line:
            save_grid_in_4326(full_data, save_path_4326)


if __name__ == '__main__':
    main()