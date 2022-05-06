import os, sys, time, copy, re, json, pickle, joblib
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from tabulate import tabulate
from collections import OrderedDict

from sklearn.model_selection import train_test_split, RandomizedSearchCV
from sklearn.metrics import confusion_matrix, accuracy_score, f1_score
from sklearn.ensemble import RandomForestClassifier

try:
    from abm_toolbox.logit_toolbox import long_form_data, logit_spec, logit_est_disp, asclogit_pred
    from abm_toolbox.abm_utils import get_haversine_distance
except:
    from logit_toolbox import long_form_data, logit_spec, logit_est_disp, asclogit_pred
    from abm_utils import get_haversine_distance

# =============================================================================
# Constants and Lookups
# =============================================================================
hh_fields = ['HH_Size', 'HH_Anual_Income', 'num_all_vehicles', 'num_all_bikes','Residence_Type']
person_fields = [
    'Age', 'Gender',  'Education', 'Income', 'Occupation',
    # 'Register_in_SZ',
]
hh_person_cat_field_lookup = {
    'HH_Anual_Income': {
        'a ≤10': 'lt20',
        'b 10-20': 'lt20',
        'c 20-30': '20-30',
        'd 30-50': '30-50',
        'e 50-100': 'gt50',
        'f 100以上': 'gt50',
    },
    'Residence_Type': {
        'Affordable Puchasing Housing': 'affordable',
        'Affordable Renting Housing': 'affordable',
        'Dormitory': 'affordable',
        'Market Puchasing Housing': 'marketprice',
        'Urban Village': 'affordable',
    },
    'Gender': {'Male':'male', 'Female':'female'},
    # 'Register_in_SZ': {'True':'yes', 'False':'no', True:'yes', False:'no'},
    'Education': {
        'Bachelor': 'college',
        'Junior Middle School and Below': 'EMH_school',
        'Senior Middle School': 'EMH_school',
        'Ph.D': 'master_phd',
        'Secondary Vocational School': 'EMH_school',
        'Vocational College': 'college',
        'Master': 'master_phd',
    },
    'Income': {
        '10-15': '10_15',
        'GT 50': 'gt30',
        'LT 10': 'lt10',
        '15-20': '15_20',
        '30-50': 'gt30',
        '20-30': '20_30',
        0: 'lt10',
    },
    'Occupation': {
        'Company Business Personnel': 'manager',
        'Self-Employed Worker': 'free',
        'Servant': 'employee',
        'University Student': 'student',
        'Health Worker': 'employee',
        'Unemployment': 'unemployment',
        'Company Common Employee': 'employee',
        'Civil Servant': 'employee',
        'Retired': 'retired',
        'Free Occupation': 'free',
        'Company Manager': 'manager',
        'Primary / Middle School Student': 'student',
        'Teacher': 'employee',
    }
}

# =============================================================================
# Functions
# =============================================================================

def get_residence_workplace_distance(row, city='Shenzhen', allow_different_work_city=False, unit='km'):
    """
    Get distance between residence and workplace for Household Travel Survey (HTS) data in Shenzhen format
    :param row: row dict extracted from HTS trips DataFrame
    :param city: the name of city
    :param allow_different_work_city: whether or not to keep records who work in different city
    :param unit: unit of distance
    :return: distance
    """
    if not all([(field in row and not np.isnan(row[field])) for field in ['Workplace_lng', 'Workplace_lat',
                                                                          'Residence_lng', 'Residence_lat']]):
        return None
    if 'Work_City' in row and row['Work_City'] != city and not allow_different_work_city:
        return None
    residence_coords = [row['Residence_lng'], row['Residence_lat']]
    workplace_coords = [row['Workplace_lng'], row['Workplace_lat']]
    try:
        dist = get_haversine_distance(residence_coords, workplace_coords)
        if unit == 'km':
            dist /= 1000
        return dist
    except:
        return None


def get_trip_duration(row, unit='hour'):
    from_time, to_time = row['From_Time'], row['To_Time']
    from_time_hour, from_time_min = [float(x) for x in from_time.split(':')]
    to_time_hour, to_time_min = [float(x) for x in to_time.split(':')]
    if to_time_hour < from_time_hour:
        to_time_hour += 24   # assuming the next day
    dur_min = (to_time_hour - from_time_hour) * 60 + to_time_min - from_time_min
    if unit == 'hour':
        duration = dur_min/60
    elif unit == 'min':
        duration = dur_min
    elif unit == 'sec':
        duration = dur_min*60
    return duration


def get_mode_cat(row):
    map_dict_5modes = {
        "Walk": "walk",
        "Metro": "pt",
        "Private Car (Driving)": "driving",
        "Bus": "pt",
        "Shared Bike": "cycle",
        "Taxi": "taxi",
        "Bike": "cycle",
        "E-Bike": "cycle",
        "Private Car (Shared Ride)": "taxi",
        "Online Bus Hailing": "taxi",
        "Company Car": "driving",
        "Online Other Car Hailing": "taxi",
    }
    map_dict = {
        "Walk": "walking",
        "Metro": "pt",
        "Private Car (Driving)": "driving",
        "Bus": "pt",
        "Shared Bike": "cycling",
        "Taxi": "driving",
        "Bike": "cycling",
        "E-Bike": "cycling",
        "Private Car (Shared Ride)": "driving",
        "Online Bus Hailing": "pt",
        "Company Car": "driving",
        "Online Other Car Hailing": "driving",
    }
    return map_dict.get(row['Main_Mode'], 'others')


def get_place_type(row, place_identifier, tolerance=100):
    """
    Get type (H=home, W=workplace, O=others) of a trip destination
    :param row: row dict extracted from HTS trips DataFrame
    :param place_identifier: the name of place, like Residence, Workplace, From, To
    :param tolerance: if the place is too close to home or workplace, it will be considered as home or workplace
    :return: H, W, O
    """
    place_coord = [row[f'{place_identifier}_lng'], row[f'{place_identifier}_lat']]
    home_coord = [row['Residence_lng'], row['Residence_lat']]
    if get_haversine_distance(place_coord, home_coord) <= tolerance:
        return 'H'
    if row['Workplace_lng'] is not None and not np.isnan(row['Workplace_lng']):
        workplace_coord = [row['Workplace_lng'], row['Workplace_lat']]
        if get_haversine_distance(place_coord, workplace_coord) <= tolerance:
            return 'W'
    return 'O'


def get_trip_purpose(row):
    tmp = [row['from_place_type'], row['to_place_type']]
    if 'H' in tmp and 'W' in tmp:
        return 'HBW'
    if 'H' in tmp and 'W' not in tmp:
        return 'HBO'
    if 'H' not in tmp:
        return 'NHB'


def pretty_print_confusion_matrix(confusion_matrix, labels, order=None, name=None):
    if order is not None:
        idx_order = [labels.index(label) for label in order]
        confusion_matrix = confusion_matrix[idx_order]
        confusion_matrix = confusion_matrix[:, idx_order]
        labels = order
    cmat_df = pd.DataFrame(confusion_matrix, columns=[f'{l}_pred' for l in labels],
                          index=[f'{l}_true' for l in labels])
    name = '' if name is None else f'for {name}'
    print('\nConfusion matrix ' + name + '\n')
    print(tabulate(cmat_df, showindex=True, headers='keys'))
    metric_df = cmat_df.sum(axis=1).to_frame(name='sum_true').rename(index={f'{m}_true': m for m in labels})
    metric_df['sum_pred'] = cmat_df.sum(axis=0).to_frame(name='sum_pred').rename(index={f'{m}_pred': m for m in labels})
    metric_df['TP'] = np.diag(confusion_matrix)
    metric_df['precision'] = metric_df['TP'] / metric_df['sum_pred']
    metric_df['recall'] = metric_df['TP'] / metric_df['sum_true']
    metric_df['f1'] = 2 * (metric_df['precision'] * metric_df['recall']) / (metric_df['precision'] + metric_df['recall'])
    print('\nMetrics ' + name + '\n')
    print(tabulate(metric_df, showindex=True, headers='keys'))


def get_trip_time_predictor(trip_time, features, n_estimators=20, test_size=0.2, random_state=1):
    predictor = RandomForestRegressor(n_estimators=n_estimators)
    x_train, x_test, y_train, y_test = train_test_split(features, trip_time, test_size=test_size, random_state=random_state)
    randomGrid = {'max_depth': range(5,50,5), 'min_samples_leaf': range(1,101,10)}

    # Create the random search object
    predictor_random_search = RandomizedSearchCV(estimator=predictor, param_distributions = randomGrid,
                                   n_iter=64, cv = 4, verbose=1, random_state=random_state,
                                   refit=True, scoring='neg_mean_squared_error', n_jobs=-1)

    # Perform the random search and find the best parameter set
    predictor_random_search.fit(x_train, y_train)
    winner = predictor_random_search.best_estimator_
    bestParams = predictor_random_search.best_params_
    return winner, bestParams


def create_mode_choice_trip_table(HTS_data_path,
                                  city='Shenzhen',
                                  households_fname='households.csv',
                                  persons_fname='persons.csv',
                                  trips_fname='trips.csv'):
    hhs_df = pd.read_csv(os.path.join(HTS_data_path, households_fname), encoding='utf-8')
    persons_df = pd.read_csv(os.path.join(HTS_data_path, persons_fname), encoding='utf-8')
    trips_df = pd.read_csv(os.path.join(HTS_data_path, trips_fname), encoding='utf-8')

    persons_df = persons_df.merge(hhs_df[['HH_ID', 'Residence_lng', 'Residence_lat']],
                                  how='inner', on='HH_ID', suffixes=('', '_hhs'))
    persons_df['home_work_dist'] = persons_df.apply(lambda row: get_residence_workplace_distance(row, city), axis=1)

    # get some useful features
    hhs_df['num_all_bikes'] = hhs_df['Num_Bike'] + hhs_df['Num_Motorcycle'] + hhs_df['Num_E_Bike']
    hhs_df['num_all_vehicles'] = hhs_df['Num_Private_Car'] + hhs_df['Num_Van'] + hhs_df['Num_Public_Car']
    persons_df.loc[persons_df['Income'].isnull(), 'Income'] = 0  # almost all of NaN-income records are students

    # get trips distance and duration
    trips_df = trips_df.loc[trips_df['From_City'] == trips_df['To_City']]
    trips_df = trips_df.loc[trips_df['From_City'] == city]
    trips_df['trip_dist_calc'] = trips_df.apply(lambda row: get_haversine_distance(
        [row['From_lng'], row['From_lat']], [row['To_lng'], row['To_lat']]) / 1000, axis=1)
    trips_df['trip_duration'] = trips_df.apply(lambda row: get_trip_duration(row), axis=1)
    trips_df['trip_speed'] = trips_df['Trip_Dist'] / trips_df['trip_duration']
    trips_df['mode'] = trips_df.apply(lambda row: get_mode_cat(row), axis=1)

    # merging housholds, persons, trips
    merge_hh_feilds = [
        'HH_ID', 'HH_Size', 'HH_Anual_Income', 'Residence_lng', 'Residence_lat',
        'Residence_Type', 'num_all_vehicles', 'num_all_bikes'
    ]
    merge_person_fields = [
        'Person_ID', 'Age', 'Gender', 'Education', 'Income', 'Occupation',
        'Workplace_lng', 'Workplace_lat', 'Work_City', 'home_work_dist',
        # 'Register_in_SZ',
    ]
    trips_df = trips_df.merge(hhs_df[merge_hh_feilds], how='inner', on='HH_ID', suffixes=('', '_hhs'))
    trips_df = trips_df.merge(persons_df[merge_person_fields], how='inner', on='Person_ID', suffixes=('', '_persons'))

    # get trip purpose (HBW, HBO, NHB)
    trips_df['from_place_type'] = trips_df.apply(lambda row: get_place_type(row, 'From'), axis=1)
    trips_df['to_place_type'] = trips_df.apply(lambda row: get_place_type(row, 'To'), axis=1)
    trips_df['trip_purpose'] = trips_df.apply(lambda row: get_trip_purpose(row), axis=1)

    # Estimating speed for different modes
    modes = {mode: {} for mode in np.unique(list(trips_df['mode']))}
    for mode in modes:
        cum_dist_km = trips_df.loc[trips_df['mode'] == mode, 'Trip_Dist'].sum()
        cum_time_hour = trips_df.loc[trips_df['mode'] == mode, 'trip_duration'].sum()
        modes[mode]['mean_speed'] = cum_dist_km / cum_time_hour
        modes[mode]['mean_speed2'] = trips_df.loc[trips_df['mode'] == mode, 'trip_speed'].mean()

    # Generate Mode Choice Dataset
    mocho_df = pd.DataFrame()
    for field in ['mode', ('Trip_Dist', 'network_dist_km')]:
        if type(field) == str:
            mocho_df[field] = trips_df[field]
        elif type(field) == tuple:
            mocho_df[field[1]] = trips_df[field[0]]
    for mode in modes:
        mocho_df[f'{mode}_time_minutes'] = trips_df['Trip_Dist'] / modes[mode]['mean_speed'] * 60
        mocho_df.loc[mocho_df['mode'] == mode, f'{mode}_time_minutes'] = trips_df.loc[mocho_df['mode']==mode,
                                                                                   'trip_duration'] * 60
    trip_purpose_dummys = pd.get_dummies(trips_df['trip_purpose'], prefix='purpose')
    mocho_df = pd.concat([mocho_df, trip_purpose_dummys], axis=1)

    for field in person_fields + hh_fields:
        if field in hh_person_cat_field_lookup:
            cat_field = trips_df.apply(
                lambda row: hh_person_cat_field_lookup[field].get(row[field], 'others'), axis=1)
            dummies = pd.get_dummies(cat_field, prefix=field.lower())
            mocho_df = pd.concat([mocho_df, dummies], axis=1)
        else:
            mocho_df[field.lower()] = trips_df[field]

    return mocho_df



class MochoModelRF:
    def __init__(self, table, seed=1):
        self.table = table
        self.seed = seed
        self.root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        mocho_models_dir = os.path.abspath('{}/cities/{}/models/mocho'.format(self.root_dir, table))
        if not os.path.exists(mocho_models_dir):
            os.makedirs(mocho_models_dir)
        self.rf_model_path = os.path.join(mocho_models_dir, 'mocho_rf.p')
        self.rf_features_path = os.path.join(mocho_models_dir, 'mocho_rf_features.json')
        try:
            self.rf_model = joblib.load(open(self.rf_model_path, 'rb'))
            self.features = json.load(open(self.rf_features_path))
        except:
            self.train()
            self.rf_model = joblib.load(open(self.rf_model_path, 'rb'))
            self.features = json.load(open(self.rf_features_path))

    def train(self):
        print('Training mode choice Random Forest model')
        mocho_df = create_mode_choice_trip_table('{}/cities/{}/raw/HTS'.format(self.root_dir, self.table))

        # train test split
        features = [c for c in mocho_df.columns if not c == 'mode']
        X = mocho_df[features]
        y = mocho_df['mode']
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=self.seed)

        # random search
        rf = RandomForestClassifier(n_estimators=32, random_state=0, class_weight='balanced')
        maxDepth = list(range(5, 100, 5))  # Maximum depth of tree
        maxDepth.append(None)
        minSamplesSplit = range(2, 42, 5)  # Minimum samples required to split a node
        minSamplesLeaf = range(1, 101, 10)  # Minimum samples required at each leaf node
        randomGrid = {'max_depth': maxDepth, 'min_samples_split': minSamplesSplit, 'min_samples_leaf': minSamplesLeaf}
        rfRandom = RandomizedSearchCV(estimator=rf, param_distributions=randomGrid,
                                      n_iter=512, cv=5, verbose=1, random_state=self.seed,
                                      refit=True, scoring='f1_macro', n_jobs=-1)
        rfRandom.fit(X_train, y_train)
        rfWinner = rfRandom.best_estimator_
        # rfBestParams = rfRandom.best_params_
        print(f'Best score for random forest: {rfRandom.best_score_}')

        # performance
        # labels = ['cycle', 'drive', 'pt', 'taxi', 'walk']
        # order = ['drive', 'taxi', 'cycle', 'walk', 'pt']
        labels = ['cycling', 'driving', 'pt', 'walking']
        order = ['driving', 'cycling', 'walking', 'pt']
        y_train_pred = rfWinner.predict(X_train)
        conf_mat_train = confusion_matrix(y_train, y_train_pred)
        pretty_print_confusion_matrix(conf_mat_train, labels, order,
                                      name='trainning data using random forest classifier')
        print('\nOverall metrics for trainning data using random forest classifier: '
              'accuracy = {:4.4f}, F1 = {:4.4f}\n'.format(accuracy_score(y_train, y_train_pred),
                                                          f1_score(y_train, y_train_pred, average='macro')))
        y_test_pred = rfWinner.predict(X_test)
        conf_mat_test = confusion_matrix(y_test, y_test_pred)
        pretty_print_confusion_matrix(conf_mat_test, labels, order, name='test data using random forest classifier')
        print('\nOverall metrics for test data using random forest classifier: accuracy = {:4.4f}, F1 = {:4.4f}\n'.format(
            accuracy_score(y_test, y_test_pred), f1_score(y_test, y_test_pred, average='macro')))

        # feature importance
        importances = rfWinner.feature_importances_
        std = np.std([tree.feature_importances_ for tree in rfWinner.estimators_], axis=0)
        indices = np.argsort(importances)[::-1]
        print("Feature ranking:")
        for f in range(len(features)):
            print("%d. %s (%f)" % (f + 1, features[indices[f]], importances[indices[f]]))

        # Plot the feature importances of the forest
        plt.figure(figsize=(16, 15))
        plt.title("Feature importances")
        plt.bar(range(len(features)), importances[indices], color="r", yerr=std[indices], align="center")
        plt.xticks(range(len(features)), [features[i] for i in indices], rotation=90, fontsize=15)
        plt.xlim([-1, len(features)])
        plt.show()

        # refit with all data (train+test) and dump to local files
        rfWinner.fit(X, y)
        joblib.dump(rfWinner, self.rf_model_path)
        json.dump(features, open(self.rf_features_path, 'w'), indent=4)
        print('\n\n(The following performance are calculating used refit model and thus only for reference)')
        y_train_pred = rfWinner.predict(X_train)
        conf_mat_train = confusion_matrix(y_train, y_train_pred)
        pretty_print_confusion_matrix(conf_mat_train, labels, order,
                                      name='trainning data using random forest classifier')
        print('\nOverall metrics for trainning data using random forest classifier: '
              'accuracy = {:4.4f}, F1 = {:4.4f}\n'.format(accuracy_score(y_train, y_train_pred),
                                                          f1_score(y_train, y_train_pred, average='macro')))
        y_test_pred = rfWinner.predict(X_test)
        conf_mat_test = confusion_matrix(y_test, y_test_pred)
        pretty_print_confusion_matrix(conf_mat_test, labels, order, name='test data using random forest classifier')
        print(
            '\nOverall metrics for test data using random forest classifier: accuracy = {:4.4f}, F1 = {:4.4f}\n'.format(
                accuracy_score(y_test, y_test_pred), f1_score(y_test, y_test_pred, average='macro')))

    def generate_feature_df(self, trips):
        feature_df = pd.DataFrame(trips)  
        for feat in ['gender', 'income', 'register_in_sz', 'education', 'hh_anual_income',
                     'occupation', 'residence_type', 'purpose']:
            new_dummys=pd.get_dummies(feature_df[feat], prefix=feat)
            feature_df=pd.concat([feature_df, new_dummys],  axis=1)
        # feature_df['drive_vehicle_time_minutes'] = feature_df.apply(lambda row: row['driving_route']['driving'], axis=1)
        # feature_df['cycle_active_time_minutes'] = feature_df.apply(lambda row: row['cycling_route']['cycling'], axis=1)
        # feature_df['walk_active_time_minutes'] = feature_df.apply(lambda row: row['walking_route']['walking'], axis=1)
        # feature_df['PT_time_minutes'] = feature_df.apply(lambda row: row['pt_route']['pt'], axis=1)
        feature_df['driving_time_minute'] = feature_df.apply(lambda row: row['driving_route']['driving'], axis=1)
        feature_df['cycling_time_minutes'] = feature_df.apply(lambda row: row['cycling_route']['cycling'], axis=1)
        feature_df['walking_time_minutes'] = feature_df.apply(lambda row: row['walking_route']['walking'], axis=1)
        feature_df['pt_time_minutes'] = feature_df.apply(lambda row: row['pt_route']['pt'], axis=1)
        # feature_df['walk_time_PT_minutes'] = feature_df.apply(lambda row: row['pt_route']['walking'], axis=1)
        # feature_df['waiting_time_PT_minutes'] = feature_df.apply(lambda row: row['pt_route']['waiting'], axis=1)
#        feature_df['network_dist_km']=feature_df.apply(lambda row: row['drive_time_minutes']*30/60, axis=1)
        for rff in self.features:
            if rff not in feature_df.columns:
                feature_df[rff]=False
        feature_df=feature_df[self.features]
        self.feature_df = feature_df

    def predict_modes(self):
        mode_probs = self.rf_model.predict_proba(self.feature_df)
        chosen_modes = [np.random.choice(self.rf_model.classes_ , size=1, replace=False, p=mode_probs[i])[0]
                        for i in range(len(mode_probs))]
        self.predicted_prob, self.predicted_modes = mode_probs, chosen_modes


class MochoModelLogit:

    def __init__(self, table, seed=1):
        self.table = table
        self.seed = seed
        self.base_alts = {0: 'drive', 1: 'taxi', 2: 'cycle', 3: 'walk', 4: 'PT'}
        mocho_models_dir = os.path.abspath('../cities/{}/models/mocho'.format(table))
        if not os.path.exists(mocho_models_dir):
            os.makedirs(mocho_models_dir)
        self.logit_model_path = os.path.join(mocho_models_dir, 'mocho_loigt.p')
        self.logit_features_path = os.path.join(mocho_models_dir, 'mocho_logit_features.json')
        try:
            self.logit_model = pickle.load(open(self.logit_model_path, 'rb'))
            logit_features = json.load(open(self.logit_features_path))
        except:
            self.train()
            self.logit_model = pickle.load(open(self.logit_model_path, 'rb'))
            logit_features = json.load(open(self.logit_features_path))
        if len(logit_features):
            self.logit_alt_attrs = logit_features['alt_attrs']
            self.logit_alt_attr_vars = logit_features['alt_attr_vars']
            self.logit_generic_attrs = logit_features['generic_attrs']
            self.logit_constant = logit_features['constant']
        else:
            self.logit_alt_attrs, self.logit_alt_attr_vars, self.logit_generic_attrs = {}, [], []

        if self.logit_model is not None and self.logit_model['just_point'] is False:
            # for convenience, use just_point=True for all cases so that we can modify the model easily
            self.logit_model['just_point'] = True
            print('Not point estimate only')

        self.new_alt_specs = []
        self.nests_spec = None
        self.new_alts = []
        self.new_alts_like = {}
        self.update_alts()
        self.prob = []
        self.v = []  # observed utility for logit
        self.mode = []


    def update_alts(self):
        pass


    def train(self):
        print('Training mode choice Logit model')
        mocho_df = create_mode_choice_trip_table('../cities/{}/raw/HTS'.format(self.table))
        alt_attrs = {'time_minutes': [f'{mode}_time_minutes' for mode in self.base_alts.values()]}
        generic_attrs = [x for x in mocho_df.columns if x != 'mode' and x not in alt_attrs.values()]
        exclude_ref = [
            'purpose_HBW', 'gender_male', 'register_in_sz_yes', 'education_college',
            'income_10_15', 'occupation_employee', 'hh_anual_income_20-30',
            'residence_type_marketprice'
        ]
        exclude_others = ['network_dist_km']
        exclude_generic_attrs = exclude_ref + exclude_others
        generic_attrs = [x for x in generic_attrs if x not in exclude_generic_attrs]
        modes_in_order = ['drive', 'taxi', 'cycle', 'walk', 'pt']
        mocho_logit_df = long_form_data(mocho_df, alt_attrs=alt_attrs, generic_attrs=generic_attrs,
                                        modes=modes_in_order)

        mocho_df_train, mocho_df_test = train_test_split(mocho_df, test_size=0.2, random_state=1)

        # using the same train/test split for logit long-form data
        # notice: group index must keep increasing, otherwise pylogit will throw error for ensure_contiguity_in_observation_rows
        tranning_idx, test_idx = list(mocho_df_train.index), list(mocho_df_test.index)
        mocho_logit_df_train = mocho_logit_df.loc[mocho_logit_df['group'].isin(tranning_idx)]
        mocho_logit_df_test = mocho_logit_df.loc[mocho_logit_df['group'].isin(test_idx)]

        model_train, numCoefs = logit_spec(mocho_logit_df_train,
                                           alt_attr_vars=list(alt_attrs.keys()),
                                           generic_attrs=generic_attrs,
                                           constant=True,
                                           alts=modes_in_order)
        logit_est_rst_dict = logit_est_disp(model_train, numCoefs, nalt=5, disp=True)

        # performance
        labels = ['cycle', 'drive', 'pt', 'taxi', 'walk']
        order = ['drive', 'taxi', 'cycle', 'walk', 'pt']
        pred_prob_train, y_train_pred, v = asclogit_pred(mocho_logit_df_train, logit_est_rst_dict,
                                                         customIDColumnName='group', alts=modes_in_order, method='max',
                                                         seed=1)
        y_train_pred = [modes_in_order[y] for y in y_train_pred]
        y_train_true = np.array(mocho_logit_df_train['choice']).reshape(-1, len(modes_in_order)).argmax(axis=1)
        y_train_true = [modes_in_order[y] for y in y_train_true]
        conf_mat_train = confusion_matrix(y_train_true, y_train_pred)
        pretty_print_confusion_matrix(conf_mat_train, labels, order, name='trainning data using MNL')
        print('\nOverall metrics for trainning data using MNL: accuracy = {:4.4f}, F1 = {:4.4f}'.format(
            accuracy_score(y_train_true, y_train_pred), f1_score(y_train_true, y_train_pred, average='macro')
        ))

        pred_prob_test, y_test_pred, v = asclogit_pred(mocho_logit_df_test, logit_est_rst_dict,
                                                       customIDColumnName='group', alts=modes_in_order, method='max',
                                                       seed=1)
        y_test_pred = [modes_in_order[y] for y in y_test_pred]
        y_test_true = np.array(mocho_logit_df_test['choice']).reshape(-1, len(modes_in_order)).argmax(axis=1)
        y_test_true = [modes_in_order[y] for y in y_test_true]
        conf_mat_test = confusion_matrix(y_test_true, y_test_pred)
        pretty_print_confusion_matrix(conf_mat_test, labels, order, name='test data using MNL')
        print('\nOverall metrics for test data using MNL: accuracy = {:4.4f}, F1 = {:4.4f}'.format(
            accuracy_score(y_test_true, y_test_pred), f1_score(y_test_true, y_test_pred, average='macro')
        ))

        # re-estimate the model with all data (train+test) and dump model to local files
        print('\nThe following is Logit model results with all data (train+test)')
        model_train, numCoefs = logit_spec(mocho_logit_df,
                                           alt_attr_vars=list(alt_attrs.keys()),
                                           generic_attrs=generic_attrs,
                                           constant=True,
                                           alts=modes_in_order)
        logit_est_rst_dict = logit_est_disp(model_train, numCoefs, nalt=5, disp=True)
        pickle.dump(logit_est_rst_dict, open(self.logit_model_path, 'wb'))
        logit_features = {
            'alt_attrs': alt_attrs,
            'alt_attr_vars': list(alt_attrs.keys()),
            'generic_attrs': generic_attrs,
            'constant': True,
            'alts': self.base_alts
        }
        json.dump(logit_features, open(self.logit_features_path, 'w'), indent=4)


            
if __name__ == "__main__":
    mocho = MochoModelRF(table='shenzhen')
    # mocho = MochoModelLogit(table='shenzhen')







       
                
