# -*- coding: utf-8 -*-
import os, pickle, json, random, copy, time
import numpy as np
import pandas as pd

from abm_toolbox.home_location_choice_model import HomeLocChoiceModel
from abm_toolbox.activity_scheduler_model import ActivityScheduler
from abm_toolbox.mode_choice_model import MochoModelRF
from abm_toolbox.transport_network import Transport_Network

from indicator_toolbox import Indicator


class MobilityModel:
    def __init__(self, table='shenzhen', H3=None,
                 transport_network_path=None,
                 activity_scheduler_path=None,
                 home_workplace_assigner_path=None):
        self.table = table
        self.H3 = H3

        if transport_network_path is None:
            transport_network_path = os.path.join('cities', table, 'clean', 'transport_network.p')
        self.transport_network_path = transport_network_path
        if activity_scheduler_path is None:
            activity_scheduler_path = os.path.join('cities', table, 'models', 'activities','activity_scheduler.p')
        self.activity_scheduler_path = activity_scheduler_path
        if home_workplace_assigner_path is None:
            home_workplace_assigner_path = os.path.join('cities', table, 'models', 'home_workplace_assigner.p')
        self.home_workplace_assigner_path = home_workplace_assigner_path

        self.load_models()

    def load_models(self):
        if not os.path.exists(self.transport_network_path):
            self.tn = Transport_Network(table=self.table)
        else:
            self.tn = pickle.load(open(self.transport_network_path, 'rb'))
        self.modes_lookup = {mode.name: mode for mode in self.tn.base_modes}

        if not os.path.exists(self.activity_scheduler_path):
            print(f'Warning: activity_scheduler not found: {os.path.abspath(self.activity_scheduler_path)}')
            self.activity_scheduler = None
        else:
            self.activity_scheduler = pickle.load(open(self.activity_scheduler_path, 'rb'))

        if not os.path.exists(self.home_workplace_assigner_path):
            print(f'Warning: home_workplace_assigner not found: {os.path.abspath(self.home_workplace_assigner_path)}')
            self.home_workplace_assigner = None
        else:
            self.home_workplace_assigner = pickle.load(open(self.home_workplace_assigner_path, 'rb'))
        self.mocho_model = MochoModelRF(table=self.table)

    def init_simulation(self):
        base_sim_pop = self.H3.Pop.base_sim_pop[:20]
        self.H3.Pop.impact = base_sim_pop
        self.activity_scheduler.assign_activity_schedule(base_sim_pop)
        self.create_trips(base_sim_pop)
        self.predict_trip_modes(base_sim_pop)

    def update_simulation(self):
        new_persons = self.generate_new_persons()
        self.home_location_choice_model.predict_home_loc(new_persons)
        self.activity_scheduler.assign_activity_schedule(new_persons)

    def create_trips(self, persons):
        for person in persons:
            trips = []
            for ind_act in range(len(person.activities) - 1):
                origin = person.activities[ind_act]
                destination = person.activities[ind_act + 1]
                if not origin == destination:
                    mode_choice_set = self.tn.get_routes(origin.location, destination.location)
                    enters_sim = ((origin.location['in_sim_area']) or (destination.location['in_sim_area']))
                    trips.append(Trip(mode_choice_set, enters_sim=enters_sim,
                                      from_activity=origin, to_activity=destination))
            person.trips = trips

    def predict_trip_modes(self, persons):
        persons_lookup = {person.idx: person for person in persons}
        # print('\t Predicting Trip modes')
        mocho_model = copy.deepcopy(self.mocho_model)
        all_trips = []
        for person_id, p in enumerate(persons):
            all_trips.extend(p.trips_to_list())
        mocho_model.generate_feature_df(all_trips)
        # print('\t \t predicting')
        mocho_model.predict_modes()
        # print('\t \t applying predictions to trips')
        for trip_idx, trip_record in enumerate(all_trips):
            person_id = trip_record['person_id']
            trip_id = trip_record['trip_id']
            predicted_mode_name = mocho_model.predicted_modes[trip_idx]
            predicted_mode = self.modes_lookup[predicted_mode_name]
            persons_lookup[person_id].trips[trip_id].set_mode(predicted_mode)

    def get_mode_split(self, persons=None, by_id=False):
        if persons == None:
            persons = self.H3.Pop.impact
        count = 0
        split = {mode_name: 0 for mode_name in self.modes_lookup}
        for person in persons:
            for trip in person.trips:
                if trip.mode is not None:
                    if trip.total_distance < 1000000:
                        split[trip.mode.name] += 1
                        count += 1
        if by_id:
            prop_split = {mode.id: split[mode_name] / count for mode_name, mode in self.modes_lookup.items()}
        else:
            prop_split = {mode_name: split[mode_name] / count for mode_name in split}
        return prop_split

    def get_avg_co2(self, persons=None):
        if persons == None:
            persons = self.H3.Pop.impact
        total_co2_kg = 0
        total_dist = 0
        count = 0
        for p in persons:
            count += 1
            for trip in p.trips:
                if trip.mode is not None:
                    if trip.total_distance < 1000000:
                        mode = trip.mode
                        total_co2_kg += trip.total_distance * mode.co2_emissions_kg_met
                        total_dist += trip.total_distance
        return total_co2_kg / count



class Trip():
    def __init__(self, mode_choice_set, enters_sim, from_activity, to_activity):
        self.enters_sim = enters_sim
        self.activity_start = from_activity.start_time
        self.mode_choice_set = mode_choice_set
        self.mode = None
        if from_activity.activity_id + to_activity.activity_id in ['HW', 'WH']:
            self.purpose = 'HBW'
        elif 'H' in [from_activity.activity_id , to_activity.activity_id]:
            self.purpose = 'HBO'
        else:
            self.purpose = 'NHB'

    def set_mode(self, mode, utility=None):
        self.mode = mode
        copy_route = mode.copy_route
        self.internal_route = self.mode_choice_set[copy_route].internal_route['internal_route']
        self.pre_time = self.mode_choice_set[copy_route].pre_time
        self.post_time = self.mode_choice_set[copy_route].post_time
        external_dist = self.mode_choice_set[copy_route].external_distance
        if external_dist == 0:
            external_dist = (self.pre_time+self.post_time) * 60 * self.mode.speed_met_s
        self.total_distance = self.internal_route['total_distance'] + external_dist   # unit: meter
        if utility is not None:
            self.utility = utility


            
def test():
    d = pickle.load(open('cities/shenzhen/clean/precooked_data.p', 'rb'))
    H3 = d['H3']

    t0 = time.time()
    M = MobilityModel(H3=H3)
    t1 = time.time()
    print(t1 - t0)

    t1 = time.time()
    M.init_simulation()
    t2 = time.time()
    print(t2 - t1)

#
if __name__ == '__main__':
    test()