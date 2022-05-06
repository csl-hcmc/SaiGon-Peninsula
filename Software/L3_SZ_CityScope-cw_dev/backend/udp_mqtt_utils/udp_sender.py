import socket, time
import numpy as np

UDP_IP = "192.168.1.8"
UDP_IP = "127.0.0.1"
# UDP_IP = "1.15.91.82"
UDP_PORT = [15800, 15820]

def generate_table_layout_message():
    all_values = [-1,17,34,13,38,37,33,29,42,48,35,10,3,8,9,43,19,23]
    all_values = [-1,17,34,13,38,37,33,29,48,35,8,9,19,23]
    data_list = np.random.choice(all_values, 276,True).tolist()
    data_list = [str(x) for x in data_list]
    data_str = 'i1 ' + ' '.join(data_list)
    return data_str, 15800
    
def generate_slider_message():
    data_str = '/slider ' + str(np.random.randint(6)) + ' ' + str(
        np.random.randint(100))
    return data_str, 15900
    
def generate_button_message():
    data_str = '/button ' + str(np.random.randint(2)) + ' ' + str(1)
    return data_str, 15900
    
def generate_message():
    what = np.random.choice(['table_layout', 'slider', 'button'])
    if what == 'table_layout':
        return generate_table_layout_message()
    elif what == 'slider':
        return generate_slider_message()
    elif what == 'button':
        return generate_button_message()


while True:
    # MESSAGE = input('Input message: ')
    MESSAGE, port = generate_message()
    # MESSAGE = b"Hello, World!"
    if MESSAGE == "exit":
        break
    MESSAGE = MESSAGE.encode()
    print("\nUDP target IP: %s" % UDP_IP)
    print("message: %s" % MESSAGE)

    sock = socket.socket(socket.AF_INET, # Internet
                     socket.SOCK_DGRAM) # UDP
    sock.sendto(MESSAGE, (UDP_IP, port))
    print("UDP target port: %s" % port)
    time.sleep(8)