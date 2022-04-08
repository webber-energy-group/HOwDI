"""
Creates plot from outputs of model
Author: Braden Pecora

In the current version, there are next to no features,
but the metadata should be fairly easy to access and utilize.
"""
import geocoder
import geopandas as gpd
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import json

## for development 
# data = json.load(open('base/outputs/outputs.json'))
# path='data/base/'

def main(data, path='data/base/',us_county_shp_file='data/US_COUNTY_SHPFILE/US_county_cont.shp'):
    
    # it seems that geopandas has a built in geocoder, but this was the first thing that worked
    # maybe its worth changing eventually...
    locations = {node: geocoder.arcgis(node + ' Texas').latlng for node in data.keys()} # takes ~ 30 seconds
    for _, latlong in locations.items():
        latlong.reverse() # is in opposite order of how geopandas will interpret 
    
    # clean data
    def get_relevant_dist_data(nodal_data):
        outgoing_dicts = nodal_data['distribution']['outgoing']
        relevant_keys = ['source_class','destination','destination_class']
        for _, outgoing_dict in outgoing_dicts.items():
            for key in list(outgoing_dict.keys()):
                if key not in relevant_keys:
                    del outgoing_dict[key]
        return [outgoing_dict for _, outgoing_dict in outgoing_dicts.items()]
    dist_data = {node: get_relevant_dist_data(nodal_data) for node, nodal_data in data.items() if nodal_data['distribution'] != {"local": {},"outgoing": {},"incoming": {} }}

    def get_relevant_prod_data(nodal_data):
        if nodal_data['production'] != {}:
            return tuple(nodal_data['production'].keys())
        else:
            return None
    prod_data = {node: get_relevant_prod_data(nodal_data) for node, nodal_data in data.items()} 

    features = []
    for node, nodal_connections in dist_data.items():
        node_latlng = locations[node]
        node_geodata = {
            'type' : 'Feature',
            'geometry' : {
                'type' : 'Point',
                'coordinates' : node_latlng
            },
            'properties' : {
                'name' : node,
                'production' : prod_data[node] # potential to lose data if 'island' that produces but not distributes
            }
        }
        features.append(node_geodata)

        for nodal_connection in nodal_connections:

            dest = nodal_connection['destination']
            dist_type = nodal_connection['source_class']
            dest_latlng = locations[dest]

            line_geodata = {
                'type' : 'Feature',
                'geometry' : {
                    'type': 'LineString',
                    'coordinates': [node_latlng, dest_latlng]
                },
                'properties' : {
                    'name': node + ' to ' + dest,
                    'dist_type': dist_type
                }
            }
            features.append(line_geodata)

    geo_data = {'type': 'FeatureCollection', 'features' : features}
    distribution = gpd.GeoDataFrame.from_features(geo_data)

    # get Texas plot
    us_county = gpd.read_file(us_county_shp_file)
    # us_county = gpd.read_file('US_COUNTY_SHPFILE/US_county_cont.shp')
    tx_county = us_county[us_county['STATE_NAME'] == 'Texas']
    tx = tx_county.dissolve()

    nodes = distribution[distribution.type == 'Point']
    connections = distribution[distribution.type == 'LineString']

    # plot
    fig, ax = plt.subplots(figsize=(10,10),dpi=1000)

    node_color = {
        'default' : '#219ebc',
        'smr': 'black',
        'smrExisting': 'grey',
        'smr+smrExisting': 'lightgrey', #tried for like an hour to get multiple colors in one marker instead of this
        'electrolyzer': 'blue'
    }
    dist_pipelineLowPurity_col = '#9b2226'
    dist_truckLiquefied_color = '#fb8500'
    dist_truckCompressed_color = '#bb3e03'

    tx.plot(ax=ax,color='white',edgecolor='black')

    nodes.plot(ax=ax, color = node_color['default'], zorder=5)
    nodes[nodes['production'] == tuple(['smr'])].plot(ax=ax, color=node_color['smr'],zorder=5)
    nodes[nodes['production'] == tuple(['smrExisting'])].plot(ax=ax, color=node_color['smrExisting'],zorder=5)
    nodes[nodes['production'] == tuple(['smr','smrExisting'])].plot(ax=ax, color=node_color['smr+smrExisting'],zorder=5)
    nodes[nodes['production'] == tuple(['electrolyzer'])].plot(ax=ax, color=node_color['electrolyzer'],zorder=5)
    # nodes[nodes['production'] == None].plot(ax=ax, color = ?)
    #TODO add different shape for producer vs consumer vs both

    connections[connections['dist_type'] == 'dist_pipelineLowPurity'].plot(ax=ax, color = dist_pipelineLowPurity_col, zorder=1)
    connections[connections['dist_type'] == 'dist_truckLiquefied'].plot(ax=ax, color = dist_truckLiquefied_color, zorder=1)
    connections[connections['dist_type'] == 'dist_truckCompressed'].plot(ax=ax, color = dist_truckCompressed_color, legend=True, zorder=1)

    #TODO Add other legend elements to legend
    legend_elements = [Line2D([0], [0], color=dist_pipelineLowPurity_col, lw=2, label='Gas Pipeline'), 
                       Line2D([0], [0], color=dist_truckLiquefied_color, lw=2, label='Liquid Truck Route'), 
                       Line2D([0], [0], color=dist_truckCompressed_color, lw=2, label='Gas Truck Route'),
                    #    Line2D([0], [0], marker='o', color=node_color, label='Node', markerfacecolor=node_color, markersize=5, lw=0)
                       ]

    ax.legend(handles=legend_elements, loc='upper left')


    fig.savefig(path + 'outputs/fig.png')

if __name__ == '__main__':
    from json import load
    data = load(open('base/outputs/outputs.json'))
    path = ''
    main(data, path)