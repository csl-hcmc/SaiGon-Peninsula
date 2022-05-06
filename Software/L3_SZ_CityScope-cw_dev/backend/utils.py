import h3.api.numpy_int as h3
import os, json, copy, random
import numpy as np
from collections import Counter
from functools import reduce
from numpyencoder import NumpyEncoder

#======================================#
#          Constants                   #
#======================================#
crs_lookup_name_to_code = {
    'urn:ogc:def:crs:OGC:1.3:CRS84': 4326,
    'urn:ogc:def:crs:EPSG::4547': 4547
}
crs_lookup_code_to_name = {v:k for k,v in crs_lookup_name_to_code.items()}


#======================================#
#             Class                    #
#======================================#
class LocationSetter:
    def __init__(self, bound_geojson_path, resolution_in, resolution_out, TN=None, num_close_nodes=5):
        bound_features = json.load(open(bound_geojson_path))['features']
        self.h3_cells_in = {resolution_in: [], resolution_out: []}
        for fea in bound_features:
            if fea['geometry']['type'] == 'Polygon':
                fea['geometry']['coordinates'] = [fea['geometry']['coordinates']]
            for poly_coords in fea['geometry']['coordinates']:
                this_fea = {'type': 'Polygon', 'coordinates': poly_coords}
                cells_with_res_in = h3.polyfill(this_fea, resolution_in, geo_json_conformant=True)
                cells_with_res_out = h3.polyfill(this_fea, resolution_out, geo_json_conformant=True)
                self.h3_cells_in[resolution_in].extend(list(cells_with_res_in))
                self.h3_cells_in[resolution_out].extend(list(cells_with_res_out))
        self.resolution_in = resolution_in
        self.resolution_out = resolution_out
        self.set_tn(TN, num_close_nodes)

    def set_location(self, coord=None, h3_cell=None, in_sim_area=None, resolution=None):
        if not resolution:
            resolution = self.resolution_in
        if resolution not in self.h3_cells_in:
            raise ValueError(f'Invalid resolution: {resolution}')
        if coord:
            h3_cell = h3.geo_to_h3(coord[1], coord[0], resolution)
        elif h3_cell:
            coord = h3.h3_to_geo(h3_cell)[::-1]
        else:
            raise ValueError(f'coord and h3_cell cannot be both None')
        if in_sim_area is None:
            in_sim_area = h3_cell in self.h3_cells_in[resolution]
        close_nodes = None
        if in_sim_area and self.TN:
            close_nodes = self.TN.get_closest_internal_nodes(coord, self.num_close_nodes)
        return {'h3': {resolution: h3_cell},
                'coord': coord,
                'in_sim_area': in_sim_area,
                'close_nodes': close_nodes}

    def set_tn(self, TN, num_close_nodes):
        self.TN = TN
        self.num_close_nodes = num_close_nodes



#======================================#
#          Functions                   #
#======================================#
def run_time(func):
    def wrapper(*args, **kw):
        t1 = time.time()
        res = func(*args, **kw)
        t2 = time.time()
        print('{:4.4f} secodns elasped for {}'.format(t2-t1, func.__name__))
        return res
    return wrapper


def parse_num(x, string_ok=False, nan_ok=False, bool_ok=True, digits=None):
    if type(x) == str and not string_ok:
        return None
    if type(x) == bool and not bool_ok:
        return None
    try:
        y = float(x)
        if digits is not None:
            y = round(y, digits)
        if np.isnan(y) and not nan_ok:
            return None
    except:
        return None
    return y

def get_first_n_digits(code, first_n_digits):
    if first_n_digits is None:
        return str(code)
    else:
        assert type(first_n_digits) == int and first_n_digits >= 1
        return str(code)[:first_n_digits]

def sample_by_p(spec_list, num):
    values = [item['value'] for item in spec_list]
    p = np.array([item['p'] for item in spec_list])
    p = p / p.sum()
    if num == 1:
        return np.random.choice(values, p=p)
    else:
        return np.random.choice(values, size=num, p=p).tolist()


def load_geojsons(geojson_path, idx_attr='idx', sort_by_idx=True):
    src_crs = None
    if not os.path.exists(geojson_path):
        print(f'Source geojson file not found:\n{os.path.abspath(geojson_path)}')
        return [], None
    geojson_content = json.load(open(geojson_path, 'r', encoding='utf-8'))
    if 'crs' in geojson_content:
        this_crs = geojson_content['crs']['properties']['name']
        this_crs = crs_lookup_name_to_code.get(this_crs, this_crs)
        if src_crs is None:
            src_crs = this_crs
    features = geojson_content['features']
    if sort_by_idx and idx_attr in features[0]['properties']:
        features.sort(key=lambda fea: fea['properties'][idx_attr])
    return features, src_crs


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


def flatten_grid_cell_attributes(type_def, height, attribute_names,
                                 area_per_floor, return_units=['area','pop']):
    """
    :param type_def:
    :param height:
    :param attribute_name:
    :param area_per_floor:
    :param return_units:
    :return:
    """
    if isinstance(height, list):
        height = height[-1]
    if type(attribute_names) != list:
        attribute_names = [attribute_names]
    if type(return_units) != list:
        return_units = [return_units]
    if 'sqm_pperson' in type_def:
        capacity_per_sqm = 1 / type_def['sqm_pperson']
    else:
        capacity_per_sqm = 0
    capacity_per_floor = capacity_per_sqm * area_per_floor
    rst = {}
    for attribute_name in attribute_names:
        if type_def[attribute_name] is not None:
            floor_assignments = random.choices(range(len(type_def[attribute_name])),
                                               weights=[group['p'] for group in type_def[attribute_name]],
                                               k=height)
            grid_cell_total = {}
            for i_g, group in enumerate(type_def[attribute_name]):
                num_floors = floor_assignments.count(i_g)
    #            total_floor_capacity=num_floors*capacity_per_floor
                for code in group['use']:
                    effective_num_floors_this_code = num_floors * group['use'][code]
                    if code in grid_cell_total:
                        grid_cell_total[code] += effective_num_floors_this_code
                    else:
                        grid_cell_total[code] = effective_num_floors_this_code
            for return_unit in return_units:
                if return_unit == 'floors':
                    rst.setdefault(attribute_name, {})[return_unit] = {code:value
                                                                       for code,value in grid_cell_total.items()}
                if return_units == 'area':
                    rst.setdefault(attribute_name, {})[return_unit] = {code: value * area_per_floor
                                                                       for code, value in grid_cell_total.items()}
                if return_units == 'capacity':
                    rst.setdefault(attribute_name, {})[return_unit] = {code: value * capacity_per_floor
                                                                       for code, value in grid_cell_total.items()}
                else:
                    print('Unrecognised return units')
    return rst


def num_neighbours_in_digraph(G, node):
    predecessors = list(G.predecessors(node))
    successors = list(G.successors(node))
    return len(set(predecessors + successors))


