import os, json, subprocess, time, sys, jenkspy
sys.path.append('../utils')
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objs as go
import dash
import dash_core_components as dcc
import dash_html_components as html
from dash.dependencies import Input, Output, State, ALL
from pyproj import Transformer
from convert_coords import convert_coords_from_crs_to_crs, crs_header_4326, crs_header_4547
from PIL import Image
from contextlib import suppress

from kde import get_kde
from closeness import get_closeness
from nearest_dist import get_nearest_distance
from simple_count import get_simple_count
from utils import num2str

import flask
from flask import Flask



def make_df(geojson, attr_name):
    if type(geojson) == dict:
        geojson_data = geojson
    else:
        geojson_data = json.load(open(geojson))
    features = geojson_data['features']
    # if 'id' not in features[0]:
        # for idx, feature in enumerate(features):
            # feature['id'] = idx
        # geojson_data['features'] = features
        # json.dump(geojson_data, open(geojson, 'w'), indent=4)
    df = pd.DataFrame([
        {
            'id': feature['id'],
            attr_name: feature['properties'][attr_name]
        } for feature in features
    ])
    return df
    

def expose_local_src(viz_folder):
    server = Flask(__name__, static_url_path='')
    STATIC_PATH = os.path.dirname(os.path.abspath(__file__))
    
    @server.route(f'/{viz_folder}/images/<src>')
    def serve_static_img(src):
        return flask.send_from_directory(STATIC_PATH, f'{viz_folder}/images/{src}', as_attachment=True)
        
    @server.after_request
    def add_header(response):
        response.cache_control.max_age = 1
        return response
        
    return server
    

def hack_on_img(img_path, rot=-10.53, width_scale=1.3198, height_scale=1.3198*0.9934, crop=True):
    im = Image.open(img_path)
    im = im.rotate(rot)
    width, height = im.size
    new_size = (int(np.round(width*width_scale)), int(np.round(height*height_scale)))
    im = im.resize(new_size)
    if crop:
        im = im.crop(im.getbbox())
    im.save(img_path)
    

def get_discrete_color(candidate_list, num):
    if len(candidate_list) == num:
        return candidate_list
    elif len(candidate_list) > num:
        idx_list = [int(np.round(x)) for x in np.linspace(0,len(candidate_list)-1,num)]
        return [candidate_list[idx] for idx in idx_list]


def do_viz_on_dash(poi_folder, kpi_folder, viz_folder, flask_server=True, colors_scale='RdYlGn', image_format='png'):

    grid1_4326_coords = {feature['id']: feature['geometry']['coordinates'] for feature in 
        json.load(open('../data/jw_grid/grid1_4326.geojson', 'r'))['features']}
    grid2_4326_coords = {feature['id']: feature['geometry']['coordinates'] for feature in 
        json.load(open('../data/jw_grid/grid2_4326.geojson', 'r'))['features']}
    poi_list = [poi.split('.')[0][4:] for poi in os.listdir(poi_folder) if poi.startswith('poi')]
    kpi_list = [kpi.split('.')[0][4:] for kpi in os.listdir(kpi_folder) if kpi.startswith('kpi')]
    poi_list.sort()
    kpi_list.sort()
    
    app = dash.Dash(__name__, server=flask_server)
    app.title = "Shenzhen CityScope Proximity Heatmap"
    app.layout = html.Div([
        html.H1('Shenzhen CityScope Proximity Heatmap', style={'margin': '0.5em'}),
        
        html.Div([  # POI selector
            html.P('Please select a type of POI:'),
            dcc.Dropdown(
                id = 'poi_dropdown',
                options = [{'label': poi, 'value': poi} for poi in poi_list],
                # value = 'covenince_stores',
                value = poi_list[0],
                clearable=False
            )
        ], style={'width': '45%', 'display': 'inline-block', 'margin': '0.5em', 'verticalAlign': 'top'}),
        
        html.Div([  # KPI selector
            html.P('Or, please select a type of KPI:'),
            dcc.Dropdown(
                id = 'kpi_dropdown',
                options = [{'label': kpi, 'value': kpi} for kpi in kpi_list],
                value = kpi_list[0],
                clearable=False
            )
        ], style={'width': '45%', 'display': 'inline-block', 'margin': '0.5em', 'verticalAlign': 'top'}),
        
        html.Div([  # method selector
            html.P('Please select a type of method:'),
            dcc.Dropdown(
                id = 'method_dropdown',
                options = [
                    {'label': 'Nearest Distance', 'value': 'nearest_distance'},
                    {'label': 'Closeness', 'value': 'closeness'},
                    {'label': 'Simple Count', 'value': 'simple_count'},
                    {'label': 'Kernel Density', 'value': 'kernel_density'},
                ],
                value = 'kernel_density',
                clearable=False
            )
        ], style={'width': '45%', 'display': 'inline-block', 'margin': '0.5em', 'verticalAlign': 'top'}),
        
        html.Div([  # parameters for different methods, might be hidden
            html.Div([  # parameter of kde
                    html.P(''),
                    html.P('Please input the bandwidth parameter:'),
                    dcc.Input(id='kde_bwm_input',value=0.1, min=0.000001, type='number')
                ], id = 'kde_hidden_div', style = {'display': 'block'}
            ),
            html.Div(  # parameter of closeness
                [
                    html.P(''),
                    html.P('If only consider POIs within certain distance, please input this maximum distance (unit: meter) below (-1 = no restrictions):'),
                    dcc.Input(id='closeness_mcd_input',value=-1, min=-1, type='number'),
                    html.P('If only consider the nearest N POIs, please input N below (-1 = no restrictions): '),
                    dcc.Input(id='closeness_nn_input', value=-1, min=-1, type='number')
                ], 
                id = 'closeness_hidden_div',
                style = {'display': 'none'}
            ),
        ], style={'width': '45%', 'display': 'inline-block', 'margin': '0.5em', 'verticalAlign': 'top'}),
        
        html.Div([
            html.Span('Please select the grid:  '),
            html.Span(
                dcc.RadioItems(
                    id = 'grid_selector',
                    options = [
                        {'label': 'Interactive Grids + Status Quo', 'value': 'grid2'}, 
                        {'label': 'All Grids', 'value': 'grid1'}
                    ],
                    value = 'grid2'
                ), style = {'display': 'inline-block'})
        ], style={'width': '45%', 'display': 'inline-block', 'margin': '0.5em', 'verticalAlign': 'top'}),
        
        
        html.Div([
            html.P('Please select the color scale:  '),
            html.P(
                dcc.Dropdown(
                    id = 'color_scale_selector',
                    options = [
                        {'label': 'Continuous: Raw', 'value': 'raw'}, 
                        {'label': 'Continuous: Ln', 'value': 'ln'},
                        {'label': 'Continuous: Log10', 'value': 'log10'},
                        {'label': 'Categorical: Natural Breaks', 'value': 'cat_nb'},
                        {'label': 'Categorical: Percentile', 'value': 'cat_per'},
                        {'label': 'Categorical: Manual', 'value': 'cat_ud'}
                    ],
                    value = 'raw', clearable=False
                ))
        ], style={'width': '20%', 'display': 'inline-block', 'margin': '0.5em', 'verticalAlign': 'top'}),
        
        html.Div([
            html.Div([
                html.P('Please input the number of categories:  '),
                dcc.Input(id='num_cat_nb', value=5, min=3, max=10, type='number')
            ], id = 'cat_nb_hidden_div', style = {'display': 'none'}),
            
            html.Div([
                html.P('List of cutoff values (comma seperated): '),
                dcc.Input(id='list_cutoff_cat_ud', value='1, 2, 3', type='text')
            ], id = 'cat_ud_hidden_div', style = {'display': 'none'}), 
            
            html.Div([
                html.P('Min value for winsorization (optional): '),
                dcc.Input(id='min_win', value='', type='text'),
                html.P('Max value for winsorization (optional): '),
                dcc.Input(id='max_win', value='', type='text')
            ], id = 'continuous_hidden_div', style = {'display': 'block'})
            
        ], style={'width': '20%', 'display': 'inline-block', 'margin': '0.5em', 'verticalAlign': 'top'}),
        
        html.Div([
            html.Button('OK for POIs', id='ok_button_poi', n_clicks=0,
                style={'width': '10%', 'padding':'10px', 'marginRight':'10px'}),
            html.Button('OK for KPIs', id='ok_button_kpi', n_clicks=0,
                style={'width': '10%', 'padding':'10px', 'marginLeft':'10px'}),
        ], style={'margin': '0.5em'}),
        
        html.Div(id='store_container', children=[]),
        html.Div(id='jpg_download', style={'display': 'none'}),
        html.Div(id='colorscale_info', style={'display': 'none'}),
        html.Div(id='output_fig')
    ])
    
    @app.callback(
        [Output('kde_hidden_div', 'style'),
         Output('closeness_hidden_div', 'style')], 
        [Input('method_dropdown', 'value')])
    def show_hidden_method_params(method):
        if method == 'kernel_density':
            return {'display': 'block'}, {'display': 'none'}
        elif method == 'closeness':
            return {'display': 'none'}, {'display': 'block'}
        else:
            return {'display': 'none'}, {'display': 'none'}
            
    
    @app.callback(
        [Output('cat_nb_hidden_div', 'style'),
         Output('cat_ud_hidden_div', 'style'),
         Output('continuous_hidden_div', 'style')],
        [Input('color_scale_selector', 'value')]
    )
    def show_hidden_colorscale_params(method):
        if method in ['raw', 'ln', 'log10']:
            return {'display': 'none'}, {'display': 'none'},  {'display': 'block'}
        elif method in ['cat_nb', 'cat_per']:
            return {'display': 'block'}, {'display': 'none'},  {'display': 'none'}
        elif method == 'cat_ud':
            return {'display': 'none'}, {'display': 'block'},  {'display': 'none'}
            
    
    @app.callback(
        # Output('choropleth', 'figure'),
        [Output('output_fig', 'children'),
         Output('store_container', 'children')],
        [Input('ok_button_poi', 'n_clicks'),
         Input('ok_button_kpi', 'n_clicks')],
        state = [
            State('poi_dropdown', 'value'),
            State('kpi_dropdown', 'value'),
            State('method_dropdown', 'value'),
            State('kde_bwm_input', 'value'),
            State('closeness_nn_input', 'value'),
            State('closeness_mcd_input', 'value'),
            State('grid_selector', 'value'),
            State('color_scale_selector', 'value'),
            State('num_cat_nb', 'value'),
            State('list_cutoff_cat_ud', 'value'),
            State('min_win', 'value'),
            State('max_win', 'value'),
            State('store_container', 'children')
        ])
    # @profile
    def do_viz_on_dash_call_back(n_clicks_poi, n_clicks_kpi, poi_name, kpi_name, 
        method, kde_bwm, closeness_nn, closeness_mcd, grid_name, 
        cs_type, cs_num_of_cat, cs_list_of_cutoff, cs_min, cs_max,
        store_container):
        
        use_colors_scale = colors_scale
        
        ctx = dash.callback_context
        if not ctx.triggered:
            trigger_id = 'startup'   # no trigger, acutally the first time when app is loaded
        else:
            trigger_id = ctx.triggered[0]['prop_id'].split('.')[0]
        if trigger_id == 'ok_button_poi':
            geojson_fpath = f'{viz_folder}/geojson/{poi_name}_{method}_{grid_name}.geojson'
            img_fpath = f'{viz_folder}/images/{poi_name}_{method}_{grid_name}.{image_format}'
            target_folder = poi_folder
            target_file_name = f'poi_{poi_name}'
        elif trigger_id == 'ok_button_kpi':
            geojson_fpath = f'{viz_folder}/geojson/{kpi_name}_{method}_{grid_name}.geojson'
            img_fpath = f'{viz_folder}/images/{kpi_name}_{method}_{grid_name}.{image_format}'
            target_folder = kpi_folder
            target_file_name = f'kpi_{kpi_name}'
        else:  
            return None, []

        # running analysis
        # IMPT: the overhead of subprocess to inital another process is unbearable !
        print('\nStart new task...')
        t0 = time.time()
        grid_file_path = f'../data/jw_grid/{grid_name}_4547.geojson'
        if method == 'kernel_density':
            # cmd = f'python kde.py -tfn {target_file_name} -sp {geojson_fpath} -bwm {kde_bwm}'
            bandwidth_multiplier = kde_bwm
            geojson = get_kde(grid_file_path, [target_file_name], target_folder, save_path=geojson_fpath, 
                save_flag=False, bandwidth_multiplier=bandwidth_multiplier)
            attr_name = f'kde_of_{target_file_name}'
        elif method == 'nearest_distance':
            # cmd = f'python nearest_dist.py -tfn {target_file_name} -sp {geojson_fpath}'
            geojson = get_nearest_distance(grid_file_path, [target_file_name], 
                target_folder, save_path=geojson_fpath, save_flag=False)
            attr_name = f'dist_to_{target_file_name}'
            # if cs_type in ['raw', 'ln', 'log10']:
            use_colors_scale = use_colors_scale + '_r'
        elif method == 'closeness':
            # cmd = f'python closeness.py -tfn {target_file_name} -sp {geojson_fpath}'
            # if closeness_nn > 0:
                # cmd += f' -nn {closeness_nn}'
            # if closeness_mcd >= 0: 
                # cmd += f' -mcd {closeness_mcd}'
            if closeness_nn <= 0: closeness_nn = None
            if closeness_mcd < 0: closeness_mcd = None
            geojson = get_closeness(grid_file_path, [target_file_name], target_folder, save_path=geojson_fpath, 
                nearest_n=closeness_nn, max_considering_dist=closeness_mcd, save_flag=False)
            attr_name = f'closeness_to_{target_file_name}'
        elif method == 'simple_count':
            geojson = get_simple_count(grid_file_path, [target_file_name], target_folder, 
                save_path=geojson_fpath, save_flag=False)
            attr_name = f'count_of_{target_file_name}'
        # cmd += f' -gfp ../data/jw_grid/{grid_name}_4547.geojson'  # set grid
        # cmd += ' -tfd ../tmp/emap_poi_epsg4547_confined'   # set poi folder
        t1 = time.time()
        print('viz starts subprocess at: ', time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time())))
        # subprocess.call(cmd, shell=True)
        
        # while not os.path.exists(geojson_fpath):
            # time.sleep(0.1)
        # print('viz pass kde.py at: ', time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time())))
        df = make_df(geojson, attr_name)
        # geojson = json.load(open(geojson_fpath))
        if geojson['crs'] == crs_header_4547:
            if grid_name == 'grid2':
                grid_4326_coords = grid2_4326_coords
            elif grid_name == 'grid1':
                grid_4326_coords = grid1_4326_coords
            for feature in geojson['features']:
                feature['geometry']['coordinates'] = grid_4326_coords[feature['id']]
            # geojson = convert_coords_from_crs_to_crs(geojson, 4547, 4326, crs_header=crs_header_4326)
        
        # change colo scale
        if cs_type == 'raw':
            pass
        elif cs_type == 'ln':
            df[attr_name] = np.ma.log(np.array(df[attr_name])).filled(0)
        elif cs_type == 'log10':
            df[attr_name] = np.ma.log10(np.array(df[attr_name])).filled(0)
            
        min_value, max_value = num2str(df[attr_name].min()), num2str(df[attr_name].max())
            
        if cs_type in ['raw', 'ln', 'log10']:   
            # use continous color scale
            use_min_winsor, use_max_winsor = None, None
            with suppress(ValueError): use_min_winsor = float(cs_min)
            with suppress(ValueError): use_max_winsor = float(cs_max)
            if (use_min_winsor is not None) and (use_max_winsor is not None) and use_min_winsor > use_max_winsor: 
                use_min_winsor, use_max_winsor = use_max_winsor, use_min_winsor
            df[attr_name] = df[attr_name].clip(use_min_winsor, use_max_winsor)
            fig = px.choropleth(df, locations='id', geojson=geojson, 
                color=attr_name, color_continuous_scale=use_colors_scale)
            cutff_str = 'None'
        else:
            # use discrete color scale
            if cs_type == 'cat_nb':
                breaks = jenkspy.jenks_breaks(np.asarray(df[attr_name]), nb_class=cs_num_of_cat)
            elif cs_type == 'cat_per':
                breaks = np.percentile(np.asarray(df[attr_name]), np.linspace(0,100, cs_num_of_cat+1)).tolist()
                # breaks = [df[attr_name].min()-1] + breaks + [df[attr_name].max()+10]
                breaks = list(set(breaks))
                breaks.sort()
            elif cs_type == 'cat_ud':
                breaks = [float(x.strip()) for x in cs_list_of_cutoff.split(',')]
                breaks.sort()
                if breaks[0] > df[attr_name].min(): breaks = [df[attr_name].min()] + breaks
                if breaks[-1] < df[attr_name].max(): breaks.append(df[attr_name].max())
            cutff_str = ', '.join([num2str(x) for x in breaks[1:-1]])
            num_cat = len(breaks)-1
            cat_labels = [f'{num2str(breaks[idx])} - {num2str(breaks[idx+1])}' for idx in range(num_cat)]
            discrete_color_scale = get_discrete_color(
                eval(f'px.colors.diverging.{use_colors_scale}'), num_cat
            )
            color_discrete_map = {k:v for k, v in zip(cat_labels, discrete_color_scale)}
            df[attr_name] = pd.cut(df[attr_name], bins=breaks, include_lowest=True, 
                duplicates='drop', labels=cat_labels)
            fig = px.choropleth(df, locations='id', geojson=geojson, color=attr_name, 
                # color_discrete_map=color_discrete_map
                color_discrete_sequence=discrete_color_scale,
                category_orders={attr_name: cat_labels},
            )
        fig.update_geos(fitbounds='locations', visible=False, projection_type='mercator')
        fig.update_traces(marker_line_width=0)
        fig.update_layout(margin={"r":0,"t":0,"l":0,"b":0}, 
            coloraxis_showscale=False, showlegend=False,
            plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)',
            geo=dict(bgcolor= 'rgba(0,0,0,0)'),
            width=3480, height=3480, autosize=True)
        t2 = time.time()
        fig.write_image(img_fpath, width=3480, height=3480)
        hack_on_img(img_fpath)
       
        # insert a new dcc.Store() object (and delete previous ones) to trigger img_url to show 
        if len(store_container) == 0:
            store_id = 0
        else:
            store_id = store_container[0]['props']['id']['index'] + 1
        color_scale_info_prompt = f'min={min_value}, max={max_value}, cutoff={cutff_str}'
        store_container = [dcc.Store(id={'type': 'new_figure', 'index': store_id}, data=color_scale_info_prompt)]
        fig.update_layout(width=1400, height=500, autosize=True,
            coloraxis_showscale=True, showlegend=True)
        fig.update_geos(projection_type='transverse mercator')
        print('\nTask finished...')
        t3 = time.time()
        # print('Run analysis costs {:4.4f} seconds, generating map costs {:4.4f} seconds, save image costs {:4.4f}'.format(
            # t1-t0, t2-t1, t3-t2))
        return dcc.Graph(figure=fig), store_container  
    
    @app.callback(
        [Output('jpg_download', 'children'),
         Output('jpg_download', 'style'),
         Output('colorscale_info', 'children'),
         Output('colorscale_info', 'style')],
        [Input('ok_button_poi', 'n_clicks'),
         Input('ok_button_kpi', 'n_clicks'),
         Input('poi_dropdown', 'value'),
         Input('kpi_dropdown', 'value'),
         Input('method_dropdown', 'value'),
         Input('grid_selector', 'value'),
         Input({'type': 'new_figure', 'index': ALL}, 'data')],
         [State('jpg_download', 'children')]
     )
    def update_image_download_link(n_clicks_poi, n_clicks_kpi, poi_name, kpi_name, method, grid_name, 
        new_img_color_scale_info, jpg_download_A):
        """
        Wish: button triggers graph, and button or graph triggers url update, 
            url will finally visible after graph finished, which takes some time to go.
        Difficulty: since Dash does not allow a single ouput to be updated by multiple callbacks, 
            we have to put all of updating things here. Besides,if A->B , A|B->C, 
            C will not be triggered unless B has been finished, which makes A->B->C (C triggered once) 
            instead of A->C and then B->C (C triggered twice). The only exception for the latter (C triggered twice) 
            is that B should be some kind of newly inserted component rather than updating an existed component 
        Solution: dynamicly insert something light (dcc.Store()) with changing index
        """
        ctx = dash.callback_context
        if not ctx.triggered:
            trigger_id = 'startup'   # no trigger, acutally the first time when app is loaded
        else:
            trigger_id = ctx.triggered[0]['prop_id'].split('.')[0]
        if trigger_id not in ['ok_button_poi', 'ok_button_kpi'] and 'index' not in trigger_id:
            return html.A("Nothing to download now"), {'display': 'none'}, '', {'display': 'none'}
        elif 'index' not in trigger_id:
            if trigger_id == 'ok_button_poi':
                image_fpath = f'{viz_folder}/images/{poi_name}_{method}_{grid_name}.{image_format}'
            elif trigger_id == 'ok_button_kpi':
                image_fpath = f'{viz_folder}/images/{kpi_name}_{method}_{grid_name}.{image_format}'
            # while not os.path.exists(image_fpath):
                # time.sleep(0.1)
            return html.A("Please click here to download image.", href=f"/{image_fpath}"), {'display': 'none'}, new_img_color_scale_info, {'display': 'none'}
        else:
            return jpg_download_A, {'display': 'block'}, new_img_color_scale_info, {'display': 'block'}
            
    app.run_server(host='0.0.0.0', debug=True, port=8051)
  
  
def main():
    poi_folder = '../tmp/emap_poi_epsg4547_confined'
    kpi_folder = '../tmp/kpi_epsg4547_confined'
    viz_folder = 'viz_files'
    image_format = 'png'
    
    for folder in [os.path.join(viz_folder, 'geojson'), os.path.join(viz_folder, 'images')]:
        if not os.path.exists(os.path.abspath(folder)):
            os.makedirs(os.path.abspath(folder))
            
    # run flask server
    server = expose_local_src(viz_folder)
    
    do_viz_on_dash(poi_folder, kpi_folder, viz_folder, server, image_format=image_format)


if __name__ == '__main__':
    main()