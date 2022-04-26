import os, json, shutil

def ensure_io_env(source_folder, target_folder, clear=True):
    assert os.path.exists(os.path.abspath(source_folder))
    if clear and os.path.exists(os.path.abspath(target_folder)):
        shutil.rmtree(os.path.abspath(target_folder))
    if not os.path.exists(os.path.abspath(target_folder)):
        os.makedirs(os.path.abspath(target_folder))

def merge_single(source_folder, source_poi_list, target_folder, target_kpi_name):
    output_full = {}
    crs = None
    features = []
    hash_ids = []
    for poi in source_poi_list:
        this_fpath = os.path.join(source_folder, f'poi_{poi}.geojson')
        if not os.path.exists(this_fpath):
            print(f'Warning: can not find {poi} file')
            continue
        this_data = json.load(open(this_fpath, encoding='utf-8'))
        if crs is None:
            output_full.update({'type': this_data['type'], 'crs': this_data['crs'], 'name': 'kpi_'+target_kpi_name})
            crs = output_full['crs']            
        assert crs == this_data['crs']
        this_features = this_data['features']
        this_unique_features = [feature for feature in this_features if feature['properties']['id'] not in hash_ids]
        hash_ids += [feature['properties']['id'] for feature in this_unique_features]
        if len(this_features) != len(this_unique_features):
            print(f'\nWarning: duplicated pois detected and ignored: len(all) = {len(this_features)}, len(unique) = {len(this_unique_features)}\n')
        features += this_unique_features
    output_full['features'] = features
    kpi_save_path = os.path.abspath(os.path.join(target_folder, 'kpi_'+target_kpi_name+'.geojson'))
    json.dump(output_full, open(kpi_save_path, 'w', encoding='utf-8'), indent=4, ensure_ascii=False)
    print(f'\nKPI of {target_kpi_name} has written to the following path:\n{kpi_save_path}')
    return output_full
    
    
    
def merge_batch(source_folder, target_folder, kpi_poi_lookup):
    for target_kpi_name, source_poi_list in kpi_poi_lookup.items():
        merge_single(source_folder, source_poi_list, target_folder, target_kpi_name)

def main():

    source_folder = '../tmp/emap_poi_epsg4547_confined'
    target_folder = '../tmp/kpi_epsg4547_confined'
    kpi_poi_lookup = {
        'EDUCATION': [
            'adult_education',
            'kindergardens',
            'middle_schools',
            'primary_schools',
            'professional_schools',
            'research_and_educational_pois',
            'research_associations',
            'research_basements',
            'special_schools',
            'universities'
        ],
        'RECREATIONAL': [
            'amusement parks',
            'cinemas_and_theaters',
            'concert_halls',
            'entertainment_centers'
        ],
        'CULTURE': [
            'art_centers',
            'art_gallaries',
            'conference_centers',
            'cultural_activity_centers',
            'cultural_squares',
            'exhibition_centers',
            'foreign_organizations',
            'libraries',
            'museums',
            'science_and_technology_museums'
        ],
        'SPORTS': [
            'cultural_and_sport_facilities',
            'fitness_centers',
            'golf_parks',
            'gyms_and_stadiums',
            'leisure_sport_facilities',
            'trainning_centers'
        ],
        'AMENITIES': [
            'bookstores',
            'covenince_stores',
            'daily_services',
            'leisure_centers',
            'markets',
            'netbars',
            'organizations',
            'post_and_telecom',
            'public_services',
            'religious_facilites',
            'restaurants',
            'shopping'
        ],
        'NATURE': [
            'parks',
            'reservoir',
            'rivers'
        ],
        'TRNASPORTATION': [
            'bus_stops',
            'parking_lots'
        ],
        'HEALTH-CARE': [
            'community_health_care_centers',
            'comprehensive_hospitials',
            'elderly_care_insititutes',
            'health_care_facilities',
            'independent_clinics',
            'pharmacies',
            'rehabilitation_centers',
            'specialized_hospitals',
            'traditional_Chinese_hospitals'
        ],
        'FINANCE': [
            'banks',
            'finance_institutes'
        ],
        'RESIDENTIAL': [
            'rural_residential_points',
            'urban_residential_points'
        ]
    }
    
    ensure_io_env(source_folder, target_folder)
    merge_batch(source_folder, target_folder, kpi_poi_lookup)
    
    
if __name__ == '__main__':
    main()