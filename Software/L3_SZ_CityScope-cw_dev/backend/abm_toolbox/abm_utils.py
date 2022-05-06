import time
import math
import gzip
import json
import os, sys
sys.path.insert(1, os.path.realpath(os.path.pardir))
from utils import LocationSetter


def run_time(func):
    def wrapper(*args, **kw):
        t1 = time.time()
        res = func(*args, **kw)
        t2 = time.time()
        print('{:4.4f} secodns elasped for {}'.format(t2-t1, func.__name__))
        return res
    return wrapper


def dict_to_gzip(data, write_location):
    json_data = json.dumps(data)
    # Convert to bytes
    encoded = json_data.encode('utf-8')
    with gzip.open(write_location, 'wb') as f:
        f.write(encoded)

def gzip_to_dict(location):
    with gzip.open(location, 'rb') as f:
        file_content = f.read()
    test2=json.loads(file_content.decode('utf-8'))
    return test2


def split_data_multiprocess(data_list, num_process):
    num_data = len(data_list)
    chunksize = int(np.ceil(num_data/num_process))
    return [data_list[x: x+chunksize] for x in range(0, num_data, chunksize)]


def get_haversine_distance(point_1, point_2):
    """
    Calculate the distance between any 2 points on earth given as [lon, lat]
    return unit: meter
    """
    # convert decimal degrees to radians
    lon1, lat1, lon2, lat2 = map(math.radians, [point_1[0], point_1[1],
                                                point_2[0], point_2[1]])
    # haversine formula
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a))
    r = 6371000 # Radius of earth in kilometers. Use 3956 for miles
    return c * r

