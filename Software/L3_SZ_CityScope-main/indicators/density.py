import json, time, os
from shapely.geometry.polygon import Polygon
from shapely.geometry import Point
import numpy as np


# constant
kpi_folder = '../tmp/kpi_epsg4547_confined'
poi_folder = '../tmp/emap_poi_epsg4547_confined'
landuse_fpath = '../tmp/physical_data_epsg4547_jw_grid_extent/current_landuse.geojson'
buildings_fpath = '../tmp/physical_data_epsg4547_jw_grid_extent/buildings.geojson'
population_mainland_fpath = '../tmp/pop_data_wgs84_jw_grid_extent_valid/resident_mainland.geojson'
population_foreign_fpath = '../tmp/pop_data_wgs84_jw_grid_extent_valid/resident_foreign.geojson'
population_hmt_fpath = '../tmp/pop_data_wgs84_jw_grid_extent_valid/resident_hmt.geojson'

crt_landuse_lookup = {
    'administration': ['Organization', 'Public Facility'],
    # 'commercial': ['Business & Financial', 'Commercial', 'Other Business & Service', 'Hotel & Restaurant'],
    'commercial': ['Commercial'],
    'cultural_entertainment': ['Culture & Entertainment'],
    'sport': ['Culture & Entertainment'],
    'health_care': ['Health Care & Charity'],
    'educational': ['Research & Education'],
    'park': ['Green & Park'],
    'residential': ['Residence', 'Rural Homestead']
}

kpi_within_lookup = { # must contain these kpi
    'sport': ['SPORTS'],
    'cultural_entertainment': ['CULTURE', 'RECREATIONAL']
}

kpi_without_lookup = { # must not contain these kpi
    # 'cultural_entertainment': ['SPORTS']
}

# source:
# http://www.fqghj.net/upload/2020/8/18/45fb7cea-f9cb-4373-9864-da03229037d7/225292ab-16af-4e5f-95f2-a5ef483c27a7.pdf
# http://www.planning.org.cn/law/uploads/2013/1383993139.pdf
min_threshold_lookup = {
    'administration': 0.8,
    'commercial': 3.2,
    'cultural_entertainment': 0.8,
    'sport': 0.5,
    'health_care': 0.9,
    'educational': 3.6,
    'park': 8,
    'residential': 23
}

max_threshold_lookup = {
    'administration': 1.1,
    'commercial': 4.0,
    'cultural_entertainment': 1.0,
    'sport': 0.8,
    'health_care': 1.1,
    'educational': 4.8,
    'park': np.inf,
    'residential': 36
}


def get_buildings_in_land(buildings, land, min_intersect_area_ratio=0.5, return_type='area'):
    land_poly = Polygon(land['geometry']['coordinates'][0][0])
    bu_poly_List = [Polygon(bu['geometry']['coordinates'][0][0]) for bu in buildings]
    intersect_area_info = [
        (land_poly.intersection(bu_poly).area, bu_poly.area)
        for bu_poly in bu_poly_List
    ]
    keep_idx = [
        bu_idx
        for bu_idx, info in enumerate(intersect_area_info)
        if (info[0] / info[1]) >= min_intersect_area_ratio
    ]
    if return_type == 'area':
        return [
            info[0]
            for bu_idx, info in enumerate(intersect_area_info)
            if bu_idx in keep_idx
        ]

def get_points_in_land(point_features, land_feature):
    land_poly = Polygon(land_feature['geometry']['coordinates'][0][0])
    points_list = [Point(point['geometry']['coordinates']) for point in point_features]
    return [point for point in points_list if land_poly.contains(point)]



def calc_density(total_population, item_list='all', only_buildings=False, print_flag=True):
    all_lands = json.load(open(landuse_fpath, 'r', encoding='utf-8'))['features']
    all_buildings = json.load(open(buildings_fpath, 'r', encoding='utf-8'))['features']

    # attr 'AREA' might not accurate since polygon has been clipped by extend of research area
    for land in all_lands:
        if 'real_area' not in land['properties']:
            land['properties']['real_area'] = Polygon(land['geometry']['coordinates'][0][0]).area

    if item_list == 'all':
        item_list = list(min_threshold_lookup.keys())
    for item in item_list:
        t0 = time.time()
        this_min_th, this_max_th = min_threshold_lookup[item], max_threshold_lookup[item]
        this_crt_landuse = crt_landuse_lookup[item]
        this_kpi_within = kpi_within_lookup.get(item, [])
        this_kpi_without = kpi_without_lookup.get(item,[])
        this_lands = [land for land in all_lands if land['properties']['DETAIL_LU_NAME'] in this_crt_landuse]
        if len(this_kpi_within) > 0:
            within_kpi_features = []
            for kpi_name in this_kpi_within:
                within_kpi_features += json.load(open(
                    os.path.join(kpi_folder, f'kpi_{kpi_name}.geojson'),
                    'r', encoding='utf-8'
                ))['features']
            this_lands = [
                land for land in this_lands
                if len(get_points_in_land(within_kpi_features, land)) > 0
            ]
        if len(this_kpi_without) > 0:
            without_kpi_features = []
            for kpi_name in this_kpi_without:
                without_kpi_features += json.load(open(
                    os.path.join(kpi_folder, f'kpi_{kpi_name}.geojson'),
                    'r', encoding='utf-8'
                ))['features']
            this_lands = [
                land for land in this_lands
                if len(get_points_in_land(without_kpi_features, land)) == 0
            ]

        if not only_buildings:
            tt_area = sum([land['properties']['real_area'] for land in this_lands])
        else:
            tt_area = 0
            for land in this_lands:
                tt_area += sum(get_buildings_in_land(all_buildings, land, return_type='area'))
        area_per_person = tt_area / total_population
        t1 = time.time()
        if print_flag:
            tmp = '(only area of buildings on these lands will be counted)' if only_buildings else '(all land area will be counted)'
            print(f'\nDensity of {item}:\n{tmp}\n' + '=='*30)
            print('Required = {:2.1f} - {:2.1f} m2, current = {:4.3f} m2'.format(
                this_min_th, this_max_th, area_per_person
            ))
            print('Calculation time: {:4.3f} seconds'.format(t1-t0))


def main():
    total_population = 0
    for fpath in [population_mainland_fpath, population_foreign_fpath, population_hmt_fpath]:
        total_population += len(json.load(open(fpath, 'r', encoding='utf-8'))['features'])
    print(f'Total population = {total_population}')
    calc_density(total_population, 'all', only_buildings=True)



if __name__ == '__main__':
    main()