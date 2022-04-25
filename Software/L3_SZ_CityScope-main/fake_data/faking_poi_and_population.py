import os, sys, json, pickle, copy, random
import numpy as np
from functools import reduce
from shapely.geometry import Point, LineString, MultiLineString
from shapely.geometry.polygon import Polygon
from shapely.geometry.multipolygon import MultiPolygon
random.seed(2021)
np.random.seed(2021)

def safe_save(content, json_path):
    this_dirname = os.path.dirname(os.path.abspath(json_path))
    if not os.path.exists(this_dirname):
        os.makedirs(this_dirname)
    json.dump(content, open(json_path, 'w', encoding='utf-8'), indent=4, ensure_ascii=False)
    
def parse_obj_data(obj_path, save_path, should_have, id_attrs=[]):
    real_project_full = json.load(open(obj_path, 'r', encoding='utf-8'))
    header = {k:real_project_full[k] for k in ['type', 'name', 'crs']}
    real_projects = real_project_full['features']
    attr_dict = {}
    for proj in real_projects:
        this_properties = proj['properties']
        for p in this_properties:
            if p not in should_have:
                continue
            if p not in attr_dict:
                attr_dict[p] = {'values': [this_properties[p]]}
            elif this_properties[p] not in attr_dict[p]['values']:
                attr_dict[p]['values'].append(this_properties[p])
    for attr in attr_dict:
        if attr in id_attrs:
            attr_dict[attr]['id'] = True
        else:
            attr_dict[attr]['id'] = False
    # keep order
    attr_dict = {k:attr_dict[k] for k in should_have}
    ref_info = {'header':header, 'attr_dict':attr_dict}
    safe_save(ref_info, save_path)
    print('\Reference info has been saved to: \n{}\n'.format(os.path.abspath(save_path)))
    return ref_info

def genenrate_points(polygon, num=1, return_type='coords'):
    xmin, ymin, xmax, ymax = polygon.bounds
    points = []
    while len(points) <= num:
        xs = np.random.uniform(xmin, xmax, num)
        ys = np.random.uniform(ymin, ymax, num)
        points_candidates = [Point(x,y) for x,y in zip(xs, ys)]
        points_ok_this_round = [p for p in points_candidates if polygon.contains(p)]
        points += points_ok_this_round
    if len(points) > num:
        chosen_idx = np.random.choice(range(len(points)), num, replace=False)
        points = [points[idx] for idx in chosen_idx]
    if return_type == 'obj':
        return points
    elif return_type == 'coords':
        return [[p.x, p.y] for p in points]
        
def match(landuse_feature, specified_landuse_property):
    for k, v in specified_landuse_property.items():
        if k not in landuse_feature['properties']:
            return False
        if type(v) != list:
            v = list(v)
        if landuse_feature['properties'][k] not in v:
            return False
    return True


def faking_point_coords(landuse_features, specified_landuse_property, num, step_flag=True):
    lu_candidates = [lu for lu in landuse_features if match(lu, specified_landuse_property)]
    steps = min(num, int(len(lu_candidates) * 1.5))
    num_per_step = num // steps
    all_points = [] 
    if step_flag:
        for step in range(steps):
            this_step_lu = np.random.choice(lu_candidates)
            if this_step_lu['geometry']['type'] == 'Polygon':
                lu_polygon = Polygon(this_step_lu['geometry']['coordinates'][0])
            elif this_step_lu['geometry']['type'] == 'MultiPolygon':
                lu_polygon = Polygon(this_step_lu['geometry']['coordinates'][0][0])
            this_step_points = genenrate_points(lu_polygon, num_per_step)
            all_points += this_step_points
        if len(all_points) < num:
            this_step_points = genenrate_points(lu_polygon, num-len(all_points))
            all_points += this_step_points
    else:
        for i in range(num):
            this_step_lu = np.random.choice(lu_candidates)
            if this_step_lu['geometry']['type'] == 'Polygon':
                lu_polygon = Polygon(this_step_lu['geometry']['coordinates'][0])
            elif this_step_lu['geometry']['type'] == 'MultiPolygon':
                lu_polygon = Polygon(this_step_lu['geometry']['coordinates'][0][0])
            this_step_points = genenrate_points(lu_polygon, 1)
            all_points += this_step_points
    features = [
        {
            "type": "Feature",
            "properties": {},
            "geometry": {
                "type": "Point",
                "coordinates": p_coords
            }
        }
        for p_coords in all_points
    ]
    return features
    
def faking_pois(name, landuse_features, specified_landuse_property, num, fake_data_save_path):
    data = {
        "type": "FeatureCollection",
        "name": name,
        "crs": {
            "type": "name",
            "properties": {
                "name": "urn:ogc:def:crs:OGC:1.3:CRS84"
            }
        },
        "features": []
    }
    if num < 30:
        step_flag = False
    else:
        step_flag = True
    features = faking_point_coords(landuse_features, specified_landuse_property, num, step_flag=step_flag)
    for idx, f in enumerate(features):
        f['properties']['OBJECTID'] = idx+1
    data['features'] = features
    safe_save(data, fake_data_save_path)
    print('\nFake pois of {} has been saved to: \n{}\n'.format(name, os.path.abspath(fake_data_save_path)))
    
def faking_pop(landuse_features, fake_data_save_path, ref_info, num_pop, num_pop_per_point, name=None):
    pop_data = {}
    num_points = num_pop // num_pop_per_point
    point_features = faking_point_coords(
        landuse_features,
        {'MAIN_LU_CODE': ['R','R2','R3']},
        num_points, step_flag=True
    )
    pop_features = []
    for point_feature in point_features:
        for i in range(num_pop_per_point):
            pop_features.append(copy.deepcopy(point_feature))
            
    pop_data['features'] = pop_features
    for attr in ref_info['header']:
        pop_data[attr] = ref_info['header'][attr]
    if name:
        pop_data['name'] = name
    for idx, feature in enumerate(pop_data['features']):
        feature['properties'] = {}
        for attr in ref_info['attr_dict']:
            random_rst = random.choice(ref_info['attr_dict'][attr]['values'])
            if ref_info['attr_dict'][attr]['id']:
                if type(random_rst) == str:
                    feature['properties'][attr] = random_rst + str(idx).zfill(3)
                elif type(random_rst) in [int, float]:
                    feature['properties'][attr] = random_rst*1000 + idx
            else:
                feature['properties'][attr] = random_rst
    safe_save(pop_data, fake_data_save_path)
    print('\nFake data has been saved to: \n{}\n'.format(os.path.abspath(fake_data_save_path)))
              
            
def main_pois():
    landuse_path = '../tmp/fake_data_output/physical_data/zoning_RA.geojson'
    poi_specs = [
        {
            'name':'poi_covenince_stores_RA', 
            'num':15, 
            'lu': {'MAIN_LU_CODE': ['C', 'C1', 'GIC', 'GIC1', 'GIC2', 'GIC3', 'GIC4', 'GIC5']},
            'save': '../tmp/fake_data_output/physical_data/poi_covenince_stores_RA.geojson'
        },
        {
            'name':'poi_research_and_educational_pois_RA', 
            'num':8, 
            'lu': {'MAIN_LU_CODE': ['C', 'C1', 'GIC', 'GIC1', 'GIC2', 'GIC3', 'GIC4', 'GIC5']},
            'save': '../tmp/fake_data_output/physical_data/poi_research_and_educational_pois_RA.geojson'
        }
    ]
    
    landuse_features = json.load(open(landuse_path, 'r', encoding='utf-8'))['features']
    for poi in poi_specs:
        faking_pois(poi['name'], landuse_features, poi['lu'], poi['num'], poi['save'])
        
        
def main_pop_mainland():
    landuse_path = '../tmp/fake_data_output/physical_data/zoning_RA.geojson'
    ref_info_path = '../data/for_fake_data/pop_mainland_ref_info.json'
    real_data_path = '../tmp/pop_data_wgs84_RA_biased_censored_randomized/RESIDENT_RA.geojson'
    fake_data_save_path = '../tmp/fake_data_output/population/resident_mainland_RA.geojson'
    name = 'resident_mainland_RA'
    
    should_have = ['ID', 'BIRTHDAY', 'SEX', 'ISLOGOUT', 'HOUSEID', 'RACE', 'MARRIAGE', 
        'EDUCATION', 'OCCUPATION', 'LIVE_STYLE', 'LEASE_REASON', 'ACCOMMODATION_TYPE', 
        'QHAREAID', 'BL_BLDG_NO',
        'UP_BLDG_FLOOR', 'BLDG_HEIGH', 'BLDG_LAND_AREA', 'BLDG_FLOOR_AREA', 'BLDG_USAGE']
    id_attrs = ['ID']
    num_pop = 10000
    num_pop_per_point = 400
    
    if not os.path.exists(os.path.abspath(ref_info_path)):
        ref_info = parse_obj_data(real_data_path, ref_info_path, should_have, id_attrs)
    else:
        ref_info = json.load(open(os.path.abspath(ref_info_path), 'r', encoding='utf-8'))
    landuse_features = json.load(open(landuse_path, 'r', encoding='utf-8'))['features']
    faking_pop(landuse_features, fake_data_save_path, ref_info, num_pop, num_pop_per_point, name)
    
    
def main_pop_hmt():
    landuse_path = '../tmp/fake_data_output/physical_data/zoning_RA.geojson'
    ref_info_path = '../data/for_fake_data/pop_hmt_ref_info.json'
    real_data_path = '../tmp/pop_data_wgs84_RA_biased_censored_randomized/resident_hmt_RA.geojson'
    fake_data_save_path = '../tmp/fake_data_output/population/resident_hmt_RA.geojson'
    name = None
    
    should_have = ['ID', 'BIRTHDAY', 'SEX', 'ISLOGOUT', 'INTIME1', 'LEAVEDATE', 'HOUSEID', 'QHAREAID',
        'BL_BLDG_NO', 'DISTRICT', 'MARRIAGE', 'OCCUPATION', 'ACCOMMODATION_TYPE', 'LIVE_STYLE', 'LEASE_REASON',
        'UP_BLDG_FLOOR', 'BLDG_HEIGH', 'BLDG_LAND_AREA', 'BLDG_FLOOR_AREA', 'BLDG_USAGE']
    id_attrs = ['ID']
    num_pop = 1000
    num_pop_per_point = 50
    
    if not os.path.exists(os.path.abspath(ref_info_path)):
        ref_info = parse_obj_data(real_data_path, ref_info_path, should_have, id_attrs)
    else:
        ref_info = json.load(open(os.path.abspath(ref_info_path), 'r', encoding='utf-8'))
    landuse_features = json.load(open(landuse_path, 'r', encoding='utf-8'))['features']
    faking_pop(landuse_features, fake_data_save_path, ref_info, num_pop, num_pop_per_point, name)
    
    
def main_pop_foreign():
    landuse_path = '../tmp/fake_data_output/physical_data/zoning_RA.geojson'
    ref_info_path = '../data/for_fake_data/pop_foreign_ref_info.json'
    real_data_path = '../tmp/pop_data_wgs84_RA_biased_censored_randomized/resident_foreign_RA.geojson'
    fake_data_save_path = '../tmp/fake_data_output/population/resident_foreign_RA.geojson'
    name = None
    
    should_have = ['ID', 'SEX', 'NATIONALITY', 'ISLOGOUT', 'HOUSEID', 'QHAREAID', 'BL_BLDG_NO', 
        'UP_BLDG_FLOOR', 'BLDG_HEIGH', 'BLDG_LAND_AREA', 'BLDG_FLOOR_AREA', 'BLDG_USAGE']
    id_attrs = ['ID']
    num_pop = 1000
    num_pop_per_point = 50
    
    if not os.path.exists(os.path.abspath(ref_info_path)):
        ref_info = parse_obj_data(real_data_path, ref_info_path, should_have, id_attrs)
    else:
        ref_info = json.load(open(os.path.abspath(ref_info_path), 'r', encoding='utf-8'))
    landuse_features = json.load(open(landuse_path, 'r', encoding='utf-8'))['features']
    faking_pop(landuse_features, fake_data_save_path, ref_info, num_pop, num_pop_per_point, name)
    
    
if __name__ == '__main__':
    # main_pois()
    main_pop_mainland()
    main_pop_hmt()
    main_pop_foreign()