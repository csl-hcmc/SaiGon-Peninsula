import os, sys, json, pickle, copy, random
import numpy as np
from functools import reduce
from shapely.geometry import Point, LineString, MultiLineString
from shapely.geometry.polygon import Polygon
from shapely.geometry.multipolygon import MultiPolygon
from pandas.core.frame import DataFrame
import pandas as pd
random.seed(2021)
np.random.seed(2021)

def safe_save(content, save_path):
    this_dirname = os.path.dirname(os.path.abspath(save_path))
    if not os.path.exists(this_dirname):
        os.makedirs(this_dirname)
    if save_path.split('.')[-1] in ['json', 'geojson']:
        json.dump(content, open(save_path, 'w', encoding='utf-8'), indent=4, ensure_ascii=False)
    elif save_path.split('.')[-1] in ['csv']:
        content = pd.DataFrame(content)
        content.to_csv(save_path, encoding='utf-8', index=False)


def parse_csv_data(csv_path, save_path, should_have, id_attrs=[]):
    real_data_records = pd.read_csv(csv_path, encoding='utf-8').to_dict('records')
    attr_dict = {}
    for record in real_data_records:
        for p in record:
            if p not in should_have:
                continue
            if p not in attr_dict:
                attr_dict[p] = {'values': [record[p]]}
            elif record[p] not in attr_dict[p]['values']:
                attr_dict[p]['values'].append(record[p])
    for attr in attr_dict:
        if attr in id_attrs:
            attr_dict[attr]['id'] = True
        else:
            attr_dict[attr]['id'] = False
    # keep order
    attr_dict = {k:attr_dict[k] for k in should_have}
    ref_info = {'attr_dict':attr_dict}
    safe_save(ref_info, save_path)
    print('\nReference info has been saved to: \n{}\n'.format(os.path.abspath(save_path)))
    return ref_info
    
def get_candidate_coords(csv_path, lat_column, lng_column, filter_column, filter_value_list):
    records = pd.read_csv(csv_path, encoding='utf-8').to_dict('records')
    coords = []
    for r in records:
        if r[filter_column] in filter_value_list:
            coords.append((r[lng_column], r[lat_column]))
    return coords   


def faking_housholds(num_hh, ref_info, fake_resident_data, save_path=None):
    if type(fake_resident_data) == dict:
        pass
    elif type(fake_resident_data) == str:
        fake_resident_data = json.load(open(fake_resident_data, encoding='utf-8'))
    else:
        print('Error fake_resident_data')
        exit()
    hhs = []
    attr_dict = ref_info['attr_dict']
    residents = fake_resident_data['features']
    for idx in range(num_hh):
        this_hh = {}
        for attr in attr_dict:
            random_rst = np.random.choice(attr_dict[attr]['values'])
            if ref_info['attr_dict'][attr]['id']:
                try:
                    this_hh[attr] = random_rst*10000 + idx
                except:
                    this_hh[attr] = str(random_rst) + str(idx).zfill(4)
            else:
                this_hh[attr] = random_rst
        random_resident = np.random.choice(residents)
        this_hh_location = random_resident['geometry']['coordinates']
        this_hh['Residence_lng'] = this_hh_location[0]
        this_hh['Residence_lat'] = this_hh_location[1]
        this_hh['HH_Size'] = this_hh['HH_Size_Age_GT_4'] + this_hh['HH_Size_Age_LT_4']
        this_hh['Car_Ownership'] = int(
            this_hh['Num_Private_Car'] + this_hh['Num_Van'] + this_hh['Num_Public_Car'] > 0
        )
        
        hhs.append(this_hh)
    if save_path is not None:
        safe_save(hhs, save_path)
        print('Fake housholds have been saved to: {}'.format(os.path.abspath(save_path)))
    return hhs
    

def faking_persons(hhs, ref_info, candidates_work_place_coords, save_path=None):
    persons = []
    attr_dict = ref_info['attr_dict']
    idx = 0
    for hh_idx, hh in enumerate(hhs):
        num_person_this_hh = hh['HH_Size']
        for p_idx in range(num_person_this_hh):
            idx += 1
            this_person = {
                'HH_ID': hh['HH_ID'],
                'Person_ID2': p_idx + 1
            }
            for attr in attr_dict:
                random_rst = np.random.choice(attr_dict[attr]['values'])
                if ref_info['attr_dict'][attr]['id']:
                    try:
                        this_person[attr] = random_rst*10000 + idx
                    except:
                        this_person[attr] = str(random_rst) + str(idx).zfill(4)
                else:
                    this_person[attr] = random_rst
            if this_person['Occupation'] not in ['Unemployment', 'Retired']:
                random_workplace_coord = random.choice(candidates_work_place_coords)
                this_person['Work_City'] = 'Shenzhen'
                this_person['Workplace_lng'] = random_workplace_coord[0]
                this_person['Workplace_lat'] = random_workplace_coord[1]
            else:
                this_person['Work_City'] = None
                this_person['Workplace_lng'] = None
                this_person['Workplace_lat'] = None
            persons.append(this_person)
    if save_path is not None:
        safe_save(persons, save_path)
        print('Fake persons have been saved to: {}'.format(os.path.abspath(save_path)))
    return persons
    
def time1_early_than_time2(time1, time2):
    hh1, mm1 = [int(x) for x in time1.split(':')]
    hh2, mm2 = [int(x) for x in time2.split(':')]
    if hh1 < hh2: return True
    if hh1 == hh2 and mm1 < mm2: return True
    return False
    
    
def time_str_to_num(time_str):
    hh, mm = [int(x) for x in time_str.split(':')]
    return hh*10000+mm

    
def faking_trips(hhs, persons, ref_info, candidates_trip_coords, save_path=None):
    trips = []
    hhs_dict = {hh['HH_ID']:hh for hh in hhs}
    attr_dict = ref_info['attr_dict']
    trip_purpose_list_without_go_home = [x for x in attr_dict['Trip_Purpose']['values']
                        if x != 'Go Home']
    trip_purpose_list_without_commuting = [x for x in attr_dict['Trip_Purpose']['values']
                        if x not in ['Commuting', 'Go to School']]
    for person in persons:
        this_person_trips = []
        time_str_list, time_num_list = [], []
        hh = hhs_dict[person['HH_ID']]
        num_trips_this_person = int(np.random.randint(5))
        last_place = (hh['Residence_lng'], hh['Residence_lat'])
        for trip_idx in range(num_trips_this_person):
            this_trip = {
                'HH_ID': person['HH_ID'],
                'Person_ID': person['Person_ID'],
                'Trip_ID': trip_idx+1
            }
            for attr in attr_dict:
                this_trip[attr] = np.random.choice(attr_dict[attr]['values'])
            if trip_idx == 0:
                this_trip['Trip_Purpose'] = np.random.choice(trip_purpose_list_without_go_home)
            elif trip_idx > 0 and this_person_trips[-1]['Trip_Purpose'] in ['Commuting', 'Go to School']:
                this_trip['Trip_Purpose'] = np.random.choice(trip_purpose_list_without_commuting)
            this_trip['From_City'], this_trip['To_City'] = 'Shenzhen', 'Shenzhen'
            this_trip['From_lng'] = last_place[0]
            this_trip['From_lat'] = last_place[1]
            candidates_trip_coords_with_origin = [x for x in candidates_trip_coords 
                if x != (this_trip['From_lng'], this_trip['From_lat'])]
            random_dest = random.choice(candidates_trip_coords_with_origin)
            this_trip['To_lng'], this_trip['To_lat'] = random_dest[0], random_dest[1]
            last_place = random_dest
            time_str_list += [this_trip['From_Time'], this_trip['To_Time']]
            time_num_list += [time_str_to_num(this_trip['From_Time']), time_str_to_num(this_trip['To_Time'])]
            # if not time1_early_than_time2(this_trip['From_Time'], this_trip['To_Time']):
                # this_trip['From_Time'], this_trip['To_Time'] = this_trip['To_Time'], this_trip['From_Time']
            this_person_trips.append(this_trip)
        time_sort_idx = np.argsort(time_num_list)
        for sorted_time_idx in range(len(time_sort_idx)):
            if sorted_time_idx % 2 == 0:
                this_person_trips[sorted_time_idx//2]['From_Time'] = time_str_list[time_sort_idx[sorted_time_idx]]
            if sorted_time_idx % 2 == 1:
                this_person_trips[sorted_time_idx//2]['To_Time'] = time_str_list[time_sort_idx[sorted_time_idx]]
        
        trips += this_person_trips
    if save_path is not None:
        safe_save(trips, save_path)
        print('Fake trips have been saved to: {}'.format(os.path.abspath(save_path)))
    return trips
                
    
                
    

def main():
    num_hh = 120
    
    real_hh_data = '../tmp/HTS_data_wgs84_biased_censored/NHTS_households_RA.csv'
    real_person_data = '../tmp/HTS_data_wgs84_biased_censored/NHTS_persons_RA.csv'
    real_trip_data = '../tmp/HTS_data_wgs84_biased_censored/NHTS_trips_RA.csv'
    fake_resident_data = '../tmp/fake_data_output_wgs84/population/resident_mainland_RA.geojson'
    
    hh_ref_info_save_path = '../data/for_fake_data/HTS_hh_ref_info.json'
    person_ref_info_save_path = '../data/for_fake_data/HTS_person_ref_info.json'
    trip_ref_info_save_path = '../data/for_fake_data/HTS_trip_ref_info.json'
    
    fake_hh_save_path = '../tmp/fake_data_output_wgs84/HTS_data/housholds_RA.csv'
    fake_person_save_path = '../tmp/fake_data_output_wgs84/HTS_data/persons_RA.csv'
    fake_trip_save_path = '../tmp/fake_data_output_wgs84/HTS_data/trips_RA.csv'
    
    hh_should_have = [
        'HH_ID', 'HH_Size', 'HH_Size_Age_GT_4', 'HH_Size_Age_LT_4', 'HH_Anual_Income', 
        'Residence_Type', 'Num_Private_Car' , 'Num_E_Bike', 'Num_Bike', 'Num_Motorcycle', 'Num_Van', 
        'Num_Public_Car', 'Num_Other_Mode', 'Car_Ownership'
    ]
    hh_id_attrs = ['HH_ID']
    person_should_have = [
        'Person_ID', 'Age', 'Gender', 'Register_in_SZ', 'Education', 'Income', 'Occupation'
    ]
    person_id_attrs = ['Person_ID']
    # trips_should_have = [
        # 'HH_ID', 'Person_ID', 'Trip_ID', 'Trip_Purpose', 'From_Time', 'Main_Mode', 'In-Vehicle Persons', 'To_Time', 'Trip_Dist', 
        # 'From_Province', 'To_Province', 'From_City', 'To_City', 'From_District', 'To_District', 
        # 'From_lng', 'From_lat', 'To_lng', 'To_lat', 'From_TAZ', 'To_TAZ'
    # ]
    trips_should_have = [
        'Trip_Purpose', 'From_Time', 'Main_Mode', 'In-Vehicle Persons', 'To_Time', 'Trip_Dist',
        'From_TAZ', 'To_TAZ'
    ]
    trips_id_attrs = []
    
    # # faking housholds
    if not os.path.exists(os.path.abspath(hh_ref_info_save_path)):
        ref_info = parse_csv_data(real_hh_data, hh_ref_info_save_path, hh_should_have, hh_id_attrs)
    else:
        ref_info = json.load(open(os.path.abspath(hh_ref_info_save_path), 'r', encoding='utf-8'))
    hhs = faking_housholds(num_hh, ref_info, fake_resident_data, fake_hh_save_path)
    
    
    # # faking persons
    if not os.path.exists(os.path.abspath(person_ref_info_save_path)):
        ref_info = parse_csv_data(real_person_data, person_ref_info_save_path, person_should_have, person_id_attrs)
    else:
        ref_info = json.load(open(os.path.abspath(person_ref_info_save_path), 'r', encoding='utf-8'))
    candidates_work_place_coords = get_candidate_coords(real_person_data, 'Workplace_lat', 'Workplace_lng', 
        'Work_City', ['Shenzhen'])
    persons = faking_persons(hhs, ref_info, candidates_work_place_coords, fake_person_save_path)
    
    
    # # faking trips
    if not os.path.exists(os.path.abspath(trip_ref_info_save_path)):
        ref_info = parse_csv_data(real_trip_data, trip_ref_info_save_path, trips_should_have, trips_id_attrs)
    else:
        ref_info = json.load(open(os.path.abspath(trip_ref_info_save_path), 'r', encoding='utf-8'))
    candidates_trip_place_coords_1 = get_candidate_coords(real_trip_data, 'To_lat', 'To_lng', 
        'To_City', ['Shenzhen'])
    candidates_trip_place_coords_2 = get_candidate_coords(real_trip_data, 'From_lat', 'From_lng', 
        'From_City', ['Shenzhen'])
    candidates_trip_coords = list(set(candidates_trip_place_coords_1 + candidates_trip_place_coords_2))
    trips = faking_trips(hhs, persons, ref_info, candidates_trip_coords, fake_trip_save_path)

if __name__ == '__main__':
    main()