import os, time, datetime
from geodata_toolbox import PointGeoData
import h3.api.numpy_int as h3
from collections import Counter

class Population(PointGeoData):
    def __init__(self, name, base_sim_pop_geojson_path=None, base_floating_pop_json_path=None,
                 table='shenzhen', proj_crs=None, person_attrs=[]):
        super().__init__(name, base_sim_pop_geojson_path, table, proj_crs)
        self.base_sim_pop_geojson_path = base_sim_pop_geojson_path
        self.base_floating_pop_json_path = base_floating_pop_json_path
        self.base_sim_pop = []
        self.base_floating_pop = []
        self.sim_pop = []
        self.person_attrs = person_attrs
        self.h3_count_base_sim_pop = {}
        self.h3_count_sim_pop = {}

    def set_base_sim_population(self, resolution=12):
        for idx, fea in enumerate(self.features[self.crs['geographic']]):
            person_idx = f'b{idx}'
            thisPerson = Person(person_idx)
            thisPerson.set_person_attrs(self.person_attrs, fea['properties'])
            coord = fea['geometry']['coordinates']
            if fea['geometry']['type'] == 'MultiPoint':
                coord = coord[0]
            thisPerson.set_location(coord=coord, resolution=resolution, location_type='home')
            self.base_sim_pop.append(thisPerson)
            self.sim_pop.append(thisPerson)
        self.h3_count_base_sim_pop['home'] = {
            resolution: self.count_population_on_h3(self.base_sim_pop, resolution, 'home')
        }

    def set_base_floating_persons(self):
        pass


    def count_population_on_h3(self, population, resolution, location_type='home', self_update=True):
        # todo: add filter
        if location_type not in self.h3_count_sim_pop:
            self.h3_count_sim_pop[location_type] = {}
        if resolution not in self.h3_count_sim_pop[location_type]:
            self.h3_count_sim_pop[location_type][resolution] = {}
        features_to_h3_cells = [
            getattr(person, location_type, {}).get('h3', {}).get(resolution, None)
            for person in population
        ]
        features_to_h3_cells = [h3_cell for h3_cell in features_to_h3_cells if h3_cell]
        counter = Counter(features_to_h3_cells)
        if self_update:
            for h3_cell, num in counter.items():
                self.h3_count_sim_pop[location_type][resolution][h3_cell] = \
                    self.h3_count_base_sim_pop.get(location_type, {}).get(
                        resolution, {}).setdefault(h3_cell, 0) + num
        return dict(counter)


class Person:
    def __init__(self, person_idx):
        self.idx = person_idx
        self.home = {'coord':None, 'h3': {}}
        self.workplace = {'coord':None, 'h3': {}}
        self.attrs = {}

    def set_person_attrs(self, attrs, src_data_object=None, default_value=None, datetime_format='%Y/%m/%d', crt_year=None):
        if type(default_value) != dict:
            default_value = {attr: default_value for attr in attrs}
        if type(attrs) == list:
            attrs = {attr: default_value[attr] for attr in attrs}
        if src_data_object:
            for attr in attrs:
                self.attrs[attr] = self._set_person_attr_from_src_data(attr,
                                                                       src_data_object,
                                                                       default_value[attr],
                                                                       datetime_format,
                                                                       crt_year)

    def _set_person_attr_from_src_data(self, attr, src_data_object, default_value=None, datetime_format=None, crt_year=None):
        """
        May need to be changed according to latest data format
        :param object:
        :param attr:
        :param datetime_format:
        :return:
        """
        if attr == 'age':
            if not datetime_format:
                datetime_format = self.datetime_format
            if not crt_year:
                crt_year = datetime.datetime.now().year
            if 'BIRTHDAY' in src_data_object:
                birth_year = time.strptime(src_data_object['BIRTHDAY'], datetime_format).tm_year
                value = crt_year - birth_year
            else:
                value = default_value
        else:
            value = src_data_object.get(attr, missing_value)
        return value

    def set_location(self, coord=None, h3_cell=None, location_type='home', resolution=None):
        if coord:
            h3_cell = h3.geo_to_h3(coord[1], coord[0], resolution) if resolution else None
        elif h3_cell:
            coord = h3.h3_to_geo(h3_cell)[::-1]
        else:
            raise ValueError(f'coord and h3_cell cannot be both None')
        if location_type == 'home':
            self.home['coord'] = coord
            self.home['h3'].update({resolution: h3_cell})
        elif location_type == 'workplace':
            self.workplace['coord'] = coord
            self.workplace['h3'].update({resolution: h3_cell})