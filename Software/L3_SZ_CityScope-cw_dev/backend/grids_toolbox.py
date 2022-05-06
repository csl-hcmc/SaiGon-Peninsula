import h3.api.numpy_int as h3
import os, json, copy, re, random
import numpy as np
from collections import Counter
from functools import reduce
from utils import *
from geodata_toolbox import PolygonGeoData
from population_toolbox import Population, HousingUnits


class TableGrids(PolygonGeoData):
    def __init__(self, name, h3_resolution, H3=None, src_geojson_path=None, table='shenzhen',
                 link_to_h3_method='polygon_intersection', proj_crs=None, spec_json_path=''):
        super().__init__(name, src_geojson_path, table, proj_crs, link_to_h3_method)
        assert 4326 in self.features and 4326 in self.shapely_objects
        self._get_spec(spec_json_path)
        self.setup_grid_idx()
        self.setup_interactive_grid()
        self.density_spec = {}

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

    def _generate_random_layout_str(self, zone=None):
        if not zone:
            zone = np.random.choice(self.interactive_grid_layout.keys())
        all_type_codes = list(self.land_type_def.keys()) + [-1]
        num_interactive_cells = len(self.interactive_grid_layout[str(zone)])
        code_list = np.random.choice(all_type_codes, num_interactive_cells, True).tolist()
        code_counter = Counter(code_list)
        layout_ratio = {code: count/num_interactive_cells for code, count in code_counter.items() if code != '-1'}
        layout_ratio = dict(sorted(layout_ratio.items(), key=lambda item: -item[1]))  # sort in decent order
        layout_str = f'i{zone} ' + ' '.join([str(x) for x in code_list])
        return layout_str, layout_ratio

    def update_randomly(self, zone=None):
        layout_str, layout_ratio = self._generate_random_layout_str(zone)
        self.update(layout_str)
        return layout_str, layout_ratio

    def update(self, layout_str=None, changed_density=None):
        if layout_str is not None:
            # just change layout, all height set to None
            self.update_interactive_grid_layout(layout_str)
        if changed_density is not None:
            # just change density def
            self.update_interactive_grid_density(changed_density)
        self.apply_density_on_interactive_grid_layout()
        self.map_interactive_grid_layout_to_h3_cells()
        self.update_housing_and_population()

    def map_interactive_grid_layout_to_h3_cells(self, resolution=None):
        H3 = self.H3
        if not resolution:
            resolution = H3.resolution
        if resolution not in self.map_to_h3_cells:
            self.link_to_h3(resolution)
        grids_to_h3_cells = self.map_to_h3_cells[resolution]
        interactive_grids_to_h3_cells, interactive_features = [], []
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
                cell_stats = {
                    "parcel_area": self.spec.get('parcel_area', -1),
                    'height': height,
                    "sqm_pperson": type_def.get('sqm_pperson', -1),
                    "LBCS": type_def.get('LBCS', {}),
                    "NAICS": type_def.get('NAICS', {})
                }
                # cell_stats = flatten_grid_cell_attributes(type_def, height,
                #                                           attribute_names=attr_names,
                #                                           area_per_floor=self.spec['cell_area'],
                #                                           return_units=item_names)
                interactive_features.append({'properties': {'usage': cell_stats}})
        h3_stats = self.aggregate_attrs_to_cells(interactive_grids_to_h3_cells,
                                                 interactive_features,
                                                 agg_attrs = {'usage': 'decompose'},
                                                 use_weight = True,
                                                 agg_attr_names=['usage'],   # do not expand name with prefix & suffix
                                                 decompose_spec_update={'assign_floors': True})
        self.h3_stats[resolution] = h3_stats
        H3.h3_stats = H3.combine_h3_stats([H3.h3_stats_base, h3_stats], agg='sum')
        H3.h3_stats_interactive = h3_stats

    def update_housing_and_population(self, resolution=None):
        H3 = self.H3
        if not resolution:
            resolution = H3.resolution
        grids_to_h3_cells = self.map_to_h3_cells[resolution]
        self.H3.Housing.new_housing.clear()
        for zone, zone_layout in self.interactive_grid_layout.items():
            for cell_idx, cell_state in zone_layout.items():
                if cell_state['code'] == -1:
                    continue
                type_def = self.land_type_def[str(cell_state['code'])]
                height = cell_state['height'] if cell_state['height'] else type_def['default_height']
                h3_cell_mapping = grids_to_h3_cells[cell_idx]
                if type_def['function'].startswith('residential'):
                    housing_type_attrs = self.spec['housing_type_def'][type_def['function']]
                    num_housing_units = round(self.spec['parcel_area'] * height / housing_type_attrs['area'])
                    if num_housing_units == 0:
                        continue
                    h3_cell_assignments = random.choices(list(h3_cell_mapping.keys()),
                                                         weights=[h3_info['weight_in_raw_data']
                                                                  for h3_info in h3_cell_mapping.values()],
                                                         k=num_housing_units)
                    H3.Housing.add_new_housing_units(housing_type=type_def['function'],
                                                     h3_cells=h3_cell_assignments,
                                                     housing_type_attrs=housing_type_attrs)
                else:
                    # todo: population for non-residential lands
                    pass
        self.H3.Housing.all_housing = self.H3.Housing.base_housing + self.H3.Housing.new_housing

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


    def update_interactive_grid_density(self, changed_density, keep_symmetry=False):
        for land_type_code, slider_value in changed_density.items():
            type_def = self.land_type_def[str(land_type_code)]
            default_height = type_def['default_height']
            lower_scale_factor = type_def['density_scale_factor']['lower']
            upper_scale_factor = type_def['density_scale_factor']['upper']
            if keep_symmetry:
                delta_lower, delta_upper = 1 - lower_scale_factor, upper_scale_factor - 1
                if delta_lower > delta_upper:
                    lower_scale_factor = 1 - delta_upper
                elif delta_lower < delta_upper:
                    upper_scale_factor = 1 + delta_lower
            scale_factor = lower_scale_factor + slider_value * (upper_scale_factor-lower_scale_factor) / 100
            new_height = default_height * scale_factor
            new_height = max(1, round(new_height))
            self.density_spec[land_type_code] = new_height


    def apply_density_on_interactive_grid_layout(self):
        for zone, zone_layout in self.interactive_grid_layout.items():
            for cell_idx, cell_state in zone_layout.items():
                if cell_state['code'] in self.density_spec:
                    cell_state['height'] = self.density_spec[cell_state['code']]


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
    def __init__(self, resolution, Pop=None, Housing=None, required_cells=[]):
        self.resolution = resolution
        self.h3_cell_area = h3.hex_area(self.resolution, 'm^2')
        self.set_population(Pop)
        self.set_housing(Housing)
        self.required_cells = required_cells
        self.values= {}
        self.h3_stats = {}
        self.h3_stats_base = {}
        self.h3_stats_interactive = {}
        self.results = {}
        self.dist_lookup = {}
        self.precooked_rsts = {}

    def set_population(self, Pop):
        if Pop:
            self.Pop = Pop
        else:
            self.Pop = Population()

    def set_housing(self, Housing):
        if Housing:
            self.Housing = Housing
        else:
            self.Housing = HousingUnits()

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
                        if parse_num(value) is not None:
                            combined_h3_stats[h3_cell][h3_attrs_lookup[attr]] += value
                        elif type(value) == dict:
                            # this is a decomposed attribute
                            rst = combined_h3_stats[h3_cell][h3_attrs_lookup[attr]]
                            if type(rst) != dict:
                                rst = copy.deepcopy(value)
                            else:
                                for composition_attr, composition_rst_level1 in value.items():
                                    for composition_item, composition_rst_level2 in composition_rst_level1.items():
                                        for class_name, class_value in composition_rst_level2.items():
                                            if composition_attr not in rst:
                                                rst[composition_attr] = {}
                                            if composition_item not in rst[composition_attr]:
                                                rst[composition_attr][composition_item] = {}
                                            if class_name not in rst[composition_attr][composition_item]:
                                                rst[composition_attr][composition_item][class_name] = class_value
                                            else:
                                                rst[composition_attr][composition_item][class_name] += class_value
                            combined_h3_stats[h3_cell][h3_attrs_lookup[attr]] = rst

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


