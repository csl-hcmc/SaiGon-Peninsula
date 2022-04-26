import os, json, time
import numpy as np


# constants
kpi_folder = '../tmp/kpi_epsg4547_confined'
poi_folder = '../tmp/emap_poi_epsg4547_confined'
landuse_fpath = '../tmp/physical_data_epsg4547_jw_grid_extent/current_landuse.geojson'
buildings_fpath = '../tmp/physical_data_epsg4547_jw_grid_extent/buildings.geojson'


def calc_diversity(population_list, log_base='e'):
    population_list = np.asarray(population_list)
    sum_pop = population_list.sum()
    ratio = population_list / sum_pop
    ratio = np.clip(ratio, 1e-20, 1)
    richness = len(population_list)
    avg_pop = sum_pop / richness
    even_prop = 1 / richness
    if log_base == 'e':
        log_ratio = np.log(ratio)
        log_even_prop = np.log(even_prop)
    elif log_base == 10:
        log_ratio = np.log10(ratio)
        log_even_prop = np.log10(even_prop)
    elif log_base == 2:
        log_ratio = np.log2(ratio)
        log_even_prop = np.log2(even_prop)
    else:
        raise TypeError('log_base must be one of "e", 2, and 10')
    raw_shannon = -np.sum(log_ratio * ratio)
    min_possible_shannon = 0
    max_possible_shannon = - even_prop * log_even_prop * len(population_list)
    if max_possible_shannon != min_possible_shannon:
        evenness =  (raw_shannon - min_possible_shannon) / (max_possible_shannon - min_possible_shannon)
    else:
        evenness = 0
    # evenness = raw_shannon / np.log(richness)
    rst = {
        'shannon_diversity_index': raw_shannon,
        'evenness': evenness,
        'richness': richness,
        'total_population': sum_pop,
        'average_population': avg_pop
    }
    return rst


def calc_diversity_poi_kpi(points_type, points_names='all', log_base='e', print_flag=True):
    t0 = time.time()
    if points_type.upper() == 'POI':
        folder = poi_folder
    elif points_type.upper() == 'KPI':
        folder = kpi_folder
    if points_names == 'all':
        points_fpaths = [os.path.join(folder, fname) for fname in os.listdir(folder)]
    else:
        if points_type.upper() == 'POI':
            points_fpaths = [os.path.join(folder, 'poi_' + fname + '.geojson') for fname in points_names]
        elif points_type.upper() == 'KPI':
            points_fpaths = [os.path.join(folder, 'kpi_' + fname + '.geojson') for fname in points_names]
    population_dict = {os.path.basename(fpath).split('.')[0][4:]:
                           len(json.load(open(fpath, 'r', encoding='utf-8'))['features'])
                       for fpath in points_fpaths}
    population_list = list(population_dict.values())
    rst = calc_diversity(population_list, log_base)
    t1 = time.time()
    if print_flag:
        print(f'\n\nDiversity of {points_type.upper()}:\n' + '=='*30)
        print('Shannon diversity index: {:4.3f}'.format(rst['shannon_diversity_index']))
        print('Evenness: {:4.3f}'.format(rst['evenness']))
        print('Calculation time: {:4.3f} seconds'.format(t1-t0))
        print('Formation: ')
        for k,v in population_dict.items():
            print('  {}: {:4.0f}'.format(k,v))
    return rst


def calc_diversity_lu_bldg(obj_type, attr='usage', value_list='all', log_base='e', weight='auto', print_flag=True):
    t0 = time.time()
    if obj_type in ['lu', 'landuse']:
        geojson = json.load(open(landuse_fpath, 'r', encoding='utf-8'))
        column = 'DETAIL_LU_NAME' if attr == 'usage' else attr
        obj_type = 'Land-use'
    elif obj_type in ['buildings', 'bldg', 'bu']:
        geojson = json.load(open(buildings_fpath, 'r', encoding='utf-8'))
        column = 'BLDG_USAGE' if attr == 'usage' else attr
        obj_type = 'Buildings'
    all_features = geojson['features']
    all_values = [f['properties'][column] for f in all_features]
    if type(value_list) == str and value_list == 'all':
        value_list = np.unique(all_values)
    elif type(value_list) == list:
        for value in value_list:
            if type(value) == list:
                assert all([v in all_values for v in value])
            else:
                assert value in all_values
    else:
        raise TypeError('usage_list must be a list, or "all"')
    population_dict = {}
    for value in value_list:
        if type(value) == list:
            features_this_value = [f for f in all_features if f['properties'][column] in value]
        else:
            features_this_value = [f for f in all_features if f['properties'][column] == value]
        assert len(features_this_value) > 0
        if weight is None:
            weight_column = None
            population_dict[value] = len(features_this_value)
        else:
            if weight == 'auto':
                if obj_type == 'Land-use':
                    weight_column = 'AREA'
                elif obj_type == 'Buildings':
                    weight_column = 'FLOOR_AREA'
            else:
                weight_column = weight
            population_dict[value] = np.sum([f['properties'].get(weight_column, 0) for f in features_this_value])

    population_list = list(population_dict.values())
    rst = calc_diversity(population_list, log_base)
    t1 = time.time()
    if print_flag:
        print(f'\n\nDiversity of {obj_type} (weight_column = {weight_column}):\n' + '==' * 30)
        print('Shannon diversity index: {:4.3f}'.format(rst['shannon_diversity_index']))
        print('Evenness: {:4.3f}'.format(rst['evenness']))
        print('Calculation time: {:4.3f} seconds'.format(t1 - t0))
        print('Formation: ')
        for k,v in population_dict.items():
            print('  {}: {:4.0f}'.format(k,v))
    return rst


def calc_diversity_population():
    pass


def main():
    calc_diversity_poi_kpi('poi', 'all')
    calc_diversity_lu_bldg('lu')


if __name__ == '__main__':
    main()
