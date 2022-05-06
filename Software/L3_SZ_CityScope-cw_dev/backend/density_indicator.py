import os
import h3.api.numpy_int as h3
import numpy as np
from grids_toolbox import H3Grids
from indicator_toolbox import Indicator
from itertools import product
from utils import num_neighbours_in_digraph, get_first_n_digits

class DensityIndicator(Indicator):
    def __init__(self, H3, name='density', Table=None, base_area=None):
        super().__init__(H3, name, Table)
        if base_area:
            self.base_area = base_area
        elif Table:
            self.base_area = Table.spec['parcel_area'] * Table.spec['nrow'] * Table.spec['ncol']
        else:
            raise ValueError('Unknown base area')
        assert self.base_area > 0
        self.default_lbcs_codes = {
            'third_places': ['2100', '2200', '2300', '7240'],
        }
        self.default_naics_codes = {
            'jobs': [
                '11', '21', '22', '23', '31', '32', '33',
                '42', '44', '45', '48', '49', '51', '52',
                '53', '54', '55', '56', '61', '62', '71',
                '72', '81', '92'
            ],
            'education': ['6111', '6113', '6115', '6116']
        }


    def return_resident_density(self, name='resident_density'):
        Pop, Housing = self.H3.Pop, self.H3.Housing
        num_residents = len(Pop.base_sim_pop) + Housing.get_tt_capacity('new')
        density_raw = num_residents / self.base_area
        density_norm = density_raw
        return {
            'name': name,
            'raw': density_raw,
            'norm': density_norm,
            'to_frontend': density_norm
        }


    def return_job_density(self, name='job_density', usage_name='usage'):
        num_jobs = 0
        for h3_cell, h3_attrs in self.H3.h3_stats.items():
            num_jobs += sum(h3_attrs[usage_name].get('NAICS', {}).get('pop', {}).values())
        density_raw = num_jobs / self.base_area
        density_norm = density_raw
        return {
            'name': name,
            'raw': density_raw,
            'norm': density_norm,
            'to_frontend': density_norm
        }


    def return_usage_density(self, name, target_classes, attr_name='LBCS',
                             item_name='area', unit_area=None,
                             usage_name='usage', first_n_digits=None):
        if item_name == 'count':
            assert unit_area > 0
        target_classes = [str(code) for code in target_classes]
        tt_area, tt_pop = 0, 0
        for h3_cell, h3_attrs in self.H3.h3_stats.items():
            decomposition = h3_attrs.get(usage_name, {}).get(attr_name, {})
            tt_area += sum([area for code, area in decomposition.get('area', {}).items()
                            if get_first_n_digits(code, first_n_digits) in target_classes])
            tt_pop += sum([area for code, area in decomposition.get('pop', {}).items()
                           if get_first_n_digits(code, first_n_digits) in target_classes])
        if item_name == 'area':
            tt = tt_area
        elif item_name == 'count':
            tt = tt_area / unit_area
        elif item_name == 'pop':
            tt = tt_pop
        else:
            raise ValueError(f'Unrecognized unit: {unit}')
        density_raw = tt / self.base_area
        density_norm = density_raw
        return {
            'name': name,
            'raw': density_raw,
            'norm': density_norm,
            'to_frontend': density_norm
        }


    def return_lbcs_density(self, name, target_lbcs_codes, item_name='area',
                            unit_area=None, usage_name='usage', first_n_digits=None):
        if type(target_lbcs_codes) == str:
            try:
                target_lbcs_codes = self.default_lbcs_codes[target_lbcs_codes]
            except:
                raise TypeError(
                    f'target_classes is not a list and cannot be found in default definition: {target_lbcs_codes}')
        return self.return_usage_density(name, target_lbcs_codes, 'LBCS', item_name, unit_area,
                                         usage_name, first_n_digits)


    def return_naics_density(self, name, target_naics_codes, item_name='area',
                             unit_area=None, usage_name='usage', first_n_digits=None):
        if type(target_naics_codes) == str:
            try:
                target_naics_codes = self.default_naics_codes[target_naics_codes]
            except:
                raise TypeError(
                    f'target_classes is not a list and cannot be found in default definition: {target_naics_codes}')
        return self.return_usage_density(name, target_naics_codes, 'NAICS', item_name, unit_area,
                                         usage_name, first_n_digits)


    def return_intersection_density(self, road_network, name='intersection_density'):
        """
        Return traffic network intersection density
        :param road_network: a networkx.DiG
        :param by:
        :return:
        """
        intersections = [
            node for node in road_network.nodes
            if num_neighbours_in_digraph(road_network, node) > 2
        ]
        num_intersections = len(intersections)
        density_raw = num_intersections / self.base_area
        density_norm = density_raw
        return {
            'name': name,
            'raw': density_raw,
            'norm': density_norm,
            'to_frontend': density_norm
        }


def test(num_trials=3):
    import pickle, time

    vars = pickle.load(open('cities/shenzhen/clean/base_data.p', 'rb'))
    Table, H3 = vars['Table'], vars['H3']
    network = pickle.load(open('cities/shenzhen/clean/sim_network.p', 'rb'))

    D = DensityIndicator(H3, Table=Table)

    for trial in range(num_trials):
        print(f'\n\nTrial {trial+1}\n' + '=='*30)
        layout_str, layout_ratio = Table.update_randomly(zone=1)

        t0 = time.time()
        residential_density = D.return_resident_density()
        job_density = D.return_job_density()
        intersection_density = D.return_intersection_density(network)
        third_place_density = D.return_lbcs_density('third_place_density',
                                                    target_lbcs_codes='third_places')
        t1 = time.time()
        print('{:4.4} seconds elapsed for computing 4 density indicators'.format(t1-t0))
        print(f'{residential_density}\n{job_density}\n{intersection_density}\n{third_place_density}')


if __name__ == '__main__':
    test(num_trials=3)