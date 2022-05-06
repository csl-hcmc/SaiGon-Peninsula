import os, time, socket, threading, json, sys, traceback
import paho.mqtt.client as mqtt
import h3.api.numpy_int as h3
import numpy as np
from scipy import stats
from grids_toolbox import H3Grids
import matplotlib.pyplot as plt

def formatting_conditions(condition_list):
    for idx, item in enumerate(condition_list):
        if type(item) != list:
            condition_list[idx] = [item]
    return condition_list


class Indicator:
    def __init__(self, H3, name='', Table=None):
        self.H3 = H3
        self.h3_features = None
        self.Table = Table
        self.work_dir = Table.work_dir if Table else None
        self.name = name
        if not self.H3.dist_lookup:
            self.H3._get_h3_dist_lookup(Table=Table)
        self.mqtt = None
        self.udp = None
        self.scheduled_tasks = []

    def set_mqtt_communicator(self, mqtt_ip='localhost', mqtt_port=1883,
                              mqtt_update_topic='update',
                              mqtt_results_topic='results'):
        topics = {
            'update': mqtt_update_topic,
            'results': mqtt_results_topic
        }
        self.mqtt = ClientMQTT(mqtt_ip, mqtt_port, topics)
        self.mqtt.connect_and_loop()


    def set_udp_communicator(self):
        pass


    def set_scheduled_tasks(self, *args):
        for fun_tuple in args:
            self.scheduled_tasks.append(fun_tuple)

    def run_scheduled_tasks(self):
        def process_tasks(msg_data):
            for fun_tuple in self.scheduled_tasks:
                condition, format_str, fun = fun_tuple
                skip_this_task = True
                if not condition:
                    skip_this_task = False
                elif type(condition) == str:
                    if condition in msg_data['task_tokens']:
                        skip_this_task = False
                elif type(condition) == list:
                    # make condition to a list of list, with each inner-list being a AND operation
                    # while the outer list being a OR operation
                    any_conditions = formatting_conditions(condition)
                    for all_conditions in any_conditions:
                        if all([item in msg_data['task_tokens'] for item in all_conditions]):
                            skip_this_task = False
                            break
                else:
                    raise ValueError(f'Invalid condition: {condition}')

                if skip_this_task:
                    continue
                try:
                    rst = fun()
                    to_frontend = rst['to_frontend']
                    task_name = rst['name']
                except Exception as e:
                    print('\n'+'='*50)
                    print(traceback.format_exc())
                    print('=' * 50 + '\n')
                formatted_rst = format_str.format(to_frontend)
                if self.mqtt:
                    (rc, mid) = self.mqtt.client.publish(f"{self.mqtt.topics['results']}/{self.name}/{task_name}",
                                                         json.dumps(formatted_rst))
        try:
            if self.mqtt:
                self.mqtt.register_handler(root_topic=self.mqtt.topics['update'],
                                           all_topics=self.mqtt.topics['update']+'/#',
                                           handler=process_tasks)
                while True:  # blocking
                    time.sleep(50)
            else:
                pass

        finally:
            if self.mqtt:
                self.mqtt.client.disconnect()


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
            # print('Strange error, check 123')
        assert min(dist_list) > 0
        return dist_list

    def _get_network_dist_to_h3_cells(self, start_h3_cell, target_h3_cells):
        # to do: network distance calculation
        return []

    def get_target_h3_cells(self, target_classes, attr_name='LBCS', item_name='area',
                             usage_name='usage', minimum_ratio_th=0):
        if type(target_classes) != list:
            target_classes = [target_classes]
        h3_cell_area = self.H3.h3_cell_area
        target_h3_cells = []
        for class_name in target_classes:
            h3_cells_contain_this_class = [
                h3_cell for h3_cell, h3_attrs in self.H3.h3_stats.items()
                if h3_attrs[usage_name][attr_name][item_name].get(str(class_name), -1) > minimum_ratio_th * h3_cell_area
            ]
            target_h3_cells += h3_cells_contain_this_class
        target_h3_cells = list(set(target_h3_cells))
        return target_h3_cells

    def normalization(self, raw, minV='auto', maxV='auto', better='high'):
        if type(raw) not in [list, tuple, dict]:
            try:
                minV, maxV = float(minV), float(maxV)
            except:
                raise ValueError('minV and maxV must be number for single value normalization')
            if better == 'high':
                normalized = (raw - minV) / (maxV - minV)
            else:
                normalized = (maxV - raw) / (maxV - minV)
            normalized = min(max(normalized, 0), 1)
        else:
            raw_values = np.array(list(raw.values())) if type(raw)==dict else np.array(raw)
            if minV == 'auto':
                minV = min(raw_values)
            if maxV == 'auto':
                maxV = max(raw_values)
            if better == 'high':
                normalized_values = (raw_values - minV) / (maxV - minV)
            else:
                normalized_values = (maxV - raw_values) / (maxV - minV)
            normalized_values = np.minimum(
                np.maximum(normalized_values, np.zeros_like(normalized_values)),
                np.ones_like(normalized_values)
            )
            normalized = normalized_values.tolist()
            if type(raw) == tuple:
                normalized = tuple(normalized)
            elif type(raw) == dict:
                normalized = {k:v for k, v in zip(raw.keys(), normalized)}
        return normalized


    def verify_heatmap(self, Table, name, target_classes, attr_name='LBCS', item_name='area', usage_name='usage',
                       minimum_ratio_th=0.1, focus_table_grid_code=None, cmap='Reds'):
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
        target_h3_cells = self.get_target_h3_cells(target_classes, attr_name, item_name, usage_name, minimum_ratio_th)
        focus_h3_features = [
            h3_fea for h3_fea, h3_cell in zip(h3_features, self.H3.h3_stats.keys())
            if h3_cell in target_h3_cells
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
    def __init__(self, table='shenzhen',
                 udp_receiver_table_ip='0.0.0.0', udp_receiver_table_port=15800,
                 udp_receiver_tablet_ip='0.0.0.0', udp_receiver_tablet_port=15900,
                 udp_sender_ip='127.0.0.1', udp_sender_port=15801,
                 tablet_spec_json_path='',
                 inner_communication='mqtt',
                 mqtt_broker_ip='localhost', mqtt_broker_port=1883,
                 mqtt_update_topic='update', mqtt_results_topic='results',
                 buffer_size=1024*8):
        self.table = table
        self._get_spec(tablet_spec_json_path)
        self.udp_receiver = {
            'table': {
                'ip': udp_receiver_table_ip,
                'port': udp_receiver_table_port
            },
            'tablet': {
                'ip': udp_receiver_tablet_ip,
                'port': udp_receiver_tablet_port
            }

        }
        self.udp_sender = {
            'ip': udp_sender_ip,
            'port': udp_sender_port
        }
        self.udp_receiver['table']['socket'] = socket.socket(socket.AF_INET,
                                                             socket.SOCK_DGRAM)
        self.udp_receiver['tablet']['socket'] = socket.socket(socket.AF_INET,
                                                              socket.SOCK_DGRAM)
        self.udp_sender['socket'] = socket.socket(socket.AF_INET,
                                                  socket.SOCK_DGRAM)

        self.inner_communication = inner_communication
        if inner_communication == 'mqtt':
            topics = {
                'update': mqtt_update_topic,
                'results': mqtt_results_topic
            }
            self.mqtt = ClientMQTT(mqtt_broker_ip, mqtt_broker_port, topics)
        else:
            self.mqtt = None

        self.config = {'buffer_size': buffer_size}
        self.Table = None
        self.table_viz_content = None
        self.indicators = []

    def _get_spec(self, tablet_spec_json_path):
        use_tablet_spec_json_path = ''
        for try_spec_path in [tablet_spec_json_path,
                              os.path.join('cities', self.table, 'clean', tablet_spec_json_path),
                              os.path.join('cities', self.table, 'clean', 'tablet_spec.json')]:
            if os.path.exists(try_spec_path) and os.path.isfile(try_spec_path):
                use_tablet_spec_json_path = try_spec_path
                break
        if use_tablet_spec_json_path:
            self.tablet_spec = json.load(open(use_tablet_spec_json_path, 'r'))
            candidate_table_viz_contents = [
                button_spec['task_name']
                for button_idx, button_spec in self.tablet_spec.get('buttons', {}).items()
                if button_spec['function'] == 'table_viz_content'
            ]
            if candidate_table_viz_contents:
                self.table_viz_content = candidate_table_viz_contents[0]
        else:
            self.tablet_spec = {}


    def add_table(self, Table):
        self.Table = Table

    def add_indicators(self, *args):
        for indicator in args:
            if not isinstance(indicator, Indicator):
                print(f'Warning: {indicator} is not a valid Indicator instance and ignored')
            self.indicators.append(indicator)

    def run(self):
        # mqtt:
        if self.inner_communication == 'mqtt':
            self.mqtt.connect_and_loop()  # connect and loop forever if not running
            for indicator in self.indicators:
                indicator.set_mqtt_communicator(mqtt_ip=self.mqtt.ip,
                                                mqtt_port=self.mqtt.port,
                                                mqtt_update_topic=self.mqtt.topics['update'],
                                                mqtt_results_topic=self.mqtt.topics['results'])
        thread_table = threading.Thread(target = self._listen_to_table,
                                        args = (self.config['buffer_size'], False),
                                        name = 'TableInteraction')
        thread_table.start()
        thread_tablet = threading.Thread(target = self._listen_to_tablet,
                                         args = (self.config['buffer_size'], False),
                                         name = 'TabletInteraction')
        thread_tablet.start()
        thread_results = threading.Thread(target = self._listen_to_indicators,
                                             args = (),
                                             name = 'thread_results')
        thread_results.start()
        for idx, indicator in enumerate(self.indicators):
            thread_indicator = threading.Thread(target = indicator.run_scheduled_tasks,
                                                args = (),
                                                name = f'thread_indicator_{idx}_{indicator.name}')
            thread_indicator.start()


    def _listen_to_table(self, buffer_size, print_flag=False):
        receiver = self.udp_receiver['table']['socket']
        try:
            receiver.bind((self.udp_receiver['table']['ip'], self.udp_receiver['table']['port']))
            while True:
                data, addr = receiver.recvfrom(buffer_size)
                data = data.strip().decode()
                data_epoch = time.time()
                task_tokens = ['screen_all']
                if self.table_viz_content:
                    task_tokens.append(self.table_viz_content)
                else:
                    task_tokens.append('heatmaps_all')
                if print_flag:
                    print(f'\nNew table data received: {data}\n')
                if self.Table:
                    self.Table.update(layout_str=data)
                    if self.mqtt:
                        self.mqtt.client.publish(
                            self.mqtt.topics['update'] + '/table',
                            json.dumps({
                                'task_tokens': task_tokens,
                                'msg': 'table updated',
                                'epoch': data_epoch,
                                'time': time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(data_epoch))
                            })
                        )
                    else:
                        # use pure udp way
                        pass
                elif print_flag:
                    print('New msg is ignored because no table exists')
        finally:
            if self.mqtt:
                self.mqtt.client.disconnect()
            receiver.shutdown(socket.SHUT_RDWR)
            receiver.close()


    def _listen_to_tablet(self, buffer_size, print_flag=False):
        receiver = self.udp_receiver['tablet']['socket']
        try:
            receiver.bind((self.udp_receiver['tablet']['ip'], self.udp_receiver['tablet']['port']))
            while True:
                data, addr = receiver.recvfrom(buffer_size)
                data = data.strip().decode()
                data_epoch = time.time()
                if print_flag:
                    print(f'\nNew tablet data received: {data}\n')
                if data.startswith('/slider'):
                    task_tokens = ['screen_all']
                    if self.table_viz_content:
                        task_tokens.append(self.table_viz_content)
                    else:
                        task_tokens.append('heatmaps_all')
                    tmp = data.split(' ')
                    slider_idx, slider_value = tmp[1], int(tmp[2])
                    if slider_idx in self.tablet_spec['sliders']:
                        slider_function = self.tablet_spec['sliders'][slider_idx]['function']
                        if slider_function == 'change density':
                            if self.Table:
                                land_type_code = self.tablet_spec['sliders'][slider_idx]['land_type_code']
                                self.Table.update(layout_str=None, changed_density={land_type_code: slider_value})
                                if self.mqtt:
                                    self.mqtt.client.publish(
                                        self.mqtt.topics['update'] + '/density',
                                        json.dumps({
                                            'task_tokens': task_tokens,
                                            'msg': 'density updated by tablet slider',
                                            'epoch': data_epoch,
                                            'time': time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(data_epoch))
                                        })
                                    )
                                else:
                                    # use pure udp way
                                    pass
                            elif print_flag:
                                print('New slider message is ignored as no table exists')
                        elif slider_function == 'some other recognized functions':
                            pass
                        elif print_flag:
                            print(f'New slider message is ignored as its function is unrecognized: {slider_function}')
                    elif print_flag:
                        print(f'Message from slider {slider_idx} is ignored as this slider is undefined')
                elif data.startswith('/button'):
                    tmp = data.split(' ')
                    button_idx, button_value = tmp[1], int(tmp[2])
                    if button_idx in self.tablet_spec['buttons']:
                        button_function = self.tablet_spec['buttons'][button_idx]['function']
                        if button_function == 'table_viz_content':
                            if button_value == 1:
                                self.table_viz_content = self.tablet_spec['buttons'][button_idx]['task_name']
                                if self.mqtt:
                                    self.mqtt.client.publish(
                                        self.mqtt.topics['update'] + '/table_viz_content',
                                        json.dumps({
                                            'task_tokens': [self.table_viz_content],
                                            'msg': 'table viz content changed by tablet button',
                                            'epoch': data_epoch,
                                            'time': time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(data_epoch))
                                        })
                                    )
                                else:
                                    # use pure udp way
                                    pass
                        elif slider_function == 'some other recognized functions':
                            pass
                        elif print_flag:
                            print(f'New button message is ignored as its function is unrecognized: {button_function}')
                    elif print_flag:
                        print(f'Message from button {button_idx} is ignored as this button is undefined')
        finally:
            if self.mqtt:
                self.mqtt.client.disconnect()
            receiver.shutdown(socket.SHUT_RDWR)
            receiver.close()


    def _listen_to_indicators(self):
        sender = self.udp_sender['socket']
        def send_to_frontend(msg_data):
            # print(sender, type(sender), self.udp_sender['ip'], self.udp_sender['port'])
            sender.sendto(msg_data.encode(), (self.udp_sender['ip'], self.udp_sender['port']))
        try:
            if self.mqtt:
                self.mqtt.register_handler(root_topic=self.mqtt.topics['results'],
                                           all_topics=self.mqtt.topics['results']+'/#',
                                           handler=send_to_frontend)
                while True:  # blocking
                    time.sleep(50)
            else:
                pass
        finally:
            if self.mqtt:
                self.mqtt.client.disconnect()
            sender.shutdown(socket.SHUT_RDWR)
            sender.close()


class ClientMQTT:
    def __init__(self, broker_ip, broker_port, topics=None, client_id=None, username=None, password=None):
        self.ip = broker_ip
        self.port = broker_port
        if not client_id:
            client_id = 'client_'+str(int(np.random.rand()*1e20))
        self.client = mqtt.Client(client_id, clean_session=False)

        if username and password:
            self.client.username_pw_set(username, password)
        self.client.on_connect = self.on_connect
        self.client.on_subscribe = self.on_subscribe
        self.client.on_message = self.on_message
        self.callbacks = {}
        self.topics = topics
        self.connected = False


    def connect_and_loop(self):
        if not self.connected:
            self.client.connect(self.ip, self.port)
            self.connected = True
            threading.Thread(target=self.__loop, daemon=True).start()
            # self.client.loop_start()

    def __loop(self):
        self.client.loop_start()

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
        try:
            root_topic = msg.topic.split('/')[0]
            msg_data = eval(msg.payload.decode())
            self.callbacks[root_topic](msg_data)
        except Exception as e:
            print('\n' + '=' * 50)
            print(traceback.format_exc())
            print(f'data: {msg.payload.decode()}')
            print('=' * 50 + '\n')

    def register_handler(self, root_topic, all_topics, handler):
        self.callbacks[root_topic] = handler
        self.client.subscribe(all_topics)
        print(f'Register {handler} to topic "{all_topics}"')

    def disconnect(self, *args, **kwargs):
        self.client.loop_stop()
        self.client.disconnect(*args, **kwargs)
        self.connected = False

    def publish(self, *args, **kwargs):
        self.client.publish(*args, **kwargs)


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