import os, json, pymongo, sys, pickle
import pandas as pd
from pandas.core.frame import DataFrame
import numpy as np

sys.path.append('../desensitization')
from clip_by_space import clip_on_shapes

from utils.lj_house_utils import *

def safely_save(data, save_path, coding='utf-8'):
    dirname = os.path.abspath(os.path.dirname(save_path))
    if not os.path.exists(dirname):
        os.makedirs(dirname)
    ext_name = os.path.basename(save_path).split('.')[-1]
    if ext_name in ['json', 'geojson']:
        json.dump(data, open(save_path, 'w', encoding=coding), indent=4, ensure_ascii=False)
    elif ext_name == 'p':
        pickle.dump(data, open(save_path, 'wb'))
    elif ext_name == 'csv':
        if type(data) != DataFrame:
            data = pd.DataFrame(data)
        data.to_csv(save_path, encoding=coding, index=False)
    else:
        print('Error: unknow save file type: {}'.format(ext_name))
    
def retrieve_lj_house_price_data_single(db, col_name, save_path=None):
    col = db[col_name]
    records = list(col.find({}))
    if save_path:
        safely_save(records, save_path)
    return records  # list

def retrieve_lj_house_price_data_multiple(db, col_name_list, save_path=None, add_district=True):
    all_records = []
    for col_name in col_name_list:
        this_records = retrieve_lj_house_price_data_single(db, col_name, None)
        if add_district:
            this_district = col_name.split('house_detailed_second_hand_lianjia_')[-1]
            for r in this_records:
                r['district'] = this_district
        all_records += this_records
    if save_path:
        safely_save(all_records, save_path)
    return all_records  # list

def clean_lj_house_price_data(data, save_path=None):
    if type(data) != DataFrame:
        df = pd.DataFrame(data)
    else:
        df = data
    df_cp = df.copy()
    df_cp['block_info_dict'] = df_cp.apply(lambda row: get_lj_house_block_info_dict(row), axis=1)
    keep_fields = ['url', 'coord_lng', 'coord_lat', 'district']
    df = df[keep_fields]
    df['district'] = df.apply(lambda row: row['district'][0].upper() + row['district'][1:], axis=1)
    df['total_price'] = df_cp.apply(lambda row: get_lj_house_totoal_price(row), axis=1)
    df['unit_price'] = df_cp.apply(lambda row: get_lj_house_unit_price(row), axis=1)
    df['layout'] = df_cp.apply(lambda row: get_lj_house_layout(row), axis=1)
    df['floor'] = df_cp.apply(lambda row: get_lj_house_floor(row), axis=1)
    df['fa'] = df_cp.apply(lambda row: get_lj_house_fa(row), axis=1)
    df['decorat'] = df_cp.apply(lambda row: {'精装':'Fine', '简装':'Simple', '毛坯':'Raw'}.get(
        row['decorat'], 'Others'), axis=1)
    df['lift'] = df_cp.apply(lambda row: {'有':'Yes', '无':'No'}.get(row['ele'], 'Unknown'), axis=1)
    df['usage'] = df_cp.apply(lambda row: get_lj_house_usage(row), axis=1)
    df['built_year'] = df_cp.apply(lambda row: get_lj_house_built_year(row), axis=1)
    df['num_house_in_block'] = df_cp.apply(lambda row: get_lj_houes_num_household(row), axis=1)
    df['management_fee'] = df_cp.apply(lambda row: get_lj_house_management_fee(row), axis=1)
    # df['management_fee_check'] = df_cp.apply(lambda row: row['block_info_dict'].get('management_fee',None), axis=1)
    if save_path:
        safely_save(df, save_path)
    return df
    
def get_geojson_lj_house_price(df, save_path=None):
    rst = {}
    rst['type'] = 'FeatureCollection'
    if save_path:
        name = os.path.basename(save_path).split('.')[0]
    else:
        name = 'lj_house_price'
    rst['name'] = name
    rst['crs'] = { "type": "name", "properties": { "name": "urn:ogc:def:crs:OGC:1.3:CRS84" } }
    rst['features'] = []
    for idx, row in df.iterrows():
        try:
            coord_lng = float(row['coord_lng'])
            coord_lat = float(row['coord_lat'])
        except:
            continue
        this_feature = {
            'type': 'Feature', 
            'properties': {}, 
            'geometry': {
                'type': 'Point',
                'coordinates': [coord_lng, coord_lat]
            }
        }
        for k, v in row.items():
            if k not in ['coord_lng', 'coord_lat']:
                if v is None or (type(v)==float and np.isnan(v)):
                    this_feature['properties'][k] = None
                else:
                    this_feature['properties'][k] = v
        rst['features'].append(this_feature)
    if save_path:
        safely_save(rst, save_path)
    return rst

def main():
    """
    db_name = 'L3_SZ_CityScope'
    col_name_list = [
        'house_detailed_second_hand_lianjia_' + x for x in [
            'futian', 'nanshan', 'luohu', 'longhua', 'baoan', 'longgang', 'yantian'
        ]
    ]
    
    # start mongodb
    client = pymongo.MongoClient('localhost', 27017)  
    db = client[db_name]   
    
    # process data
    records = retrieve_lj_house_price_data_multiple(db, col_name_list, '../data/house_price_lj/house_price_full_ch.csv')
    clean_df = clean_lj_house_price_data(records, '../data/house_price_lj/house_price.csv')
    clean_json = get_geojson_lj_house_price(clean_df, '../data/house_price_lj/house_price.geojson')
    """
    # it is already bd_09 coordinates, so no need to convert coordinates
    mask_polygon = '../data/border_RA_biased.geojson'
    source_features = '../data/house_price_lj/house_price.geojson'
    clip_on_shapes(source_features, mask_polygon=mask_polygon, name_append='RA', 
        save_shp_path='../data/house_price_lj/house_price_RA.geojson'
    )
    
    

if __name__ == '__main__':
    main()