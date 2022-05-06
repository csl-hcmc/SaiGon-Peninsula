import os, sys, json, pickle, copy, random
import numpy as np
from functools import reduce
from shapely.geometry import Point, LineString, MultiLineString
from shapely.geometry.polygon import Polygon
from shapely.geometry.multipolygon import MultiPolygon
from pyproj import Transformer
random.seed(2021)
np.random.seed(2021)

def safe_save(content, json_path):
    this_dirname = os.path.dirname(os.path.abspath(json_path))
    if not os.path.exists(this_dirname):
        os.makedirs(this_dirname)
    json.dump(content, open(json_path, 'w', encoding='utf-8'), indent=4, ensure_ascii=False)

def get_reference_center_area(ref_polygon_data_path):
    d = json.load(open(ref_polygon_data_path, 'r', encoding='utf-8'))
    crs = d['crs']
    features = d['features']
    feature = np.random.choice(features)
    if feature['geometry']['type'] == 'MultiPolygon':
        poly = Polygon(feature['geometry']['coordinates'][0][0])
    elif feature['geometry']['type'] == 'Polygon':
        poly = Polygon(feature['geometry']['coordinates'][0])
    centroid = poly.centroid
    center = [centroid.x, centroid.y]
    area = poly.area
    ref_info = {'crs':crs, 'center':center, 'area':area}
    return ref_info
    
    
def get_converting_ref(ref_converting_source_path, ref_info):
    data = json.load(open(ref_converting_source_path, 'r', encoding='utf-8'))
    features = data['features']
    rand_feature = np.random.choice(features)
    if rand_feature['geometry']['type'] == 'MultiPolygon':
        poly = Polygon(rand_feature['geometry']['coordinates'][0][0])
    elif rand_feature['geometry']['type'] == 'Polygon':
        poly = Polygon(rand_feature['geometry']['coordinates'][0])
    area = poly.area
    scale = np.sqrt(ref_info['area'] / area)
    scaled_polygon_coords = [[coord[0]*scale, coord[1]*scale] for coord in list(poly.exterior.coords)]
    scaled_poly = Polygon(scaled_polygon_coords)
    centroid = scaled_poly.centroid
    center = [centroid.x, centroid.y]
    move = [
        ref_info['center'][0] - center[0],
        ref_info['center'][1] - center[1]
    ]
    
    ref_info['move'] = move
    ref_info['scale'] = scale
    return ref_info
    

def convert_coords_to_ref(source, ref_info, save_path=None):
    if type(source) == dict:
        data = source
    elif type(source) == str:
        data = json.load(open(source, 'r', encoding='utf-8'))
    else:
        print('Source error')
        exit()
    data['crs'] = ref_info['crs']
    features = data['features']
    for f in features:
        if f['geometry']['type'] == 'MultiPolygon':
            for polygon_level1 in f['geometry']['coordinates']:
                for polygon_level2 in polygon_level1:
                    for coord in polygon_level2:
                        coord[0] = coord[0]*ref_info['scale'] + ref_info['move'][0]
                        coord[1] = coord[1]*ref_info['scale'] + ref_info['move'][1]
        elif f['geometry']['type'] == 'Polygon':
            for polygon_level1 in f['geometry']['coordinates']:
                for coord in polygon_level1:
                    coord[0] = coord[0]*ref_info['scale'] + ref_info['move'][0]
                    coord[1] = coord[1]*ref_info['scale'] + ref_info['move'][1]
        elif f['geometry']['type'] == 'Point':
            coord = f['geometry']['coordinates']
            coord[0] = coord[0]*ref_info['scale'] + ref_info['move'][0]
            coord[1] = coord[1]*ref_info['scale'] + ref_info['move'][1]
        elif f['geometry']['type'] == 'MultiLineString':
            for line_level1 in f['geometry']['coordinates']:
                for coord in line_level1:
                    coord[0] = coord[0]*ref_info['scale'] + ref_info['move'][0]
                    coord[1] = coord[1]*ref_info['scale'] + ref_info['move'][1]
        elif f['geometry']['type'] == 'LineString':
            for coord in f['geometry']['coordinates']:
                coord[0] = coord[0]*ref_info['scale'] + ref_info['move'][0]
                coord[1] = coord[1]*ref_info['scale'] + ref_info['move'][1]
    data['features'] = features
    if save_path is not None:
        safe_save(data, save_path)
        print('Finished converting to certain ref, data saved to: {}'.format(os.path.abspath(save_path)))
    return data
    
def convert_coords_from_crs_to_crs(source, source_crs, save_crs, save_path=None, crs_header=None):
    transformer = Transformer.from_crs(source_crs, save_crs)
    if type(source) == dict:
        data = source
    elif type(source) == str:
        data = json.load(open(source, 'r', encoding='utf-8'))
    else:
        print('Source error')
        exit()
    if crs_header:
        data['crs'] = crs_header
    features = data['features']
    for f in features:
        if f['geometry']['type'] == 'MultiPolygon':
            for polygon_level1 in f['geometry']['coordinates']:
                for polygon_level2 in polygon_level1:
                    for coord in polygon_level2:
                        new_coord = transformer.transform(coord[1], coord[0])
                        coord[0], coord[1] = new_coord[1], new_coord[0]
        elif f['geometry']['type'] == 'Polygon':
            for polygon_level1 in f['geometry']['coordinates']:
                for coord in polygon_level1:
                    new_coord = transformer.transform(coord[1], coord[0])
                    coord[0], coord[1] = new_coord[1], new_coord[0]
        elif f['geometry']['type'] == 'Point':
            coord = f['geometry']['coordinates']
            new_coord = transformer.transform(coord[1], coord[0])
            coord[0], coord[1] = new_coord[1], new_coord[0]
        elif f['geometry']['type'] == 'MultiLineString':
            for line_level1 in f['geometry']['coordinates']:
                for coord in line_level1:
                    new_coord = transformer.transform(coord[1], coord[0])
                    coord[0], coord[1] = new_coord[1], new_coord[0]
        elif f['geometry']['type'] == 'LineString':
            for coord in f['geometry']['coordinates']:
                new_coord = transformer.transform(coord[1], coord[0])
                coord[0], coord[1] = new_coord[1], new_coord[0]
    data['features'] = features
    if save_path is not None:
        safe_save(data, save_path)
        print('Finished converting to expecting CRS, data saved to: {}'.format(os.path.abspath(save_path)))
    return data
    

def change_outer_path(outer_path, inner_path, another_outer_path):
    outer_path = os.path.abspath(outer_path)
    inner_path = os.path.abspath(inner_path)
    another_outer_path = os.path.abspath(another_outer_path)
    pure_inner_path_segments = []
    while outer_path != inner_path:
        inner_path, tail = os.path.split(inner_path)
        pure_inner_path_segments.append(tail)
    pure_inner_path_segments = pure_inner_path_segments[::-1]   
    rst = os.path.join(another_outer_path, os.path.join(*pure_inner_path_segments))
    return rst
    
    
def batch_converting(source_dir, save_dir, ref_info, source_crs, save_crs, crs_header=None):
    if not os.path.exists(os.path.abspath(source_dir)):
        print('Source dir error')
        exit()
    if not os.path.exists(os.path.abspath(save_dir)):
        os.makedirs(os.path.abspath(save_dir))
    for root, dirs, files in os.walk(source_dir):
        for this_dir in dirs:
            this_dir_target_full = os.path.join(os.path.abspath(save_dir), this_dir)
            if not os.path.exists(this_dir_target_full):
                os.makedirs(this_dir_target_full)
        for file in files:
            if file.endswith('geojson'):
                this_file_path_full = os.path.join(root, file)
                this_file_save_path_full = change_outer_path(source_dir, this_file_path_full, save_dir)
                data_to_ref = convert_coords_to_ref(source=this_file_path_full, ref_info=ref_info)
                data_to_expecting_crs = convert_coords_from_crs_to_crs(
                    source = data_to_ref, 
                    source_crs = source_crs, 
                    save_crs = save_crs, 
                    save_path = this_file_save_path_full, 
                    crs_header = crs_header
                )
        
  
def test():
    
    ref_polygon_data_path = r'D:\01 - L3\Shenzhen CityScope\data\forMIT\data_samples\1.3.1 - buildings.geojson'
    ref_converting_source_path = r'D:\01 - L3\Shenzhen CityScope\L3_SZ_CityScope\tmp\fake_data_output\buildings_RA.geojson'
    
    crs_header = {
        "type": "name",
        "properties": {
            "name": "urn:ogc:def:crs:OGC:1.3:CRS84"
        }
    }
    
    # get ref_into
    ref_info = get_reference_center_area(ref_polygon_data_path)
    ref_info = get_converting_ref(ref_converting_source_path, ref_info)
    for k, v in ref_info.items(): print(f'{k}: {v}')
    
    source_path = r'D:\01 - L3\Shenzhen CityScope\L3_SZ_CityScope\tmp\fake_data_output\buildings_RA.geojson'
    save_path = r'D:\01 - L3\Shenzhen CityScope\L3_SZ_CityScope\tmp\fake_data_output\buildings_RA10.geojson'
    save_path2 = r'D:\01 - L3\Shenzhen CityScope\L3_SZ_CityScope\tmp\fake_data_output\buildings_RA20.geojson'
    convert_coords_to_ref(source_path, ref_info, save_path)
    convert_coords_from_crs_to_crs(save_path, 4547, 4326, save_path2, crs_header)
 

def main():
    
    ref_polygon_data_path = r'D:\01 - L3\Shenzhen CityScope\data\forMIT\data_samples\1.3.1 - buildings.geojson'
    ref_converting_source_path = r'D:\01 - L3\Shenzhen CityScope\L3_SZ_CityScope\tmp\fake_data_output\buildings_RA.geojson'
    crs_header = {
        "type": "name",
        "properties": {
            "name": "urn:ogc:def:crs:OGC:1.3:CRS84"
        }
    }
    source_crs = 4547
    save_crs = 4326
    
    # get ref_into
    ref_info = get_reference_center_area(ref_polygon_data_path)
    ref_info = get_converting_ref(ref_converting_source_path, ref_info)
    for k, v in ref_info.items(): print(f'{k}: {v}')
    
    source_dir = r'D:\01 - L3\Shenzhen CityScope\L3_SZ_CityScope\tmp\fake_data_output'
    save_dir = r'D:\01 - L3\Shenzhen CityScope\L3_SZ_CityScope\tmp\fake_data_output_wgs84'
    batch_converting(source_dir, save_dir, ref_info, source_crs, save_crs, crs_header=crs_header)

 
if __name__ == '__main__':
    main()