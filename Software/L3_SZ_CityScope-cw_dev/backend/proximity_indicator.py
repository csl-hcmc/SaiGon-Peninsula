import os
import h3.api.numpy_int as h3
import numpy as np
from scipy import stats
from grids_toolbox import H3Grids
from indicator_toolbox import Indicator, dist_unit_converter


class ProximityIndicator(Indicator):
    def __init__(self, H3, name='proximity', Table=None):
        super().__init__(H3, name, Table)

    def kde(self, name, target_classes, attr_name='LBCS', item_name='area', usage_name='usage',
            minimum_ratio_th=0.0, bandwidth_multiplier=None, normalization=True,
            required_cells=None, round_digits=3, Table_to_map=None, self_update=True):
        target_h3_cells = self.get_target_h3_cells(target_classes, attr_name, item_name, usage_name, minimum_ratio_th)
        sim_points = []
        for h3_cell in target_h3_cells:
            lat, lon = h3.h3_to_geo(h3_cell)
            sim_points.append([lon, lat])
        sim_points = np.asarray(sim_points).T
        kernel = stats.gaussian_kde(sim_points, 'scott')
        if bandwidth_multiplier is not None:
            kernel.set_bandwidth(bw_method=kernel.factor * bandwidth_multiplier)
        kde_rst = {}
        if not required_cells:
            required_cells = self.H3.required_cells
        for h3_cell in required_cells:
            lat, lon = h3.h3_to_geo(h3_cell)
            kde_rst[h3_cell] = kernel([lon, lat])[0]
        if self_update:
            self.H3.values[name] = kde_rst
        if Table_to_map:
            kde_rst = Table_to_map.get_grid_value_from_h3_cells(self.H3.resolution, name, self_update)
        if normalization:
            normalized_rst = self.normalization(kde_rst, minV='auto', maxV='auto', better='high')
            to_frontend_rst = ' '.join([str(round(d, round_digits)) for d in normalized_rst])
        else:
            normalized_rst = None
            to_frontend_rst = ' '.join([str(round(d, round_digits)) for d in kde_rst])
        return {'name': name,
                'raw': kde_rst,
                'normalized': normalized_rst,
                'to_frontend': to_frontend_rst}

    def closeness(self, name, target_classes, attr_name='LBCS', item_name='area', usage_name='usage',
                  minimum_ratio_th=0.0, power=1.0, nearest_k=None, normalization=True,
                  required_cells=None,  round_digits=3, Table_to_map=None, self_update=True):
        target_h3_cells = self.get_target_h3_cells(target_classes, attr_name, item_name, usage_name, minimum_ratio_th)
        closeness_rst = {}
        if not required_cells:
            required_cells = self.H3.required_cells
        for start_h3_cell in required_cells:
            dist_list = self._get_straight_line_dist_to_h3_cells(start_h3_cell, target_h3_cells)
            if nearest_k:
                dist_list.sort()
                dist_list = dist_list[:nearest_k]
            if len(dist_list) == 0:
                closeness_rst[start_h3_cell] = 0
            else:
                closeness_rst[start_h3_cell] = sum([1/(d**power) for d in dist_list]) / len(dist_list)
        if self_update:
            self.H3.values[name] = closeness_rst
        if Table_to_map:
            closeness_rst = Table_to_map.get_grid_value_from_h3_cells(self.H3.resolution, name, self_update)
        if normalization:
            normalized_rst = self.normalization(closeness_rst, minV='auto', maxV='auto', better='high')
            to_frontend_rst = ' '.join([str(round(d, round_digits)) for d in normalized_rst])
        else:
            normalized_rst = None
            to_frontend_rst = ' '.join([str(round(d, round_digits)) for d in closeness_rst])
        return {'name': name,
                'raw': closeness_rst,
                'normalized': normalized_rst,
                'to_frontend': to_frontend_rst}

    def nearest_dist(self, name, target_classes, attr_name='LBCS', item_name='area', usage_name='usage',
                     minimum_ratio_th=0.0, kth=1, dist_method='straight_line', normalization=True,
                     required_cells=None, round_digits=3, Table_to_map=None, self_update=True):
        target_h3_cells = self.get_target_h3_cells(target_classes, attr_name, item_name, usage_name, minimum_ratio_th)
        nearest_dist_rst = {}
        if not required_cells:
            required_cells = self.H3.required_cells
        for start_h3_cell in required_cells:
            if dist_method == 'straight_line':
                dist_list = self._get_straight_line_dist_to_h3_cells(start_h3_cell, target_h3_cells)
            elif dist_method == 'network':
                dist_list = self._get_network_dist_to_h3_cells(start_h3_cell, target_h3_cells)
            dist_list.sort()
            if len(dist_list) == 0:
                nearest_dist_rst[start_h3_cell] = -1
            else:
                nearest_dist_rst[start_h3_cell] = dist_list[kth-1]
        if self_update:
            self.H3.values[name] = nearest_dist_rst
        if Table_to_map:
            nearest_dist_rst = Table_to_map.get_grid_value_from_h3_cells(self.H3.resolution, name, self_update)
        if normalization:
            normalized_rst = self.normalization(nearest_dist_rst, minV='auto', maxV='auto', better='high')
            to_frontend_rst = ' '.join([str(round(d, round_digits)) for d in normalized_rst])
        else:
            normalized_rst = None
            to_frontend_rst = ' '.join([str(round(d, round_digits)) for d in nearest_dist_rst])
        return {'name': name,
                'raw': nearest_dist_rst,
                'normalized': normalized_rst,
                'to_frontend': to_frontend_rst}

    def return_accessibility_within_dist(self, name, population_attr,
                                         target_classes, attr_name='LBCS', item_name='area', usage_name='usage',
                                         minimum_ratio_th=0.0, kth=1,
                                         dist_threshold=500.0, dist_unit='m', speed=3.6,
                                         dist_method='straight_line'):
        required_cells = [
            h3_cell for h3_cell, h3_attrs in self.H3.h3_stats.items()
            if h3_attrs.get(population_attr, -1) > 0
        ]
        nearest_dist_rst = self.nearest_dist(name, target_classes, attr_name, item_name, usage_name,
                                             minimum_ratio_th, kth, dist_method,
                                             required_cells=required_cells, Table_to_map=None,
                                             normalization=False, self_update=False)['raw']
        if dist_unit != 'km':
            nearest_dist_rst = {
                h3_cell: dist_unit_converter(raw_value, 'km', return_unit=dist_unit, speed=speed)
                for h3_cell, raw_value in nearest_dist_rst.items()
            }
        tt_pop, accessibile_pop = 0, 0
        for h3_cell in required_cells:
            this_pop = self.H3.h3_stats[h3_cell][population_attr]
            tt_pop += this_pop
            if nearest_dist_rst[h3_cell] <= dist_threshold:
                accessibile_pop += this_pop
        rst = {
            'name': name,
            'raw': accessibile_pop,
            'normalized': accessibile_pop/tt_pop,
            'to_frontend': accessibile_pop/tt_pop
        }
        return rst


def test(num_trials=3):
    import pickle, time
    import matplotlib.pyplot as plt

    vars = pickle.load(open('cities/shenzhen/clean/base_data.p', 'rb'))
    Table, H3 = vars['Table'], vars['H3']

    P = ProximityIndicator(H3, Table=Table)

    for trial in range(num_trials):
        print(f'\n\nTrial {trial + 1}\n' + '==' * 30)
        layout_str, layout_ratio = Table.update_randomly(zone=1)
        t0 = time.time()
        park_proximity = P.return_accessibility_within_dist('park_proximity',
                                                            population_attr='tt_pop',
                                                            target_classes=5500,
                                                            kth=1,
                                                            dist_threshold=500 / 1.5)
        t1 = time.time()
        print('{:4.4} seconds elapsed for computing a proximity indicator'.format(t1-t0))
        print(park_proximity)

        park_proximity_heatmap = P.closeness('park_proximity_heatmap',
                                             target_classes=5500,
                                             minimum_ratio_th=0.25,
                                             power=0.75)
        t2 = time.time()
        print('{:4.4} seconds elapsed for computing a proximity heatmap'.format(t2-t1))
        P.verify_heatmap(Table, name='park_proximity_heatmap',
                         target_classes=5500,
                         minimum_ratio_th=0.25,
                         focus_table_grid_code=38)
        plt.show()


if __name__ == '__main__':
    test(num_trials=3)