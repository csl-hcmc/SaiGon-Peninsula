import paho.mqtt.client as mqtt_client
import time, random
import numpy as np

def connect_mqtt(broker, port, client_id=None, username=None, password=None):
    def on_connect(client, userdata, flags, rc):
        if rc == 0:
            print("Connected to MQTT Broker!")
            pass
        else:
            print("Failed to connect, return code %d\n", rc)
    if client_id:
        client = mqtt_client.Client(client_id)
    else:
        client = mqtt_client.Client()
    if username and password:
        client.username_pw_set(username, password)
    client.on_connect = on_connect
    client.connect(broker, port)
    return client

    
def random_publish(client, topic, interval=10):
    while True:
        time.sleep(interval)
        client.publish(topic, str(random.random()))
        print('published')
        
        
def random_publish2(client, topic_parent, topic_child, interval=4):
    tp2 = list(topic_child.keys())
    while True:
        time.sleep(interval)
        r_topic2 = random.choice(tp2)
        r = random.random()
        if r < 0.5: r += 0.5
        format_str = topic_child[r_topic2].format(r)
        # print(f'{topic_parent}/{r_topic2}', '\n', format_str, '\n\n')
        client.publish(f'{topic_parent}/{r_topic2}', format_str)
 
 
def main():
    broker = 'localhost'
    broker = '1.15.91.82'
    port = 1883
    topic_parent = 'results'
    topic_child = {
        'density/resident_density': 'r deres {}',
        'density/job_density': 'r deem {}',
        'density/third_place_density': 'r de3pd {}',
        'density/intersection_density': 'r pid {}',
        'diversity/residential_job_ratio': 'r dirjr {}',
        'proximity_value/third_place_proximity': 'r pa3p {}',
    }
    
    topic_child = {
        'building_energy/building_energy': 'r ipbe {}'
    }
    
    # topic = 'update'
    username = 'butlr'
    password = '2019Ted/'
    client = connect_mqtt(broker, port, username=username, password=password)
    client.loop_start()
    # random_publish(client, topic)
    random_publish2(client, topic_parent, topic_child)
    
    
if __name__ == "__main__":
    main()
    