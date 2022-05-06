import h3.api.numpy_int as h3
import os, json, copy, re, random
import matplotlib.pyplot as plt
from pyproj import Transformer, CRS
from shapely.geometry import Point, LineString, MultiLineString, shape
from shapely.geometry.polygon import Polygon
import numpy as np
from collections import Counter
from functools import reduce
from numpyencoder import NumpyEncoder
from utils import *
from typing import Union, Optional, Dict, List
try:
    import geopandas as gpd
    import h3pandas
except:
    pass


class GeoData:
    """
    GeoData is the base class to process and store geo data in geojson format.
    It has following attributes:
        table: str, table name of this CityScope project
        name: str, the name of this GeoData
        crs: dict, coordinate system of this GeoData, each value is epsg code.
            key 'src': the CRS from source geojson file;
            key 'geographic': geographic CRS. If src CRS is geographic, use it, if not, use 4326;
            key 'projected': projected CRS;
        features: Dict[list], features of this GeoData in geojson feature object format with different CRS
            keys are epsg codes of different CRS,
            values are list of features in geojson format with the same order
        shapely_objects: Dict["shapely shapes"]: shapely shapes of this GeoData with different CRS
            keys are epsg codes of different CRS,
            values are list shape shapes with the same order as features
        map_to_h3_cells: Dict[List[dict]]: mapping-to-h3-cells information with different h3 resolutions
            keys are h3 resolutions,
            values are list of dict containing mapping-to-h3-cell information, the list order is the same as features.
            see params "cells_to_map" of aggregate_attrs_to_cells() method for more information on how these
            mapping-to-cell dict are organized.
        h3_stats: Dict[int, Dict[int, dict]]: statistics of h3 cells after aggregate raw data to h3 with different resolutions.
            keys are h3 resolutions,
            values are dict containing stats information of each h3 cell on which raw data is aggregated.
                keys are h3 cell index
                values are aggregating results on corresponding h3 cell.
                see help on return of aggregate_attrs_to_cells() method for more information on how these results are organized
        transformer: Dict[int, Dict[int, 'Transformer_object']]: lookup for Transformer objects to convert CRS,
            keys of outer dict are epsg codes of from_CRS, and keys of inner dict are epsg codes of to_CRS.
            Note that the inclusion of Transformer objects will make the whole instance unpicklable. To pickle the
            instance, we need to delete it, eg, setting self.transformer = {}
    """
    def __init__(self, name: str, src_geojson_path: Optional[str]=None,
                 table: str='shenzhen', proj_crs: Optional[int]=None) -> None:
        """
        Initializer of the instance
        :param name: the name of this GeoData
        :param src_geojson_path: the path of geojson file to load data. It could the full path,
            or only the last part of the path in the following format: cities/{table}/geojson/last-part-of-the-path
        :param table: table name of this CityScope project
        :param proj_crs: the epsg code for projected coordinate system of this GeoData. If CRS indicated in
            geojson file is already a projected CRS, this argument could be ignored as None.
        """
        self.table = table
        self.name = name
        self.work_dir = f'./cities/{table}'
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
        self.set_default_decompose_spec()

    def load_data(self, to_4326: bool, to_shapely: bool) -> None:
        """
        Load data from geojson file
        :param to_4326: whether to convert raw CRS to WGS84 CRS (epsg: 4326)
        :param to_shapely: whether to make a copy of shape shapes
        :return: None
        """
        geojson_path = self.src_geojson_path
        features, src_crs = load_geojsons(geojson_path)
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

    def _convert_to_shapely(self, feature: dict) -> 'Geometry':
        """
        Convert a feature in dict to a shapely shape object
        :param feature: raw feature from geojson features list
        :return: shape geometry class of this feature
        """
        try:
            shapely_object = shape(feature['geometry'])
        except:
            shapely_object = None
        return shapely_object

    def convert_to_shapely(self, crs: Optional[int]=None, self_update: bool=True) -> List['Geometry']:
        """
        Convert self.features to shapely
        :param crs: specify epsg code of CRS to be converted, if set to None, use the source CRS
        :param self_update: if set to True, then self.shapely_objects[crs] is also updated
        :return: the list of shapely Geometry with the same order in self.features list
        """
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

    def _convert_crs(self, feature: dict, to_crs: int, from_crs: int, in_place: bool=True) -> dict:
        """
        Convert the CRS of a feature
        :param feature: raw feature from the features of geojson file
        :param to_crs: epsg code of the new CRS to which the raw feature will be converted
        :param from_crs: epsg code of current CRS of raw feature
        :param in_place: if set to True, then the feature itself will be updated, otherwise conversion will
            happen on its copy.
        :return: the same feature with geometry converted to "to_crs" from "from_crs"
        """
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

    def convert_crs_for_features(self, to_crs: int, from_crs: Optional[int]=None,
                                 save_to: Optional[str]=None) -> List[dict]:
        """
        Convert self.features to another CRS, and save converted features to local file upon request
        :param to_crs: epsg code of the new CRS to which the raw features will be converted
        :param from_crs: epsg code of current CRS of raw features, if None, then use the source CRS
        :param save_to: the path to save the converted features to a geojson file, if None, then do not save.
        :return: the converted features with the same order as raw features in self.features[from_crs]
        """
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

    def set_default_decompose_spec(self, decompose_spec_default: dict=None, update: bool=False) -> None:
        """
        Set default decompose specification.
        For raw data and table grid, it has a field specifying its total area, population density, and composition
        in the form of ratio of different classes based on different classification systems, such as LBCS, NAICS.
        Example 1: a building feature stored in geojson file could have "usage" field in its "properties" like follows。
            "usage": {
                "area": 90.41,
                "sqm_pperson": 40.05629908195996,
                "LBCS": {
                    "2100": 0.5530361685654241,
                    "3000": 0.44696383143457585
                },
                "NAICS": {
                    "44": 0.5530361685654241,
                    "31": 0.44696383143457585
                }
            }
        Example 2: a grid cell could has its usage being defined like follows.
            {
                "function": "office_small",
                "sqm_pperson": 5.0,
                "default_height": 6,
                "LBCS": [
                    {
                        "p": 1,
                        "use": {
                            "2400": 1.0
                        }
                    }
                ],
                "NAICS": [
                    {
                        "p": 1,
                        "use": {
                            "52": 0.5,
                            "54": 0.5
                        }
                    }
                ],
                "density_scale_factor": {
                    "lower": 0.2,
                    "upper": 3.0
                }
            }
        Base on these information, we could decompose the total amount (area, pop, etc.) to different classes, and
        default specifications of decomposition is stored in self.decompose_spec_default (dict) and has following keys:
            "total_area_attr_name": specify the attribute name for "total area", default="area" (Example 1)
            "area_per_floor_attr_name": specify the attribute name for "area per floor attr", default="parcel_area"
            "area_per_person_attr_name": specify the attribute name for "area_per_person", default="sqm_pperson" (Example 1 & 2)
            "num_floors_attr_name": specify the attribute name for "num_floors", default="height"
            "composition": specify how do we decompose attributes, by default, it is:
                "LBCS": ["area", "pop"]: decompose area and population according to LBCS system
                "NAICS": ["area", "pop"]: decompose area and population according to NAICS system
            "assign_floors": indicate whether to sample functions to different floors. Note that for raw data we
                are generally defining ratio of different classes for the whole entity as we do not have detailed
                information for each floor, thus there is generally no needs to assign floors; in contrast, for
                table grids it's possible to consider varied functions for different floors, so we should assign
                floor functions based on our definition.
            "floor_proportion_attr_name": when different floors have varied usage, specify the attribute name
                for floor_proportion, default="p" (Example 2)
            "floor_usage_attr_name": when different floors have varied usage, specify the attribute name
                for floor usage, default="use" (Example 2)
        These default specifications are predefined and could be overridden by user settings fully or partially.
        :param decompose_spec_default: user settings of decompose_spec_default which would override the predefined one
        :param update: if set to False, then the user setting will fully replace the predefined, even though it is
            incomplete; if set to True, then only update those redefined by user settings and keep other unchanged.
        """
        self.decompose_spec_default = {
            'total_area_attr_name': 'area',
            'area_per_floor_attr_name': 'parcel_area',
            'area_per_person_attr_name': 'sqm_pperson',
            'num_floors_attr_name': 'height',
            'composition': {
                'LBCS': ['area', 'pop'],
                'NAICS': ['area', 'pop']
            },
            'assign_floors': False,
            'floor_proportion_attr_name': 'p',
            'floor_usage_attr_name': 'use'
        }
        if decompose_spec_default:
            if not update:
                self.decompose_spec_default = decompose_spec_default
            else:
                self.decompose_spec_default.update(decompose_spec_default)

    def aggregate_attrs_to_cells(self, cells_to_map: List[dict], features: List[dict],
                                 agg_attrs: Dict[str, str]={}, agg_attr_names: Optional[List[str]]=None,
                                 use_weight: bool=True, decompose_spec_update: Optional[dict]=None) -> Dict[int, dict]:
        """
        Aggregate attributes of this GeoData to cells-system, generally to H3 cells
        :param cells_to_map: it defines which cells should a feature be mapped to using a dict. The keys of the dict
            are cell idx and values are weight information given by a inner dict. In this inner dict, the key of
            "intersection_area" shows the area of intersection part between the raw geometry and the cell; the key of
            "weight_in_raw_data" shows the ratio of intersection part to raw geometry;
            the key of "weight_in_new_data" shows the ratio of intersection part to cell.
            For PointGeoData, "weight_in_raw_data" is always 1 as to the cell which contains the point.
            These mapping-dict are kept in a list with the same order as param features
        :param features: list of features get from geojson file, it has the same order with params cells_to_map
        :param agg_attrs: defines which attributes of features should be aggregated to cells using what methods. Keys
            are attribute names, and values are corresponding aggregation methods. Following methods are supported:
                (1) count: the count of raw features within/intersected with a cell
                (2) sum: the (weighted) sum of the specified attribute of raw features within/intersected with a cell
                (3) min: the (weighted) min of the specified attribute of raw features within/intersected with a cell
                (4) max: the (weighted) max of the specified attribute of raw features within/intersected with a cell
                (5) mean: the (weighted) mean of the specified attribute of raw features within/intersected with a cell
                (6) decompose: a special method particularly designed for "usage" attribute which stores information
                    of total area, population density, composition of subclasses of LBCS, NAICS, etc.
        :param agg_attr_names: the list of names for new attributes of cells after aggregation. If set to None, then
            use the default naming convention: adding a prefix "[name of this geodata]_" and a suffix "_(aggregation method)",
            for instance: if we aggregate the "area" attribute of the GeoData named "building" using "sum" method,
            then the default agg_attr_name would be "[building]_area_(sum)"
        :param use_weight: whether to use weight defined in params cells_to_map when applying aggregation methods of
            count, sum, min, max, mean.
        :param decompose_spec_update: if aggregation method is "decompose" for some attribute, the code requires some
            decompose specifications. There is already a set of predefined specifications, and user could update
            them through this dict. For more information regarding decompose specifications, see set_default_decompose_spec
        :return: a dict storing aggregated values for each cell. Keys are cell index, and values are inner dict with
            keys being aggregated attribute name and values being aggregated attribute value.
            For instance, for methods other than "decompose", the returned dict might look like:
            {
                627145810095648767: {'[buildings]_area_(sum)': 100},
                627145810096746495: {'[buildings]_area_(sum)': 100},
                ...
            }
            For method of "decompose", the returned dict generally looks like:
            {
                627145810095648767: {
                    '[buildings]_usage_(decompose)': {
                        'LBCS': {
                            'area': {
                                '2100': 100,
                                '3000': 100
                            },
                            'pop': {
                                '2100': 100,
                                '3000': 100
                            }
                        },
                        'NAICS': {
                            'area': {
                                '44': 100,
                                 31': 100
                            },
                            'pop': {
                                '44': 100,
                                '31': 100
                            }
                        }
                    }
                },
                627145810096746495: ...
            }
        """
        decompose_spec = copy.deepcopy(self.decompose_spec_default)
        if decompose_spec_update:
            decompose_spec.update(decompose_spec_update)
        if agg_attr_names is None:
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
            elif agg_method == 'decompose':
                for cell in h3_stats.keys():
                    data_to_agg = h3_stats[cell][agg_save_name]
                    weight_to_agg = weights[cell]
                    cell_agg_rst = {}
                    for composition_attr, composition_item_list in decompose_spec['composition'].items():
                        for composition_item in composition_item_list:
                            # e.g. composition_attr=LBCS, composition_item=area
                            cell_agg_rst.setdefault(composition_attr, {})[composition_item] = {}
                    for d, wei in zip(data_to_agg, weight_to_agg):
                        area_pperson = d.get(decompose_spec['area_per_person_attr_name'], -1)
                        data_composition = {}   # create a new name to replace d[composition_attr] to avoid error from re-modifying raw data
                        floor_group_tts = {}
                        if not decompose_spec['assign_floors']:
                            tt_area = d.get(decompose_spec['total_area_attr_name'], -1)
                            tt_pop = tt_area / area_pperson if area_pperson > 0 else -1
                            tt = {'area': tt_area*wei, 'pop': tt_pop*wei}
                            for composition_attr in decompose_spec['composition']:
                                floor_group_tts[composition_attr] = [tt]
                                data_composition[composition_attr] = [{
                                    decompose_spec['floor_proportion_attr_name']: 1,
                                    decompose_spec['floor_usage_attr_name']: d[composition_attr]
                                }]
                        else:
                            for composition_attr in decompose_spec['composition']:
                                floor_group_tts[composition_attr] = []
                                try:
                                    assert composition_attr in d and type(d[composition_attr])==list
                                except:
                                    raise TypeError(f'Composition attribute {composition_attr} not found or not list when assigning floors')
                                try:
                                    height = d[decompose_spec['num_floors_attr_name']]
                                    assert height >= 1 and type(height) == int
                                except:
                                    raise ValueError(f'Invalid height ({height}) when assigning floors')
                                floor_assignments = random.choices(range(len(d[composition_attr])),
                                                                   weights = [group[decompose_spec['floor_proportion_attr_name']]
                                                                              for group in d[composition_attr]],
                                                                   k = height)
                                for i_g, group in enumerate(d[composition_attr]):
                                    num_floors = floor_assignments.count(i_g)
                                    tt_area = d.get(decompose_spec['area_per_floor_attr_name'], -1) * num_floors
                                    tt_pop = tt_area / area_pperson if area_pperson > 0 else -1
                                    tt = {'area': tt_area * wei, 'pop': tt_pop * wei}
                                    floor_group_tts[composition_attr].append(tt)
                                data_composition[composition_attr] = d[composition_attr]
                        for composition_attr, composition_item_list in decompose_spec['composition'].items():
                            for composition_item in composition_item_list:
                                for tt, floor_group in zip(floor_group_tts[composition_attr], data_composition[composition_attr]):
                                    if tt[composition_item] > 0 :
                                        floor_group_usage = floor_group[decompose_spec['floor_usage_attr_name']]
                                        for class_name, ratio in floor_group_usage.items():
                                            # e.g. composition_attr=LBCS, composition_item=area, class_name=2100, ratio=0.5
                                            # => we are processing area of LBCS-2100, and we know the ratio of LBCS-2100 is 0.5
                                            if class_name not in cell_agg_rst[composition_attr][composition_item]:
                                                cell_agg_rst[composition_attr][composition_item][class_name] = tt[composition_item] * ratio
                                            else:
                                                cell_agg_rst[composition_attr][composition_item][class_name] += tt[composition_item] * ratio
                    h3_stats[cell][agg_save_name] = cell_agg_rst
            else:
                raise ValueError(f'Unrecognised agg_method "{agg_method}" for {attr}')
        return h3_stats

    def export_h3_features(self, resolution: int, save_to: Optional[str]=None) -> List[dict]:
        """
        Export h3 cells on which attributes of this GeoData are aggregated to geojson features,
            properties of these h3 features are aggregated results
        :param resolution: h3 resolution
        :param save_to: the path to save the exported h3 features to a local geojson file, if None, then do not save.
        :return: list of exported h3 features, not the full geojson content, only its "features"
        """
        if not self.h3_stats:
            print('Error: must have h3_info first')
            return
        h3_stats = self.h3_stats[resolution]
        h3_features = export_h3_features(h3_stats, save_to)
        return h3_features

    def export_geojson(self, crs: Optional[int]=None, save_to: Optional[str]=None) -> None:
        """
        Export this GeoData to a local geojson file
        :param crs: the epsg code of CRS to export, if None, then use the source CRS
        :param save_to: the path to save the geojson file, if None, then do not save
        :return: None
        """
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

    def plot(self, features: Optional[List[dict]]=None, crs: Optional[int]=None,
             ax: Optional['Matplotlib_AxisObject']=None,
             value: Optional[List[Union[int, float]]]=None, **kargs) -> 'Matplotlib_AxisObject':
        """
        Make plot for this GeoData or other features
        :param features: list of features in geojson format, if None, then use self.features (features of this GeoData)
            with default geographic CRS
        :param crs: epsg code of CRS to be plotted, if None, then use default geographic CRS
        :param ax: a matplotlib axis object on which the features will be plotted, if None, then a new axis will be created
        :param value: list of numbers with the same order as list of features. If not None, then a choropleth plot
            will be created based on these values; if None, then unified color is used and the plot would be just for
            locations of features.
        :param kargs: other arguments for plot controls that are valid in geopandas GeoDataFrame.plot()
        :return: the matplotlib axis object on which the features are plotted.
        """
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
    def __init__(self, name: str, src_geojson_path: Optional[str] = None,
                 table: str = 'shenzhen', proj_crs: Optional[int] = None) -> None:
        """
        Initializer of the instance.
        PointGeoData is subclass inheriting from base class GeoData, it is designed to process points,
            such as POIs.
        :param name: the name of this GeoData
        :param src_geojson_path: the path of geojson file to load data. It could the full path,
            or only the last part of the path in the following format: cities/{table}/geojson/last-part-of-the-path
        :param table: table name of this CityScope project
        :param proj_crs: the epsg code for projected coordinate system of this GeoData. If CRS indicated in
            geojson file is already a projected CRS, this argument could be ignored as None.
        """
        super().__init__(name, src_geojson_path, table, proj_crs)

    def link_to_h3(self, resolution: int=12) -> None:
        """
        Link this PointgonGeoData to h3 cells, a point will be linked to the h3 cell which contains this point
        :param resolution: resolution of h3 cells to be linked with
        :return: None, updates self.map_to_h3_cells[resolution] in place
        """
        features_to_h3_cells = []
        for fea in self.features[self.crs['geographic']]:
            coord = fea['geometry']['coordinates']
            if fea['geometry']['type'] == 'MultiPoint':
                coord = coord[0]
            h3_cell = h3.geo_to_h3(coord[1], coord[0], resolution)
            features_to_h3_cells.append(h3_cell)
        self.map_to_h3_cells[resolution] = features_to_h3_cells

    def make_h3_stats(self, resolution: int, agg_attrs: Dict[str, str]={}, count: bool=True) -> None:
        """
        Link this PointGeoData to h3 cells, then aggregate its attributes on h3 cells and make statistics
            for each h3 cell being linked with one or more points
        :param resolution: resolution of h3 cells to be linked with
        :param agg_attrs: defines which attributes of features should be aggregated to cells using what methods.
            See params agg_attrs of aggregate_attrs_to_cells() method for more information of available aggregation methods
        :param count: whether to include the count of points in h3 cells as an attribute of h3 cells
        :return: None, updates self.h3_stats[resolution] in place, see return of aggregate_attrs_to_cells() method
            for how h3_stats as the results are formatted.
        """
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
    def __init__(self, name: str, src_geojson_path: Optional[str]=None,
                 table: str='shenzhen', proj_crs: Optional[int]=None,
                 link_to_h3_method: str='polygon_intersection') -> None:
        """
        Initializer of the instance.
        PolygonGeoData is subclass inheriting from base class GeoData, it is designed to process polygons,
            such as buildings, land parcels.
        :param name: the name of this GeoData
        :param src_geojson_path: the path of geojson file to load data. It could the full path,
            or only the last part of the path in the following format: cities/{table}/geojson/last-part-of-the-path
        :param table: table name of this CityScope project
        :param proj_crs: the epsg code for projected coordinate system of this GeoData. If CRS indicated in
            geojson file is already a projected CRS, this argument could be ignored as None.
        :param link_to_h3_method: how to link this PolygonGeoData to h3, should be one of "polygon_intersection" and
            "centroid". If set to "polygon_intersection", then polygons will be linked to any h3 cells that intersect
            with it and information regarding intersection area and weights based on ratio of intersection area are
            also provided; in contrast, if set to "centroid", then a polygon will only be linked to one h3 cell who
            contains the centroid of this polygon, in this case, intersection area will be the whole area of the polygon
        """
        super().__init__(name, src_geojson_path, table, proj_crs)
        if link_to_h3_method not in  ['polygon_intersection', 'centroid']:
            raise ValueError(f'Invalid link_to_h3_method: {link_to_h3_method}')
        self.link_to_h3_method = link_to_h3_method

    def _get_buffer(self, feature_idx: int, buffer_dist: float, to_crs: int) -> dict:
        """
        Get the buffered polygon with certain distance
        :param feature_idx: the order index of the input polygon feature in self.features[some-CRS]
        :param buffer_dist: buffer distance with the same unit as projected CRS, for instance, meter for epsg 4547
        :param to_crs: epsg code for the target CRS, the returned feature will be converted to this CRS
        :return: buffered polygon feature in target CRS in geojson format
        """
        # step.1 get shapely object in projected CRS so that unit is meter
        if self.crs['projected'] not in self.shapely_objects:
            self.convert_to_shapely(self.crs['projected'], self_update=True)
        polygon_shapely_object_projected = self.shapely_objects[self.crs['projected']][feature_idx]
        # step.3 get buffered shapely object in projected CRS
        buffered_polygon_shapely_object_projected = polygon_shapely_object_projected.buffer(buffer_dist)
        # step.4 get coordinates and geojson feature
        try:
            # for Polygon
            coords = list(buffered_polygon_shapely_object_projected.exterior.coords)
        except:
            # for MultiPolygon
            coords = list(list(buffered_polygon_shapely_object_projected.geoms)[0].exterior.coords)
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

    def link_to_h3(self, resolution: int=11, self_update: bool=True) -> List[Union[int, Dict[int, dict]]]:
        """
        Link this PolygonGeoData to h3 cells
        :param resolution: resolution of h3 cells to be linked with
        :param self_update: whether to update self.map_to_h3_cells attribute
        :return: list of mapping-to-h3-cells info with the same order as self.features.
                 If linking method is "polygon_intersection", then list element is dict:
                     keys are index of h3 cells with which the polygon should be linked
                     values are weights information given in a dict when linking this polygon with the h3 cell, including:
                         key="intersection_area": the area of intersection part between the polygon and h3 cell
                         key="weight_in_raw_data": the ratio of intersection_area to the area of polygon
                         key="weight_in_new_data": the ratio of intersection_area to the area of h3 cell
                 If linking method is "centroid", then list element is int index of h3 cell with which the polygon should be linked.
        """
        if self.link_to_h3_method == 'polygon_intersection':
            features_to_h3_cells = self.link_to_h3_using_polygon_intersection(resolution, self_update)
        elif self.link_to_h3_method == 'centroid':
            features_to_h3_cells = self.link_to_h3_using_centroid(resolution, self_update)
        return features_to_h3_cells

    def link_to_h3_using_polygon_intersection(self, resolution: int=11, self_update: bool=True) -> List[Dict[int, dict]]:
        """
        Link this PolygonGeoData to h3 cells based on polygon intersections
        :param resolution: resolution of h3 cells to be linked with
        :param self_update: whether to update self.map_to_h3_cells attribute
        :return: list of mapping-to-h3-cells info with the same order as self.features, elements are dict:
                 keys are index of h3 cells with which the polygon should be linked
                 values are weights information given in a dict when linking this polygon with the h3 cell, including:
                     key="intersection_area": the area of intersection part between the polygon and h3 cell
                     key="weight_in_raw_data": the ratio of intersection_area to the area of polygon
                     key="weight_in_new_data": the ratio of intersection_area to the area of h3 cell
        """
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

    def link_to_h3_using_centroid(self, resolution: int=11, self_update: bool=True) -> List[int]:
        """
        Link this PolygonGeoData to h3 cells based on centroid
        :param resolution: resolution of h3 cells to be linked with
        :param self_update: whether to update self.map_to_h3_cells attribute
        :return: list of mapping-to-h3-cells info with the same order as self.features,
            elements are int index of h3 cells.
        """
        features_to_h3_cells = []
        for fea in self.features[self.crs['geographic']]:
            coord = fea['geometry']['coordinates']
            if fea['geometry']['type'] == 'MultiPoint':
                coord = coord[0]
            h3_cell = h3.geo_to_h3(coord[1], coord[0], resolution)
            features_to_h3_cells.append(h3_cell)
        if self_update:
            self.map_to_h3_cells[resolution] = features_to_h3_cells
        return features_to_h3_cells

    def make_h3_stats(self, resolution: int, agg_attrs: Dict[str, str]={}) -> None:
        """
        Link this PolygonGeoData to h3 cells, then aggregate its attributes on h3 cells and make statistics
            for each h3 cell being linked with one or more polygons
        :param resolution: resolution of h3 cells to be linked with
        :param agg_attrs: defines which attributes of features should be aggregated to cells using what methods.
            See params agg_attrs of aggregate_attrs_to_cells() method for more information of available aggregation methods
        :return: None, updates self.h3_stats[resolution] in place, see return of aggregate_attrs_to_cells() method
            for how h3_stats as the results are formatted.
        """
        if resolution not in self.map_to_h3_cells:
            self.link_to_h3(resolution)
        features_to_h3_cells = self.map_to_h3_cells[resolution]
        h3_stats = self.aggregate_attrs_to_cells(features_to_h3_cells, self.features[self.crs['src']], agg_attrs, use_weight=True)
        self.h3_stats[resolution] = h3_stats