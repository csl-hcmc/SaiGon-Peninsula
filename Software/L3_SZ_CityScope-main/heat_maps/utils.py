import os, sys, json, time
import pandas as pd
import numpy as np
import geopandas as gpd

from shapely.geometry.polygon import Polygon
from shapely.geometry.multipolygon import MultiPolygon

def euclidean_distance(x, y):
    x, y = np.asarray(x), np.asarray(y)
    return np.sqrt(np.sum((x - y) ** 2))

    
def distance_from_centroid(centroid: list, target_feature: dict):
    """
    centroid: [centroid_x, centroid_y]
    """
    if target_feature['geometry']['type'] == 'Point':
        return euclidean_distance(centroid, target_feature['geometry']['coordinates'])
    elif target_feature['geometry']['type'] == 'MultiPoint':
        return euclidean_distance(centroid, target_feature['geometry']['coordinates'][0])
    elif target_feature['geometry']['type'] == 'MultiPolygon':
        target_polygon = Polygon(target_feature['geometry']['coordinates'][0][0])
        target_centroid = [target_polygon.centroid.x, target_polygon.centroid.y]
        return euclidean_distance(centroid, ttarget_centroid)
    elif target_feature['geometry']['type'] == 'Polygon':
        target_polygon = Polygon(target_feature['geometry']['coordinates'][0])
        target_centroid = [target_polygon.centroid.x, target_polygon.centroid.y]
        return euclidean_distance(centroid, ttarget_centroid)
    elif target_feature['geometry']['type'] == 'MultiLineString':
        min_dist_to_node = min([euclidean_distance(centroid, node) 
            for node in target_feature['geometry']['coordinates'][0]])
        return min_dist_to_node
          
    
def get_epsg(geojson_content: dict):
    crs = geojson_content.get('crs', None)
    if crs is not None:
        crs = crs['properties']['name']
    epsg_crs_lookup = {
        "urn:ogc:def:crs:EPSG::4547": 4547,
        "urn:ogc:def:crs:OGC:1.3:CRS84": 4326,
    }
    return epsg_crs_lookup.get(crs, 'unknown')
    
    
def num2str(num):
    if (num < 1e-4 or num > 1e8) and num > 0:
        return '{:4.4e}'.format(num)
    elif (-num < 1e-4 or -num > 1e8) and num < 0:
        return '{:4.4e}'.format(num)
    elif num == int(num):
        return str(int(num))
    elif num == round(num,4):
        return str(num)
    else:
        return '{:4.4f}'.format(num)
        
        
