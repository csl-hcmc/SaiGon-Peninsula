import os, sys, json, pickle, copy, random
from functools import reduce
random.seed(2021)

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
    
        
def faking_data(fake_data_source_path, fake_data_save_path, ref_info, save_feature_type=None):
    source_full = json.load(open(fake_data_source_path, 'r', encoding='utf-8'))
    save_full = copy.deepcopy(source_full)
    for attr in ref_info['header']:
        save_full[attr] = ref_info['header'][attr]
    for idx, feature in enumerate(save_full['features']):
        if save_feature_type is not None:
            if save_feature_type == 'MultiPolygon' and feature['geometry']['type'] == 'Polygon':
                feature['geometry']['type'] = 'MultiPolygon'
                feature['geometry']['coordinates'] = [feature['geometry']['coordinates']]
            if save_feature_type == 'MultiLineString' and feature['geometry']['type'] == 'LineString':
                feature['geometry']['type'] = 'MultiLineString'
                feature['geometry']['coordinates'] = [feature['geometry']['coordinates']]
        feature['properties'] = {}
        for attr in ref_info['attr_dict']:
            random_rst = random.choice(ref_info['attr_dict'][attr]['values'])
            if ref_info['attr_dict'][attr]['id']:
                if type(random_rst) == str:
                    feature['properties'][attr] = random_rst + str(idx).zfill(4)
                elif type(random_rst) in [int, float]:
                    feature['properties'][attr] = random_rst*10000 + idx
            else:
                feature['properties'][attr] = random_rst
    safe_save(save_full, fake_data_save_path)
    print('\nFake data has been saved to: \n{}\n'.format(os.path.abspath(fake_data_save_path)))
    
    
def main_road_center_line():
    ref_info_path = '../data/for_fake_data/road_center_line_ref_info.json'
    real_data_path = '../tmp/emap_poi_wgs84_RA_biased_censored/emap_roads_center_line_RA.geojson'
    fake_data_source_path = '../tmp/fake_data_source/road_center_line.geojson'
    fake_data_save_path = '../tmp/fake_data_output/physical_data/emap_roads_center_line_RA.geojson'
    
    should_have = ['road_id', 'road_len', 'width']
    id_attrs = ['road_id']
    save_feature_type = 'MultiLineString'
    
    if not os.path.exists(os.path.abspath(ref_info_path)):
        ref_info = parse_obj_data(real_data_path, ref_info_path, should_have, id_attrs)
    else:
        ref_info = json.load(open(os.path.abspath(ref_info_path), 'r', encoding='utf-8'))
    faking_data(fake_data_source_path, fake_data_save_path, ref_info, save_feature_type)
    
    
def main_road_boundary_line():
    ref_info_path = '../data/for_fake_data/roads_boundary_line_ref_info.json'
    real_data_path = '../tmp/emap_poi_wgs84_RA_biased_censored/emap_roads_boundary_line_RA.geojson'
    fake_data_source_path = '../tmp/fake_data_source/road_boudary_line.geojson'
    fake_data_save_path = '../tmp/fake_data_output/physical_data/emap_roads_boundary_line_RA.geojson'
    
    should_have = ['road_id', 'road_len', 'width']
    id_attrs = ['road_id']
    save_feature_type = 'MultiLineString'
    
    if not os.path.exists(os.path.abspath(ref_info_path)):
        ref_info = parse_obj_data(real_data_path, ref_info_path, should_have, id_attrs)
    else:
        ref_info = json.load(open(os.path.abspath(ref_info_path), 'r', encoding='utf-8'))
    faking_data(fake_data_source_path, fake_data_save_path, ref_info, save_feature_type)
 
def main_bus_lines():
    ref_info_path = '../data/for_fake_data/bus_line_ref_info.json'
    real_data_path = '../tmp/emap_poi_wgs84_RA_biased_censored/emap_bus_lines_RA.geojson'
    fake_data_source_path = '../tmp/fake_data_source/bus_lines.geojson'
    fake_data_save_path = '../tmp/fake_data_output/physical_data/emap_bus_lines_RA.geojson'
    
    should_have = ['LINE_ID', 'START_TIME', 'END_TIME', 'BIDIRECTION', 'STATION_NUM', 
        'FRONT_ID', 'TERMINAL_ID', 'PAIRLINEID']
    id_attrs = ['LINE_ID']
    save_feature_type = 'MultiLineString'
    
    if not os.path.exists(os.path.abspath(ref_info_path)):
        ref_info = parse_obj_data(real_data_path, ref_info_path, should_have, id_attrs)
    else:
        ref_info = json.load(open(os.path.abspath(ref_info_path), 'r', encoding='utf-8'))
    faking_data(fake_data_source_path, fake_data_save_path, ref_info, save_feature_type)

def main_bus_stops():
    ref_info_path = '../data/for_fake_data/bus_stop_ref_info.json'
    real_data_path = '../tmp/emap_poi_wgs84_RA_biased_censored/emap_bus_stops_RA.geojson'
    fake_data_source_path = '../tmp/fake_data_source/bus_stops.geojson'
    fake_data_save_path = '../tmp/fake_data_output/physical_data/emap_bus_stops_RA.geojson'
    
    should_have = ['STOP_ID', 'LINE_ID', 'SEQID']
    id_attrs = []
    save_feature_type = 'Point'
    
    if not os.path.exists(os.path.abspath(ref_info_path)):
        ref_info = parse_obj_data(real_data_path, ref_info_path, should_have, id_attrs)
    else:
        ref_info = json.load(open(os.path.abspath(ref_info_path), 'r', encoding='utf-8'))
    faking_data(fake_data_source_path, fake_data_save_path, ref_info, save_feature_type)
    

def main_subway_lines():
    ref_info_path = '../data/for_fake_data/subway_line_ref_info.json'
    real_data_path = '../tmp/emap_poi_wgs84_RA_biased_censored/emap_subway_lines_RA.geojson'
    fake_data_source_path = '../tmp/fake_data_source/subway_lines.geojson'
    fake_data_save_path = '../tmp/fake_data_output/physical_data/emap_subway_lines_RA.geojson'
    
    should_have = ['SUBWAY_ID']
    id_attrs = ['SUBWAY_ID']
    save_feature_type = 'MultiLineString'
    
    if not os.path.exists(os.path.abspath(ref_info_path)):
        ref_info = parse_obj_data(real_data_path, ref_info_path, should_have, id_attrs)
    else:
        ref_info = json.load(open(os.path.abspath(ref_info_path), 'r', encoding='utf-8'))
    faking_data(fake_data_source_path, fake_data_save_path, ref_info, save_feature_type)
    

def main_subway_exits():
    ref_info_path = '../data/for_fake_data/subway_exit_ref_info.json'
    real_data_path = '../tmp/emap_poi_wgs84_RA_biased_censored/emap_subway_exits_RA.geojson'
    fake_data_source_path = '../tmp/fake_data_source/subway_exits.geojson'
    fake_data_save_path = '../tmp/fake_data_output/physical_data/emap_subway_exits_RA.geojson'
    
    should_have = ['SUBWAYEXIT_ID']
    id_attrs = ['SUBWAYEXIT_ID']
    save_feature_type = 'Point'
    
    if not os.path.exists(os.path.abspath(ref_info_path)):
        ref_info = parse_obj_data(real_data_path, ref_info_path, should_have, id_attrs)
    else:
        ref_info = json.load(open(os.path.abspath(ref_info_path), 'r', encoding='utf-8'))
    faking_data(fake_data_source_path, fake_data_save_path, ref_info, save_feature_type)
    

def main_parks():
    ref_info_path = '../data/for_fake_data/park_ref_info.json'
    real_data_path = '../tmp/emap_poi_wgs84_RA_biased_censored/emap_parks_RA.geojson'
    fake_data_source_path = '../tmp/fake_data_source/parks.geojson'
    fake_data_save_path = '../tmp/fake_data_output/physical_data/emap_parks_RA.geojson'
    
    should_have = ['ID', 'AREA']
    id_attrs = ['ID']
    save_feature_type = 'MultiPolygon'
    
    if not os.path.exists(os.path.abspath(ref_info_path)):
        ref_info = parse_obj_data(real_data_path, ref_info_path, should_have, id_attrs)
    else:
        ref_info = json.load(open(os.path.abspath(ref_info_path), 'r', encoding='utf-8'))
    faking_data(fake_data_source_path, fake_data_save_path, ref_info, save_feature_type)
    

def main_rivers():
    ref_info_path = '../data/for_fake_data/river_ref_info.json'
    real_data_path = '../tmp/emap_poi_wgs84_RA_biased_censored/emap_rivers_RA.geojson'
    fake_data_source_path = '../tmp/fake_data_source/rivers.geojson'
    fake_data_save_path = '../tmp/fake_data_output/physical_data/emap_rivers_RA.geojson'
    
    should_have = ['ID', 'AREA', 'LENGTH']
    id_attrs = ['ID']
    save_feature_type = 'MultiLineString'
    
    if not os.path.exists(os.path.abspath(ref_info_path)):
        ref_info = parse_obj_data(real_data_path, ref_info_path, should_have, id_attrs)
    else:
        ref_info = json.load(open(os.path.abspath(ref_info_path), 'r', encoding='utf-8'))
    faking_data(fake_data_source_path, fake_data_save_path, ref_info, save_feature_type)
 
if __name__ == '__main__':
    # main_road_center_line()
    # main_road_boundary_line()
    # main_bus_lines()
    # main_bus_stops()
    # main_subway_exits()
    # main_subway_lines()
    main_parks()
    main_rivers()
    