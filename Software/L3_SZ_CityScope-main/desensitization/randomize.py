import json, os, sys, copy
import numpy as np
import pandas as pd
from functools import reduce

def get_samples(source_file, save_file, sample_flag=True, sample_num='same', 
                shuffle_properties='all', seed=2021, name_append=None):
    """
    randomly sample {num} features from raw data,
    and randomly change the properties
    """
    if seed is not None:
        np.random.seed(seed)
    raw_data = json.load(open(source_file, 'r', encoding='utf-8'))
    data = copy.deepcopy(raw_data)
    features = data['features']
    data['features'] = []
    if name_append is not None:
        data['name'] = data['name'] + '_' + name_append
    if sample_flag:
        if type(sample_num)==str and sample_num == 'same':
            sample_num = len(features)
        assert type(sample_num) == int
    if shuffle_properties is None:
        shuffle_properties = []
    else:
        all_properties = reduce(lambda a,b:a+b, [list(f['properties'].keys()) for f in features], [])
        all_properties = list(set(all_properties))
        if type(shuffle_properties) == str and shuffle_properties=='all':
            shuffle_properties = all_properties
        assert type(shuffle_properties) == list
        shuffle_properties = [p for p in shuffle_properties if p in all_properties]
    # print('all_properties: ', all_properties)
    # sampling features
    if sample_flag:
        # notice: when a feature is sampled multiple times, they are
        # sharing the same memory, so it's problematic to directly use np.random.choice
        sampled_index = np.random.choice(range(len(features)), 
            size=sample_num, replace=True).tolist()
        sampled_features = [copy.deepcopy(features[this_idx]) 
            for this_idx in sampled_index]
        # sampled_features = np.random.choice(features, 
            # size=sample_num, replace=True).tolist()
    else:
        sampled_features = features
    
    # shuffle properties
    property_values = {p: [f['properties'].get(p, None) for f in sampled_features] 
        for p in shuffle_properties}
    for p in shuffle_properties:
        property_values[p] = np.random.permutation(property_values[p]).tolist()
    for f_idx, f in enumerate(sampled_features):
        for p in shuffle_properties:
            f['properties'][p] = property_values[p][f_idx]
     
    data['features'] = sampled_features
    if not os.path.exists(os.path.dirname(save_file)):
        os.makedirs(os.path.dirname(save_file))
    json.dump(data, open(save_file, 'w', encoding='utf-8'), indent=4, ensure_ascii=False)
    print('Ranomization finished, new file saved to: \n{}'.format(os.path.abspath(save_file)))
    return
  
    
def main():
    source_folder = '../tmp/pop_data_wgs84_RA_biased_censored'
    target_folder = '../tmp/pop_data_wgs84_RA_biased_censored_randomized'
    source_files = os.listdir(os.path.abspath(source_folder))
    for f in source_files:
        source_file = os.path.join(source_folder, f)
        save_file = os.path.join(target_folder, f)
        get_samples(source_file, save_file)
    
if __name__ == '__main__':
    main()
