import paho.mqtt.client as mqtt_client
import time, random, jsonpickle

def connect_mqtt(broker, port, client_id=None, username=None, password=None):
    def on_connect(client, userdata, flags, rc):
        if rc == 0:
            print("Connected to MQTT Broker!")
            pass
        else:
            print("Failed to connect, return code %d\n", rc)
    
    def on_message(client, userdata, msg):
        # print(msg.payload)
        data = eval(msg.payload.decode())
        # print(msg.payload)
        # data = jsonpickle.decode(msg.payload)
        print(data)
    
    if client_id:
        client = mqtt_client.Client(client_id)
    else:
        client = mqtt_client.Client()
    if username and password:
        client.username_pw_set(username, password)
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(broker, port)
    return client

    
 
 
def main():
    broker = 'localhost'
    broker = '1.15.91.82'
    port = 1883
    topic = 'cw/test'
    topic = 'update'
    # topic = 'results'
    client = connect_mqtt(broker, port)
    client.subscribe(topic)
    client.loop_forever()
    
    
if __name__ == "__main__":
    main()
    