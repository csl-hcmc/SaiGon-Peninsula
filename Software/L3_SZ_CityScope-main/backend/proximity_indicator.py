import os
import h3.api.numpy_int as h3
import numpy as np
from scipy import stats
from geodata_toolbox import H3Grids
import matplotlib.pyplot as plt
from indicator_toolbox import Indicator, dist_unit_converter


class ProximityIndicator(Indicator):
    def __init__(self, H3, Table=None):
        super().__init__(H3, Table)

    def kde(self, name, target_attr, minimum_ratio_th=0, bandwidth_multiplier=None,
            required_cells=None, self_update=True):
        h3_cell_area = h3.hex_area(self.H3.resolution, 'm^2')
        sim_points = []
        for h3_cell, h3_attrs in self.H3.h3_stats.items():
            if h3_attrs.get(target_attr, -1) > minimum_ratio_th * h3_cell_area:
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
        return kde_rst

    def closeness(self, name, target_attr, minimum_ratio_th=0, power=1, nearest_k=None,
                  required_cells=None, self_update=True):
        h3_cell_area = h3.hex_area(self.H3.resolution, 'm^2')
        target_h3_cells = [
            h3_cell for h3_cell, h3_attrs in self.H3.h3_stats.items()
            if h3_attrs.get(target_attr, -1) > minimum_ratio_th * h3_cell_area
        ]
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
        return closeness_rst

    def nearest_dist(self, name, target_attr, minimum_ratio_th=0, kth=1, dist_method='straight_line',
                     required_cells=None, self_update=True):
        h3_cell_area = h3.hex_area(self.H3.resolution, 'm^2')
        target_h3_cells = [
            h3_cell for h3_cell, h3_attrs in self.H3.h3_stats.items()
            if h3_attrs.get(target_attr, -1) > minimum_ratio_th * h3_cell_area
        ]
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
        return nearest_dist_rst

    def return_accessibility_within_dist(self, name, population_attr,
                                         target_attr, minimum_ratio_th=0, kth=1,
                                         dist_threshold=500, dist_unit='m', speed=3.6,
                                         dist_method='straight_line'):
        required_cells = [
            h3_cell for h3_cell, h3_attrs in self.H3.h3_stats.items()
            if h3_attrs.get(population_attr, -1) > 0
        ]
        nearest_dist_rst = self.nearest_dist(name,target_attr, minimum_ratio_th, kth,
                                             dist_method, required_cells, self_update=False)
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
            'normalized': accessibile_pop/tt_pop
        }
        return rst


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




def main():
    pass

if __name__ == '__main__':
    main()