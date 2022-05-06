import os, json, pymongo, sys, pickle, re
import pandas as pd
from pandas.core.frame import DataFrame

def get_float(row, key):
    try:
        return float(row[key])
    except:
        return None

def get_lj_house_totoal_price(row):
    use_summary_total_price = False
    if row['price'].endswith('万'):
        try:
            price = round(float(row[:-1]))
        except:
            use_summary_total_price = True
    else:
        use_summary_total_price = True
    if use_summary_total_price:
        try:
            price = round(float(row['summary_total_price']))
        except:
            price = None
    return price

def get_lj_house_unit_price(row):
    tmp_unit_price = re.compile('([0-9]+)元/平米').findall(str(row['unit_price']))
    if len(tmp_unit_price) == 1:
        unit_price = int(tmp_unit_price[0])
    else:
        tmp_summary_unit_price = re.compile('单价([0-9]+)元/平米').findall(str(row['summary_unit_price']))
        if len(tmp_summary_unit_price) == 1:
            unit_price = int(tmp_summary_unit_price[0])
        else:
            unit_price = None
    return unit_price

def get_lj_house_layout(row):
    rst = []
    br_re = re.compile('([0-9])室').findall(str(row['layout']))
    if len(br_re) == 1:
        rst.append(str(br_re[0]) + 'br')
    lr_re = re.compile('([0-9])厅').findall(str(row['layout']))
    if len(lr_re) == 1:
        rst.append(str(lr_re[0]) + 'lr/dr')
    k_re = re.compile('([0-9])厨').findall(str(row['layout']))
    if len(k_re) == 1:
        rst.append(str(k_re[0]) + 'k')
    wc_re = re.compile('([0-9])卫').findall(str(row['layout']))
    if len(wc_re) == 1:
        rst.append(str(wc_re[0]) + 'wc')
    return ', '.join(rst)

def get_lj_house_floor(row, ch_to_en={'高':'High', '中':'Medium', '低':'Low'}):
    floor_re = re.compile("(['高','中','低'])楼层").findall(str(row['floor']))
    if len(floor_re) == 1:
        floor = floor_re[0]
    else:
        floor = None
    floor = ch_to_en.get(floor, None)
    return floor

def get_lj_house_fa(row):
    if row['fa'] is None: return None
    fa_re = re.compile("([0-9.]+)㎡").findall(row['fa'])
    if len(fa_re) == 1:
        fa = float(fa_re[0])
    else:
        fa = None
    return fa

def get_lj_house_usage(row):
    usage_ch = row['usage_type']
    if usage_ch == '普通住宅':
        return 'Common Condo'
    elif usage_ch == '公寓':
        return 'Appartment'
    elif usage_ch == '商务公寓':
        return 'Business Appartment'
    elif usage_ch == '商业办公类':
        return 'Business Office'
    elif usage_ch == '商住两用':
        return 'Business & Residence'
    elif usage_ch == '别墅':
        return 'Villa'
    else:
        return None
    
def get_lj_house_block_info_dict(row):
    if type(row['block_info']) == dict:
        return row['block_info']
    # original block_info have mongoDB class ObjectID, which is unrecognizable
    block_info_str = re.sub('ObjectId\(.*?\)', "''", row['block_info'])  # str
    try:
        block_info = eval(block_info_str)  # dict
    except:
        block_info = {}
        key_value_pair_list = block_info_str.split(',')
        for key_value_pair in key_value_pair_list:
            key_value = [x.strip() for x in key_value_pair.split(':')]
            key, value = key_value[0][1:-1], key_value[1][1:-1]  # get rid of quote
            block_info[key] = value
    return block_info

def get_lj_house_built_year(row):
    try_summary_info = True
    built_year = None
    if 'built_year' in row['block_info_dict']:
        built_year_str =  row['block_info_dict']['built_year']
        if built_year_str is None:
            return None
        built_year_re = re.compile('([0-9]+)年').findall(built_year_str)
        if len(built_year_re) == 1:
            built_year = int(built_year_re[0])
            try_summary_info = False
    if try_summary_info:
        built_year_re = re.compile('([0-9]+)年').findall(row['summary_info'])
        if len(built_year_re) == 1:
            built_year = int(built_year_re[0])
    return built_year

def get_lj_houes_num_household(row):
    if 'house_num' in row['block_info_dict']:
        house_num_str = row['block_info_dict']['house_num']
        if house_num_str is None:
            return None
        house_num_re = re.compile('([0-9]+)户').findall(house_num_str)
        if len(house_num_re) == 1:
            return int(house_num_re[0])
        else:
            return None
    else:
        return None
    
def get_lj_house_management_fee(row):
    if 'management_fee' in row['block_info_dict']:
        fee = row['block_info_dict']['management_fee']
        if fee is None:
            return None
        fee_re1 = re.compile('^([0-9.]+)元/平米/月').findall(fee)
        if len(fee_re1) == 1:
            return float(fee_re1[0])
        else:
            fee_re2 = re.compile('([0-9.]+)至([0-9.]+)元/平米/月').findall(fee)
            if len(fee_re2) == 1:
                # using average (float) instead of range (str) 
                return (float(fee_re2[0][0]) + float(fee_re2[0][1])) / 2
    else:
        return None