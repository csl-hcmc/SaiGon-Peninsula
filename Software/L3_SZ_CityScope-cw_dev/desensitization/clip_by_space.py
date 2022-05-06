import os, json, copy, sys

from shapely.geometry import Point, LineString, MultiLineString
from shapely.geometry.polygon import Polygon
from shapely.geometry.multipolygon import MultiPolygon
# import matplotlib.pyplot as plt

def get_first_polygon_from_geojson(polygon_geojson): 
    if type(polygon_geojson) == dict:
        pass
    elif type(polygon_geojson) == str and polygon_geojson.endswith('.geojson'):
        polygon_geojson = json.load(open(polygon_geojson, 'r', encoding='utf-8'))
    polygon = polygon_geojson['features'][0]
    if polygon['geometry']['type'] == 'Polygon':
        polygon = Polygon(polygon['geometry']['coordinates'][0])
    elif polygon['geometry']['type'] == 'MultiPolygon':
        polygon = Polygon(polygon['geometry']['coordinates'][0][0])
    return polygon

def clip_point_given_mask(point_feature, mask_polygon):
    """
    """
    if type(mask_polygon) != Polygon:
        mask_polygon = get_first_polygon_from_geojson(mask_polygon)
    rst = []
    if point_feature['geometry']['type'] == 'Point':
        this_point = Point(point_feature['geometry']['coordinates'])
        if mask_polygon.contains(this_point): 
            rst.append(copy.deepcopy(point_feature))
    elif point_feature['geometry']['type'] == 'MultiPoint':
        for this_point_coord in point_feature['geometry']['coordinates']:
            this_point = Point(this_point_coord)
            if mask_polygon.contains(this_point):
                new_point_feature = copy.deepcopy(point_feature)
                new_point_feature['geometry']['coordinates'] = [this_point_coord]
    return rst
    


def clip_on_shapes(source_shp, mask_polygon, save_shp_path=None, name_append='RA'):
    if type(source_shp) == dict:
        source_data = source_shp
    elif type(source_shp) == str and source_shp.endswith('.geojson'):
        source_data = json.load(open(source_shp, 'r', encoding='utf-8'))
    else:
        print('Error source data')
        exit()
        
    if type(mask_polygon) == dict:
        pass
    elif type(mask_polygon) == str and mask_polygon.endswith('.geojson'):
        mask_polygon = json.load(open(mask_polygon, 'r', encoding='utf-8'))
    else:
        print('Error mask polygon')
        exit()
        
    mask_polygon = mask_polygon['features'][0]
    if mask_polygon['geometry']['type'] == 'Polygon':
        mask_polygon = Polygon(mask_polygon['geometry']['coordinates'][0])
    elif mask_polygon['geometry']['type'] == 'MultiPolygon':
        mask_polygon = Polygon(mask_polygon['geometry']['coordinates'][0][0])
        
    keep_features = []
    for feature in source_data['features']:
        if feature['geometry']['type'] == 'Point':
            this_geobj = Point(feature['geometry']['coordinates'])
        elif feature['geometry']['type'] == 'MultiPoint':
            this_geobj = Point(feature['geometry']['coordinates'][0])
        elif feature['geometry']['type'] == 'Polygon':
            this_geobj = Polygon(feature['geometry']['coordinates'][0])
        elif feature['geometry']['type'] == 'MultiPolygon':
            this_geobj = Polygon(feature['geometry']['coordinates'][0][0])
        elif feature['geometry']['type'] == 'MultiLineString':
            this_geobj = LineString(feature['geometry']['coordinates'][0])
        else:
            print('Invalid geometry type: {}, converting failed'.format(feature['geometry']['type']))
            exit()
        if mask_polygon.contains(this_geobj):
            keep_features.append(feature)
        elif type(this_geobj) == LineString and mask_polygon.intersection(this_geobj).length > 0:
            clipped_feature_overall = mask_polygon.intersection(this_geobj)
            if type(clipped_feature_overall) == LineString:
                clipped_feature_list = [clipped_feature_overall]
            elif type(clipped_feature_overall) == MultiLineString:
                clipped_feature_list = list(clipped_feature_overall)
            for clipped_feature in clipped_feature_list:
                if clipped_feature.length <0.00000001: continue
                clipped_feature_coords = list(clipped_feature.coords)
                clipped_feature_coords = [[x[0], x[1]] for x in clipped_feature_coords]
                new_feature = copy.deepcopy(feature)
                new_feature['geometry']['coordinates'] = [clipped_feature_coords]
                keep_features.append(new_feature)
        elif type(this_geobj) == Polygon and mask_polygon.intersection(this_geobj).area > 0:
            clipped_feature_overall = mask_polygon.intersection(this_geobj)
            if type(clipped_feature_overall) == Polygon:
                clipped_feature_list = [clipped_feature_overall]
            elif type(clipped_feature_overall) == MultiPolygon:
                clipped_feature_list = list(clipped_feature_overall)
            for clipped_feature in clipped_feature_list:
                if clipped_feature.area < 0.00000000001: continue
                clipped_feature_coords = list(clipped_feature.exterior.coords)
                clipped_feature_coords = [[x[0], x[1]] for x in clipped_feature_coords]
                new_feature = copy.deepcopy(feature)
                if feature['geometry']['type'] == 'Polygon':
                    new_feature['geometry']['coordinates'] = [clipped_feature_coords]
                elif feature['geometry']['type'] == 'MultiPolygon':
                    new_feature['geometry']['coordinates'] = [[clipped_feature_coords]]
                keep_features.append(new_feature)
    rst = {}
    for attr in ['type', 'name', 'crs']:
        rst[attr] = source_data[attr]
    if name_append is not None:
        rst['name'] = rst['name'] + '_' + name_append
    rst['features'] = keep_features
    
    if save_shp_path is not None:
        if not os.path.exists(os.path.dirname(save_shp_path)):
            os.makedirs(os.path.dirname(save_shp_path))
        json.dump(rst, open(save_shp_path, 'w', encoding='utf-8'), indent=4, ensure_ascii=False)
        print('Clipped file saved at:\n{}'.format(os.path.abspath(save_shp_path)))
    return rst

def batch_mask(source_folder, mask_polygon_file_path, target_folder, name_append='RA', skip_existed=True):
    if not os.path.exists(target_folder):
        os.makedirs(target_folder)
    file_list = [x for x in os.listdir(source_folder) if x.endswith('.geojson')]
    mask_polygon = json.load(open(mask_polygon_file_path,'r', encoding='utf-8'))
    for file_name in file_list:
        print('\nCurrent working on: {}'.format(file_name))
        source_file_path = os.path.join(source_folder, file_name)
        file_name_base = file_name.split('.')[0]
        if name_append is not None:
            save_file_name = file_name_base + '_' + name_append + '.geojson'
        else:
            save_file_name = file_name + '.geojson'
        save_file_path = os.path.join(target_folder, save_file_name)
        if os.path.exists(save_file_path) and skip_existed:
            print('Skipped, as the file already exists at:\n{}'.format(save_file_path))
            continue
        clip_on_shapes(source_file_path, mask_polygon=mask_polygon, save_shp_path=save_file_path, name_append=name_append)
    return

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
        # working on emaps and pois: D:\01 - L3\Shenzhen CityScope\data\raw\physical\0809_解密.gdb
        source_folder = r'D:\01 - L3\Shenzhen CityScope\data\raw\physical\0809_解密.gdb\export_geojson_wgs84'
        mask_polygon = '../data/border_RA.geojson'
        target_folder = '../tmp/emap_poi_wgs84_RA'
        name_append = 'RA'
        batch_mask(source_folder, mask_polygon, target_folder, name_append)
        pass

    if 'physical' in working_on or working_on_all:
        print('\nWorking on: physical')
        # working on other physical layers: D:\01 - L3\Shenzhen CityScope\data\forMIT
        # source_folder = r'D:\01 - L3\Shenzhen CityScope\data\forMIT\physical_data_wgs84'
        source_folder = '../tmp/physical_data_epsg4547_jw_grid_extent_buffered'
        # mask_polygon = '../data/border_RA.geojson'
        # target_folder = '../tmp/physical_data_wgs84_RA'
        # name_append = 'RA'
        # mask_polygon = '../data/jw_grid/grid_2_oriented_extent_wgs84.geojson'
        # target_folder = '../tmp/physical_data_wgs84_jw_grid_extent'
        # name_append = 'jw_grid_extent'
        # mask_polygon = '../data/jw_grid/grid_2_buffered_extent_wgs84.geojson'
        mask_polygon = '../data/jw_grid/grid_2_oriented_extent.geojson'
        # target_folder = '../tmp/physical_data_wgs84_jw_grid_extent_buffered'
        target_folder = '../tmp/physical_data_epsg4547_jw_grid_extent'
        name_append = 'jw_grid_extent_buffered'
        batch_mask(source_folder, mask_polygon, target_folder, name_append)
        pass

    if 'big_data' in working_on or working_on_all:
        print('\nWorking on: big_data')
        # working on big data: D:\01 - L3\Shenzhen CityScope\data\forMIT
        # do not do it here, do it manually, as we only have 3 TAZs in research area,
        # and only one file to process, also, there is one file need not to be cliped (TAZs for the whole city)
        pass

    if 'pop_data' in working_on or working_on_all:
        print('\nWorking on: pop_data')
        # working on pop data:
        # source_folder = r'D:\01 - L3\Shenzhen CityScope\data\forMIT\pop_data_wgs84'
        source_folder = '../tmp/pop_data_wgs84_jw_grid_extent_buffered'
        # mask_polygon = '../data/border_RA.geojson'
        # target_folder = '../tmp/pop_data_wgs84_RA'
        # mask_polygon = '../data/jw_grid/grid_2_buffered_extent_wgs84.geojson'
        mask_polygon = '../data/jw_grid/grid_2_oriented_extent_wgs84.geojson'
        target_folder = '../tmp/pop_data_wgs84_jw_grid_extent'
        name_append = 'jw_grid_extent'
        batch_mask(source_folder, mask_polygon, target_folder, name_append)
        pass


if __name__ == '__main__':
    # mask_polygon = 'odata/border_RA_biased.geojson'
    # source_shape = json.load(open(r'F:\01 - L3\Shenzhen CityScope\data\problem.json', 'r', encoding='utf-8'))
    # save_file = 'pro.geojson'
    # x = clip_on_shapes(source_shape, mask_polygon, save_file)
    # c = x['features'][0]['geometry']['coordinates']
    # print(len(c))
    # exit()
    main()