import os
import h3.api.numpy_int as h3
import numpy as np
from collections import Counter
from grids_toolbox import H3Grids
from indicator_toolbox import Indicator
from itertools import product


class DiversityIndicator(Indicator):
    def __init__(self, H3, name='diversity', Table=None):
        super().__init__(H3, name, Table)
        self.default_lbcs_codes = {
            'residential': ['1101', '1105', '1150'],
            'third_places': ['2510', '2520', '2530', '2540'],
        }
        self.default_naics_codes = {
            'jobs': [
                '11', '21', '22', '23', '31',
                # '32', '33', '42',
                '44', '45', '48', '49', '51', '52',
                '53', '54', '55', '56', '61', '62', '71',
                '72', '81', '92'
            ],
            'education': ['6111', '6113', '6115', '6116']
        }


    def _calc_diversity(self, population_list, log_base='e'):
        population_list = np.asarray(population_list)
        sum_pop = population_list.sum()
        if sum_pop == 0:
            print('Warning: ill population and diversity results as sum(population)=0')
            return {
                'shannon_diversity_index': 0,
                'evenness': 0,
                'richness': 0,
                'total_population': 0,
                'average_population': 0
            }
        ratio = population_list / sum_pop
        ratio = np.clip(ratio, 1e-20, 1)
        richness = len(population_list)
        avg_pop = sum_pop / richness
        even_prop = 1 / richness
        if log_base == 'e':
            log_ratio = np.log(ratio)
            log_even_prop = np.log(even_prop)
        elif log_base == 10:
            log_ratio = np.log10(ratio)
            log_even_prop = np.log10(even_prop)
        elif log_base == 2:
            log_ratio = np.log2(ratio)
            log_even_prop = np.log2(even_prop)
        else:
            raise TypeError('log_base must be one of "e", 2, and 10')
        raw_shannon = -np.sum(log_ratio * ratio)
        min_possible_shannon = 0
        max_possible_shannon = - even_prop * log_even_prop * len(population_list)
        if max_possible_shannon != min_possible_shannon:
            evenness = (raw_shannon - min_possible_shannon) / (max_possible_shannon - min_possible_shannon)
        else:
            evenness = 0
        return {
            'shannon_diversity_index': raw_shannon,
            'evenness': evenness,
            'richness': richness,
            'total_population': sum_pop,
            'average_population': avg_pop
        }


    def return_residential_diversity(self, name='residential_diversity', method='lbcs', item_name='area',
                                     target_lbcs_codes=None, usage_name='usage', first_n_digits=None,
                                     target_housing_types=None):
        if method == 'lbcs':
            assert item_name in ['area', 'pop']
            if not target_lbcs_codes:
                target_lbcs_codes = self.default_lbcs_codes['residential']
                first_n_digits = None
            return self.return_usage_diversity(name, target_lbcs_codes, 'LBCS', item_name, usage_name, first_n_digits)
        elif method == 'housing_types':
            housing_units = self.H3.Housing.all_housing
            housing_type_def = self.H3.Housing.housing_type_def
            housing_type_stats = dict(Counter([h.housing_type for h in housing_units]))
            if target_housing_types:
                housing_type_stats = {h_type:count for h_type, count in housing_type_stats.items()
                                      if h_type in target_housing_types}
            if item_name == 'count':
                pass
            if item_name == 'area':
                for h_type, count in housing_type_stats.items():
                    housing_type_stats[h_type] = count * housing_type_def['h_type']['area']
            if item_name == 'pop':
                for h_type, count in housing_type_stats.items():
                    housing_type_stats[h_type] = count * housing_type_def['h_type']['num_household_members']
            rst = self._calc_diversity(population_list=list(housing_type_stats.values()))
            return {
                'name': name,
                'composition': housing_type_stats,
                'raw': rst['shannon_diversity_index'],
                'normalized': rst['evenness'],
                'to_frontend': rst['evenness']
            }
        elif method == 'profiles':
            # todo: add person file
            pass
        else:
            raise ValueError(f'Unrecognized method: {method}')


    def return_job_diversity(self, name='job_diversity', target_naics_codes=None, item_name='pop',
                             usage_name='usage', first_n_digits=None):
        if not target_naics_codes:
            target_naics_codes = self.default_naics_codes['jobs']
            first_n_digits = None
        return self.return_usage_diversity(name, target_naics_codes, 'NAICS', item_name, usage_name, first_n_digits)


    def return_residential_job_ratio(self, name='residential_job_ratio', usage_name='usage'):
        Pop, Housing = self.H3.Pop, self.H3.Housing
        num_residents = len(Pop.base_sim_pop) + Housing.get_tt_capacity('new')
        num_jobs = 0
        for h3_cell, h3_attrs in self.H3.h3_stats.items():
            num_jobs += sum(h3_attrs[usage_name].get('NAICS', {}).get('pop', {}).values())
        ratio_raw = num_residents / num_jobs
        ratio_norm = 2 * min(num_residents, num_jobs) / (num_residents + num_jobs)
        return {
            'name': name,
            'raw': ratio_raw,
            'norm': ratio_norm,
            'to_frontend': ratio_norm
        }


    def return_usage_diversity(self, name, target_classes, attr_name='LBCS', item_name='area', usage_name='usage', first_n_digits=None):
        if type(target_classes) != list:
            raise TypeError(f'target_classes must be a list: {target_classes}')
        target_classes = [str(class_name) for class_name in target_classes]
        class_stats = {class_name: 0 for class_name in target_classes}
        for h3_cell, class_name in product(self.H3.h3_stats, target_classes):
            decomposition = self.H3.h3_stats[h3_cell].get(usage_name, {}).get(attr_name, {}).get(item_name, {})
            if not first_n_digits:
                class_stats[class_name] += decomposition.get(str(class_name), 0)
            else:
                class_stats[class_name] += sum([value for code, value in decomposition.items()
                                                if str(code)[:first_n_digits] in target_classes])
        rst = self._calc_diversity(list(class_stats.values()), 'e')
        return {'name': name,
                'composition': class_stats,
                'raw': rst['shannon_diversity_index'],
                'normalized': rst['evenness'],
                'to_frontend': rst['evenness']}


    def return_lbcs_area_diversity(self, name, target_lbcs_codes, usage_name='usage', first_n_digits=None):
        if type(target_lbcs_codes) == str:
            try:
                target_lbcs_codes = self.default_lbcs_codes[target_lbcs_codes]
            except:
                raise TypeError(f'target_classes is not a list and cannot be found in default definition: {target_lbcs_codes}')
        return self.return_usage_diversity(name, target_lbcs_codes, 'LBCS', 'area', usage_name, first_n_digits)


    def return_naics_diversity(self, name, target_naics_codes, item_name='pop', usage_name='usage', first_n_digits=None):
        if type(target_naics_codes) == str:
            try:
                target_naics_codes = self.default_naics_codes[target_naics_codes]
            except:
                raise TypeError(f'target_classes is not a list and cannot be found in default definition: {target_naics_codes}')
        return self.return_usage_diversity(name, target_naics_codes, 'NAICS', item_name, usage_name, first_n_digits)


def test(num_trials=3):
    import pickle, time

    vars = pickle.load(open('cities/shenzhen/clean/base_data.p', 'rb'))
    Table, H3 = vars['Table'], vars['H3']

    D = DiversityIndicator(H3, Table=Table)

    for trial in range(num_trials):
        print(f'\n\nTrial {trial+1}\n' + '=='*30)
        layout_str, layout_ratio = Table.update_randomly(zone=1)
        t0 = time.time()
        residential_diversity = D.return_residential_diversity()
        job_diversity = D.return_job_diversity()
        residential_job_ratio = D.return_residential_job_ratio()
        third_place_diversity = D.return_lbcs_area_diversity('third_place_diversity',
                                                             target_lbcs_codes='third_places')
        t1 = time.time()
        print('{:4.4} seconds elapsed for computing 4 diversity indicators'.format(t1-t0))
        print(f'{residential_diversity}\n{job_diversity}\n{residential_job_ratio}\n{third_place_diversity}')


if __name__ == '__main__':
    test(num_trials=3)