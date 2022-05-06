import json, os, sys
from coordTransform_utils import bd09_to_wgs84, wgs84_to_bd09
import numpy as np
import pandas as pd


def geojson_coord_convert_wgs84_to_bd09(source_file, save_file, name_append=None):
    data = json.load(open(source_file, 'r', encoding='utf-8'))
    data['crs']['properties']['name'] = 'urn:ogc:def:crs:OGC:1.3:CRS84'
    features = data['features']
    # starting convert coords
    for idx, feature in enumerate(features):
        ftype = feature['geometry']['type']
        coords = feature['geometry']['coordinates']
        if ftype == 'MultiPoint':
            new_coords = [wgs84_to_bd09(coords[0][0], coords[0][1])]
        elif ftype == 'MultiPolygon':
            new_coords = []
            for mpolygon in coords:
                new_mpolygon = []
                for polygon in mpolygon:
                    new_polygon = []
                    for this_coord in polygon:
                        this_new_coord = wgs84_to_bd09(this_coord[0], this_coord[1])
                        new_polygon.append(this_new_coord)
                    new_mpolygon.append(new_polygon)
                new_coords.append(new_mpolygon)
        elif ftype == 'Polygon':
            new_coords = []
            for polygon in coords:
                new_polygon = []
                for this_coord in polygon:
                    this_new_coord = wgs84_to_bd09(this_coord[0], this_coord[1])
                    new_polygon.append(this_new_coord)
            new_coords.append(new_polygon)
        elif ftype == 'LineString':
            new_coords = []
            for this_coord in coords:
                this_new_coord = wgs84_to_bd09(this_coord[0], this_coord[1])
                new_coords.append(this_new_coord)
        elif ftype == 'MultiLineString':
            new_coords = []
            for line in coords:
                new_line = []
                for this_coord in line:
                    this_new_coord = wgs84_to_bd09(this_coord[0], this_coord[1])
                    new_line.append(this_new_coord)
                new_coords.append(new_line)
        elif ftype == 'Point':
            new_coords = wgs84_to_bd09(coords[0], coords[1])
        else:
            print('Invalid geometry type: {}, converting failed'.format(ftype))
            exit()
        features[idx]['geometry']['coordinates'] = new_coords
    data['features'] = features
    if name_append is not None:
        data['name'] = data['name'] + '_' + name_append
    if not os.path.exists(os.path.dirname(save_file)):
        os.makedirs(os.path.dirname(save_file))
    json.dump(data, open(save_file, 'w', encoding='utf-8'), indent=4, ensure_ascii=False)
    print('Coords converting finished, new file saved to: \n{}'.format(os.path.abspath(save_file)))
    return
    
def batch_conversion_geojson(source_folder, target_folder, name_append=None, skip_existed=True):
    if not os.path.exists(target_folder):
        os.makedirs(target_folder)
    file_list = [x for x in os.listdir(source_folder) if x.endswith('.geojson')]
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
        geojson_coord_convert_wgs84_to_bd09(source_file_path, save_file_path, name_append)
    return
    
def csv_coord_convert_wgs84_to_bd09(source_file, save_file, columns=[], name_append=None):
    if not os.path.exists(os.path.dirname(save_file)):
        os.makedirs(os.path.dirname(save_file))
    df = pd.read_csv(source_file, encoding='utf-8')
    use_columns = []
    for lng_c, lat_c in columns:
        if lng_c in df.columns and lat_c in df.columns: 
            use_columns.append((lng_c, lat_c))
        else: print('Warning: column {} and/or {} is not in data'.format(lng_c, lat_c))
    # use_columns = [x for x in columns if x in df.columns]
    records = df.to_dict(orient='records')
    for r in records:
        for lng_c, lat_c in use_columns:
            this_lng, this_lat = r[lng_c], r[lat_c]
            this_new_coord = wgs84_to_bd09(this_lng, this_lat)
            r[lng_c] = this_new_coord[0]
            r[lat_c] = this_new_coord[1]
    new_df = pd.DataFrame(records)
    new_df.to_csv(save_file, encoding='utf-8', index=False)
    print('Coords converting finished, new file saved to: \n{}'.format(os.path.abspath(save_file)))
    return new_df
            
        
        
    
    
    
def main():

    if len(sys.argv) == 2:
        working_on = [x.strip() for x in sys.argv[1].split(',')]
        working_on_all = False
    else:
        working_on = []
        working_on_all = True
    print('\nWorking on list: {}\nWorking on all: {}'.format(working_on, working_on_all))
    

    if 'emaps_pois' in working_on or working_on_all:
        print('\nWorking on: emaps_pois')
        # source_folder = r'D:\01 - L3\Shenzhen CityScope\data\raw\physical\0809_解密.gdb\export_geojson_wgs84_RA'
        source_folder = '../tmp/emap_poi_wgs84_RA'
        target_folder = '../tmp/emap_poi_wgs84_RA_biased'
        name_append = None
        batch_conversion_geojson(source_folder, target_folder, name_append)

    if 'physical' in working_on or working_on_all:
        print('\nWorking on: physical')
        # source_folder = r'D:\01 - L3\Shenzhen CityScope\data\forMIT\physical_data_wgs84_RA'
        source_folder = '../tmp/physical_data_wgs84_RA'
        target_folder = '../tmp/physical_data_wgs84_RA_biased'
        name_append = None
        batch_conversion_geojson(source_folder, target_folder, name_append)
        
    if 'big_data' in working_on or working_on_all:
        print('\nWorking on: big_data')
        # source_folder = r'F:\01 - L3\Shenzhen CityScope\data\forMIT\big_data_wgs84'
        source_folder = '../tmp/big_data_wgs84'
        target_folder = '../tmp/big_data_wgs84_biased'
        name_append = None
        batch_conversion_geojson(source_folder, target_folder, name_append)
        
    if 'HTS_data' in working_on or working_on_all:
        print('\nWorking on: HTS_data')
        source_folder = r'D:\01 - L3\Shenzhen CityScope\data\forMIT\NHTS_data_wgs84'
        target_folder = '../tmp/HTS_data_wgs84_biased'
        name_append = None
        batch_conversion_geojson(source_folder, target_folder, name_append)
        csv_coord_convert_wgs84_to_bd09(
            source_file = os.path.join(source_folder, 'NHTS_households_RA.csv'), 
            save_file = os.path.join(target_folder, 'NHTS_households_RA.csv'), 
            columns=[('Residence_lng', 'Residence_lat')], 
            name_append=None
        )
        csv_coord_convert_wgs84_to_bd09(
            source_file = os.path.join(source_folder, 'NHTS_persons_RA.csv'), 
            save_file = os.path.join(target_folder, 'NHTS_persons_RA.csv'), 
            columns=[('Workplace_lng', 'Workplace_lat')], 
            name_append=None
        )
        csv_coord_convert_wgs84_to_bd09(
            source_file = os.path.join(source_folder, 'NHTS_trips_RA.csv'), 
            save_file = os.path.join(target_folder, 'NHTS_trips_RA.csv'), 
            columns=[('From_lng', 'From_lat'), ('To_lng', 'To_lat')], 
            name_append=None
        )
        
    if 'pop_data' in working_on or working_on_all:
        print('\nWorking on: pop_data')
        # source_folder = r'F:\01 - L3\Shenzhen CityScope\data\forMIT\pop_data_wgs84_RA'
        source_folder = '../tmp/pop_data_wgs84_RA'
        target_folder = '../tmp/pop_data_wgs84_RA_biased'
        name_append = None
        batch_conversion_geojson(source_folder, target_folder, name_append)
    
    if '3d' in working_on or working_on_all:  
        print('\nWorking on: 3d')
        # 3d origin:
        source_file = r'D:\01 - L3\Shenzhen CityScope\data\data_desensitization\coord_convert\3d_5_wgs84.geojson'
        save_file = '../tmp/3d_5_bd09.geojson'
        geojson_coord_convert_wgs84_to_bd09(source_file, save_file, name_append=None)

def work1():
    src_dir = r'C:\Users\tiamo\Desktop\sending_data\raw'
    des_dir = r'C:\Users\tiamo\Desktop\sending_data\new'
    batch_conversion_geojson(src_dir, des_dir)


if __name__ == '__main__':
    # main()
    work1()
