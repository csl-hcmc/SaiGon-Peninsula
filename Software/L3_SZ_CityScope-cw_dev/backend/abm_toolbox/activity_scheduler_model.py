import os, time, pickle, copy, sys
import numpy as np
import pandas as pd
import h3.api.numpy_int as h3
import multiprocessing
import concurrent.futures
try:
    from abm_toolbox.abm_utils import split_data_multiprocess, LocationSetter
except:
    from abm_utils import split_data_multiprocess, LocationSetter



class Activity:
    def __init__(self, activity_id, start_time, activity_name, location):
        self.activity_id = activity_id
        self.location = location
        self.name = activity_name
        self.start_time = start_time


class ActivityScheduler:
    def __init__(self, table='shenzhen', sample_motif_path=None, activity_spec_path=None, save_model_path=None,
                 resolution=11, resolution_out=8, location_setter=None):
        self.table = table
        self.resolution = resolution
        if sample_motif_path is None:
            sample_motif_path = os.path.join('../cities', table, 'models', 'activities', 'sample_motifs.csv')
        self.sample_motif_path = sample_motif_path
        if activity_spec_path is None:
            activity_spec_path = os.path.join('../cities', table, 'models', 'activities', 'activity_spec.json')
        self.activity_spec_path = activity_spec_path
        if save_model_path is None:
            save_model_path = os.path.join('../cities', table, 'models', 'activities', 'activity_scheduler.p')
        self.save_model_path = save_model_path

        if location_setter:
            self.location_setter = location_setter
        else:
            try:
                bound_geojson_path = f'../cities/{table}/geojson/bounds.geojson'
                self.location_setter = LocationSetter(bound_geojson_path, resolution, resolution_out)
            except Exception as e:
                raise ValueError(f'Error: failed to create a location setter\n{e}')

        self.load_data_and_models()
        self.save()


    def load_data_and_models(self):
        if not os.path.exists(self.sample_motif_path):
            print(f'Warning: sample_motifs not found: {os.path.abspath(self.sample_motif_path)}')
            self.sample_motifs = None
        else:
            self.sample_motifs = pd.read_csv(self.sample_motif_path)

        if not os.path.exists(self.activity_spec_path):
            print(f'Warning: activity_spec not found: {os.path.abspath(self.activity_spec_path)}')
            self.activity_names = {
                'H': 'Home',
                'W': 'Work'
            }
            self.potential_locations = {}
        else:
            activity_spec = json.load(open(self.activity_spec_path))
            self.activity_names = {k:v['name'] for k,v in activity_spec.items()}


    def assign_activity_schedule(self, persons):
        self.predict_motif_cluster(persons)
        self.batch_sample_motif(persons)
        self.generate_activities(persons)


    def predict_motif_cluster(self, persons):
        for person in persons:
            person.motif_cluster = np.random.choice([1,2,3,4,5])


    def batch_sample_motif(self, persons):
        motif_clusters = list(set(self.sample_motifs['cluster'].tolist()))
        for motif_cluster in motif_clusters:
            these_persons = [person for person in persons if person.motif_cluster == motif_cluster]
            if len(these_persons) == 0:
                continue
            motif_options = self.sample_motifs.loc[self.sample_motifs['cluster'] == motif_cluster].to_dict('records')
            motifs = np.random.choice(motif_options, size=len(these_persons), replace=True)
            for person, motif in zip(these_persons, motifs):
                person.hourly_activity_ids = [motif[f'hour_{hour}'] for hour in range(24)]

    # too slow, don't use
    def sample_motif(self, person):
        motif_options = self.sample_motifs.loc[self.sample_motifs['cluster'] == person.motif_cluster].to_dict(
            'records')
        motif = random.choice(motif_options)
        person.hourly_activity_ids = [motif[f'hour_{hour}'] for hour in range(24)]


    def generate_activities_concurrent(self, persons, num_workers=8):
        # for mini_batch_persons in split_data_multiprocess(persons, num_process):
        #     p = multiprocessing.Process(target=self.assign_activities, args=(mini_batch_persons,))
        #     p.start()
        #     p.Daemon = True
        # p.join()
        mini_batch_persons = split_data_multiprocess(persons, num_workers)
        with concurrent.futures.ThreadPoolExecutor(max_workers=num_workers) as executor:
            executor.map(self.assign_activities, mini_batch_persons)


    def generate_activities(self, persons):
        for person in persons:
            activities = []
            last_location = person.home
            for t, a_id in enumerate(person.hourly_activity_ids):
                if ((t == 0) or (a_id != person.hourly_activity_ids[t - 1])):
                    activity_start_time = t * 3600 + np.random.randint(3600)
                    activity_name = self.activity_names.get(a_id, 'Others')
                    if activity_name == 'Home':
                        activity_location = person.home
                    elif activity_name == 'Work':
                        activity_location = person.workplace
                    else:
                        activity_location = self.find_places(activity_name, last_location)
                    activities.append(Activity(activity_id=a_id,
                                               start_time=activity_start_time,
                                               activity_name=activity_name,
                                               location=activity_location))
                    last_location = activity_location
            person.activities = activities


    def find_places(self, activity_name, origin_location):
        origin_h3_cell = origin_location['h3'][self.resolution]
        dist = np.random.randint(20, 100)   # res=11: avg edge length=25m -> 500m ~ 2.5km
        des_h3_cell = np.random.choice(h3.hex_ring(origin_h3_cell, dist))
        # des_location = {
        #     'h3': {self.resolution: des_h3_cell},
        #     'coord': h3.h3_to_geo(des_h3_cell)[::-1]
        # }
        des_location = self.location_setter.set_location(h3_cell=des_h3_cell, resolution=self.resolution)
        return des_location


    def save(self, save_model_path=None):
        if not save_model_path:
            save_model_path = self.save_model_path
        pickle.dump(self, open(save_model_path, 'wb'))



def test():
    precooked_data = pickle.load(open('../cities/shenzhen/clean/precooked_data.p', 'rb'))
    population = precooked_data['population']

    pop = population.base_sim_pop + copy.deepcopy(population.base_sim_pop) + copy.deepcopy(population.base_sim_pop)
    AS = ActivityScheduler()
    t0 = time.time()
    AS.predict_motif_cluster(pop)
    # t_last = t0
    AS.batch_sample_motif(pop)
    for idx, person in enumerate(pop):
        # if idx % 1000 == 0:
        #     t_crt = time.time()
        #     print(f'{idx} / {len(population.base_sim_pop)}: {round(100*idx/len(population.base_sim_pop), 2)}%, {round(t_crt-t_last, 3)} secs')
        #     t_last = t_crt
        # AS.sample_motif(person)
        AS.generate_activities([person])
    t1 = time.time()
    print('test1: ', round(t1-t0, 5), 'sec')
    AS.save()

def test2():
    precooked_data = pickle.load(open('../cities/shenzhen/clean/precooked_data.p', 'rb'))
    population = precooked_data['population']

    pop = population.base_sim_pop + copy.deepcopy(population.base_sim_pop) + copy.deepcopy(population.base_sim_pop)
    AS = ActivityScheduler()
    t0 = time.time()
    AS.predict_motif_cluster(pop)
    AS.batch_sample_motif(pop)
    AS.generate_activities_concurrent(pop)
    t1 = time.time()
    print('test2: ', round(t1 - t0, 5), 'sec')




if __name__ == '__main__':
    import sys
    sys.path.insert(0, 'D:/L3/L3_SZ_CityScope/backend')
    from geodata_toolbox import *
    test()
    # test2()
