import os, time, datetime, random, pickle
import pandas as pd
import numpy as np
from pyproj import Transformer, CRS
import h3.api.numpy_int as h3
from collections import Counter
from geodata_toolbox import PolygonGeoData
from utils import *


individual_pop_attr_lookup = {
    'SEX': {
        'attr_name': 'gender',
        'value_lookup': {
            "1": "male",
            "2": "female"
        }
    },
    'MARRYID': {
        'attr_name': 'marriage',
        'value_lookup': {
            "1": "single",
            "2": "married",
            "3": "widowed",
            "4": "divorced",
            "5": "unknown",
            "9": "unknown"
        }
    },
    'EDULEVELID': {
        'attr_name': 'education',
        'value_lookup': {
            "0": "master_phd",
            "1": "master_phd",
            "2": "college",
            "3": "college",
            "4": "Secondary Vocational School",
            "5": "EMH_school",
            "6": "EMH_school",
            "7": "EMH_school",
            "8": "EMH_school",
            "9": "others"
        },
        'raw_value_lookup': {
            "0": "PhD",
            "1": "Master",
            "2": "Bachlor",
            "3": "Vocational College",
            "4": "Secondary Vocational School",
            "5": "High Middle School",
            "6": "Junior Middle School",
            "7": "Below Junior Middle School",
            "8": "Compulsory Education Aged (Student)",
            "9": "Preschool Aged"
        }
    },
    "TRADEID": {
        'attr_name': 'occupation',
        'value_lookup': {
            "1": "employee",
            "2": "employee",
            "3": "employee",
            "4": "employee",
            "5": "others",
            "6": "employee",
            "7": "employee",
            "8": "unemployment",
            "9": "student"
        },
        'resample': {
            'employee': [
                {'value': 'employee', 'p': 0.39},
                {'value': 'retired', 'p': 0.18},
                {'value': 'manager', 'p': 0.14},
                {'value': 'free', 'p': 0.08},
            ]
        },
        'raw_value_lookup': {
            "1": "Industry",
            "2": "Commercial",
            "3": "Service",
            "4": "Transportation",
            "5": "Agriculture",
            "6": "Construction",
            "7": "Others",
            "8": "Unemployed",
            "9": "Non-labor Aged"
        },
        'comment': 'need to post-processing for employee, manager, retired, and free by sampling'
    },
}


class HomeWorkplaceAssigner:
    def __init__(self, pickled_taz_path=None, taz_geojson_path=None, commuting_od_path=None,
                 save_path=None, table='shenzhen', proj_crs=None, resolution=11, target_taz_list=None,
                 in_sim_area_taz_list=[1029, 1020, 1054], quick_assign=True):
        self.table = table
        self.resolution = resolution
        self.quick_assign = quick_assign

        if taz_geojson_path is None:
            taz_geojson_path = os.path.join('cities', table, 'geojson', 'taz.geojson')
        if commuting_od_path is None:
            commuting_od_path = os.path.join('cities', table, 'raw', 'commuting_od.csv')
        if pickled_taz_path is None:
            pickled_taz_path = os.path.join('cities', table, 'clean', 'TAZ.p')
        if os.path.exists(pickled_taz_path):
            self.TAZ = pickle.load(open(pickled_taz_path, 'rb'))
        else:
            self.TAZ = PolygonGeoData(name='taz', src_geojson_path=taz_geojson_path, table=table,
                                      proj_crs=proj_crs, link_to_h3_method='polygon_intersection')
            self.TAZ.link_to_h3(resolution, True)
            self.TAZ.transformer = None   # avoid unpickable error
            pickle.dump(self.TAZ, open(pickled_taz_path, 'wb'))
        self.commuting_od_df = pd.read_csv(commuting_od_path)
        if target_taz_list is None:
            target_taz_list = self.commuting_od_df['From_TAZ'].tolist() + self.commuting_od_df['To_TAZ'].tolist()
            target_taz_list = list(set(target_taz_list))
        self.target_taz_list = target_taz_list
        self.in_sim_area_taz_list = in_sim_area_taz_list
        self.calc_commuting_ratio()
        self.build_lookups()
        if save_path is None:
            save_path = os.path.join('cities', table, 'models', 'home_workplace_assigner.p')
        self.compress_and_save(save_path)


    def build_lookups(self):
        self.h3_cell_to_taz = {}
        self.taz_to_h3_cell = {}
        for taz_fea, h3_info in zip(self.TAZ.features[self.TAZ.crs['src']], self.TAZ.map_to_h3_cells[self.resolution]):
            taz_idx = taz_fea['properties']['NO']
            self.taz_to_h3_cell[taz_idx] = {}
            for h3_cell, h3_stats in h3_info.items():
                self.taz_to_h3_cell[taz_idx][h3_cell] = h3_stats['weight_in_raw_data']
                weight = h3_stats['weight_in_new_data']
                if h3_cell not in self.h3_cell_to_taz:
                    self.h3_cell_to_taz[h3_cell] = {'taz': taz_idx, 'weight': weight}
                elif self.h3_cell_to_taz[h3_cell]['weight'] < weight:
                    self.h3_cell_to_taz[h3_cell] = {'taz': taz_idx, 'weight': weight}


    def calc_commuting_ratio(self):
        self.from_ratio = {}
        self.to_ratio = {}
        df = self.commuting_od_df
        for taz_idx in self.target_taz_list:
            from_this_taz_df = df.loc[df['From_TAZ'] == taz_idx]
            to_this_taz_df = df.loc[df['To_TAZ']==taz_idx]
            from_this_taz_tt = from_this_taz_df['Trip_Num'].sum()
            to_this_taz_tt = to_this_taz_df['Trip_Num'].sum()
            self.from_ratio[taz_idx] = {
                des_taz['To_TAZ']: des_taz['Trip_Num'] / from_this_taz_tt
                for des_taz in from_this_taz_df.to_dict('records')
            }
            self.to_ratio[taz_idx] = {
                ori_taz['From_TAZ']: ori_taz['Trip_Num'] / to_this_taz_tt
                for ori_taz in to_this_taz_df.to_dict('records')
            }


    def assign_workplace(self, persons, location_setter=None):
        taz_to_persons = {}
        for person in persons:
            this_home_taz = self.h3_cell_to_taz[person.home['h3'][self.resolution]]['taz']
            if this_home_taz not in taz_to_persons:
                taz_to_persons[this_home_taz] = [person]
            else:
                taz_to_persons[this_home_taz].append(person)
        for taz, pop_in_this_taz in taz_to_persons.items():
            num_persons = len(pop_in_this_taz)
            des_ratio = self.from_ratio[taz]
            des_taz_list = np.random.choice(list(des_ratio.keys()),
                                            size=num_persons,
                                            replace=True,
                                            p=list(des_ratio.values()))
            for person, des_taz in zip(pop_in_this_taz, des_taz_list):
                if  location_setter:
                    in_sim_area = None
                else:
                    in_sim_area = des_taz in self.in_sim_area_taz_list
                if self.quick_assign:
                    this_h3_cell = random.choice(list(self.taz_to_h3_cell[des_taz].keys()))
                else:
                    this_h3_cell = np.random.choice(list(self.taz_to_h3_cell[des_taz].keys()),
                                                   p=list(self.taz_to_h3_cell[des_taz].values()))
                person.set_location(h3_cell=this_h3_cell, resolution=self.resolution,
                                    location_type='workplace', in_sim_area=in_sim_area,
                                    location_setter=location_setter)


    def assign_home(self, persons, location_setter=None):
        taz_to_persons = {}
        for person in persons:
            this_workplace_taz = self.h3_cell_to_taz[person.workplace['h3'][self.resolution]]['taz']
            if this_workplace_taz not in taz_to_persons:
                taz_to_persons[this_workplace_taz] = [person]
            else:
                taz_to_persons[this_workplace_taz].append(person)
        for taz, pop_in_this_taz in taz_to_persons.items():
            num_persons = len(pop_in_this_taz)
            ori_ratio = self.to_ratio[taz]
            ori_taz_list = np.random.choice(list(ori_ratio.keys()),
                                            size=num_persons,
                                            replace=True,
                                            p=list(ori_ratio.values()))
            for person, ori_taz in zip(pop_in_this_taz, ori_taz_list):
                if  location_setter:
                    in_sim_area = None
                else:
                    in_sim_area = ori_taz in self.in_sim_area_taz_list
                if self.quick_assign:
                    this_h3_cell = random.choice(list(self.taz_to_h3_cell[ori_taz].keys()))
                else:
                    this_h3_cell = np.random.choice(list(self.taz_to_h3_cell[ori_taz].keys()),
                                                    p=list(self.taz_to_h3_cell[ori_taz].values()))
                person.set_location(h3_cell=this_h3_cell, resolution=self.resolution,
                                    location_type='home', in_sim_area=in_sim_area,
                                    location_setter=location_setter)


    def compress_and_save(self, save_path):
        self.TAZ = None
        with open(save_path, 'wb') as f:
            pickle.dump(self, f)


    def build_lookups_between_taz_and_h3(self):
        od_h3 = {}
        for row_idx, row in self.commuting_od_df.iterrows():
            pass



class Population:
    def __init__(self, base_sim_pop_geojson_path=None,
                 base_floating_pop_json_path=None,
                 table='shenzhen', resolution=11,
                 person_attr_spec_path=None,
                 home_workplace_assigner_path=None,
                 location_setter=None, resolution_out=8):
        self.table = table
        self.work_dir = f'./cities/{table}'
        self.resolution = resolution
        if not person_attr_spec_path:
            person_attr_spec_path = os.path.join('cities', table, 'clean', 'person_attr_spec.json')
        try:
            self.person_attr_spec = json.load(open(person_attr_spec_path, 'r'))
        except:
            print('Warning: cannot load person_attr_spec')
            self.person_attr_spec = {}
        if base_sim_pop_geojson_path is not None and not os.path.exists(base_sim_pop_geojson_path):
            base_sim_pop_geojson_path = os.path.join('cities', table, 'geojson', base_sim_pop_geojson_path)
        self.base_sim_pop_geojson_path = base_sim_pop_geojson_path
        if base_floating_pop_json_path is not None and not os.path.exists(base_floating_pop_json_path):
            base_floating_pop_json_path = os.path.join('cities', table, 'geojson', base_floating_pop_json_path)
        self.base_floating_pop_json_path = base_floating_pop_json_path
        self.base_sim_pop = []
        self.base_floating_pop = []
        self.sim_pop = []
        self.h3_count_base_sim_pop = {}
        self.h3_count_sim_pop = {}
        if home_workplace_assigner_path is None:
            home_workplace_assigner_path = os.path.join('cities', table, 'models', 'home_workplace_assigner.p')
        if os.path.exists(home_workplace_assigner_path):
            self.home_workplace_assigner = pickle.load(open(home_workplace_assigner_path, 'rb'))
        else:
            self.home_workplace_assigner = None
        if location_setter:
            self.location_setter = location_setter
        else:
            try:
                bound_geojson_path = f'cities/{table}/geojson/bounds.geojson'
                self.location_setter = LocationSetter(bound_geojson_path, resolution, resolution_out)
            except Exception as e:
                raise ValueError(f'Error: failed to create a location setter\n{e}')

    def set_base_sim_population(self):
        features, src_crs = load_geojsons(self.base_sim_pop_geojson_path)
        transformer = Transformer.from_crs(src_crs, 4326) if src_crs != 4326 else None
        num_persons = len(features)
        random_persons_pool = self.generate_random_persons_pool(num_persons)
        for idx, fea in enumerate(features):
            person_idx = f'b{idx}'
            this_person_attrs = random_persons_pool[idx]   # this is just random attr combination as placeholder
            this_person_attrs_true = self.parse_person_attrs_from_individual_label_data(fea['properties'])
            this_person_attrs.update(this_person_attrs_true)
            thisPerson = Person(person_idx)
            thisPerson.set_person_attrs(this_person_attrs)
            coord = fea['geometry']['coordinates']
            if fea['geometry']['type'] == 'MultiPoint':
                coord = coord[0]
            if transformer:
                new_coord = transformer.transform(coord[1], coord[0])
                coord[0], coord[1] = new_coord[1], new_coord[0]
            thisPerson.set_location(self.location_setter, coord=coord, resolution=self.resolution, location_type='home')
            self.base_sim_pop.append(thisPerson)
            self.sim_pop.append(thisPerson)
        if self.home_workplace_assigner:
            self.home_workplace_assigner.assign_workplace(self.sim_pop, location_setter=self.location_setter)
        self.h3_count_base_sim_pop['home'] = {
            self.resolution: self.count_population_on_h3(self.base_sim_pop, self.resolution, 'home')
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

    def generate_random_persons_pool(self, num_persons, person_attr_spec=None):
        if not person_attr_spec:
            person_attr_spec = self.person_attr_spec
        attr_sampled_values = {}
        for attr_name, attr_spec in person_attr_spec.items():
            if type(attr_spec) == list:
                attr_sampled_values[attr_name] = sample_by_p(attr_spec, num_persons)
            else:
                attr_sampled_values[attr_name] = [attr_spec] * num_persons
        persons = [{attr_name: attr_sampled_values[attr_name][idx]
                    for attr_name in person_attr_spec} for idx in range(num_persons)]
        return persons

    def parse_person_attrs_from_individual_label_data(self, src_data_object, datetime_format='%Y/%m/%d', crt_year=2022):
        person_attrs = {}
        for raw_attr_name in individual_pop_attr_lookup:
            if raw_attr_name in src_data_object:
                attr_lookup = individual_pop_attr_lookup[raw_attr_name]
                new_attr_name = attr_lookup['attr_name']
                # print(attr_lookup, src_data_object[raw_attr_name], '\n\n')
                raw_attr_value = str(int(src_data_object[raw_attr_name]))
                new_attr_value = attr_lookup['value_lookup'][raw_attr_value]
                if 'resample' in attr_lookup and new_attr_value in attr_lookup['resample']:
                    new_attr_value = sample_by_p(attr_lookup['resample'][new_attr_value], num=1)
                person_attrs[new_attr_name] = new_attr_value
        if 'BIRTHDAY' in src_data_object:
            try:
                birth_year = time.strptime(src_data_object['BIRTHDAY'], datetime_format).tm_year
                person_attrs['age'] = crt_year - birth_year
            except:
                try:
                    birth_year = time.strptime(src_data_object['BIRTHDAY'].split(' ')[0], datetime_format).tm_year
                    person_attrs['age'] = crt_year - birth_year
                except:
                    print('Fail to convert this birthday to age: ', src_data_object['BIRTHDAY'])
        return person_attrs


class Person:
    def __init__(self, person_idx):
        self.idx = person_idx
        self.home = {'coord':None, 'h3': {}}
        self.workplace = {'coord':None, 'h3': {}}
        self.attrs = {}
        self.trips = []


    def set_person_attrs(self, person_attrs):
    # def set_person_attrs(self, person_attrs, src_data_object=None, default_value=None, datetime_format='%Y/%m/%d', crt_year=None):
    #     if type(default_value) != dict:
    #         default_value = {attr: default_value for attr in attrs}
    #     if type(attrs) == list:
    #         attrs = {attr: default_value[attr] for attr in attrs}
    #     if src_data_object:
    #         for attr in attrs:
    #             self.attrs[attr] = self._set_person_attr_from_src_data(attr,
    #                                                                    src_data_object,
    #                                                                    default_value[attr],
    #                                                                    datetime_format,
    #                                                                    crt_year)
        self.attrs = person_attrs

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

    def set_location(self, location_setter=None, coord=None, h3_cell=None,
                     location_type='home', in_sim_area=None, resolution=None):
        if location_setter:
            location_obj = location_setter.set_location(coord, h3_cell, in_sim_area, resolution)
            if location_type == 'home':
                self.home = location_obj
            elif location_type == 'workplace':
                self.workplace = location_obj
        else:
            if coord:
                h3_cell = h3.geo_to_h3(coord[1], coord[0], resolution) if resolution else None
            elif h3_cell:
                coord = h3.h3_to_geo(h3_cell)[::-1]
            else:
                raise ValueError(f'coord and h3_cell cannot be both None')
            if location_type == 'home':
                self.home['coord'] = coord
                self.home['h3'].update({resolution: h3_cell})
                self.home['in_sim_area'] = in_sim_area
            elif location_type == 'workplace':
                self.workplace['coord'] = coord
                self.workplace['h3'].update({resolution: h3_cell})
                self.workplace['in_sim_area'] = in_sim_area

    def trips_to_list(self):
        trips_list = []
        for tid, trip in enumerate(self.trips):
            this_trip_record = {
                'person_id': self.idx,
                'trip_id': tid,
                'num_all_vehicles': self.attrs['num_all_vehicles'],
                'num_all_bikes': self.attrs['num_all_bikes'],
                'hh_size': self.attrs['hh_size'],
                'income': self.attrs['income'],
                'register_in_sz': self.attrs['register_in_sz'],
                'education': self.attrs['education'],
                'gender': self.attrs['gender'],
                'age': self.attrs['age'],
                'occupation': self.attrs['occupation'],
                'residence_type': self.attrs['residence_type'],
                'hh_anual_income': self.attrs['hh_anual_income'],
                'purpose': trip.purpose
            }
            if trip.mode_choice_set:
                for mode in trip.mode_choice_set:
                    this_trip_record[mode + '_route'] = trip.mode_choice_set[mode].costs
                # todo: better way to calc network_dist_km
                # this_trip_record['network_dist_km'] = this_trip_record['driving_route']['driving'] * 30 / 60
                network_dist_km = (trip.mode_choice_set['driving'].internal_route['internal_route']['total_distance'] +
                                   trip.mode_choice_set['driving'].external_distance) / 1000
                this_trip_record['network_dist_km'] = network_dist_km
                if this_trip_record['network_dist_km'] > 0:
                    trips_list.append(this_trip_record)
                else:
                    print('Warning: non-positive distance found and discarded: ', [trip.enters_sim, trip.purpose])
        return trips_list


class HousingUnits:
    def __init__(self, housing_type_def=None, table='shenzhen', resolution=11):
        self.table = table
        self.set_housing_type_def(housing_type_def)
        self.base_housing = []
        self.new_housing = []
        self.all_housing = []
        self.resolution = resolution

    def set_housing_type_def(self, housing_type_def):
        self.housing_type_def = {}
        if type(housing_type_def) == dict:
            self.housing_type_def = housing_type_def
        elif type(housing_type_def) == str:
            for try_spec_path in [housing_type_def, os.path.join('cities', self.table, 'clean', housing_type_def)]:
                if os.path.exists(try_spec_path) and os.path.isfile(try_spec_path):
                    content = json.load(open(try_spec_path, 'r'))
                    if 'housing_type_def' in content:
                        self.housing_type_def = content['housing_type_def']
                    else:
                        self.housing_type_def = content

    def set_base_housing_units_from_buildings(self, Buildings, housing_type_attr='housing_type',
                                              usage_attr='usage', decompose_attr='LBCS', area_attr='area',
                                              residential_code='11', first_n_digits=2,
                                              default_housing_type='residential_medium'):
        """
        :param Buildings: should be an instance of GeoData (PolygonData)
        :param housing_type_attr:
        :param default_housing_type:
        :return:
        """
        self.base_housing.clear()
        if self.resolution not in Buildings.map_to_h3_cells:
            Buildings.link_to_h3(self.resolution)
        for bldg_fea, h3_cell_mapping in zip(Buildings.features[Buildings.crs['geographic']],
                                             Buildings.map_to_h3_cells[self.resolution]):
            # e.g., area_decomposition = properties['usage']['LBCS']['area'] = {'1150':1000, '2200': 200}
            ratio_decomposition = bldg_fea['properties'].get(usage_attr, {}).get(decompose_attr, {})
            residential_ratio = sum([ratio for code, ratio in ratio_decomposition.items() if
                                    (str(code)[:first_n_digits] if first_n_digits else str(code)) == residential_code])
            if not residential_ratio > 0:
                continue
            residential_area = residential_ratio * bldg_fea['properties'][usage_attr][area_attr]
            housing_type = bldg_fea['properties'].get(housing_type_attr, default_housing_type)
            if housing_type not in self.housing_type_def:
                print(f'Residential building ignored when set housing units for unknown housing type [{housing_type}]')
                continue
            else:
                housing_attrs = self.housing_type_def[housing_type]
            num_housing_units = max(1, round(residential_area / housing_attrs['area']))
            h3_cell_assignments = random.choices(list(h3_cell_mapping.keys()),
                                                 weights=[h3_info['weight_in_raw_data']
                                                          for h3_info in h3_cell_mapping.values()],
                                                 k=num_housing_units)
            crt_idx = len(self.base_housing)
            self.base_housing.extend([
                HousingUnit(housing_idx=f'b{crt_idx+idx}',
                            housing_type=housing_type,
                            vacant=False,
                            h3_cell=h3_cell,
                            resolution=self.resolution)
                for idx, h3_cell in enumerate(h3_cell_assignments)
            ])

        self.all_housing = self.base_housing + self.new_housing


    def add_new_housing_units(self, housing_type, h3_cells, housing_type_attrs=None):
        crt_idx = len(self.new_housing)
        if housing_type_attrs and housing_type not in self.housing_type_def:
            self.housing_type_def[housing_type] = housing_type_attrs
        self.new_housing.extend([
            HousingUnit(housing_idx=f'n{crt_idx+idx}',
                        housing_type=housing_type,
                        vacant=True,
                        h3_cell=h3_cell,
                        resolution=self.resolution)
            for idx, h3_cell in enumerate(h3_cells)
        ])

    def get_tt_capacity(self, housing_units, default_capacity=3):
        if type(housing_units) == str:
            if housing_units == 'base':
                housing_units = self.base_housing
            elif housing_units == 'new':
                housing_units = self.new_housing
            elif housing_units == 'all':
                housing_units = self.all_housing
            else:
                raise ValueError('Unrecognized housing units alias')
        tt_capacity = sum([self.housing_type_def[h.housing_type].get(
            'num_household_members', default_capacity) for h in housing_units])
        return tt_capacity


class HousingUnit:
    def __init__(self, housing_idx, housing_type, vacant, coord=None, h3_cell=None, resolution=None):
        self.idx = housing_idx
        self.housing_type = housing_type
        self.loc = {'coord':None, 'h3': {}}
        self.vacant = vacant
        if coord or (h3_cell and resolution):
            self.set_location(coord, h3_cell, resolution)

    def set_location(self, coord=None, h3_cell=None, resolution=None):
        if coord:
            h3_cell = h3.geo_to_h3(coord[1], coord[0], resolution) if resolution else None
        elif h3_cell:
            coord = h3.h3_to_geo(h3_cell)[::-1]
        else:
            raise ValueError(f'coord and h3_cell cannot be both None')
        self.loc['coord'] = coord
        self.loc['h3'].update({resolution: h3_cell})
