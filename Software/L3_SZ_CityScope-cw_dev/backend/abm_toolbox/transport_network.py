import os, sys
import json, time, copy, pickle
import h3.api.numpy_int as h3
import pandas as pd
import numpy as np
import networkx as nx
from scipy import spatial
from shapely.geometry import Point, shape
import matplotlib.pyplot as plt
import matplotlib
try:
    from abm_toolbox.abm_utils import dict_to_gzip, gzip_to_dict
except:
    from abm_utils import dict_to_gzip, gzip_to_dict

class Mode:
    def __init__(self, mode_spec, mode_id):
        self.speed_met_s = mode_spec['speed_m_s']
        self.name = mode_spec['name']
        self.activity = mode_spec['activity']
        self.internal_net = mode_spec['internal_net']
        self.co2_emissions_kg_met = mode_spec['co2_emissions_kg_met']
        self.fixed_costs = mode_spec['fixed_costs']
        self.id = mode_id
        if 'weight' in mode_spec:
            # not needed for new modes
            self.weight = mode_spec['weight']
        if 'copy_route' in mode_spec:
            self.copy_route = mode_spec['copy_route']


class Route():
    def __init__(self, internal_route, costs, pre_time=0, post_time=0, external_distance=0):
        self.internal_route = internal_route
        self.pre_time = pre_time
        self.post_time = post_time
        self.costs = costs
        self.external_distance = external_distance


class Transport_Network:
    def __init__(self, table='shenzhen', external_routes_db_name='external_routes', external_h3_resolution=None):
        self.table = table
        self.root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.external_routes_db_name = external_routes_db_name
        self.external_route_costs_path = f'{self.root_dir}/cities/{table}/clean/ext_route_costs.json'
        self.external_h3_resolution = external_h3_resolution
        self.mode_spec_path = f'{self.root_dir}/cities/{table}/clean/mode_spec.json'
        self.sim_net_floyd_result_paths = {
            mode: f'{self.root_dir}/cities/{table}/clean/internal_net/fw_result_{mode}.gzip'
            for mode in ['driving', 'pt', 'active']
        }
        self.sim_net_floyd_df_paths = {
            mode: f'{self.root_dir}/cities/{table}/clean/internal_net/sim_net_df_floyd_{mode}.csv'
            for mode in ['driving', 'pt', 'active']
        }
        self.portal_path = f'{self.root_dir}/cities/{table}/geojson/portals.geojson'
        self.save_path = f'{self.root_dir}/cities/{table}/clean/transport_network.p'

        self.load_data()
        # self.save()

    def load_data(self):
        # load external cost
        try:
            self.external_costs = json.load(open(self.external_route_costs_path))
        except:
            self.external_costs = self.prepare_external_routes()
        if not self.external_h3_resolution:
            sample_mode = list(self.external_costs.keys())[0]
            sample_h3_cell = list(self.external_costs[sample_mode].keys())[0]
            self.external_h3_resolution = h3.h3_get_resolution(int(sample_h3_cell))

        # load base modes
        self.base_modes = [Mode(mode_spec, mode_idx)
                           for mode_idx, mode_spec in enumerate(json.load(open(self.mode_spec_path)))]

        # load internal network and costs
        self.sim_net_floyd_results = {}
        self.sim_net_floyd_df = {}
        for mode in ['driving', 'pt', 'active']:
            if self.sim_net_floyd_result_paths[mode].endswith('.json'):
                self.sim_net_floyd_results[mode] = json.load(open(self.sim_net_floyd_result_paths[mode]))
            elif self.sim_net_floyd_result_paths[mode].endswith('.gzip'):
                self.sim_net_floyd_results[mode] = gzip_to_dict(self.sim_net_floyd_result_paths[mode])
            self.sim_net_floyd_df[mode] = pd.read_csv(self.sim_net_floyd_df_paths[mode])
        self.nodes_to_link_attributes = {}
        self.node_to_lon_lat = {}
        self.sim_node_ids = {}
        self.internal_nodes_kdtree = {}
        self.link_collection = {}
        for mode in ['driving', 'pt', 'active']:
            self.nodes_to_link_attributes[mode] = {}
            self.node_to_lon_lat[mode] = {}
            weight_columns = [col for col in self.sim_net_floyd_df[mode] if 'minutes' in col]
            for ind, row in self.sim_net_floyd_df[mode].iterrows():
                node_key = '{}_{}'.format(row['aNodes'], row['bNodes'])
                self.nodes_to_link_attributes[mode][node_key] = {
                    'distance': row['distance'],
                    'from_coord': [float(row['aNodeLon']), float(row['aNodeLat'])],
                    'to_coord': [float(row['bNodeLon']), float(row['bNodeLat'])]}
                for col in weight_columns:
                    self.nodes_to_link_attributes[mode][node_key][col] = row[col]
                if mode == 'pt':
                    self.nodes_to_link_attributes[mode][node_key]['activity'] = row.get('activity', None)
                else:
                    # activity attribute only used in the pt network
                    # for other modes, activity is the same on every link
                    self.nodes_to_link_attributes[mode][node_key]['activity'] = None
                if row['aNodes'] not in self.node_to_lon_lat[mode]:
                    self.node_to_lon_lat[mode][str(row['aNodes'])] = [float(row['aNodeLon']), float(row['aNodeLat'])]
                if row['bNodes'] not in self.node_to_lon_lat[mode]:
                    self.node_to_lon_lat[mode][str(row['bNodes'])] = [float(row['bNodeLon']), float(row['bNodeLat'])]
            self.sim_node_ids[mode] = [node for node in self.node_to_lon_lat[mode]]
            sim_node_lls = [self.node_to_lon_lat[mode][node] for node in self.sim_node_ids[mode]]
            self.internal_nodes_kdtree[mode] = spatial.KDTree(np.array(sim_node_lls))

        # load portals
        portals_geojson = json.load(open(self.portal_path))
        self.portals = {}
        for idx, feature in enumerate(portals_geojson['features']):
            # pid = f'p{idx+1}'
            pid = feature['properties']['id']
            portal_geometry = feature['geometry']
            portal_shape = shape(portal_geometry)
            close_nodes = {}
            for mode in self.sim_node_ids:
                close_nodes[mode] = [node_id for node_id in self.sim_node_ids[mode]
                                     if portal_shape.contains(Point(self.node_to_lon_lat[mode][node_id]))]
            self.portals[pid] = {
                'geometry': portal_geometry,
                'close_nodes': close_nodes
            }
        self.pids = list(self.portals.keys())


    def get_external_costs(self, coord, portal_id, h3_cell_external=None):
            if h3_cell_external:
                h3_cell = h3_cell_external
            else:
                h3_cell = h3.geo_to_h3(coord[1], coord[0], self.external_h3_resolution)
            # portal_id = str(portal_id)
            # if not portal_id.startswith('p'):
            #     portal_id = f'p{portal_id}'
            return {mode: self.external_costs[mode].get(str(h3_cell), {}).get(portal_id,
                                                                              {'distance': 1000000,
                                                                               'duration': 1000000,
                                                                               'price': 1000000})
                    for mode in self.external_costs}

    def get_closest_internal_nodes(self, from_coordinates, n_nodes):
        node_ids = {}
        for mode in self.internal_nodes_kdtree:
            node_ids[mode] = [self.sim_node_ids[mode][n_ind] for n_ind in
                              self.internal_nodes_kdtree[mode].query(from_coordinates, n_nodes)[1]]
        return node_ids

    def get_node_path_from_fw_try_multi(self, from_list, to_list, mode):
        for fn in from_list:
            for tn in to_list:
                try:
                    node_path = self.get_node_path_from_fw(fn, tn, mode)
                    return node_path
                except:
                    pass
        return None

    def get_node_path_from_fw(self, from_node, to_node, internal_net):
        if from_node == to_node:
            return []
        pred = to_node
        path = [pred]
        while not pred == from_node:
            pred = str(self.sim_net_floyd_results[internal_net][from_node][pred])
            path.insert(0, pred)
        return path

    def get_path_coords_distances(self, path, internal_net, weight, mode):
        """
        takes a list of node ids and returns:
            a list of coordinates of each node
            a list of distances of each link
        may return empty lists if the path has length of 0 or 1
        """
        coords, distances, activities, minutes = [], [], [], []
        costs = {'driving': 0, 'walking': 0, 'waiting': 0, 'cycling': 0, 'pt': 0}
        if len(path) > 1:
            for node_ind in range(len(path) - 1):
                from_node = path[node_ind]
                to_node = path[node_ind + 1]
                link_attributes = self.nodes_to_link_attributes[internal_net].get('{}_{}'.format(from_node, to_node), None)
                if link_attributes is None:
                    print('Skip error: link {}_{} does not exist'.format(from_node, to_node))
                    link_attributes = {'distance': 0, weight: 0,
                                       'from_coord': self.node_to_lon_lat[internal_net][str(from_node)],
                                       'to_coord': self.node_to_lon_lat[internal_net][str(to_node)]}
                distances += [link_attributes['distance']]
                coords += [link_attributes['from_coord']]
                minutes += [link_attributes[weight]]
                # if mode.name == 'pt':
                #     costs[link_attributes['activity']] += link_attributes[weight]
                #     activities.append(link_attributes['activity'])
                # else:
                #     costs[mode.activity] += link_attributes[weight]
                costs[mode.activity] += link_attributes[weight]
            # add the final coordinate of the very last segment
            coords += [link_attributes['to_coord']]
        return coords, distances, activities, minutes, costs

    def get_internal_routes(self, from_loc, to_loc):
        routes = {}
        for im, mode in enumerate(self.base_modes):
            internal_net = mode.internal_net
            if not from_loc['close_nodes']:
                from_loc['close_nodes'] = self.get_closest_internal_nodes(from_loc['coord'], 5)
            if not to_loc['close_nodes']:
                to_loc['close_nodes'] = self.get_closest_internal_nodes(to_loc['coord'], 5)
            path = self.get_node_path_from_fw_try_multi(from_loc['close_nodes'][internal_net],
                                                        to_loc['close_nodes'][internal_net], internal_net)
            if path is None:
                coords, distances, total_distance, activities, minutes = [], [], float('1e10'), [], []
                costs = {'driving': 0, 'walking': 0, 'waiting': 0, 'cycling': 0, 'pt': 0}
            else:
                coords, distances, activities, minutes, costs = self.get_path_coords_distances(path, internal_net,
                                                                                               mode.weight, mode=mode)
                total_distance = sum(distances)
            routes[mode.name] = {
                'costs': costs,
                'internal_route': {
                    'node_path': path, 'distances': distances,
                    'activities': activities, 'minutes': minutes,
                    'total_distance': total_distance, 'coords': coords}}
        return routes

    def get_routes(self, from_loc, to_loc):
        """
        gets the best route by each mode between 2 locations
        returns a Route object
        If the from_loc or to_loc is not a grid cell (i.e. is outside the sim area)
        the Route returned will contain the internal part of the route as well
        as well the time duration of the external portion (pre or post)

        """
        if from_loc['in_sim_area'] and to_loc['in_sim_area']:
            # completely internal route
            routes = self.get_internal_routes(from_loc, to_loc)
            return {mode: Route(internal_route=routes[mode], costs=routes[mode]['costs']) for mode in routes}
        elif (not from_loc['in_sim_area']) and to_loc['in_sim_area']:
            # trip arriving into the site
            external_routes_by_portal = {pid: self.get_external_costs(from_loc['coord'], pid,
                                                                      h3_cell_external=from_loc['h3'].get(
                                                                          self.external_h3_resolution, None))
                                         for pid, portal in self.portals.items()}
            internal_routes_by_portal = {pid: self.get_internal_routes(portal, to_loc)
                                         for pid, portal in self.portals.items()}
            best_routes = self.get_best_portal_routes(external_routes_by_portal, internal_routes_by_portal, 'in')
            return best_routes
        elif from_loc['in_sim_area'] and (not to_loc['in_sim_area']):
            external_routes_by_portal = {pid: self.get_external_costs(to_loc['coord'], pid,
                                                                      h3_cell_external=to_loc['h3'].get(
                                                                          self.external_h3_resolution, None))
                                         for pid, portal in self.portals.items()}
            internal_routes_by_portal = {pid: self.get_internal_routes(from_loc, portal)
                                         for pid, portal in self.portals.items()}
            best_routes = self.get_best_portal_routes(external_routes_by_portal, internal_routes_by_portal, 'out')
            return best_routes
        else:
            routes, external_distance = self.get_approx_routes(from_loc, to_loc)
            return {mode: Route(internal_route=routes[mode],
                                costs=routes[mode]['costs'],
                                external_distance=external_distance)
                    for mode in routes}

    def get_best_portal_routes(self, external_routes_by_portal, internal_routes_by_portal, direction):
        """
        Takes a dict containing the internal routes by each mode and portal and
        a dict containing the external routes by each mode and portal
        returns the best portal route for each mode
        """
        best_routes = {}
        for mode in external_routes_by_portal[self.pids[0]]:
            best_portal_route = None
            best_portal_time = float('inf')
            for pid, portal in self.portals.items():
                # total_external_time = sum([external_routes_by_portal[pid][mode][t
                #                            ] for t in external_routes_by_portal[pid][mode]])
                total_external_time = external_routes_by_portal[pid][mode]['duration']
                total_external_distance = external_routes_by_portal[pid][mode]['distance']
                all_times = {
                    t: internal_routes_by_portal[pid][mode]['costs'][t] +
                       (external_routes_by_portal[pid][mode]['duration'] if t==mode else 0)
                        # external_routes_by_portal[pid][mode][t]
                    # for t in external_routes_by_portal[pid][mode]
                    for t in internal_routes_by_portal[pid][mode]['costs']
                }
                total_time = sum(all_times[t] for t in all_times)
                if total_time < best_portal_time:
                    best_portal_time = total_time
                    best_portal_route = internal_routes_by_portal[pid][mode]
                    best_costs = all_times
                    best_external_time = total_external_time
                    best_external_distance = total_external_distance
            if direction == 'in':
                best_routes[mode] = Route(internal_route=best_portal_route, costs=best_costs,
                                          pre_time=best_external_time, external_distance=best_external_distance)
            else:
                best_routes[mode] = Route(internal_route=best_portal_route, costs=best_costs,
                                          post_time=best_external_time, external_distance=best_external_distance)
        return best_routes

    def get_approx_routes(self, from_loc, to_loc):
        routes = {}
        # distance = 1.4 * get_haversine_distance(from_loc.centroid, to_loc.centroid)
        distance = h3.point_dist(from_loc['coord'][::-1], to_loc['coord'][::-1], unit='m')
        for im, mode in enumerate(self.base_modes):
            routes[mode.name] = {
                'costs': {'driving': 0, 'walking': 0, 'waiting': 0,
                          'cycling': 0, 'pt': 0},
                'internal_route': {'node_path': [], 'distances': [],
                                   'total_distance': 0, 'coords': []}}
            routes[mode.name]['costs'][mode.activity] = (distance / mode.speed_met_s) / 60
            for f_act in mode.fixed_costs:
                routes[mode.name]['costs'][f_act] += mode.fixed_costs[f_act]
        return routes, distance

    def prepare_external_routes(self):
        ext_route_costs = {}
        import pymongo
        client = pymongo.MongoClient('localhost', 27017)
        db = client[self.external_routes_db_name]
        collections = db.list_collection_names()
        ts = last_t = time.time()
        print('\nPreparing external route costs:\n' + '=='*30)
        for port in collections:
            print(f'\nPreparing for port: {port}')
            col = db[port]
            data_list = col.find()
            for data in data_list:
                h3_cell = data['h3_cell']
                mode = data['mode']
                if mode == 'cycle':
                    mode = 'cycling'
                route_rst_list = data['route'].get('result', {}).get('routes', [])
                if not route_rst_list:
                    distance, duration, price = 1e10, 1e10, 1e10
                    print(f"From {port} to {h3_cell} by {mode}: {data['route']}")
                    if data['route']['status'] == 1:
                        continue
                else:
                    route_rst = route_rst_list[0]
                    distance = route_rst.get('distance', 1e10)
                    duration = route_rst.get('duration', 1e10)
                    price = route_rst.get('price', 1e10)
                # print(col_name, h3_cell, mode, distance, duration, price)
                if mode not in ext_route_costs:
                    ext_route_costs[mode] = {}
                if h3_cell not in ext_route_costs[mode]:
                    ext_route_costs[mode][h3_cell] = {}
                ext_route_costs[mode][h3_cell][port] = {
                    'distance': distance,
                    'duration': duration / 60,
                    'price': price
                }
            crt_t = time.time()
            print('Port {} finished, time = {:4.4f} seconds\n\n'.format(port, crt_t-last_t))
            last_t = crt_t
        json.dump(ext_route_costs, open(self.external_route_costs_path, 'w'), indent=4)
        te = time.time()
        print('External route costs prepared and saved, time = {:4.4f} seconds'.format(te-ts))
        return ext_route_costs

    def get_link_collection(self):
        for mode in self.nodes_to_link_attributes:
            links = [(link['from_coord'], link['to_coord'])
                     for name, link in self.nodes_to_link_attributes[mode].items()]
            self.link_collection[mode] = matplotlib.collections.LineCollection(links, colors='grey')

    def viz_transportation_network(self, mode, fig=None, ax=None):
        if not self.link_collection:
            self.get_link_collection()
        if not fig:
            fig = plt.figure(figsize=(16, 12))
        if not ax:
            ax = fig.add_subplot(111)
        link_collection = copy.deepcopy(self.link_collection[mode])
        ax.add_collection(link_collection)
        ax.axis('off')
        ax.axis('equal')
        return ax, fig

    def viz_path(self, from_loc, to_loc, route, mode, fig=None, ax=None):
        ax, fig = self.viz_transportation_network(mode, fig, ax)
        from_coord = from_loc['coord']
        to_coord = to_loc['coord']
        node_path = route[mode].internal_route['internal_route']['node_path']
        if not fig:
            fig = plt.figure(figsize=(16, 12))
        if not ax:
            ax = fig.add_subplot(111)
        ori, = ax.plot(from_coord[0], from_coord[1], 'b>',
                       label='origin', markersize=15)
        des, = ax.plot(to_coord[0], to_coord[1], 'g^', label='destination',
                       markersize=15)
        node_to_lon_lat = self.node_to_lon_lat[mode]
        if node_path is not None and len(node_path) > 0:
            lon = np.array([(node_to_lon_lat[node_path[i]][0], node_to_lon_lat[node_path[i + 1]][0])
                            for i in range(len(node_path) - 1)]).transpose()
            lat = np.array([(node_to_lon_lat[node_path[i]][1], node_to_lon_lat[node_path[i + 1]][1])
                            for i in range(len(node_path) - 1)]).transpose()
            r = ax.plot(lon, lat, '-', color='red', linewidth=3)
        ax.axis('off')
        ax.axis('equal')
        ax.legend()

    def save(self):
        pickle.dump(self, open(self.save_path, 'wb'))



def test():
    tn = Transport_Network()
    # tn.prepare_external_routes()


if __name__ == '__main__':
    test()