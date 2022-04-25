import os, sys, json, pickle, copy, random
from functools import reduce
random.seed(2021)

def safe_save(content, json_path):
    this_dirname = os.path.dirname(os.path.abspath(json_path))
    if not os.path.exists(this_dirname):
        os.makedirs(this_dirname)
    json.dump(content, open(json_path, 'w', encoding='utf-8'), indent=4, ensure_ascii=False)
        

def parse_obj_data(obj_path, save_path, should_have, pairs=None):
    id_attrs = ['OBJECTID']
    real_buildings_full = json.load(open(obj_path, 'r', encoding='utf-8'))
    header = {k:real_buildings_full[k] for k in ['type', 'name', 'crs']}
    real_buildings = real_buildings_full['features']
    attr_dict = {}
    pair_attr_dict = {}
    for bu in real_buildings:
        this_properties = bu['properties']
        for p in this_properties:
            if p not in should_have:
                continue
            if p not in attr_dict:
                attr_dict[p] = {'values': [this_properties[p]]}
            elif this_properties[p] not in attr_dict[p]['values']:
                attr_dict[p]['values'].append(this_properties[p])
            if pairs is not None and p in pairs:
                if not p in pair_attr_dict:
                    pair_attr_dict[p] = [{x: this_properties[x] for x in pairs[p]}]
                else:
                    pair_attr_dict[p].append({x: this_properties[x] for x in pairs[p]})
    for attr in attr_dict:
        if attr in id_attrs:
            attr_dict[attr]['id'] = True
        else:
            attr_dict[attr]['id'] = False
    # keep order
    attr_dict = {k:attr_dict[k] for k in should_have}
    ref_info = {'header':header, 'attr_dict':attr_dict, 'pair_attr_dict':pair_attr_dict, 'pairs':pairs}
    safe_save(ref_info, save_path)
    print('\nBuilding reference info has been saved to: \n{}\n'.format(os.path.abspath(save_path)))
    return ref_info
    
        
def faking_landuse(fake_buildings_source_path, fake_buildings_save_path, ref_info, better_choice_map=None):
    source_full = json.load(open(fake_buildings_source_path, 'r', encoding='utf-8'))
    save_full = copy.deepcopy(source_full)
    attr_dict = ref_info['attr_dict']
    pair_attr_dict = ref_info['pair_attr_dict']
    pair_attrs_list = reduce(lambda a,b:a+b, list(ref_info['pairs'].values()))
    if better_choice_map is not None:
        better_choice_map_match_list_flatten = reduce(lambda a,b:a+b, list(better_choice_map['match_on'].values()))
    for attr in ref_info['header']:
        save_full[attr] = ref_info['header'][attr]
    for idx, feature in enumerate(save_full['features']):
        if feature['geometry']['type'] == 'Polygon':
            feature['geometry']['type'] = 'MultiPolygon'
            feature['geometry']['coordinates'] = [feature['geometry']['coordinates']]
        if better_choice_map is not None:
            from_key_value = feature['properties'][better_choice_map['from_key']]
            to_key = better_choice_map['to_key']
            if from_key_value in better_choice_map['match_on']:
                best_pair_key_value = random.choice(better_choice_map['match_on'][from_key_value]) 
            else:
                best_pair_key_value = random.choice(better_choice_map_match_list_flatten)
            pair_candidate = [x for x in pair_attr_dict[to_key] if x[to_key]==best_pair_key_value]
            paired_properties = random.choice(pair_candidate)
        else:
            paired_properties = {}
            for paired_key, paired_candidates in pair_attr_dict.items():
                this_paired_properties = random.choice(paired_candidates)
                paired_properties = dict(paired_properties, **this_paired_properties)
        feature['properties'] = {}
        for attr in paired_properties:
            feature['properties'][attr] = paired_properties[attr]
        for attr in attr_dict:
            if attr not in pair_attrs_list:
                random_rst = random.choice(ref_info['attr_dict'][attr]['values'])
            else:
                continue
            
            if ref_info['attr_dict'][attr]['id']:
                if type(random_rst) == str:
                    feature['properties'][attr] = random_rst + str(idx).zfill(4)
                elif type(random_rst) in [int, float]:
                    feature['properties'][attr] = random_rst*10000 + idx
            else:
                feature['properties'][attr] = random_rst
    safe_save(save_full, fake_buildings_save_path)
    print('\nFake landuse has been saved to: \n{}\n'.format(os.path.abspath(fake_buildings_save_path)))
    
    
def main_zoning():
    zoning_ref_info_path = '../data/for_fake_data/zoning_ref_info.json'
    real_zoning_path = '../tmp/physical_data_wgs84_RA_biased_censored/zoning_RA.geojson'
    should_have = ['OBJECTID', 'LU_CODE', 'LU_FUNCTION', 'ARRANGE', 'MAIN_LU_CODE', 
        'PLOT_AREA', 'FLOOR_AREA', 'GREEN_PERCENTAGE']
    pairs = {'MAIN_LU_CODE': ['LU_CODE', 'LU_FUNCTION', 'ARRANGE', 'MAIN_LU_CODE']}
    fake_zoning_source_path = '../tmp/fake_data_source/zoning.geojson'
    fake_zoning_save_path = '../tmp/fake_data_output/physical_data/zoning_RA.geojson'
    better_choice_map_from_fake_to_real = {'match_on': {
        'YD-C23': ['C', 'C1', 'GIC', 'GIC1', 'GIC2', 'GIC3', 'GIC4', 'GIC5'],
        'YD-C11': ['C', 'C1', 'GIC', 'GIC1', 'GIC2', 'GIC3', 'GIC4', 'GIC5'],
        'YD-S11': ['S2', 'S3'],
        'YD-E6': ['G', 'G1', 'G2'],
        'YD-S2': ['S2', 'S3'],
        'YD-R2': ['R','R2','R3'],
        'YD-C5': ['C', 'C1', 'GIC', 'GIC1', 'GIC2', 'GIC3', 'GIC4', 'GIC5'],
        'YD-E1': ['G', 'G1', 'G2'],
        'YD-C21': ['C', 'C1', 'GIC', 'GIC1', 'GIC2', 'GIC3', 'GIC4', 'GIC5'],
        'YD-C3': ['C', 'C1', 'GIC', 'GIC1', 'GIC2', 'GIC3', 'GIC4', 'GIC5'],
        'YD-T23': ['U1', 'U2'],
        'YD-G1': ['G', 'G1', 'G2'],
        'YD-S3': ['S2', 'S3'],
        'YD-U1': ['U1', 'U2'],
        'YD-R12': ['R','R2','R3'],
        'YD-U3': ['U1', 'U2'],
    }}
    better_choice_map_from_fake_to_real['from_key'] = 'Layer'
    better_choice_map_from_fake_to_real['to_key'] = 'MAIN_LU_CODE'
    
    
    if not os.path.exists(os.path.abspath(zoning_ref_info_path)):
        ref_info = parse_obj_data(real_zoning_path, zoning_ref_info_path, should_have, pairs)
    else:
        ref_info = json.load(open(os.path.abspath(zoning_ref_info_path), 'r', encoding='utf-8'))
    
    faking_landuse(fake_zoning_source_path, fake_zoning_save_path, ref_info, better_choice_map_from_fake_to_real)
    
def main_current_landuse():
    crt_lu_ref_info_path = '../data/for_fake_data/current_landuse_ref_info.json'
    real_crt_lu_path = '../tmp/physical_data_wgs84_RA_biased_censored/current_landuse_RA.geojson'
    should_have = ['OBJECTID', 'LU_NAME', 'DETAIL_LU_CODE', 'DETAIL_LU_NAME', 'AREA']
    pairs = {'DETAIL_LU_NAME': ['DETAIL_LU_CODE', 'LU_NAME', 'DETAIL_LU_NAME']}
    fake_crt_lu_source_path = '../tmp/fake_data_source/current_landuse.geojson'
    fake_crt_lu_save_path = '../tmp/fake_data_output/physical_data/current_landuse_RA.geojson'
    better_choice_map_from_fake_to_real = {'match_on': {
        'YD-T1': ['Railway', 'Street', 'Vacant Land'],
        'YD-R22': ['Residence'],
        'YD-C11': ['Commercial', 'Culture & Entertainment','Health Care & Charity', 'Hotel & Restaurant', 
            'Research & Education', 'Public Facility', 'Business & Financial', 'Organization', 
            'Other Business & Service', 'Publication'],
        'YD-E61': ['Green & Park', 'Vacant Land'],
        'YD-E1': ['Green & Park', 'Vacant Land'],
        'YD-R2': ['Residence'],
        'YD-C63': ['Commercial', 'Culture & Entertainment','Health Care & Charity', 'Hotel & Restaurant', 
            'Research & Education', 'Public Facility', 'Business & Financial', 'Organization', 
            'Other Business & Service', 'Publication'],
        'YD-M2': ['Research & Education', 'Public Facility', 'Organization', 'Business & Financial'],
        'YD-M1': ['Research & Education', 'Public Facility', 'Organization', 'Business & Financial'],
        'YD-C3': ['Commercial', 'Culture & Entertainment','Health Care & Charity', 'Hotel & Restaurant', 
            'Research & Education', 'Public Facility', 'Business & Financial', 'Organization', 
            'Other Business & Service', 'Publication'],
        'YD-E2': ['Green & Park', 'Vacant Land'],
        'YD-T23': ['Railway', 'Street', 'Vacant Land'],
        'YD-C51': ['Commercial', 'Culture & Entertainment','Health Care & Charity', 'Hotel & Restaurant', 
            'Research & Education', 'Public Facility', 'Business & Financial', 'Organization', 
            'Other Business & Service', 'Publication'],
        'YD-C22': ['Commercial', 'Culture & Entertainment','Health Care & Charity', 'Hotel & Restaurant', 
            'Research & Education', 'Public Facility', 'Business & Financial', 'Organization', 
            'Other Business & Service', 'Publication'],
        'YD-U1': ['Railway', 'Street', 'Vacant Land'],
        'YD-S22': ['Railway', 'Street', 'Vacant Land'],
    }}
    better_choice_map_from_fake_to_real['from_key'] = 'Layer'
    better_choice_map_from_fake_to_real['to_key'] = 'DETAIL_LU_NAME'
    
    
    if not os.path.exists(os.path.abspath(crt_lu_ref_info_path)):
        ref_info = parse_obj_data(real_crt_lu_path, crt_lu_ref_info_path, should_have, pairs)
    else:
        ref_info = json.load(open(os.path.abspath(crt_lu_ref_info_path), 'r', encoding='utf-8'))
    
    faking_landuse(fake_crt_lu_source_path, fake_crt_lu_save_path, ref_info, better_choice_map_from_fake_to_real)
    
    
    
if __name__ == '__main__':
    main_current_landuse()