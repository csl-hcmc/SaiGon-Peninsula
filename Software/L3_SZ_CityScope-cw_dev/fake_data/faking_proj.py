import os, sys, json, pickle, copy, random
from functools import reduce
random.seed(2021)

def safe_save(content, json_path):
    this_dirname = os.path.dirname(os.path.abspath(json_path))
    if not os.path.exists(this_dirname):
        os.makedirs(this_dirname)
    json.dump(content, open(json_path, 'w', encoding='utf-8'), indent=4, ensure_ascii=False)
    
def parse_obj_data(obj_path, save_path):
    should_have = ['OBJECTID', 'PROJ_NAME', 'STATUS']
    id_attrs = ['OBJECTID']
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
    print('\Project reference info has been saved to: \n{}\n'.format(os.path.abspath(save_path)))
    return ref_info
    
        
def faking_projects(fake_projects_source_path, fake_projects_save_path, ref_info):
    source_full = json.load(open(fake_projects_source_path, 'r', encoding='utf-8'))
    save_full = copy.deepcopy(source_full)
    for attr in ref_info['header']:
        save_full[attr] = ref_info['header'][attr]
    for idx, feature in enumerate(save_full['features']):
        if feature['geometry']['type'] == 'Polygon':
            feature['geometry']['type'] = 'MultiPolygon'
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
    safe_save(save_full, fake_projects_save_path)
    print('\nFake projects has been saved to: \n{}\n'.format(os.path.abspath(fake_projects_save_path)))
    
    
def main():
    projects_ref_info_path = '../data/for_fake_data/projects_ref_info.json'
    real_projects_path = '../tmp/physical_data_wgs84_RA_biased_censored/projects_RA.geojson'
    fake_projects_source_path = '../tmp/fake_data_source/projects.geojson'
    fake_projects_save_path = '../tmp/fake_data_output/physical_data/projects_RA.geojson'
    
    if not os.path.exists(os.path.abspath(projects_ref_info_path)):
        ref_info = parse_obj_data(real_projects_path, projects_ref_info_path)
    else:
        ref_info = json.load(open(os.path.abspath(projects_ref_info_path), 'r', encoding='utf-8'))
    faking_projects(fake_projects_source_path, fake_projects_save_path, ref_info)
    
if __name__ == '__main__':
    main()