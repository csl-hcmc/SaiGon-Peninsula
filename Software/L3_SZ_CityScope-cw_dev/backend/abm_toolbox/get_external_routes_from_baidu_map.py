import requests
import pandas as pd
import json, pickle
import time
import os
import pymongo
# from coordTransform_utils import bd09_to_wgs84
import matplotlib.pyplot as plt
import numpy as np
import h3.api.numpy_int as h3
from numpyencoder import NumpyEncoder
from shapely.geometry import shape

AK = '7qdhm1YO5gIn2Po2opvueIVbzQwK1XnR'


def get_route_detailed(mode, origin_lng, origin_lat, destination_lng, destination_lat, ak=None):
    if mode == 'pt':
        url = "http://api.map.baidu.com/direction/v2/transit"
    elif mode == 'cycle':
        url = "https://api.map.baidu.com/direction/v2/riding"
    elif mode == 'driving':
        url = "https://api.map.baidu.com/direction/v2/driving"
    else:
        raise ValueError(f'Mode must be one of "pt", "cycle", "driving": {mode}')

    if not ak:
        ak = AK
    params = {
        'origin': f'{round(origin_lat, 6)},{round(origin_lng, 6)}',
        'destination': f'{round(destination_lat, 6)},{round(destination_lng, 6)}',
        'page_size': 10,
        'page_index': 1,
        'ak': ak,
        'coord_type': 'wgs84',
        'output': 'json'
    }
    if mode in ['pt']:
        params['departure_time'] = '08:00'
    try:
        r = requests.get(url, params=params)
        rst = json.loads(r.text)
    except Exception as e:
        print(e)
        rst = None
    return rst


def get_route_light(mode, origin_lng, origin_lat, destination_lng, destination_lat, ak=None):
    if mode == 'pt':
        url = "https://api.map.baidu.com/directionlite/v1/transit"
    elif mode == 'cycle':
        url = "https://api.map.baidu.com/directionlite/v1/riding"
    elif mode == 'driving':
        url = "https://api.map.baidu.com/directionlite/v1/driving"
    elif mode == 'walking':
        url = "https://api.map.baidu.com/directionlite/v1/walking"
    else:
        raise ValueError(f'Mode must be one of "pt", "cycle", "driving", "walking": {mode}')

    if not ak:
        ak = AK
    params = {
        'origin': f'{round(origin_lat, 6)},{round(origin_lng, 6)}',
        'destination': f'{round(destination_lat, 6)},{round(destination_lng, 6)}',
        'ak': ak,
        'coord_type': 'wgs84'
    }
    if mode in ['pt']:
        params['departure_time'] = '08:00'
    try:
        r = requests.get(url, params=params)
        rst = json.loads(r.text)
    except Exception as e:
        print('Get route error')
        print(e)
        rst = None
    return rst


def save(rst, json_path, pickle_path):
    this_port_rst = rst
    this_port_rst_json_save_path = json_path
    this_port_rst_pickle_save_path = pickle_path
    try:
        json.dump(this_port_rst, open(this_port_rst_json_save_path, 'w'), ensure_ascii=False)
    except Exception as e:
        print('Fail to save json result')
        print(e)
    pickle.dump(this_port_rst, open(this_port_rst_pickle_save_path, 'wb'))


def batch_get_routes_from_h3_to_ports(ports_geojson_path, h3_cells):
    ts = time.time()
    port_features = json.load(open(ports_geojson_path, 'r'))['features']
    num_cells = len(h3_cells)
    ports = {}
    for port in port_features:
        pid = port['properties']['id']
        p_shape = shape(port['geometry'])
        p_coord = (p_shape.centroid.x, p_shape.centroid.y)
        ports[f'p{pid}'] = p_coord
    for pid, p_coord in ports.items():
        print(f'\n\nNow working on port {pid}')
        print('='*40)
        this_port_rst_save_dir = os.path.abspath('external_routes')
        if not os.path.exists(this_port_rst_save_dir):
            os.makedirs(this_port_rst_save_dir)
        this_port_rst_json_save_path = os.path.join(this_port_rst_save_dir, f'{pid}.json')
        this_port_rst_pickle_save_path = os.path.join(this_port_rst_save_dir, f'{pid}.p')
        if os.path.exists(this_port_rst_json_save_path):
            this_port_rst = json.load(open(this_port_rst_json_save_path))
        elif os.path.exists(this_port_rst_pickle_save_path):
            this_port_rst = pickle.load(open(this_port_rst_pickle_save_path, 'rb'))
        else:
            this_port_rst = {
                'port': {'pid': pid, 'p_coord': p_coord},
                'result': {}
            }
        last_time = time.time()
        for h3_cell_idx, h3_cell in enumerate(h3_cells):
            if h3_cell_idx % 100 == 0:
                current_time = time.time()
                print('current={}, total={}, percent={:4.3f}%, time={:4.3f}sec, now={}'.format(
                    h3_cell_idx, num_cells, 100*h3_cell_idx/num_cells, current_time-last_time,
                    time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(time.time()))))
                last_time = current_time
                save(this_port_rst, this_port_rst_json_save_path, this_port_rst_pickle_save_path)
            h3_cell_coords = h3.h3_to_geo(h3_cell)
            h3_cell_str = str(h3_cell)
            for mode in ['pt', 'cycle', 'driving', 'walking']:
                if mode in this_port_rst['result'].get(h3_cell_str, {}) and this_port_rst[
                    'result'].get(h3_cell_str, {}).get(mode, None) is not None:
                    continue
                this_rst = get_route_light(mode=mode,
                                           origin_lng=h3_cell_coords[1],
                                           origin_lat=h3_cell_coords[0],
                                           destination_lng=p_coord[0],
                                           destination_lat=p_coord[1])
                if h3_cell_str not in this_port_rst['result']:
                    this_port_rst['result'][h3_cell_str] = {}
                this_port_rst['result'][h3_cell_str][mode] = this_rst
        save(this_port_rst, this_port_rst_json_save_path, this_port_rst_pickle_save_path)
        print(f'Port {pid} finished')
    te = time.time()
    print('Total time cost: {:4.4f} seconds'.format(te-ts))



def batch_get_routes_from_h3_to_ports_db(ports_geojson_path, h3_cells, db_name='external_routes'):
    client = pymongo.MongoClient('localhost', 27017)
    db = client[db_name]
    ts = time.time()
    port_features = json.load(open(ports_geojson_path, 'r'))['features']
    num_cells = len(h3_cells)
    ports = {}
    for port in port_features:
        pid = port['properties']['id']
        p_shape = shape(port['geometry'])
        p_coord = (p_shape.centroid.x, p_shape.centroid.y)
        ports[pid] = p_coord
    for pid, p_coord in ports.items():
        print(f'\n\nNow working on port {pid}')
        print('='*40)
        col = db[pid]
        last_time = time.time()
        for h3_cell_idx, h3_cell in enumerate(h3_cells):
            if h3_cell_idx % 100 == 0:
                current_time = time.time()
                print('current={}, total={}, percent={:4.3f}%, time={:4.3f}sec, now={}'.format(
                    h3_cell_idx, num_cells, 100*h3_cell_idx/num_cells, current_time-last_time,
                    time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(time.time()))))
                last_time = current_time
            h3_cell_coords = h3.h3_to_geo(h3_cell)
            h3_cell_str = str(h3_cell)
            for mode in ['pt', 'cycle', 'driving', 'walking']:
                existed = list(col.find({'h3_cell': h3_cell_str, 'mode': mode}))
                if len(existed) > 0 and existed[0]['route']['status'] != 1:
                    continue
                print(f'    Looking for: from {h3_cell_str} to {pid} by {mode}')
                this_rst = get_route_light(mode=mode,
                                           origin_lng=h3_cell_coords[1],
                                           origin_lat=h3_cell_coords[0],
                                           destination_lng=p_coord[0],
                                           destination_lat=p_coord[1])
                if this_rst:
                    wrap_rst = {
                        'h3_cell': h3_cell_str,
                        'mode': mode,
                        'route': this_rst
                    }
                    col.insert_one(wrap_rst)
        print(f'Port {pid} finished')
    te = time.time()
    print('Total time cost: {:4.4f} seconds'.format(te-ts))



def get_h3_cells(geojson_path, resolution):
    features = json.load(open(geojson_path))['features']
    h3_cells = []
    for fea in features:
        if fea['geometry']['type'] == 'Polygon':
            fea['geometry']['coordinates'] = [fea['geometry']['coordinates']]
        # if fea['geometry']['type'] == 'MultiPolygon':
        #     fea['geometry']['type'] = 'Polygon'
        #     fea['geometry']['coordinates'] = fea['geometry']['coordinates'][0]
        # print(fea)
        for poly_coords in fea['geometry']['coordinates']:
            this_fea = {'type': 'Polygon', 'coordinates': poly_coords}
            try:
                this_cells = h3.polyfill(this_fea, resolution, geo_json_conformant=True)
            except:
                print(fea)
                exit()
            h3_cells += list(this_cells)
    return h3_cells


def export_h3_features(h3_stats, save_to=None):
    if type(h3_stats) == list:
        h3_stats = {h3_cell:{} for h3_cell in h3_stats}
    h3_features = []
    for h3_cell, properties in h3_stats.items():
        h3_boundary = h3.h3_to_geo_boundary(h3_cell, geo_json=True)
        h3_boundary = [list(coord) for coord in h3_boundary]  # tuple -> list
        properties['h3_id'] = h3_cell
        h3_features.append({
            "type": "Feature",
            "properties": properties,
            "geometry": {
                "type": "Polygon",
                "coordinates": [h3_boundary]
            }
        })
    if save_to:
        save_fname = os.path.basename(save_to).split('.')[0]
        h3_geojson_content = {
            "type": "FeatureCollection",
            "name": save_fname,
            "crs": {
                "type": "name",
                "properties": {
                    "name": "urn:ogc:def:crs:OGC:1.3:CRS84"
                }
            },
            "features": h3_features
        }
        json.dump(h3_geojson_content, open(save_to, 'w', encoding='utf-8'),
                  indent=4, ensure_ascii=False, cls=NumpyEncoder)
    return h3_features


def test():
    mode = 'driving'
    origin_lat = 22.60142937
    origin_lng = 113.8813341
    destination_lat = 22.55186403
    destination_lng = 114.0510859
    origin_place = '（博智中心）广东省深圳市宝安区宝田一路62号'
    desination_place = '（景田南五街福田区景田金色假日(景田南五街东)）广东省深圳市福田区'
    rst1 = get_route_light(mode, origin_lng, origin_lat, destination_lng, destination_lat)
    rst2 = get_route_detailed(mode, origin_lng, origin_lat, destination_lng, destination_lat)
    rst = {'light': rst1, 'detailed': rst2}
    json.dump(rst, open('driving.json', 'w'), indent=4, ensure_ascii=False)
    print(rst1)


def test2():
    t1 = time.time()
    geojson_path = '../cities/shenzhen/geojson/taz.geojson'
    resolution = 9
    cells = get_h3_cells(geojson_path, resolution)
    t2 = time.time()
    h3_stats = {cell:{} for cell in cells}
    export_h3_features(h3_stats, f'sz_whole_res_{resolution}.geojson')
    t3 = time.time()
    print(len(cells), t2-t1, t3-t2)

def test3():
    ports_geojson_path = '../cities/shenzhen/geojson/ports.geojson'
    taz_geojson_path = '../cities/shenzhen/geojson/taz.geojson'
    resolution = 8
    h3_cells = get_h3_cells(taz_geojson_path, resolution)
    batch_get_routes_from_h3_to_ports_db(ports_geojson_path, h3_cells)



if __name__ == '__main__':
    test3()