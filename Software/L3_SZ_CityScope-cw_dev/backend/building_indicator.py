import os, joblib, pickle
import pandas as pd
from indicator_toolbox import Indicator
from model_fitting_toolbox import fit_rf_regressor
from population_toolbox import HousingUnit

pba_to_lbcs={
    1: '9000',   # Vacant => Agriculture, forestry, fishing and hunting
    2: '2400',   # Office => Business, professional, scientific, and technical services
    4: '2400',   # Laboratory => Business, professional, scientific, and technical services
    5: '3000',   # Nonrefrigerated warehouse => Manufacturing and wholesale trade
    6: '2500',   # Food sales => Food services
    7: '6400',   # Public order and safety => Public Safety
    8: '6500',   # Outpatient health care => Health and human services
    11: '3000',  # Refrigerated warehouse => Manufacturing and wholesale trade
    12: '6600',  # Religious worship => Religious institutions
    13: '5000',  # Public assembly => Arts, entertainment, and recreation
    14: '6100',  # Education => Educational services
    15: '2500',  # Food service => Food services
    16: '6500',  # Inpatient health care => Health and human services
    17: '6500',  # Nursing => Health and human services
    18: '1300',  # Lodging =》Hotels, motels, or other accommodation services
    23: '2100',  # Strip shopping mall => Retail sales or service
    24: '2100',  # Enclosed mall => Retail sales or service
    25: '2100',  # Retail other than mall => Retail sales or service
    26: '4300',  # Service => Utilities and utility services
    91: '9000',  # Other => Agriculture, forestry, fishing and hunting
}

# some other lbcs are also existing, make it recognizable by referring to similar lbcs
lbcs_refer = {
    '2200': '2400',  # Finance and Insurance => Business, professional, scientific, and technical services
    '4200': '4300',  # Communications and information => Utilities and utility services
    '5100': '5000',  # Performing arts or supporting establishment => Arts, entertainment, and recreation
    '5200': '5000',  # Museums and other special purpose recreational institutions => Arts, entertainment, and recreatio
    '5300': '5000',  # Amusement, sports, or recreation establishment => Arts, entertainment, and recreatio
    '5500': '9000',  # Natural and other recreational parks => Agriculture, forestry, fishing and hunting?
    '6200': '6400',  # Public administration => Public Safety
}


climate_coding_commercial = {
    1: 'Very cold/Cold',
    2: 'Mixed-humid',
    3: 'Hot-dry/Mixed-dry/Hot-humid',
    5: 'Marine',
    7: 'Withheld to protect confidentiality'
}

def get_formatted_climate(climate, return_for):
    if climate in ['Very cold', 'Cold']:
        if return_for == 'commercial':
            return 'Very cold/Cold'
        else:
            return 'Cold/Very Cold'
    elif climate in ['Marine']:
        return climate
    elif climate in ['Mixed-humid']:
        if return_for == 'commercial':
            return 'Mixed-humid'
        else:
            return 'Mixed-Humid'
    elif climate in ['Hot-dry', 'Mixed-dry']:
        if return_for == 'commercial':
            return 'Hot-dry/Mixed-dry/Hot-humid'
        else:
            return 'Hot-Dry/Mixed-Dry'
    elif climate in ['Hot-humid']:
        if return_for == 'commercial':
            return 'Hot-dry/Mixed-dry/Hot-humid'
        else:
            return 'Hot-Humid'
    else:
        raise ValueError(f'Unrecognized climate')


class BuildingEnergyIndicator(Indicator):
    def __init__(self, H3, name='building_energy', Table=None, climate='Hot-humid'):
        super().__init__(H3, name, Table)
        self.training_data_path = {'commercial': None, 'residential': None}
        self.model_path = {'commercial': None, 'residential': None}
        self.models = {'commercial': None, 'residential': None}
        self.climate = {
            'commercial': get_formatted_climate(climate, 'commercial'),
            'residential': get_formatted_climate(climate, 'residential')
        }
        if self.work_dir:
            training_data_dir = os.path.join(self.work_dir, 'raw', 'building_energy')
            self.training_data_path.update({
                'commercial': os.path.join(training_data_dir, '2012_public_use_data_aug2016.csv'),
                'residential': os.path.join(training_data_dir, 'recs2015_public_v4.csv'),
            })
            model_dir = os.path.join(self.work_dir, 'models', 'building_energy')
            if os.path.exists(self.work_dir) and not os.path.exists(model_dir):
                os.makedirs(model_dir)
            self.model_path.update({
                'commercial': os.path.join(model_dir, 'commercial.p'),
                'residential': os.path.join(model_dir, 'residential.p'),
            })
        self.load_models()
        self.base_energy = {'commercial': {}, 'residential': {}}
        self.norm_bounds = {'min': 10000, 'max': 50000}

    def load_models(self, bldg_types=('commercial', 'residential'), retrain=True):
        for bldg_type in bldg_types:
            try:
                self.models[bldg_type] = joblib.load(self.model_path[bldg_type])
            except Exception as e:
                print(f'\nFail to load [{bldg_type}] building energy model: {e}')
                if retrain:
                    self.train(bldg_types=[bldg_type])

    def train(self, bldg_types=('commercial', 'residential'), n_estimators=64, n_iter=512, verbose=1):
        for bldg_type in bldg_types:
            if bldg_type == 'commercial':
                self._train_commercial_building_energy_model(n_estimators, n_iter, verbose)
            elif bldg_type == 'residential':
                self._train_residential_building_energy_model(n_estimators, n_iter, verbose)

    def _train_commercial_building_energy_model(self, n_estimators, n_iter, verbose=1):
        data_df = pd.read_csv(self.training_data_path['commercial'], encoding='utf-8')
        data_df.loc[data_df['NFLOOR'] == 994, 'NFLOOR'] = 20
        data_df.loc[data_df['NFLOOR'] == 995, 'NFLOOR'] = 30
        # data_df['AGE'] = data_df.apply(lambda row: row['YRCONC'], axis=1)
        data_df['LBCS'] = data_df.apply(lambda row: pba_to_lbcs[row['PBA']], axis=1)
        data_df['SQM'] = 0.092 * data_df['SQFT']
        data_df['CLIMATE'] = data_df.apply(lambda row: climate_coding_commercial[int(row['PUBCLIM'])], axis=1)

        numerical_regressors = ['NFLOOR', 'NWKER', 'SQM']
        categorical_regressors = ['LBCS', 'CLIMATE']
        target = 'MFBTU'
        rst = fit_rf_regressor(data_df, target, numerical_regressors, categorical_regressors,
                               n_estimators=n_estimators, n_iter=n_iter, verbose=verbose)
        self.models['commercial'] = rst
        joblib.dump(rst, self.model_path['commercial'])

    def _train_residential_building_energy_model(self, n_estimators, n_iter, verbose=1):
        data_df = pd.read_csv(self.training_data_path['residential'], encoding='utf-8')
        data_df.loc[data_df['NUMBERAC'] < 0, 'NUMBERAC'] = 0
        data_df = data_df.loc[data_df['TYPEHUQ'].isin([2, 3, 4, 5])]   # get rid of mobile house
        data_df['SQM'] = (data_df['TOTCSQFT'] + data_df['TOTUCSQFT']) * 0.092

        numerical_regressors = ['TOTROOMS', 'BEDROOMS', 'SQM', 'NHSLDMEM', 'NUMFRIG', 'NUMBERAC', 'TVCOLOR']
        categorical_regressors = ['CLIMATE_REGION_PUB', 'FUELHEAT']
        target = 'TOTALBTU'
        rst = fit_rf_regressor(data_df, target, numerical_regressors, categorical_regressors,
                               n_estimators=n_estimators, n_iter=n_iter, verbose=verbose)
        self.models['residential'] = rst
        joblib.dump(rst, self.model_path['residential'])

    def return_energy_pperson(self, name, bldg_types=('commercial', 'residential'),
                              norm_minV=None, norm_maxV=None):
        if not norm_minV:
            norm_minV = self.norm_bounds['min']
        if not norm_maxV:
            norm_maxV = self.norm_bounds['max']
        tt_energy, tt_pop = 0, 0
        for bldg_type in bldg_types:
            if bldg_type == 'commercial':
                commercial_new = self.predict_commercial_building_energy(input_data=self.H3.h3_stats_interactive,
                                                                         input_dtype='h3_stats')
                tt_energy += self.base_energy['commercial'].get('tt_energy', 0)
                tt_energy += commercial_new['BTU_pred'].sum()
                tt_pop += self.base_energy['commercial'].get('tt_pop', 0)
                tt_pop += commercial_new['NWKER'].sum()
            elif bldg_type == 'residential':
                residential_new = self.predict_residential_building_energy(housing_units='new')
                tt_energy += self.base_energy['residential'].get('tt_energy', 0)
                tt_energy += residential_new['BTU_pred'].sum()
                tt_pop += self.base_energy['residential'].get('tt_pop', 0)
                tt_pop += residential_new['NHSLDMEM'].sum()
        energy_pperson = tt_energy / tt_pop if tt_pop > 0 else 0
        if energy_pperson == 0:
            norm_energy_pperson = 0
        else:
            norm_energy_pperson = self.normalization(energy_pperson, minV=norm_minV, maxV=norm_maxV, better='low')
        return {'name': name,
                'raw': energy_pperson,
                'unit': 'BTU/person*year',
                'normalized': norm_energy_pperson,
                'to_frontend': norm_energy_pperson}

    def predict_commercial_building_energy(self, input_data, input_dtype='h3_cells'):
        if input_dtype == 'buildings':
            df_pred = self._collect_commercial_features_from_buildings(input_data)
        else:
            df_pred = self._collect_commercial_features_from_h3_cells(input_data)
        model = self.models['commercial']['model']
        if df_pred.shape[0] > 0:
            y_pred = model.predict(df_pred.values)
            df_pred['BTU_pred'] = y_pred
        else:
            # empty dataset => create a empty df instead
            df_pred = pd.DataFrame(columns=['BTU_pred', 'NWKER'])
        return df_pred

    def _collect_commercial_features_from_buildings(self, buildings, usage_name='usage', num_floor_name='NFLOOR'):
        records = []
        commerical_features = self.models['commercial']['features']
        accept_lbcs_list = [fea.split('_')[1] for fea in commerical_features if fea.startswith('LBCS_')]
        for bldg in buildings:
            bldg = bldg['properties']
            full_lbcs = bldg['usage']['LBCS']
            if not full_lbcs:   # empty for roads, backup, etc.
                continue
            # get the first 2 digits of the lbcs code with maximum share
            main_lbcs = max(full_lbcs, key=full_lbcs.get)[:2] + '00'
            main_lbcs = lbcs_refer.get(main_lbcs, main_lbcs)
            if main_lbcs not in accept_lbcs_list:
                continue
            this_record = {fea: 0 for fea in commerical_features}
            this_record.update({
                'NFLOOR': bldg[num_floor_name],
                'SQM': bldg[usage_name]['area'],
                f'LBCS_{main_lbcs}': 1,
                'NWKER': bldg[usage_name]['area'] / bldg[usage_name]['sqm_pperson'],
                f"CLIMATE_{self.climate['commercial']}": 1
            })
            records.append(this_record)
        df_pred = pd.DataFrame(records)
        return df_pred

    def _collect_commercial_features_from_h3_cells(self, h3_stats, usage_name='usage'):
        records = []
        commerical_features = self.models['commercial']['features']
        accept_lbcs_list = [fea.split('_')[1] for fea in commerical_features if fea.startswith('LBCS_')]
        for h3_cell, h3_attrs in h3_stats.items():
            full_lbcs = h3_attrs[usage_name]['LBCS']['pop']
            if not full_lbcs:   # empty for roads, backup, etc.
                continue
            # get the first 2 digits of the lbcs code with maximum share
            main_lbcs = max(full_lbcs, key=full_lbcs.get)[:2] + '00'
            main_lbcs = lbcs_refer.get(main_lbcs, main_lbcs)
            if main_lbcs not in accept_lbcs_list:
                continue
            this_record = {fea: 0 for fea in commerical_features}
            tt_area = sum(h3_attrs[usage_name]['LBCS']['area'].values())
            tt_workers = sum(h3_attrs[usage_name]['LBCS']['pop'].values())
            if 'height' in h3_attrs:
                num_floors = h3_attrs['height']
            else:
                num_floors =  max(1, int(tt_area / self.H3.h3_cell_area))
            this_record.update({
                'NFLOOR': num_floors,
                'SQM': tt_area,
                f'LBCS_{main_lbcs}': 1,
                'NWKER': tt_workers,
                f"CLIMATE_{self.climate['commercial']}": 1
            })
            records.append(this_record)
        df_pred = pd.DataFrame(records)
        return df_pred

    def predict_residential_building_energy(self, housing_units):
        df_pred = self._collect_residential_features(housing_units)
        model = self.models['residential']['model']
        if df_pred.shape[0] > 0:
            y_pred = model.predict(df_pred.values)
            df_pred['BTU_pred'] = y_pred
        else:
            # empty dataset => create a empty df instead
            df_pred = pd.DataFrame(columns=['BTU_pred', 'NHSLDMEM'])
        return df_pred

    def _collect_residential_features(self, housing_units):
        records = []
        residential_features = self.models['residential']['features']
        if type(housing_units) == str:
            if housing_units == 'new':
                housing_units = self.H3.Housing.new_housing
            elif housing_units == 'base':
                housing_units = self.H3.Housing.base_housing
            elif housing_units == 'all':
                housing_units = self.H3.Housing.all_housing
            else:
                raise ValueError('Unrecognized housing_units string')
        elif type(housing_units) == list and isinstance(housing_units[0], HousingUnit):
            pass
        else:
            raise ValueError('Invalid housing_units')
        for house in housing_units:
            this_record = {fea: 0 for fea in residential_features}
            housing_attrs = self.H3.Housing.housing_type_def[house.housing_type]
            fuel_heat_code = housing_attrs.get('fuel_heat_code', 5)  # default=5: electricity
            this_record.update({
                'TOTROOMS': housing_attrs.get('num_rooms', 6),
                'BEDROOMS': housing_attrs.get('num_bedrooms', 3),
                'SQM': housing_attrs.get('area', 120),
                'NHSLDMEM': housing_attrs.get('num_household_members', 3),
                'NUMFRIG': housing_attrs.get('num_fridge', 2),
                'NUMBERAC': housing_attrs.get('num_ac', 2),
                'TVCOLOR': housing_attrs.get('num_tv', 2),
                f"CLIMATE_REGION_PUB_{self.climate['residential']}": 1,
                f'FUELHEAT_{fuel_heat_code}': 1
            })
            records.append(this_record)
        df_pred = pd.DataFrame(records)
        return df_pred

    def set_base_energy(self, bldg_type, tt_energy, tt_pop):
        self.base_energy[bldg_type] = {
            'tt_energy': tt_energy,
            'tt_pop': tt_pop,
            'btu_pperson': tt_energy/tt_pop if tt_pop>0 else 0
        }

def test(num_trials=3):
    from geodata_toolbox import PolygonGeoData
    from population_toolbox import HousingUnits
    import time

    vars = pickle.load(open('cities/shenzhen/clean/base_data.p', 'rb'))
    Table, H3 = vars['Table'], vars['H3']
    print('Table and H3 loaded')
    BE = BuildingEnergyIndicator(H3, Table=Table)

    Buildings = PolygonGeoData(name='buildings', src_geojson_path='0323/building_final.geojson')
    H3.Housing.set_housing_type_def('housing_type_def.json')
    H3.Housing.set_base_housing_units_from_buildings(Buildings)

    t0 = time.time()
    rst = BE.predict_commercial_building_energy(input_data=Buildings.features[Buildings.crs['src']],
                                                input_dtype='buildings')
    t1 = time.time()
    print('Energy per worker for base buildings: {:4.2f} BTU/person, time costed: {:4.2f} seconds'.format(
        rst['BTU_pred'].sum() / rst['NWKER'].sum(), t1-t0
    ))
    BE.set_base_energy(bldg_type='commercial', tt_energy=rst['BTU_pred'].sum(), tt_pop=rst['NWKER'].sum())

    t0 = time.time()
    rst = BE.predict_residential_building_energy(housing_units='base')
    t1 = time.time()
    print('Energy per resident for base buildings: {:4.2f} BTU/person, time costed: {:4.2f} seconds'.format(
        rst['BTU_pred'].sum() / rst['NHSLDMEM'].sum(), t1 - t0
    ))
    BE.set_base_energy(bldg_type='residential', tt_energy=rst['BTU_pred'].sum(), tt_pop=rst['NHSLDMEM'].sum())

    for trial in range(num_trials):
        print(f'\n\nTrial {trial + 1}\n' + '==' * 30)
        layout_str, layout_ratio = Table.update_randomly(zone=1)

        t0 = time.time()
        energy = BE.return_energy_pperson('building_energy')
        t1 = time.time()
        print('{:4.4} seconds elapsed for computing building energy indicator'.format(t1 - t0))
        print(energy)

        t0 = time.time()
        rst = BE.predict_commercial_building_energy(input_data=H3.h3_stats_interactive,
                                                    input_dtype='h3_stats')
        t1 = time.time()
        print('Energy per worker for updated interactive cells: {:4.2f} BTU/person, time costed: {:4.2f} seconds'.format(
            rst['BTU_pred'].sum() / rst['NWKER'].sum() if rst['NWKER'].sum()>0 else 0, t1-t0
        ))
        # print('Layout: ', {code: '{:4.2f}%'.format(ratio*100) for code, ratio in layout_ratio.items()})

        t0 = time.time()
        rst = BE.predict_residential_building_energy(housing_units='new')
        t1 = time.time()
        print('Enery per resident for updated interactive cells: {:4.2f} BTU/pperson, time costed: {:4.2f} seconds'.format(
            rst['BTU_pred'].sum() / rst['NHSLDMEM'].sum() if rst['NHSLDMEM'].sum()>0 else 0, t1-t0
        ))



if __name__ == '__main__':
    test(num_trials=3)