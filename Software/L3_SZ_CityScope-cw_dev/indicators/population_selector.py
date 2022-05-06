import os, time, json, sys
sys.path.append('../utils')
from general import NpEncoder

def do_select_population(source_pop_file, filter_dict, save_path=None):
    print(f'\nFor file: {source_pop_file}')
    full_data = json.load(open(source_pop_file, 'r', encoding='utf-8'))
    features = full_data['features']
    print(f'The number of features before filtering: {len(features)}')
    for attr, value in filter_dict.items():
        if type(value) == list:
            features = [f for f in features if f['properties'][attr] in value]
        else:
            features = [f for f in features if f['properties'][attr] == value]
    full_data['features'] = features
    print(f'The number of features after filtering: {len(features)}')
    if save_path is not None:
        json.dump(full_data, open(save_path, 'w', encoding='utf-8'),indent=4, cls=NpEncoder)
    return full_data

def batch_select_population(source_pop_folder, filter_dict, save_pop_folder):
    # todo: different conditions for different type of populations
    if not os.path.exists(save_pop_folder):
        os.makedirs(save_pop_folder)
    fnames = os.listdir(source_pop_folder)
    for fname in fnames:
        source_path = os.path.join(source_pop_folder, fname)
        save_path = os.path.join(save_pop_folder, fname)
        do_select_population(source_path, filter_dict, save_path=save_path)

def main():
    source_pop_folder = '../tmp/pop_data_wgs84_jw_grid_extent'
    save_pop_folder = '../tmp/pop_data_wgs84_jw_grid_extent_valid'
    filter_dict = {
        'ISLOGOUT': 0
    }
    batch_select_population(source_pop_folder, filter_dict, save_pop_folder)


if __name__ == '__main__':
    main()




