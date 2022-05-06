import os, json, copy, sys

from shapely.geometry import Point
from shapely.geometry.polygon import Polygon
from shapely.geometry.multipolygon import MultiPolygon

def get_first_polygon_from_geojson(polygon_geojson): 
    if type(polygon_geojson) == dict:
        pass
    elif type(polygon_geojson) == str and polygon_geojson.endswith('.geojson'):
        polygon_geojson = json.load(open(polygon_geojson, 'r', encoding='utf-8'))
    polygon = polygon_geojson['features'][0]
    if polygon['geometry']['type'] == 'Polygon':
        polygon = Polygon(polygon['geometry']['coordinates'][0])
    elif polygon['geometry']['type'] == 'MultiPolygon':
        polygon = Polygon(polygon['geometry']['coordinates'][0][0])
    return polygon
    

def clip_point_given_mask(point_feature, mask_polygon):
    """
    """
    if type(mask_polygon) != Polygon:
        mask_polygon = get_first_polygon_from_geojson(mask_polygon)
    rst = []
    if point_feature['geometry']['type'] == 'Point':
        this_point = Point(point_feature['geometry']['coordinates'])
        if mask_polygon.contains(this_point): 
            rst.append(copy.deepcopy(point_feature))
    elif point_feature['geometry']['type'] == 'MultiPoint':
        for this_point_coord in point_feature['geometry']['coordinates']:
            this_point = Point(this_point_coord)
            if mask_polygon.contains(this_point):
                new_point_feature = copy.deepcopy(point_feature)
                new_point_feature['geometry']['coordinates'] = [this_point_coord]
    return rst
    

def get_buffer(extent_polygon, dist=1500):
    return extent_polygon.buffer(dist)
    
def confine_poi(poi_source_path, mask_polygon, poi_save_folder, poi_save_name=None):
    print(f'\nProcessing {poi_source_path}...')
    if not os.path.exists(poi_save_folder):
        os.makedirs(poi_save_folder)
    if poi_save_name is None:
        poi_save_name = os.path.basename(poi_source_path)
        
    if type(mask_polygon) != Polygon:
        mask_polygon = get_first_polygon_from_geojson(mask_polygon)
        
    pois_full_data = json.load(open(poi_source_path, 'r', encoding='utf-8'))
    pois = pois_full_data['features']
    
    keep_pois = []
    for poi in pois:
        this_point = Point(poi['geometry']['coordinates'])
        if mask_polygon.contains(this_point):
            keep_pois.append(copy.deepcopy(poi))
    if pois_full_data['name'] != poi_save_name:
        pois_full_data['name'] = poi_save_name
    pois_full_data['features'] = keep_pois
    
    if len(keep_pois) == 0:
        print(f'Do not save confined {poi_source_path} because of zero records after confining')
        return pois_full_data
    
    save_path_full = os.path.join(poi_save_folder, poi_save_name)
    json.dump(pois_full_data, open(save_path_full, 'w'), indent=4)
    print(f'Confined POIs have been saved to {os.path.abspath(save_path_full)}')
    return pois_full_data
    
    
def main():
    poi_source_folder = '../tmp/emap_poi_epsg4547'
    confined_poi_save_folder = '../tmp/emap_poi_epsg4547_confined'
    extent_polygon_path_4547 = '../data/jw_grid/grid_2_oriented_extent.geojson'
    dist = 500
    
    extent_polygon = get_first_polygon_from_geojson(
        convert_coords_from_crs_to_crs(extent_polygon_path_4547, 4547, 4326)
    )
    buffer_polygon = get_buffer(extent_polygon, dist)
    poi_fnames = [f for f in os.listdir(poi_source_folder) if f.startswith('poi')]
    for poi_fname in poi_fnames:
        confine_poi(os.path.join(poi_source_folder, poi_fname), buffer_polygon, confined_poi_save_folder)



if __name__ == '__main__':
    main()