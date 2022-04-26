import os, time, socket, threading, json
import paho.mqtt.client as mqtt
import h3.api.numpy_int as h3
import numpy as np
from scipy import stats
from geodata_toolbox import H3Grids
import matplotlib.pyplot as plt

class Indicator:
    def __init__(self, H3, Table=None):
        self.H3 = H3
        self.h3_features = None
        if not self.H3.dist_lookup:
            self.H3._get_h3_dist_lookup(Table=Table)


    def _get_straight_line_dist_to_h3_cells(self, start_h3_cell, target_h3_cells):
        dist_list = [
            self.H3.dist_lookup.get(start_h3_cell, {}).get(target_h3_cell, None)
            for target_h3_cell in target_h3_cells
        ]
        inner_dist = h3.edge_length(self.H3.resolution) / 2
        # in case distance is not in precooked lookup...
        while not all(dist_list):
            idx_of_none = dist_list.index(None)
            # print(start_h3_cell,  target_h3_cells[idx_of_none], dist_list[idx_of_none])
            target_h3_cell = target_h3_cells[idx_of_none]
            this_dist = h3.point_dist(h3.h3_to_geo(start_h3_cell), h3.h3_to_geo(target_h3_cell)) \
                if start_h3_cell != target_h3_cell else inner_dist
            dist_list[idx_of_none] = this_dist
            self.H3.dist_lookup.setdefault(start_h3_cell, {})[target_h3_cell] = this_dist
            print('Strange error, check 123')
        assert min(dist_list) > 0
        return dist_list

    def _get_network_dist_to_h3_cells(self, start_h3_cell, target_h3_cells):
        # to do: network distance calculation
        return []


    def verify_heatmap(self, Table, name, target_attr, minimum_ratio_th,
                       focus_table_grid_code=None, cmap='Reds'):
        if focus_table_grid_code is None:
            focus_table_grid_code = []
        elif type(focus_table_grid_code) != list:
            focus_table_grid_code = [focus_table_grid_code]
        ax0 = plt.subplot(2, 1, 1)
        self.plot_heatmap(Table, name, ax=ax0, cmap=cmap)
        ax1 = plt.subplot(2, 1, 2)
        if not self.h3_features:
            self.h3_features = self.H3.export_h3_features()
        h3_features = self.h3_features
        h3_cell_area = h3.hex_area(self.H3.resolution, 'm^2')
        focus_h3_features = [
            h3_fea for h3_fea, h3_cell in zip(h3_features, self.H3.h3_stats.keys())
            if self.H3.h3_stats[h3_cell].get(target_attr, -1) > minimum_ratio_th * h3_cell_area
        ]
        # h3_values = [rst.get(h3_feature['properties']['h3_id'], None) for h3_feature in h3_features]
        # Table.plot(ax=ax2, features=h3_features,
        #        crs=4326, value=h3_values, cmap='Reds')
        Table.plot(ax=ax1, features=focus_h3_features, crs=4326, facecolor='grey', edgecolor='grey')
        if focus_table_grid_code:
            focus_locations = [0 for i in range(len(Table.features[Table.crs['geographic']]))]
            for zone, zone_layout in Table.interactive_grid_layout.items():
                for cell_id, cell_state in zone_layout.items():
                    if cell_state['code'] in focus_table_grid_code:
                        focus_locations[cell_id] = 1
            focus_locations_colorized = [
                'none' if fl==0 else 'r'
                for fl in focus_locations
            ]
            Table.plot(color=focus_locations_colorized, ax=ax1)
        Table.plot(ax=ax1, facecolor='none', edgecolor='grey', linewidth=0.5)
        ax1.set_xlim(ax0.get_xlim())
        ax1.set_ylim(ax0.get_ylim())

    def plot_heatmap(self, Table, name, ax=None, cmap='Reds'):
        if not ax:
            ax = plt.gca()
        table_grid_values = Table.get_grid_value_from_h3_cells(self.H3.resolution,
                                                               name,
                                                               self_update=False)
        Table.plot(value=table_grid_values, ax=ax, cmap=cmap)


class Handler:
    def __init__(self, udp_receiver_ip, udp_receiver_port, udp_sender_ip, udp_sender_port,
                 use_mqtt=True, mqtt_ip='localhost', mqtt_port=1883,
                 mqtt_update_topic='update', mqtt_results_topic='results',
                 buffer_size=1024*8):
        self.udp_receiver = {
            'ip': udp_receiver_ip,
            'port': udp_receiver_port
        }
        self.udp_sender = {
            'ip': udp_sender_ip,
            'port': udp_sender_port
        }
        self.udp_receiver['socket'] = socket.socket(socket.AF_INET,
                                                    socket.SOCK_DGRAM)
        self.udp_sender['socket'] = socket.socket(socket.AF_INET,
                                                  socket.SOCK_DGRAM)
        if use_mqtt:
            self.mqtt = {
                'ip': mqtt_ip,
                'port': mqtt_port,
                'topics': {
                    'update': mqtt_update_topic,
                    'results': mqtt_results_topic
                },
                'client': ClientMQTT(mqtt_ip, mqtt_port)
            }
        else:
            self.mqtt = None
        self.config = {'buffer_size': buffer_size}
        self.Table = None
        self.indicators = []

    def add_table(self, Table):
        self.Table = Table

    def add_indicator(self, *args):
        for indicator in args:
            if not isinstance(indicator, 'Indicator'):
                print(f'Warning: {indicator} is not a valid Indicator instance and ignored')
            self.indicators.append(indicator)

    def run(self):
        thread_table = threading.Thread(target = self._listen_to_table,
                                        args = (self.config['buffer_size'], True),
                                        name = 'TableInteraction')
        thread_table.start()
        thread_indicators = threading.Thread(target = self._listen_to_indicators,
                                             args = (),
                                             name = 'IndicatorResults')
        thread_indicators.start()
        # self._listen_to_indicators()


    def _listen_to_table(self, buffer_size, print_flag=False):
        receiver = self.udp_receiver['socket']
        try:
            receiver.bind((self.udp_receiver['ip'], self.udp_receiver['port']))
            while True:
                data, addr = receiver.recvfrom(buffer_size)
                data = data.strip().decode()
                data_epoch = time.time()
                if print_flag:
                    print(f'\nNew data received: {data}\n')
                if self.Table:
                    self.Table.update(layout_str=data)
                    if self.mqtt:
                        self.mqtt['client'].publish(
                            self.mqtt['topics']['update'],
                            json.dumps({
                                'msg': 'table updated',
                                'epoch': data_epoch,
                                'time': time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(data_epoch))
                            })
                        )
                    else:
                        # use pure udp way
                        pass
                else:
                    if print_flag:
                        print('New msg is thrown as no table exists')
        finally:
            if self.mqtt:
                self.mqtt['client'].disconnect()
            receiver.shutdown(socket.SHUT_RDWR)
            receiver.close()

    def _listen_to_indicators(self):
        sender = self.udp_sender['socket']
        def send_to(msg):
            print('fuck1: ', msg)
            sender.sendto(msg, (self.udp_sender['ip'], self.udp_sender['port']))
        try:
            if self.mqtt:
                mqtt_client = self.mqtt['client']
                # mqtt_client.register_handler(self.mqtt['topics']['results'], send_to)
                mqtt_client.register_handler('results', send_to)
                while True:  # blocking
                    time.sleep(50)
            else:
                pass
        finally:
            if self.mqtt:
                self.mqtt['client'].disconnect()
            sender.shutdown(socket.SHUT_RDWR)
            sender.close()


class ClientMQTT:
    def __init__(self, broker, port, client_id=None, username=None, password=None):
        if client_id:
            self.client = mqtt.Client(client_id)
        else:
            self.client = mqtt.Client()
        if username and password:
            self.client.username_pw_set(username, password)
        self.client.on_connect = self.on_connect
        self.client.on_subscribe = self.on_subscribe
        self.client.on_message = self.on_message
        self.callbacks = {}
        self.client.connect(broker, port)
        # self.client.subscribe("results")
        # self.__run()
        threading.Thread(target=self.__run, daemon=True).start()

    def __run(self):
        self.client.loop_forever()

    def on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            print("Connected to MQTT Broker!")
        else:
            print("Failed to connect, return code %d\n", rc)
        for topic in self.callbacks:
            self.client.subscribe(topic)

    def on_subscribe(self, client, userdata, mid, granted_qos):
        pass

    def on_message(self, client, userdata, msg):
        self.callbacks[msg.topic](eval(msg.payload.decode()))

    def register_handler(self, topic, handler):
        self.callbacks[topic] = handler
        self.client.subscribe(topic)
        print(f'Register {handler} to topic "{topic}"')

    def disconnect(self):
        self.client.disconnect()


def dist_unit_converter(raw_value, raw_unit, return_unit, speed=None):
    assert raw_unit in ['m', 'km', 'sec', 'min', 'h']
    assert return_unit in ['m', 'km', 'sec', 'min', 'h']
    if raw_unit in ['m', 'km']:
        if raw_unit == 'km':
            dist_in_km = raw_value
        elif raw_unit == 'm':
            dist_in_km = raw_value / 1000
        dist_in_h = None
    if raw_unit in ['sec', 'min', 'h']:
        dist_in_km = None
        if raw_unit == 'sec':
            dist_in_h = raw_value / 3600
        elif raw_unit == 'min':
            dist_in_h = raw_value / 60
        elif raw_unit == 'h':
            dist_in_h = raw_value
    if not dist_in_h:
        dist_in_h = dist_in_km / speed
    if not dist_in_km:
        dist_in_km = dist_in_h * speed
    if return_unit == 'm':
        return_value = dist_in_km * 1000
    elif return_unit == 'km':
        return_value = dist_in_km
    elif return_unit == 'h':
        return_value = dist_in_h
    elif return_unit == 'min':
        return_value = dist_in_h * 60
    elif return_unit == 'sec':
        return_value = dist_in_h * 3600
    return return_value


from geodata_toolbox import *
from population_toolbox import Population, Person
def main():
    resolution = 11
    POIs = PointGeoData(name='pois',
                        src_geojson_path='poi_LBCS.geojson')

    POIs.make_h3_stats(resolution=resolution, agg_attrs={
        "2100_area": "sum",
        "2200_area": "sum",
        "2500_area": "sum",
        "5300_area": "sum",
        "6200_area": "sum",
        "6510_area": "sum",
        "6560_area": "sum"
    })

    Buildings = PolygonGeoData(name='buildings',
                               src_geojson_path='building_LBCS.geojson')

    Buildings.make_h3_stats(resolution, agg_attrs={
        '2100_area': 'sum',
        '2200_area': 'sum',
        '2500_area': 'sum',
        '5300_area': 'sum',
        "6200_area": 'sum',
        "6510_area": 'sum',
        "6560_area": 'sum',
        "1100_area": 'sum',
        "2400_area": 'sum',
        "3000_area": 'sum',
        "3600_area": 'sum',
        "4100_area": 'sum',
        "4200_area": 'sum',
        "4242_area": 'sum',
        "4300_area": 'sum',
        "5100_area": 'sum',
        "5200_area": 'sum',
        "5500_area": 'sum',
        "6100_area": 'sum',
        "6400_area": 'sum',
        "6530_area": 'sum'
    })

    LU = PolygonGeoData(name='landuse',
                        src_geojson_path='Land_LBCS.geojson')
    LU.make_h3_stats(resolution, agg_attrs={
        "3600_area": "sum",
        "5000_area": "sum",
        "5500_area": "sum",
        "4100_area": "sum",
        "9000_area": "sum"
    })
    print('Data loaded')

    Pop = Population('population', 'base_pop.geojson', None,
                     'shenzhen', proj_crs=4547, person_attrs=[])
    Pop.set_base_sim_population(resolution)
    print('Population loaded')

    H3 = H3Grids(resolution)
    pop_stats = {k: {'tt_pop': v} for k, v in Pop.h3_count_sim_pop['home'][resolution].items()}
    h3_stats = H3.combine_h3_stats([Buildings.h3_stats[resolution],
                                    POIs.h3_stats[resolution],
                                    LU.h3_stats[resolution],
                                    pop_stats
                                    ])

    T = TableGrids('table', resolution, H3=H3,
                   src_geojson_path='grid1_4326.geojson',
                   table='shenzhen',
                   proj_crs=4546)
    print('Tables initiated')

    H = Handler(udp_receiver_ip='127.0.0.1',
                udp_receiver_port=15800,
                udp_sender_ip='127.0.0.1',
                udp_sender_port=15801)
    print('Handler initialized')
    H.add_table(T)
    H.run()


if __name__ == '__main__':
    main()