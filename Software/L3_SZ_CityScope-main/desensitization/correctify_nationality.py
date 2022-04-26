import pandas as pd
import os
import json

# json_source = r'F:\01 - L3\Shenzhen CityScope\data\forMIT\pop_data_wgs84_RA_biased\resident_foreign_RA.geojson'
# right_nationality_source = r'F:\01 - L3\Shenzhen CityScope\data\raw\population\人口数据导出\residentoutside_utf8.csv'
# json_save_to = r'F:\01 - L3\Shenzhen CityScope\data\forMIT\pop_data_wgs84_RA_biased\resident_foreign_right_nationality_RA.geojson'

json_source = '../tmp/pop_data_wgs84_RA_biased/resident_foreign_RA.geojson'
right_nationality_source = r'D:\01 - L3\Shenzhen CityScope\data\raw\population\人口数据导出\residentoutside_utf8.csv'
json_save_to = '../tmp/pop_data_wgs84_RA_biased/resident_foreign_right_nationality_RA.geojson'


d = json.load(open(json_source, encoding='utf-8'))
df = pd.read_csv(right_nationality_source, encoding='utf-8')
all_people = df.to_dict('records')
all_people = {x['ID']:x for x in all_people}

for idx, feature in enumerate(d['features']):
    # print(feature['properties']['NATIONALITY'])
    this_person = all_people[feature['properties']['ID']]
    if 'NATIONALITY' in feature['properties']:
        feature['properties']['NATIONALITY'] = this_person['NATIONALITY']
    else:
        feature['properties']['NATIONALITY'] = None
        
json.dump(d, open(json_save_to, 'w', encoding='utf-8'), indent=4, ensure_ascii=False)
    