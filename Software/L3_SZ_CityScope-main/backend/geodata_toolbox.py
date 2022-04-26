import h3.api.numpy_int as h3
import os, json, copy, re, random
import geopandas as gpd
import matplotlib.pyplot as plt
import h3pandas
from pyproj import Transformer, CRS
from shapely.geometry import Point, LineString, MultiLineString, shape
from shapely.geometry.polygon import Polygon
import numpy as np
from collections import Counter
from functools import reduce
from numpyencoder import NumpyEncoder

crs_lookup_name_to_code = {
    'urn:ogc:def:crs:OGC:1.3:CRS84': 4326,
    'urn:ogc:def:crs:EPSG::4547': 4547
}
crs_lookup_code_to_name = {v:k for k,v in crs_lookup_name_to_code.items()}

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

def flatten_grid_cell_attributes(type_def, height, attribute_name,
                                 area_per_floor, return_units='capacity'):
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
    grid_cell_total = {}
    if type_def[attribute_name] is not None:
        if 'sqm_pperson' in type_def:
            capacity_per_sqm = 1 / type_def['sqm_pperson']
        else:
            capacity_per_sqm=0
        capacity_per_floor = capacity_per_sqm * area_per_floor
        floor_assignments = random.choices(range(len(type_def[attribute_name])),
                                           weights=[group['p'] for group in type_def[attribute_name]],
                                           k=height)
        for i_g, group in enumerate(type_def[attribute_name]):
            num_floors = floor_assignments.count(i_g)
#            total_floor_capacity=num_floors*capacity_per_floor
            for code in group['use']:
                effective_num_floors_this_code = num_floors * group['use'][code]
                if code in grid_cell_total:
                    grid_cell_total[code] += effective_num_floors_this_code
                else:
                    grid_cell_total[code] = effective_num_floors_this_code
    if return_units == 'floors':
        return grid_cell_total
    elif return_units == 'capacity':
        for code in grid_cell_total:
            grid_cell_total[code] *= capacity_per_floor
        return grid_cell_total
    elif return_units == 'area':
        for code in grid_cell_total:
            grid_cell_total[code] *= area_per_floor
        return grid_cell_total
    else:
        print('Unrecognised return units')



class GeoData:
    def __init__(self, name, src_geojson_path=None, table='shenzhen', proj_crs=None):
        self.table = table
        self.name = name
        if src_geojson_path is not None and not os.path.exists(src_geojson_path):
            src_geojson_path = os.path.join('cities', table, 'geojson', src_geojson_path)
        self.src_geojson_path = src_geojson_path
        self.crs = {'src': 'src', 'geographic':4326, 'projected':proj_crs}
        self.features = {}
        self.transformer = {}
        self.shapely_objects = {}
        self.map_to_h3_cells = {}
        self.h3_stats = {}
        if src_geojson_path:
            self.load_data(to_4326=True, to_shapely=True)

    def load_data(self, to_4326, to_shapely):
        geojson_path_list = self.src_geojson_path
        features, src_crs = load_geojsons(geojson_path_list)
        self.crs['src'] = src_crs
        self.features[self.crs['src']] = features
        if CRS(self.crs['src']).is_projected and self.crs['projected'] is None:
            self.crs['projected'] = self.crs['src']
        if not self.crs['projected']:
            print('Error: must either specify projected crs or load geojson files with projected crs')
            exit()
        # get features with epsg4326
        if self.crs['src'] == 4326:
            pass
        elif to_4326:
            self.features[4326] = self.convert_crs_for_features(4326)
        else:
            self.features[4326] = None

        # get shapely objects with epsg4326
        if to_shapely:
            self.convert_to_shapely(crs=4326, self_update=True)


    def _convert_to_shapely(self, feature):
        try:
            shapely_object = shape(feature['geometry'])
        except:
            shapely_object = None
        return shapely_object

    def convert_to_shapely(self, crs=None, self_update=True):
        if not self.features:
            return
        if not crs:
            crs = self.crs['src']
        if crs in self.features:
            features = self.features[crs]
        else:
            features = self.convert_crs_for_features(crs)
        shapely_objects = []

        for fea in features:
            shapely_object = self._convert_to_shapely(fea)
            shapely_objects.append(shapely_object)
        if self_update:
            self.shapely_objects[crs] = shapely_objects
        return shapely_objects


    def _convert_crs(self, feature, to_crs, from_crs, in_place=True):
        if not from_crs in self.transformer or to_crs not in self.transformer[from_crs]:
            transformer = Transformer.from_crs(from_crs, to_crs)
            self.transformer.setdefault(from_crs, {})[to_crs] = transformer
        else:
            transformer = self.transformer[from_crs][to_crs]
        if not in_place:
            feature = copy.deepcopy(feature)
        if feature['geometry']['type'] == 'MultiPolygon':
            for polygon in feature['geometry']['coordinates']:
                for line in polygon:
                    for coord in line:
                        new_coord = transformer.transform(coord[1], coord[0])
                        coord[0], coord[1] = new_coord[1], new_coord[0]
        elif feature['geometry']['type'] == 'Polygon':
            for line in feature['geometry']['coordinates']:
                for coord in line:
                    new_coord = transformer.transform(coord[1], coord[0])
                    coord[0], coord[1] = new_coord[1], new_coord[0]
        elif feature['geometry']['type'] == 'Point':
            coord = feature['geometry']['coordinates']
            new_coord = transformer.transform(coord[1], coord[0])
            coord[0], coord[1] = new_coord[1], new_coord[0]
        elif feature['geometry']['type'] == 'MultiPoint':
            for coord in feature['geometry']['coordinates']:
                new_coord = transformer.transform(coord[1], coord[0])
                coord[0], coord[1] = new_coord[1], new_coord[0]
        elif feature['geometry']['type'] == 'MultiLineString':
            for line in feature['geometry']['coordinates']:
                for coord in line:
                    new_coord = transformer.transform(coord[1], coord[0])
                    coord[0], coord[1] = new_coord[1], new_coord[0]
        elif feature['geometry']['type'] == 'LineString':
            for coord in feature['geometry']['coordinates']:
                new_coord = transformer.transform(coord[1], coord[0])
                coord[0], coord[1] = new_coord[1], new_coord[0]
        return feature


    def convert_crs_for_features(self, to_crs, from_crs=None, save_to=None):
        if not from_crs:
            from_crs = self.crs['src']
        features = copy.deepcopy(self.features[from_crs])
        for fea in features:
            self._convert_crs(fea, to_crs, from_crs)
        if save_to:
            name = os.path.basename(save_to).split('.')[0]
            geojson_content_to_save = {
                "type": "FeatureCollection",
                "name": name,
                "crs": {
                    "type": "name",
                    "properties": {
                        "name": crs_lookup_code_to_name[to_crs]
                    }
                },
                "features": features
            }
            json.dump(geojson_content_to_save, open(save_to, 'w', encoding='utf-8'),
                      indent=4, ensure_ascii=False, cls=NumpyEncoder)
        return features

    def aggregate_attrs_to_cells(self, cells_to_map, features, agg_attrs={}, agg_save_names=None, use_weight=True):
        if agg_save_names is None:
            agg_attr_names = [f'[{self.name}]_{attr}_({agg_method})' for attr, agg_method in agg_attrs.items()]
        assert len(agg_attr_names) == len(agg_attrs)
        h3_stats = {}
        weights = {}
        for cells_info, fea in zip(cells_to_map, features):
            for cell, info in cells_info.items():
                if cell not in h3_stats:
                    h3_stats[cell] = {agg_save_name:[] for agg_save_name in agg_attr_names}
                for attr, agg_save_name in zip(agg_attrs, agg_attr_names):
                    h3_stats[cell][agg_save_name].append(fea['properties'].get(attr, None))
                weights[cell] = weights.setdefault(cell, []) + [info['weight_in_raw_data']]

        # now we have list, and then do aggregation
        for attr, agg_save_name in zip(agg_attrs, agg_attr_names):
            agg_method = agg_attrs[attr]
            if agg_method == 'list':
                pass
            elif agg_method == 'count':
                for cell in h3_stats.keys():
                    if not use_weight:
                        h3_stats[cell][agg_save_name] = len(h3_info[cell][agg_save_name])
                    else:
                        h3_stats[cell][agg_save_name] = sum(weights[cell])
            elif agg_method in ['sum', 'mean', 'min', 'max']:
                for cell in h3_stats.keys():
                    data_to_agg = h3_stats[cell][agg_save_name]
                    weight_to_agg = weights[cell]
                    # get rid of invalid value
                    if not use_weight:
                        data_to_agg = [d for d in data_to_agg if parse_num(d) is not None]
                    else:
                        data_to_agg = [d*wei for d,wei in zip(data_to_agg, weight_to_agg)
                                       if parse_num(d) is not None]
                    if agg_method == 'sum':
                        h3_stats[cell][agg_save_name] = sum(data_to_agg)
                    elif agg_method == 'mean':
                        h3_stats[cell][agg_save_name] = sum(data_to_agg) / len(data_to_agg)
                    elif agg_mthod == 'min':
                        h3_stats[cell][agg_save_name] = mean(data_to_agg)
                    elif agg_method == 'max':
                        h3_stats[cell][agg_save_name] = max(data_to_agg)
        return h3_stats

    def export_h3_features(self, resolution, save_to=None):
        if not self.h3_stats:
            print('Error: must have h3_info first')
            return
        h3_stats = self.h3_stats[resolution]
        h3_features = export_h3_features(h3_stats, save_to)
        return h3_features

    def export_geojson(self, crs=None, save_to=None):
        if not save_to:
            return
        if crs is None:
            crs = self.crs['src']
        features = self.features[crs]
        name = os.path.basename(save_to).split('.')[0]
        geojson_content_to_save = {
            "type": "FeatureCollection",
            "name": name,
            "crs": {
                "type": "name",
                "properties": {
                    "name": crs_lookup_code_to_name[crs]
                }
            },
            "features": features
        }
        json.dump(geojson_content_to_save, open(save_to, 'w', encoding='utf-8'),
                  indent=4, ensure_ascii=False, cls=NumpyEncoder)


    def plot(self, features=None, crs=None, ax=None, value=None, **kargs):
        if crs is None:
            crs = self.crs['geographic']
        if features is None:
            features = self.features[self.crs['geographic']]
        elif type(features) == dict:
            features = features[crs]
        features = copy.deepcopy(features)
        for fea in features:
            fea['geometry'] = shape(fea['geometry'])
        gdf = gpd.GeoDataFrame(features, crs=f'EPSG:{crs}')
        if ax:
            if not value:
                gdf.plot(ax=ax, **kargs)
            else:
                gdf['value'] = value
                gdf.plot(ax=ax, column='value', **kargs)
        else:
            if not value:
                ax = gdf.plot(**kargs)
            else:
                gdf['value'] = value
                ax = gdf.plot(column='value', **kargs)
        plt.axis('equal')
        plt.axis('off')
        return ax

class PointGeoData(GeoData):

    def link_to_h3(self, resolution=12):
        features_to_h3_cells = []
        for fea in self.features[self.crs['geographic']]:
            coord = fea['geometry']['coordinates']
            if fea['geometry']['type'] == 'MultiPoint':
                coord = coord[0]
            h3_cell = h3.geo_to_h3(coord[1], coord[0], resolution)
            features_to_h3_cells.append(h3_cell)
        self.map_to_h3_cells[resolution] = features_to_h3_cells

    def make_h3_stats(self, resolution, agg_attrs={}, count=True):
        if resolution not in self.map_to_h3_cells:
            self.link_to_h3(resolution)
        features_to_h3_cells = self.map_to_h3_cells[resolution]
        h3_cells_to_map = [{h3_cell: {'weight_in_raw_data': 1}} for h3_cell in features_to_h3_cells]
        h3_stats = self.aggregate_attrs_to_cells(h3_cells_to_map, self.features[self.crs['src']], agg_attrs)
        if count:
            counter = Counter(features_to_h3_cells)
            for cell, num in counter.items():
                h3_stats[cell][f'{self.name}_count'] = num
        self.h3_stats[resolution] = h3_stats


class PolygonGeoData(GeoData):

    def _get_buffer(self, feature_idx, buffer_dist, to_crs):
        # step.1 get shapely object in projected CRS so that unit is meter
        if self.crs['projected'] not in self.shapely_objects:
            self.convert_to_shapely(self.crs['projected'], self_update=True)
        polygon_shapely_object_projected = self.shapely_objects[self.crs['projected']][feature_idx]
        # step.3 get buffered shapely object in projected CRS
        buffered_polygon_shapely_object_projected = polygon_shapely_object_projected.buffer(buffer_dist)
        # step.4 get coordinates and geojson feature
        coords = list(buffered_polygon_shapely_object_projected.exterior.coords)
        buffered_polygon_coords_projected = [[[coord[0], coord[1]] for coord in coords]]
        buffered_feature_projected = {
            'geometry': {
                'type': 'Polygon',
                'coordinates': buffered_polygon_coords_projected
            }
        }
        # step.5 convert CRS back to "to_crs"
        if to_crs != self.crs['projected']:
            buffered_feature = self._convert_crs(buffered_feature_projected, to_crs=to_crs,
                                                 from_crs=self.crs['projected'], in_place=False)
        else:
            buffered_feature = buffered_feature_projected
        return buffered_feature

    def link_to_h3(self, resolution=11, self_update=True):
        features_to_h3_cells = []
        h3_shapely_objects = {}
        buffer_dist = h3.edge_length(resolution, unit='m')
        for fea_idx, fea in enumerate(self.features[4326]):
            polygon_shapely_object = self.shapely_objects[4326][fea_idx]
            # add buffer to make sure all related h3 cells could be found, need 4 steps:
            buffered_geojson_geometry = self._get_buffer(fea_idx, buffer_dist*1.1, 4326)['geometry']
            polygon_area = polygon_shapely_object.area
            h3_cells = h3.polyfill(buffered_geojson_geometry, resolution, True)
            h3_cells_detailed = {}
            for h3_cell in h3_cells:
                if h3_cell not in h3_shapely_objects:
                    h3_shapely_object = Polygon(h3.h3_to_geo_boundary(h3_cell, geo_json=True))
                else:
                    h3_shapely_object = h3_shapely_objects[h3_cell]
                h3_area = h3_shapely_object.area
                intersection_area = polygon_shapely_object.intersection(h3_shapely_object).area
                if intersection_area == 0:
                    continue
                area_ratio_in_polygon = intersection_area / polygon_area
                area_ratio_in_h3 = intersection_area / h3_area
                h3_cells_detailed[h3_cell] = {
                    'intersection_area': intersection_area,
                    'weight_in_raw_data': area_ratio_in_polygon,
                    'weight_in_new_data': area_ratio_in_h3,
                }
            features_to_h3_cells.append(h3_cells_detailed)
            # print(fea_idx, ': ', sum([v['weight_in_raw_data'] for v in h3_cells_detailed.values()]))
        if self_update:
            self.map_to_h3_cells[resolution] = features_to_h3_cells
        return features_to_h3_cells

    def make_h3_stats(self, resolution, agg_attrs={}):
        if resolution not in self.map_to_h3_cells:
            self.link_to_h3(resolution)
        features_to_h3_cells = self.map_to_h3_cells[resolution]
        h3_stats = self.aggregate_attrs_to_cells(features_to_h3_cells, self.features[self.crs['src']], agg_attrs, use_weight=True)
        self.h3_stats[resolution] = h3_stats


class TableGrids(PolygonGeoData):
    def __init__(self, name, h3_resolution, H3=None, src_geojson_path=None,
                 table='shenzhen', proj_crs=None, spec_json_path=''):
        super().__init__(name, src_geojson_path, table, proj_crs)
        assert 4326 in self.features and 4326 in self.shapely_objects
        self._get_spec(spec_json_path)
        self.setup_grid_idx()
        self.setup_interactive_grid()

        self.grid_centroids = [[obj.centroid.x, obj.centroid.y] for obj in self.shapely_objects[4326]]
        self.upstream_h3_cells = {}
        self.required_h3_cells = {}
        self.get_required_h3_cells(h3_resolution)
        if H3:
            H3.required_cells = self.required_h3_cells[H3.resolution]
            self.H3 = H3
        else:
            self.H3 = H3Grids(h3_resolution, self.required_h3_cells[h3_resolution])
        self.values = {}

    def _get_spec(self, spec_json_path):
        use_spec_json_path = ''
        for try_spec_path in [spec_json_path,
                              os.path.join('cities',self.table,'clean',spec_json_path),
                              os.path.join('cities', self.table, 'clean', 'table_grid_spec.json')]:
            if os.path.exists(try_spec_path) and os.path.isfile(try_spec_path):
                use_spec_json_path = try_spec_path
                break
        if use_spec_json_path:
            self.spec = json.load(open(use_spec_json_path, 'r'))
            self.land_type_def = self.spec.get('land_type_def', {})
        else:
            self.spec = {}
            self.land_type_def = {}
            print('Warning: there is no valid specification for this grids.')


    def get_grid_value_from_h3_cells(self, resolution, h3_attr=None, table_attr=None, self_update=True):
        if not h3_attr:
            h3_attr = list(self.H3.values.keys())[0]
        if not table_attr:
            table_attr = h3_attr
        values = []
        for h3_cell in self.upstream_h3_cells:
            try:
                grid_value = self.H3.values[h3_attr][h3_cell]
            except:
                grid_value = None
            values.append(grid_value)
        if self_update:
            self.values[table_attr] = values
        return values


    def update(self, layout_str):
        self.update_interactive_grid_layout(layout_str)
        self.map_interactive_grid_layout_to_h3_cells()


    def map_interactive_grid_layout_to_h3_cells(self, resolution=None, attr_name='lbcs', return_units='area'):
        H3 = self.H3
        if not resolution:
            resolution = H3.resolution
        if resolution not in self.map_to_h3_cells:
            self.link_to_h3(resolution)
        grids_to_h3_cells = self.map_to_h3_cells[resolution]
        interactive_grids_to_h3_cells, interactive_features, interactive_attrs = [], [], []
        for zone, zone_layout in self.interactive_grid_layout.items():
            for cell_idx, cell_state in zone_layout.items():
                if cell_state['code'] == -1:
                    continue
                if str(cell_state['code']) not in self.land_type_def:
                    print(f'Cannot find type_def for code={cell_state["code"]}')
                    continue
                type_def = self.land_type_def[str(cell_state['code'])]
                height = cell_state['height'] if cell_state['height'] else type_def['default_height']
                interactive_grids_to_h3_cells.append(grids_to_h3_cells[cell_idx])
                cell_stats = flatten_grid_cell_attributes(type_def, height,
                                                          attribute_name=attr_name,
                                                          area_per_floor=self.spec['cell_area'],
                                                          return_units=return_units)
                # show return_units, such as: 1100 -> 1100_area
                cell_stats = {f'{k}_{return_units}': v for k, v in cell_stats.items()}
                interactive_attrs += list(cell_stats.keys())
                interactive_features.append({'properties': cell_stats})
        interactive_attrs = list(set(interactive_attrs))
        h3_stats = self.aggregate_attrs_to_cells(interactive_grids_to_h3_cells,
                                                 interactive_features,
                                                 agg_attrs = {attr:'sum' for attr in interactive_attrs},
                                                 use_weight = True)
        self.h3_stats[resolution] = h3_stats
        H3.h3_stats = H3.combine_h3_stats([
            H3.h3_stats_base, h3_stats
        ], agg='sum')


    def setup_grid_idx(self, save_to=True):
        if 'idx' not in self.features[self.crs['src']][0]['properties']:
            if self.spec:
                self._auto_set_grid_idx(save_to)
            else:
                for serialno in range(len(self.features[self.crs['src']])):
                    for crs in self.features.keys():
                        self.features[crs][idx]['properties'].update({'idx': serialno})
                if save_to == True:
                    save_to = self.src_geojson_path
                if save_to:
                    self.export_geojson(self.crs['src'], save_to)
            # reorder the features according to idx
            idx_list = [fea['properties']['idx'] for fea in self.features[self.crs['src']]]
            order = np.argsort(idx_list)
            for crs in self.features:
                self.features[crs] = [self.features[crs][i] for i in order]
            for crs in self.shapely_objects:
                self.shapely_objects[crs] = [self.shapely_objects[crs][i] for i in order]

        else:
            pass   # grid idx have are stored in geojson and have been read to self.features

    def _auto_set_grid_idx(self, save_to=True):
        try:
            origin_coord = np.asarray(self.spec['auto_indexing']['origin_coord'])
            col_unit_coord = np.asarray(self.spec['auto_indexing']['col_unit_coord'])
            row_unit_coord = np.asarray(self.spec['auto_indexing']['row_unit_coord'])
            crs = self.spec['auto_indexing'].get('crs', None)
            ncol = self.spec['ncol']
        except:
            print('Cannot get auto-indexing information from specification')
            return
        if not crs:
            crs = self.crs['src']
        x_vector = col_unit_coord - origin_coord
        y_vector = row_unit_coord - origin_coord
        if crs not in self.features:
            features = self.convert_crs_for_features(crs)
        else:
            features = self.features[crs]

        for serialno, fea in enumerate(features):
            shape_obj = self._convert_to_shapely(fea)
            cx, cy = shape_obj.centroid.x, shape_obj.centroid.y
            vector = np.asarray([cx, cy]) - origin_coord
            row_idx = int(round((vector * y_vector).sum() / (y_vector * y_vector).sum()))
            column_idx = int(round((vector * x_vector).sum() / (x_vector * x_vector).sum()))
            overall_idx = 0 + row_idx * ncol + column_idx
            for crs_key in self.features.keys():
                self.features[crs_key][serialno]['properties'].update(
                    {'row_idx': row_idx, 'column_idx': column_idx, 'idx': overall_idx}
                )
        if save_to == True:
            save_to = self.src_geojson_path
        if save_to:
            self.export_geojson(self.crs['src'], save_to)

    def _get_grid_by_idx(self, idx, crs=None):
        if not crs:
            crs = self.crs['src']
        return self.features[crs][idx]

    def setup_interactive_grid(self, save_to=True):
        if 'is_interactive' not in self.features[self.crs['src']][0]['properties']:
            if not self.spec and False:
                print('There is no grid specification and thus interactive grids can not ge set')
                return
            for crs in self.features.keys():
                for fea in self.features[crs]:
                    fea['properties'].update({
                        'is_interactive': 0,
                        'interactive_zone': -1
                    })
            interactive_grid_index = self.spec['interactive_grid_index']
            interactive_grid_layout = {}
            for zone, idx_list in interactive_grid_index.items():
                interactive_grid_layout[zone] = {}
                for idx in idx_list:
                    interactive_grid_layout[zone][idx] = -1
                    for crs in self.features.keys():
                        self._get_grid_by_idx(idx, crs)['properties'].update(
                            {'is_interactive': 1, 'interactive_zone': zone}
                        )
            self.interactive_grid_layout = interactive_grid_layout
        else:
            pass  # interactive grid index are stored in geojson and has already load to self.features
        self._init_interactive_grid_layout()

    def _init_interactive_grid_layout(self):
        interactive_grid_layout = {}
        for zone, idx_list in self.spec['interactive_grid_index'].items():
            interactive_grid_layout[zone] = {
                idx: {'code':-1, 'height':None}
                for idx in idx_list
            }
        self.interactive_grid_layout = interactive_grid_layout


    def update_interactive_grid_layout(self, layout_str):
        # how to update height individually?
        tmp = [x for x in layout_str.strip().split(' ')]
        this_zone = tmp[0].strip()
        assert this_zone.startswith('i')
        this_zone = this_zone[1:]
        this_layout = [int(x) for x in tmp[1:]]
        grid_index_in_this_zone = list(self.interactive_grid_layout[this_zone].keys())
        if len(this_layout) != len(grid_index_in_this_zone):
            print("#elements in the string ({}) does not match with #grids ({}), layout skipped.".format(
                len(this_layout), len(indices)))
        self.interactive_grid_layout[this_zone] = {
            idx: {'code': type_code, 'height': None}
            for idx, type_code in zip(grid_index_in_this_zone, this_layout)
        }



    def set_random_value_on_h3_cells(self, resolution, h3_cells=None):
        if not h3_cells:
            h3_cells = self.required_h3_cells.get(
                resolution, self.get_required_h3_cells(resolution)
            )
        tmp = np.random.rand(len(h3_cells))
        rand_data = {cell:d for cell, d in zip(h3_cells, tmp)}
        self.H3.values['rand'] = rand_data
        return rand_data

    def get_required_h3_cells(self, resolution):
        upstream_h3_cells = [h3.geo_to_h3(c[1], c[0], resolution) for c in self.grid_centroids]
        self.upstream_h3_cells = upstream_h3_cells
        required_h3_cells = list(set(upstream_h3_cells))
        if resolution not in self.required_h3_cells:
            self.required_h3_cells[resolution] = required_h3_cells
        return required_h3_cells


class H3Grids:
    def __init__(self, resolution, required_cells=[]):
        self.resolution = resolution
        self.required_cells = required_cells
        self.values= {}
        self.h3_stats = {}
        self.h3_stats_base = {}
        self.results = {}
        self.dist_lookup = {}

    def combine_h3_stats(self, h3_stats_list, missing_value=0, remove_prefix=True, remove_suffix=True, agg='sum'):
        h3_stats_list = [x for x in h3_stats_list if len(x)>0]   # get rid of empty h3_stats
        h3_cells = reduce(lambda x,y: x+y, [list(h3_stats.keys()) for h3_stats in h3_stats_list], [])
        h3_attrs = reduce(lambda x,y: x+y, [list(list(h3_stats.values())[0].keys()) for h3_stats in h3_stats_list], [])
        # print('Original attribute names:')
        # print(h3_attrs)
        h3_attrs_raw = copy.deepcopy(h3_attrs)
        if remove_prefix:
            prefix_pattern = re.compile('^\[.*\]_(.*)')
            prefix_match = [prefix_pattern.findall(attr) for attr in h3_attrs]
            h3_attrs = [match[0] if len(match)>0 else raw_attr for raw_attr, match in zip(h3_attrs, prefix_match)]
        if remove_suffix:
            suffix_pattern = re.compile('(.*)_\(.*\)$')
            suffix_match = [suffix_pattern.findall(attr) for attr in h3_attrs]
            h3_attrs = [match[0] if len(match)>0 else raw_attr for raw_attr, match in zip(h3_attrs, suffix_match)]
        h3_attrs_lookup = {raw: new for raw, new in zip(h3_attrs_raw, h3_attrs)}
        h3_attrs = list(set(h3_attrs))   # get rid of duplicated attr names
        # print('\nCombined attribute names:')
        # print(h3_attrs)
        combined_h3_stats = {
            h3_cell: {h3_attr: missing_value for h3_attr in h3_attrs}
            for h3_cell in h3_cells
        }
        for this_h3_stats in h3_stats_list:
            for h3_cell, attrs_dict in this_h3_stats.items():
                for attr, value in attrs_dict.items():
                    if agg == 'sum':
                        combined_h3_stats[h3_cell][h3_attrs_lookup[attr]] += value
                    elif agg == 'replace':
                        combined_h3_stats[h3_cell][h3_attrs_lookup[attr]] = value
        self.h3_stats = combined_h3_stats
        return combined_h3_stats

    def set_current_h3_stats_as_base(self):
        self.h3_stats_base = self.h3_stats

    def export_h3_features(self, save_to=None):
        if not self.h3_stats:
            print('Error: must have h3_info first')
            return
        h3_stats = self.h3_stats
        h3_features = export_h3_features(h3_stats, save_to)
        return h3_features

    def _get_h3_dist_lookup(self, from_h3_cells=None, to_h3_cells=None, Table=None, self_update=True):
        if not from_h3_cells:
            from_h3_cells = self.required_cells
        if not to_h3_cells:
            to_h3_cells = list(self.h3_stats.keys())
            if Table:
                if self.resolution in Table.map_to_h3_cells:
                    link_rst_list = Table.map_to_h3_cells[self.resolution]
                else:
                    link_rst_list = Table.link_to_h3(self.resolution, self_update=False)
                h3_cells_linked_to_table = reduce(lambda x,y: x+y,
                                                  [list(link_rst.keys()) for link_rst in link_rst_list],
                                                  [])
                to_h3_cells += h3_cells_linked_to_table
                to_h3_cells = list(set(to_h3_cells))

        inner_dist = h3.edge_length(self.resolution) / 2
        dist_lookup = {}
        for from_h3_cell in from_h3_cells:
            dist_lookup[from_h3_cell] = {
                to_h3_cell: h3.point_dist(h3.h3_to_geo(from_h3_cell), h3.h3_to_geo(to_h3_cell))
                if to_h3_cell != from_h3_cell else inner_dist
                for to_h3_cell in to_h3_cells
            }
        if self_update:
            self.dist_lookup = dist_lookup
        return dist_lookup






def main():
    # Parks = PointGeoData(table='shenzhen', name='parks', src_geojson_path=r'D:\L3\temp\sources\park_green_pois.geojson')
    # feaatures = Parks.convert_crs_for_features(4326, save_to='abc.geojson')
    # Parks.link_to_h3(12)
    # Parks.export_h3_features(12, save_to='bbb12.geojson')

    # Buildings = PolygonGeoData(table='shenzhen', name='buildings', src_geojson_path=r'D:\L3\to_jiwen\polygons\buildings.geojson')
    # Buildings.make_h3_stats(11, agg_attrs={'FLOOR_AREA': 'sum'})
    # # Buildings.export_h3_features(11, save_to='bldg11.geojson')
    # ax = Buildings.plot(facecolor='blue', edgecolor='grey', linewidth=1, zorder=2)
    # Buildings.make_h3_stats(12)
    # Buildings.make_h3_stats(11)
    # h3_features_12 = Buildings.export_h3_features(12)
    # h3_features_11 = Buildings.export_h3_features(12)
    # Buildings.plot(h3_features_12, ax=ax, facecolor='red', alpha=0.3, edgecolor='grey', linewidth=1, zorder=2)
    # plt.show()

    """
    Buildings = PolygonGeoData(name='buildings', src_geojson_path='0302 SZ LBCS/building_LBCS.geojson')
    Buildings.make_h3_stats(11, agg_attrs={
        '2100_area': 'sum',
        '2200_area': 'sum',
        '2500_area': 'sum',
        '5300_area': 'sum',
        "6200_area": 'sum',
        "6510_area": 'sum',
        "6560_area": 'sum',
        "1100_area": 'sum',
        "2400_area": 'sum',
        "3000_area": 'sum',
        "3600_area": 'sum',
        "4100_area": 'sum',
        "4200_area": 'sum',
        "4242_area": 'sum',
        "4300_area": 'sum',
        "5100_area": 'sum',
        "5200_area": 'sum',
        "5500_area": 'sum',
        "6100_area": 'sum',
        "6400_area": 'sum',
        "6530_area": 'sum'
    })
    POIs = PointGeoData(name='pois', src_geojson_path='0302 SZ LBCS/poi_LBCS.geojson')
    POIs.make_h3_stats(11, agg_attrs={
        "2100_area": "sum",
        "2200_area": "sum",
        "2500_area": "sum",
        "5300_area": "sum",
        "6200_area": "sum",
        "6510_area": "sum",
        "6560_area": "sum"
    })

    LU = PolygonGeoData(name='landuse', src_geojson_path='0302 SZ LBCS/Land_LBCS.geojson')
    LU.make_h3_stats(11, agg_attrs={
        "3600_area": "sum",
        "5000_area": "sum",
        "5500_area": "sum",
        "4100_area": "sum",
        "9000_area": "sum"
    })


    H3 = H3Grids(11)
    H3.combine_h3_stats([Buildings.h3_stats[11], POIs.h3_stats[11]])
    # h3_features_11 = Buildings.export_h3_features(11, 'tmp/buildings_h3_11.geojson')
    # ax = Buildings.plot(facecolor='blue')
    # Buildings.plot(h3_features_11, ax=ax, facecolor='red', alpha=0.4, edgecolor='grey', linewidth=1)
    # plt.show()
    """

    import pickle, random
    h3_cells = pickle.load(open('tmp/h3_cells.json', 'rb'))
    Table = TableGrids('table', '../temp/sources/grid1_4326.geojson', 'shenzhen', proj_crs=4546)
    rand_data = Table.set_random_value_on_h3_cells(11, h3_cells)
    N = 10
    for i in range(N):
        center_h3_cell = random.choice(h3_cells)
        h3_cells_in_area = h3.h3_to_children(h3.h3_to_parent(center_h3_cell,9), 11)
        for c in h3_cells_in_area:
            if c in rand_data:
                rand_data[c] += np.random.rand()*5
    values = Table.map_h3_cell_value(11, rand_data)
    ax1 = plt.subplot(2, 1, 1)
    ax2 = plt.subplot(2, 1, 2)
    Table.plot(value=values, ax=ax1, cmap='Reds')

    h3_features = []
    for h3_cell in rand_data:
        h3_boundary = h3.h3_to_geo_boundary(h3_cell, geo_json=True)
        h3_boundary = [list(coord) for coord in h3_boundary]
        h3_features.append({
            "type": "Feature",
            "properties": {},
            "geometry": {
                "type": "Polygon",
                "coordinates": [h3_boundary]
            }
        })
    Table.plot(ax=ax2, features=h3_features, crs=4326, value=list(rand_data.values()), cmap='Reds')
    Table.plot(ax=ax2, facecolor='none', edgecolor='grey', linewidth=0.5)
    ax1.axis('off')
    ax2.axis('off')
    ax2.set_xlim(ax1.get_xlim())
    ax2.set_ylim(ax1.get_ylim())
    plt.show()

def test():
    T = TableGrids('table', 12,
                   src_geojson_path='grid1_4326.geojson',
                   table='shenzhen',
                   proj_crs=4546)


    
if __name__ == '__main__':
    # main()
    test()