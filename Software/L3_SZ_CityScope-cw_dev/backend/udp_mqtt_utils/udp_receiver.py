import socket, os

UDP_IP = "192.168.1.8"
UDP_IP = "127.0.0.1"
UDP_IP = "0.0.0.0"
UDP_PORT = 15900

sock = socket.socket(socket.AF_INET, # Internet
                     socket.SOCK_DGRAM) # UDP
# sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
# sock.setsockopt(socket.SOL_SOCKET, socket. SO_REUSEPORT, 1)
sock.bind((UDP_IP, UDP_PORT))

while True:
    data, addr = sock.recvfrom(1024*200) # buffer size in bytes
    data = data.strip().decode()
    print("received message: %s" % data)
    print('\n\n')
    if data == 'clear':
        os.system('clear')
    if data == 'exit':
        break