import json, os, re, hashlib, sys
import pandas as pd

def hash_md5(inp, salt=''):
    return hashlib.md5(bytes(str(inp)+salt, encoding='utf-8')).hexdigest()

def geojson_filter_attributes(source_path, keep_attrs=[], hash_attrs=[], translate_attrs={}, new_attr_names={}, save_path=None, name_append=None):
    data = json.load(open(source_path, 'r', encoding='utf-8'))
    if name_append is not None:
        data['name'] = data['name'] + '_' + name_append
    if type(translate_attrs) == str and translate_attrs.endswith('.json'):
        translate_attrs = json.load(open(translate_attrs, 'r', encoding='utf-8'))
    for idx, feature in enumerate(data['features']):
        new_properties = {}
        # get keep_attrs:
        for attr in keep_attrs:
            if attr in feature['properties']:
                new_properties[attr] = feature['properties'][attr]
            else:
                new_properties[attr] = None
                # print('Warning: feature does not have this "keep_attr": ', attr)
        # new_properties = {attr:feature['properties'][attr] for attr in keep_attrs if attr in feature['properties']}
        # get has attrs:
        for attr in hash_attrs:
            if attr in feature['properties']:
                new_properties[attr] = hash_md5(feature['properties'][attr])
            else:
                new_properties[attr] = None
                # print('Warning: feature does not have this "hash_attr": ', attr)
        # get translate attrs:
        for attr in translate_attrs:
            if attr in feature['properties']:
                if feature['properties'][attr] is None:
                    new_properties[attr] = None
                elif feature['properties'][attr] in translate_attrs[attr]:
                    new_properties[attr] = translate_attrs[attr][feature['properties'][attr]]
                elif str(feature['properties'][attr]) in translate_attrs[attr]:
                    new_properties[attr] = translate_attrs[attr][str(feature['properties'][attr])]
                else:
                    new_properties[attr] = None
                    print('Warning: cannot find a English translation for value "{}" in {}'.format(feature['properties'][attr], attr))
            else:
                new_properties[attr] = None
                # print('Warning: feature does not have this "translate_attr": ', attr)
        for old_attr_name, new_attr_name in new_attr_names.items():
            if old_attr_name in new_properties:
                new_properties[new_attr_name] = new_properties.pop(old_attr_name)
            else:
                print('Warning: feature does not have this "attr_name": ', old_attr_name)
        feature['properties'] = new_properties
    if save_path is not None:
        if not os.path.exists(os.path.dirname(save_path)):
            os.makedirs(os.path.dirname(save_path))
        json.dump(data, open(save_path, 'w', encoding='utf-8'), ensure_ascii=False, indent=4)
        print('Censored file saved at:\n{}'.format(os.path.abspath(save_path)))
    return
    
def batch_geojson_filter_attributes(source_folder, target_folder, file_pattern=None, 
        keep_attrs=[], hash_attrs=[], translate_attrs={}, new_attr_names={}, name_append=None, skip_existed=True):
    if not os.path.exists(target_folder):
        os.makedirs(target_folder)
    file_list = [x for x in os.listdir(source_folder) if x.endswith('.geojson')]
    if file_pattern is not None:
        file_pattern = re.compile(file_pattern)
        file_list = [x for x in file_list if file_pattern.findall(x)]
    for file_name in file_list:
        print('\nCurrent working on: {}'.format(file_name))
        source_file_path = os.path.join(source_folder, file_name)
        file_name_base = file_name.split('.')[0]
        if name_append is not None:
            save_file_name = file_name_base + '_' + name_append + '.geojson'
        else:
            save_file_name = file_name_base + '.geojson'
        save_file_path = os.path.join(target_folder, save_file_name)
        if os.path.exists(save_file_path) and skip_existed:
            print('Skipped, as the file already exists at:\n{}'.format(save_file_path))
            continue
        if type(translate_attrs) == str and translate_attrs.endswith('.json'):
            translate_attrs = json.load(open(translate_attrs, 'r', encoding='utf-8'))
        geojson_filter_attributes(source_file_path, keep_attrs, hash_attrs, translate_attrs, new_attr_names,
            save_path=save_file_path, name_append=name_append)
    return
    
def csv_filter_attributes(source_file, save_file, keep_attrs=[], hash_attrs=[], translate_attrs={}, new_attr_names={}, name_append=None):
    if not os.path.exists(os.path.dirname(save_file)):
        os.makedirs(os.path.dirname(save_file))
    df = pd.read_csv(source_file, encoding='utf-8')
    records = df.to_dict(orient='records')
    for idx, record in enumerate(records):
        new_record = {}
        for attr in keep_attrs:
            if attr in record:
                new_record[attr] = record[attr]
            else:
                print('Warning: record does not have this "keep_attr": ', attr)
        # get hash attrs:
        for attr in hash_attrs:
            if attr in record:
                new_record[attr] = hash_md5(record[attr])
            else:
                print('Warning: record does not have this "hash_attr": ', attr)
        # get translate attrs:
        for attr in translate_attrs:
            if attr in record:
                if record[attr] is None or record[attr] == '':
                    new_record[attr] = ''
                elif record[attr] in translate_attrs[attr]:
                    new_record[attr] = translate_attrs[attr][record[attr]]
                else:
                    new_record[attr] = ''
                    print('Warning: cannot find a English translation for value "{}"'.format(record[attr]))
            else:
                print('Warning: record does not have this "translate_attr": ', attr)
        for old_attr_name, new_attr_name in new_attr_names.items():
            if old_attr_name in new_record:
                new_record[new_attr_name] = new_record.pop(old_attr_name)
            else:
                print('Warning: feature does not have this "attr_name": ', old_attr_name)
        records[idx] = new_record   
    new_df = pd.DataFrame(records)
    new_df.to_csv(save_file, encoding='utf-8', index=False)
    print('Censored file saved at:\n{}'.format(os.path.abspath(save_file)))
    return new_df
    

def main():
    
    if len(sys.argv) == 2:
        working_on = [x.strip() for x in sys.argv[1].split(',')]
        working_on_all = False
    else:
        working_on = []
        working_on_all = True
    print('\nWorking on list: {}\nWorking on all: {}'.format(working_on, working_on_all))
    
    if 'pois' in working_on or working_on_all:
        print('\nWorking on: pois')
        # processing poi files
        # source_folder = r'F:\01 - L3\Shenzhen CityScope\data\raw\physical\0809_解密.gdb\export_geojson_wgs84_RA_biased
        source_folder = '../tmp/emap_poi_wgs84_RA_biased'
        target_folder = '../tmp/emap_poi_wgs84_RA_biased_censored'
        file_pattern = '^poi_.*_RA.*\.geojson'
        keep_attrs = ['OBJECTID']
        skip_existed = True
        batch_geojson_filter_attributes(source_folder, target_folder, file_pattern, keep_attrs, skip_existed=skip_existed)
    
    if 'emaps' in working_on or working_on_all:
        print('\nWorking on: emaps')
        # working on emaps and pois: F:\01 - L3\Shenzhen CityScope\data\raw\physical\0809_解密.gdb
        # source_folder = r'F:\01 - L3\Shenzhen CityScope\data\raw\physical\0809_解密.gdb\export_geojson_wgs84_RA_biased'
        source_folder = '../tmp/emap_poi_wgs84_RA_biased'
        target_folder = '../tmp/emap_poi_wgs84_RA_biased_censored'
        source_file_dict = {
            'buildings': 'emap_buildings_RA.geojson',
            'bus_lines': 'emap_bus_lines_RA.geojson',
            'bus_stops': 'emap_bus_stops_RA.geojson',
            'inner_roads': 'emap_inner_roads_center_line_RA.geojson',
            'parks': 'emap_parks_RA.geojson',
            'rivers': 'emap_rivers_RA.geojson',
            'roads_boundary': 'emap_roads_boundary_line_RA.geojson',
            'roads_center': 'emap_roads_center_line_RA.geojson',
            'subway_exits': 'emap_subway_exits_RA.geojson',
            'subway_lines_planned': 'emap_subway_lines_planned_RA.geojson',
            'subway_lines': 'emap_subway_lines_RA.geojson'
        }
        target_file_dict = {k:v for k,v in source_file_dict.items()}
        keep_attrs_dict = {
            'buildings': [
                'OBJECTID', 'UP_BLDG_FLOOR', 'DOWN_BLDG_FLOOR', 'BLDG_HEIGHT', 
                'BLDG_LD_AREA', 'FLOOR_AREA', 'BLDG_USE_NAME', 'BLDG_USESTATE_NAME', 
                'SHAPE_Length', 'SHAPE_Area'
            ],
            'bus_lines': ['OBJECTID', 'START_TIME', 'END_TIME', 'BIDIRECTION', 'STATION_NUM', 'SHAPE_Length'],
            'bus_stops': ['OBJECTID', 'SEQID'],
            'inner_roads': ['OBJECTID', 'width', 'road_len', 'SHAPE_Length'],
            'parks': ['OBJECTID', 'AREA', 'SHAPE_Area', 'SHAPE_Length'],
            'rivers': ['OBJECTID', 'LENGTH', 'AREA', 'SHAPE_Length'],
            'roads_boundary': ['OBJECTID', 'width', 'road_len', 'SHAPE_Length'],
            'roads_center': ['OBJECTID', 'width', 'road_len', 'SHAPE_Length'],
            'subway_exits': ['OBJECTID'],
            'subway_lines_planned': ['OBJECTID'],
            'subway_lines': ['OBJECTID', 'SHAPE_Length']
        }
        hash_attrs_dict = {
            'buildings': ['BLDG_ID'],
            'bus_lines': ['LINE_ID', 'FRONT_ID', 'ERMINAL_ID', 'PAIRLINEID'],
            'bus_stops': ['STOP_ID', 'LINE_ID'],
            'inner_roads': ['road_id'],
            'parks': ['ID'],
            'rivers': ['ID'],
            'roads_boundary': ['road_id'],
            'roads_center': ['road_id'],
            'subway_exits': ['SUBWAYEXIT_ID'],
            'subway_lines_planned': [],
            'subway_lines': ['SUBWAY_ID']
        }
        translate_attrs_dict = {
            'buildings': 'lookup/emap_buildings_ch_to_en.json',
            'bus_lines': {},
            'bus_stops': {},
            'inner_roads': {},
            'parks': {},
            'rivers': {},
            'roads_boundary': {},
            'roads_center': {},
            'subway_exits': {},
            'subway_lines_planned': {},
            'subway_lines': {}
        }
        new_attr_names_dict = {
            'buildings': {'BLDG_USE_NAME': 'USAGE', 'BLDG_USESTATE_NAME': 'USESTATE'},
            'bus_lines': {'ERMINAL_ID': 'TERMINAL_ID'},
            'bus_stops': {},
            'inner_roads': {},
            'parks': {},
            'rivers': {},
            'roads_boundary': {},
            'roads_center': {},
            'subway_exits': {},
            'subway_lines_planned': {},
            'subway_lines': {}
        }
        for key in keep_attrs_dict:
            geojson_filter_attributes(
                source_path = os.path.join(source_folder, source_file_dict[key]), 
                keep_attrs = keep_attrs_dict[key], 
                hash_attrs = hash_attrs_dict[key], 
                translate_attrs = translate_attrs_dict[key], 
                new_attr_names = new_attr_names_dict[key], 
                save_path = os.path.join(target_folder, target_file_dict[key]), 
                name_append = None
            )
    
    if 'physical' in working_on or working_on_all:
        print('\nWorking on: physical')
        # working on other physical layers: F:\01 - L3\Shenzhen CityScope\data\forMIT
        # source_folder = r'F:\01 - L3\Shenzhen CityScope\data\forMIT\physical_data_wgs84_RA_biased'
        source_folder = '../tmp/physical_data_wgs84_RA_biased'
        target_folder = '../tmp/physical_data_wgs84_RA_biased_censored'
        source_folder = '../tmp/physical_data_wgs84_jw_grid_extent_buffered'
        target_folder = '../tmp/physical_data_wgs84_jw_grid_extent_buffered'
        # source_file_dict = {
        #     'buildings': 'buildings_RA.geojson',
        #     'zones': 'zoning_RA.geojson',
        #     'current_landuse': 'current_landuse_RA.geojson',
        #     'projects': 'projects_RA.geojson'
        # }
        source_file_dict = {
            'buildings': 'buildings_jw_grid_extent_buffered.geojson',
            'current_landuse': 'current_landuse_jw_grid_extent_buffered.geojson'
        }
        target_file_dict = {k:v for k,v in source_file_dict.items()}
        keep_attrs_dict = {
            'buildings': [
                'BLDG_HEIGHT', 'UP_BLDG_FLOOR', 'DOWN_BLDG_FLOOR', 'BLDG_NUM', 'FLOOR_AREA',
                'Shape_Leng', 'Shape_Area'
            ],
            # 'zones': [
            #     'OBJECTID', 'LU_CODE', 'PLOT_AREA', 'FLOOR_AREA', 'GREEN_PERC', 'MAINCODE',
            #     'SHAPE_AREA', 'SHAPE_LEN'
            # ],
            'current_landuse': ['OBJECTID', 'TBMJ', 'XHDLBM', 'SHAPE_AREA', 'SHAPE_LEN'], 
            # 'projects': ['OBJECTID', 'SHAPE_AREA', 'SHAPE_LEN']
        }
        hash_attrs_dict = {
            'buildings': ['BLDG_NO'],
            # 'zones': [],
            'current_landuse': [],
            # 'projects': []
        }
        translate_attrs_dict = {
            'buildings': 'lookup/buildings_properties_ch_to_en.json',
            # 'zones': 'lookup/zoning_properties_ch_to_eng.json',
            'current_landuse': 'lookup/crt_landuse_properties_ch_to_eng.json',
            # 'projects': 'lookup/projects_properties_ch_to_eng.json'
        }
        new_attr_names_dict = {
            'buildings': {},
            # 'zones': {
            #     'LU_FUNCTIO': 'LU_FUNCTION',
            #     'GREEN_PERC': 'GREEN_PERCENTAGE',
            #     'ARRANGE_FA': 'ARRANGE',
            #     'MAINCODE': 'MAIN_LU_CODE'
            # },
            'current_landuse': {
                'TBMJ': 'AREA',
                'GBDLMC': 'LU_NAME',
                'XHDLBM': 'DETAIL_LU_CODE',
                'XHDLMC': 'DETAIL_LU_NAME'
            },
            # 'projects': {
            #     'TB_PROJ_NA': 'PROJ_NAME',
            #     'TB_TRACE_S': 'STATUS'
            # }
        }
        for key in keep_attrs_dict:
            geojson_filter_attributes(
                source_path = os.path.join(source_folder, source_file_dict[key]), 
                keep_attrs = keep_attrs_dict[key], 
                hash_attrs = hash_attrs_dict[key], 
                translate_attrs = translate_attrs_dict[key], 
                new_attr_names = new_attr_names_dict[key], 
                save_path = os.path.join(target_folder, target_file_dict[key]), 
                name_append = None
            )
    
    if 'big_data' in working_on or working_on_all:
        print('\nWorking on: big_data')
        # working on big data: F:\01 - L3\Shenzhen CityScope\data\forMIT
        # source_folder = r'F:\01 - L3\Shenzhen CityScope\data\forMIT\big_data_wgs84_biased'
        source_folder = '../tmp/big_data_wgs84_biased'
        target_folder = '../tmp/big_data_wgs84_biased_censored'
        geojson_filter_attributes(
            source_path = os.path.join(source_folder, 'TAZ_big_data_SZ.geojson'), 
            save_path = os.path.join(target_folder, 'TAZ_big_data_SZ.geojson'),
            keep_attrs=['AREA'], hash_attrs=['NO'], translate_attrs={}, 
            new_attr_names={'NO':'TAZ_ID'},  name_append=None)
        geojson_filter_attributes(
            source_path = os.path.join(source_folder, 'agg_population_big_data_RA.geojson'), 
            save_path = os.path.join(target_folder, 'agg_population_big_data_RA.geojson'),
            keep_attrs=[
                'AREA', 'Resident_Num', 'Resident_Den', 'Worker_Num', 'Worker_Den', 
                'Daytime_Floating_Pop_Num', 'Daytime_Floating_Pop_Den',
                'Night_Floating_Pop_Num', 'Night_Floating_Pop_Den'
            ], 
            hash_attrs=['NO'], translate_attrs={}, 
            new_attr_names={'NO': 'TAZ_ID'},  name_append=None)
        csv_filter_attributes(
            source_file = os.path.join(source_folder, 'commuting_od_big_data_RA.csv'), 
            save_file = os.path.join(target_folder, 'commuting_od_big_data_RA.csv'), 
            keep_attrs=['Trip_Num'], hash_attrs=['From_TAZ', 'To_TAZ'], translate_attrs={}, new_attr_names={}
        )
        csv_filter_attributes(
            source_file = os.path.join(source_folder, 'holiday_overall_od_big_data_RA.csv'), 
            save_file = os.path.join(target_folder, 'holiday_overall_od_big_data_RA.csv'), 
            keep_attrs=['Trip_Num'], hash_attrs=['From_TAZ', 'To_TAZ'], translate_attrs={}, new_attr_names={}
        )
        
    if 'HTS_data' in working_on or working_on_all:
        print('\nWorking on: HTS_data')
        # working on NHTS data: F:\01 - L3\Shenzhen CityScope\data\forMIT
        # source_folder = r'F:\01 - L3\Shenzhen CityScope\data\forMIT\NHTS_data_wgs84_biased'
        source_folder = '../tmp/HTS_data_wgs84_biased'
        target_folder = '../tmp/HTS_data_wgs84_biased_censored'
        geojson_filter_attributes(
            source_path = os.path.join(source_folder, 'NHTS_households_RA.geojson'), 
            save_path = os.path.join(target_folder, 'NHTS_households_RA.geojson'),
            keep_attrs=[
                'HH_Size', 'HH_Size_Age_GT_4', 'HH_Size_Age_LT_4',
                'HH_Anual_Income', 'Residence_Type', 'Num_Private_Car',
                'Num_E_Bike', 'Num_Bike', 'Num_Motorcycle', 'Num_Van',
                'Num_Public_Car', 'Num_Other_Mode', 'Car_Ownership', 'HH_ID2'
            ], 
            hash_attrs=['TAZ', 'HH_ID'], 
            translate_attrs={}, name_append=None,
            new_attr_names={})
        csv_filter_attributes(
            source_file = os.path.join(source_folder, 'NHTS_households_RA.csv'), 
            save_file = os.path.join(target_folder, 'NHTS_households_RA.csv'), 
            keep_attrs=[
                'HH_Size', 'HH_Size_Age_GT_4', 'HH_Size_Age_LT_4',
                'HH_Anual_Income', 'Residence_Type', 'Num_Private_Car',
                'Num_E_Bike', 'Num_Bike', 'Num_Motorcycle', 'Num_Van',
                'Num_Public_Car', 'Num_Other_Mode', 'Car_Ownership', 
                'Residence_lng', 'Residence_lat', 'HH_ID2'
            ], 
            hash_attrs=['TAZ', 'HH_ID'], 
            translate_attrs={}, 
            new_attr_names={}
        )
        csv_filter_attributes(
            source_file = os.path.join(source_folder, 'NHTS_persons_RA.csv'), 
            save_file = os.path.join(target_folder, 'NHTS_persons_RA.csv'), 
            keep_attrs=[
                'Age', 'Gender', 'Register_in_SZ', 'Education', 'Income',
                'Occupation', 'Work_Province', 'Work_City', 'Work_District',
                'Workplace_lng', 'Workplace_lat', 'Person_ID2'
            ], 
            hash_attrs=['HH_ID', 'Person_ID'], 
            translate_attrs={}, 
            new_attr_names={}
        )
        csv_filter_attributes(
            source_file = os.path.join(source_folder, 'NHTS_trips_RA.csv'), 
            save_file = os.path.join(target_folder, 'NHTS_trips_RA.csv'), 
            keep_attrs=[
                'Trip_ID', 'Trip_Purpose', 'From_Time', 'Main_Mode', 
                'In-Vehicle Persons', 'To_Time', 'Trip_Dist',
                'From_Province', 'To_Province', 'From_City', 'To_City',
                'From_District', 'To_District', 
                'From_lng', 'From_lat', 'To_lng', 'To_lat'
            ], 
            hash_attrs=['HH_ID', 'Person_ID', 'From_TAZ', 'To_TAZ'], 
            translate_attrs={}, 
            new_attr_names={}
        )
    
    if 'pop_data' in working_on or working_on_all:
        print('\nWorking on: pop_data')
        # working on population data: F:\01 - L3\Shenzhen CityScope\data\forMIT
        # source_folder = r'F:\01 - L3\Shenzhen CityScope\data\forMIT\pop_data_wgs84_RA_biased'
        source_folder = '../tmp/pop_data_wgs84_RA_biased'
        target_folder = '../tmp/pop_data_wgs84_RA_biased_censored'
        geojson_filter_attributes(
            source_path = os.path.join(source_folder, 'RESIDENT_RA.geojson'), 
            save_path = os.path.join(target_folder, 'RESIDENT_RA.geojson'),
            keep_attrs=[
                'BIRTHDAY', 'SEX', 'NATIONID', 'MARRYID', 'ISLOGOUT',
                'BL_UP_BLDG_FL', 'BL_BLDG_HEIGH', 
                'BL_BLDG_LD_AR', 'BL_FLOOR_AREA'
            ], 
            hash_attrs=['ID', 'HOUSEID', 'QHAREAID', 'BL_BLDG_NO'], 
            translate_attrs='lookup/resident_ch_to_en.json', name_append=None,
            new_attr_names={
                'NATIONID': 'RACE',
                'MARRYID': 'MARRIAGE',
                'EDULEVELID': 'EDUCATION',
                'TRADEID': 'OCCUPATION',
                'DOMICILETYPE': 'ACCOMMODATION_TYPE',
                'BIDEFASHION': 'LIVE_STYLE',
                'LEASEREASONID': 'LEASE_REASON',
                'BL_UP_BLDG_FL': 'UP_BLDG_FLOOR',
                'BL_BLDG_HEIGH': 'BLDG_HEIGH',
                'BL_BLDG_LD_AR': 'BLDG_LAND_AREA',
                'BL_FLOOR_AREA': 'BLDG_FLOOR_AREA',
                'BL_BLDG_USE_1': 'BLDG_USAGE'
            })
            
        geojson_filter_attributes(
            source_path = os.path.join(source_folder, 'resident_hmt_RA.geojson'), 
            save_path = os.path.join(target_folder, 'resident_hmt_RA.geojson'),
            keep_attrs=[
                'BIRTHDAY', 'SEX', 'MARRYID', 'ISLOGOUT', 'INTIME1', 'LEAVEDATE',
                'BL_UP_BLDG_FL', 'BL_BLDG_HEIGH', 
                'BL_BLDG_LD_AR', 'BL_FLOOR_AREA'
            ], 
            hash_attrs=['ID', 'HOUSEID', 'QHAREAID', 'BL_BLDG_NO'], 
            translate_attrs='lookup/resident_hmt_ch_to_en.json', name_append=None,
            new_attr_names={
                'MARRYID': 'MARRIAGE',
                'TRADEID': 'OCCUPATION',
                'DOMICILETYPE': 'ACCOMMODATION_TYPE',
                'BIDEFASHION': 'LIVE_STYLE',
                'LEASEREASONID': 'LEASE_REASON',
                'BL_UP_BLDG_FL': 'UP_BLDG_FLOOR',
                'BL_BLDG_HEIGH': 'BLDG_HEIGH',
                'BL_BLDG_LD_AR': 'BLDG_LAND_AREA',
                'BL_FLOOR_AREA': 'BLDG_FLOOR_AREA',
                'BL_BLDG_USE_1': 'BLDG_USAGE'
            })
            
        geojson_filter_attributes(
            source_path = os.path.join(source_folder, 'resident_foreign_right_nationality_RA.geojson'), 
            save_path = os.path.join(target_folder, 'resident_foreign_RA.geojson'),
            keep_attrs=[
                'SEX', 'NATIONALITY', 'ISLOGOUT', 
                'BL_UP_BLDG_FL', 'BL_BLDG_HEIGH', 
                'BL_BLDG_LD_AR', 'BL_FLOOR_AREA'
            ], 
            hash_attrs=['ID', 'HOUSEID', 'QHAREAID', 'BL_BLDG_NO'], 
            translate_attrs='lookup/resident_foreign_ch_to_en.json', name_append=None,
            new_attr_names={
                'BL_UP_BLDG_FL': 'UP_BLDG_FLOOR',
                'BL_BLDG_HEIGH': 'BLDG_HEIGH',
                'BL_BLDG_LD_AR': 'BLDG_LAND_AREA',
                'BL_FLOOR_AREA': 'BLDG_FLOOR_AREA',
                'BL_BLDG_USE_1': 'BLDG_USAGE'
            })

    
if __name__ == '__main__':
    # debug
    # source_file = r'F:\01 - L3\Shenzhen CityScope\data\raw\physical\0809_解密.gdb\export_geojson_wgs84_RA_biased\emap_bus_lines_RA.geojson'
    # save_file = 'strange.json'
    # geojson_filter_attributes(source_file, save_path=save_file, 
        # keep_attrs=['OBJECTID', 'START_TIME', 'END_TIME', 'BIDIRECTION', 'STATION_NUM', 'SHAPE_Length'],
        # hash_attrs=['LINE_ID', 'FRONT_ID', 'ERMINAL_ID', 'PAIRLINEID'],
        # new_attr_names = {'ERMINAL_ID': 'TERMINAL_ID'})
    # exit()
    main()