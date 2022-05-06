import os, random, importlib, time, copy, pickle
from functools import partial

from geodata_toolbox import *
from grids_toolbox import TableGrids, H3Grids
from proximity_indicator import ProximityIndicator
from diversity_indicator import DiversityIndicator
from density_indicator import DensityIndicator
from building_indicator import BuildingEnergyIndicator
from population_toolbox import Population, Person
from indicator_toolbox import Handler

resolution = 11
table = 'shenzhen'


precooked_fpath = f'cities/{table}/clean/precooked_data.p'
precooked_existence = False
if os.path.exists(precooked_fpath):
    precooked_data = pickle.load(open(precooked_fpath, 'rb'))
    precooked_existence = True
    Buildings = precooked_data['Buildings']
    T = precooked_data['Table']
    H3 = precooked_data['H3']
    network = precooked_data['network']
    print(f"\nPrecooked data loaded: {', '.join(list(precooked_data.keys()))}\n")
else:
    # load geodata
    POIs = PointGeoData(name='pois',
                        src_geojson_path='0323/poi_outside_final.geojson')
    POIs.make_h3_stats(resolution=resolution, agg_attrs={
        'usage': 'decompose'
    })

    Buildings = PolygonGeoData(name='buildings',
                               src_geojson_path='0323/building_final.geojson')
    Buildings.make_h3_stats(resolution, agg_attrs={
        'usage': 'decompose'
    })

    LU = PolygonGeoData(name='landuse',
                        src_geojson_path='0323/land_final.geojson')
    LU.make_h3_stats(resolution, agg_attrs={
        'usage': 'decompose'
    })
    print('Data loaded\n')

    # load population
    population = Population(base_sim_pop_geojson_path='base_pop.geojson',
                            base_floating_pop_json_path=None,
                            table='shenzhen',
                            resolution=resolution)
    population.set_base_sim_population()
    print('Population loaded\n')


    # load network
    network = pickle.load(open('cities/shenzhen/clean/sim_network.p', 'rb'))

    # initialize H3 and Table grids
    H3 = H3Grids(resolution, Pop=population)
    pop_stats = {k:{'tt_pop':v} for k,v in population.h3_count_sim_pop['home'][resolution].items()}
    h3_stats = H3.combine_h3_stats([Buildings.h3_stats[resolution],
                                    POIs.h3_stats[resolution],
                                    LU.h3_stats[resolution],
                                    pop_stats])
    H3.set_current_h3_stats_as_base()
    H3.Housing.set_housing_type_def('housing_type_def.json')
    H3.Housing.set_base_housing_units_from_buildings(Buildings)

    T = TableGrids('table', resolution, H3=H3,
                   src_geojson_path='grid1_4326.geojson',
                   table='shenzhen',
                   proj_crs=4546)
    print('H3 and Table grids created\n')
# create Handler
H = Handler(udp_receiver_table_ip='0.0.0.0',
            udp_receiver_table_port=15800,
            udp_receiver_tablet_ip='0.0.0.0',
            udp_receiver_tablet_port=15900,
            udp_sender_ip='127.0.0.1',
            udp_sender_port=15801,
            mqtt_broker_ip='1.15.91.82',
            tablet_spec_json_path='tablet_spec.json')
H.add_table(T)
print('Handler created\n')


# create indicators and tasks
Prox = ProximityIndicator(H3, name='proximity_value', Table=T)
ProxHeatmap = ProximityIndicator(H3, name='proximity_heatmap', Table=T)
Diversity = DiversityIndicator(H3, Table=T)
Density = DensityIndicator(H3, Table=T)
BE = BuildingEnergyIndicator(H3, name='building_energy', Table=T)

# precooking
if 'base_commercial_building_energy' not in H3.precooked_rsts:
    rst = BE.predict_commercial_building_energy(input_data=Buildings.features[Buildings.crs['src']],
                                                input_dtype='buildings')
    H3.precooked_rsts['base_commercial_building_energy'] = rst
else:
    rst = H3.precooked_rsts['base_commercial_building_energy']
BE.set_base_energy(bldg_type='commercial', tt_energy=rst['BTU_pred'].sum(), tt_pop=rst['NWKER'].sum())

if 'base_residential_building_energy' not in H3.precooked_rsts:
    rst = BE.predict_residential_building_energy(housing_units='base')
    H3.precooked_rsts['base_residential_building_energy'] = rst
else:
    rst = H3.precooked_rsts['base_residential_building_energy']
BE.set_base_energy(bldg_type='residential', tt_energy=rst['BTU_pred'].sum(), tt_pop=rst['NHSLDMEM'].sum())

if not precooked_existence:
    # pyproj._transformer._Transformer is unpickable so remove it
    for obj in [POIs, Buildings, LU, T, H3, network, population,]:
        try:
            if hasattr(obj, 'transformer'):
                setattr(obj, 'transformer', {})
        except:
            pass
    precooked_data = {
        'POIs': POIs,
        'Buildings': Buildings,
        'LU': LU,
        'Table': T,
        'H3': H3,
        'network': network,
        'population': population
    }
    pickle.dump(precooked_data, open(precooked_fpath, 'wb'))


ProxHeatmap.set_scheduled_tasks(
    (
        [['heatmap_park_proximity'], ['heatmaps_all']],
        'ap: {}',
        partial(ProxHeatmap.closeness,
                name='heatmap_park_proximity',
                target_classes=5500,
                minimum_ratio_th=0.25,
                Table_to_map=T,
                power=0.75)
    ),
    (
        [['heatmap_third_place_proximity'], ['heatmaps_all']],
        'a3p: {}',
        partial(ProxHeatmap.closeness,
                name='heatmap_third_place_proximity',
                target_classes=[2100, 2200, 2300, 7240],
                minimum_ratio_th=0.25,
                Table_to_map=T,
                power=0.75)
    )
)

Prox.set_scheduled_tasks(
    (
        'screen_all',
        'r pap {}',
        partial(Prox.return_accessibility_within_dist,
                name='park_proximity',
                population_attr='tt_pop',
                target_classes=5500,
                kth=1,
                dist_threshold=500/1.5)
    ),
    (
        'screen_all',
        'r pa3p {}',
        partial(Prox.return_accessibility_within_dist,
                name='third_place_proximity',
                population_attr='tt_pop',
                target_classes=[2100, 2200, 2300, 7240],
                kth=1,
                dist_threshold=500/1.5)
    )
)

Diversity.set_scheduled_tasks(
    (
        'screen_all',
        'r di3p {}',
        partial(Diversity.return_lbcs_area_diversity,
                name='third_place_diversity',
                target_lbcs_codes='third_places')
    ),
    (
        'screen_all',
        'r dir {}',
        partial(Diversity.return_residential_diversity)
    ),
    (
        'screen_all',
        'r dij {}',
        partial(Diversity.return_job_diversity)
    ),
    (
        'screen_all',
        'r dirjr {}',
        partial(Diversity.return_residential_job_ratio)
    )
)

Density.set_scheduled_tasks(
    (
        'screen_all',
        'r deres {}',
        partial(Density.return_resident_density)
    ),
    (
        'screen_all',
        'r deem {}',
        partial(Density.return_job_density)
    ),
    (
        'screen_all',
        'r de3pd {}',
        partial(Density.return_lbcs_density,
                name='third_place_density',
                target_lbcs_codes='third_places')
    ),
    (
        'screen_all',
        'r pid {}',
        partial(Density.return_intersection_density,
                road_network=network)
    )
)

BE.set_scheduled_tasks(
    (
        'screen_all',
        'r ipbe {}',
        partial(BE.return_energy_pperson,
                name='building_energy')
    )
)

print('Indicators created\n')

H.add_indicators(ProxHeatmap, Prox, Diversity, Density, BE)
H.run()
