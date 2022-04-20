"""
Creates plot from outputs of model
Author: Braden Pecora

In the current version, there are next to no features,
but the metadata should be fairly easy to access and utilize.
"""
# import geocoder
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
    # locations = {node: geocoder.arcgis(node + ' Texas').latlng for node in data.keys()} # takes ~ 30 seconds
    # for _, latlong in locations.items():
    #     latlong.reverse() # is in opposite order of how geopandas will interpret 
    node_data = json.load(open('data/nodes/nodes.geojson'))['features']
    locations = {d['properties']['node']: d['geometry']['coordinates'] for d in node_data}

    
    # clean data
    def get_relevant_dist_data(nodal_data):
        # returns a list of dicts used in a dict comprehension with only the `relevant_keys`
        outgoing_dicts = nodal_data['distribution']['outgoing']
        relevant_keys = ['source_class','destination','destination_class']
        for _, outgoing_dict in outgoing_dicts.items():
            for key in list(outgoing_dict.keys()):
                if key not in relevant_keys:
                    del outgoing_dict[key]
        return [outgoing_dict for _, outgoing_dict in outgoing_dicts.items()]
    dist_data = {node: get_relevant_dist_data(nodal_data) for node, nodal_data in data.items() if nodal_data['distribution'] != {"local": {},"outgoing": {},"incoming": {} }}

    def get_relevant_p_or_c_data(nodal_data_p_or_c):
        # p_or_c = production or consumption
        # turns keys of nodal_data['production'] or nodal_data['consumption'] into a set,
        # used in the dictionary comprehensions below
        if nodal_data_p_or_c != {}:
            return set(nodal_data_p_or_c.keys())
        else:
            return None
    prod_data = {node: get_relevant_p_or_c_data(nodal_data['production']) for node, nodal_data in data.items()} 
    cons_data = {node: get_relevant_p_or_c_data(nodal_data['consumption']) for node, nodal_data in data.items()} 
    
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
                'production' : prod_data[node], # potential to lose data if 'island' that produces but not distributes
                'consumption' : cons_data[node],
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


    ########
    # Plot

    #initialize figure
    fig, ax = plt.subplots(figsize=(10,10),dpi=300)

    # get Texas plot
    us_county = gpd.read_file(us_county_shp_file)
    # us_county = gpd.read_file('US_COUNTY_SHPFILE/US_county_cont.shp')
    tx_county = us_county[us_county['STATE_NAME'] == 'Texas']
    tx = tx_county.dissolve()
    tx.plot(ax=ax,color='white',edgecolor='black')

    # Plot nodes
    nodes = distribution[distribution.type == 'Point']
    node_plot_tech = { # Options for Node by technology
        'default':
            {
                'name': 'No Production (Color)',
                'color':'#219ebc',
                'marker': '.',
                'set' : None,
                'b' : lambda df: df['production'].isnull()
            },
        'smr':
            {
                'name': 'New SMR (Color)',
                'color': 'red',
                'set': set(('smr',)),
                'b' : lambda df: df['production'] == set(('smr',))
            },
        'smrExisting':
            {
                'name': 'Existing SMR (Color)',
                'color': 'yellow',
                'set' : set(('smrExisting',)),
                'b' : lambda df: df['production'] == set(('smrExisting',))
            },
        'smr+smrExisting':
            {
                'name': 'New and Existing SMR (Color)',
                'color': 'orange',
                'set' : set(('smr','smrExisting')),
                'b' : lambda df: df['production'] == set(('smr','smrExisting'))
                # I want a better way to do this, but I could not find one
                # I tried to find a way to have the color split, but 
                # a) I could not get it to work, and 
                # b) it seems you can only split with two colors in matplotlib
                # ... seems like all the permutations will get hair fairly fast,
                # we should probably find a way to do this
            }
        # and so on... (ccs not implemented -> can't plot ccs, electrolysis since never built)
    }
    node_plot_type = { # Options for node by Production, Consumption, or both
        # 'none' :
        #     {
        #         'b' : lambda df: df['production'].isnull() & df['consumption'].isnull(),
        #         'marker' : '.',
        #     },
        'production' :
            {
                'name': 'Production (Shape)',
                'b' : lambda df: df['production'].notnull() & df['consumption'].isnull(),
                'marker' : '^',
            },
        'consumption' :
            {
                'name': 'Consumption (Shape)',
                'b' : lambda df: df['production'].isnull() & df['consumption'].notnull(),
                'marker' : 'v',
            },
        'both' :
            {
                'name': 'Production and Consumption (Shape)',
                'b' : lambda df: df['production'].notnull() & df['consumption'].notnull(),
                'marker' : 'D',
            },
    }
    # Plot nodes based on production/consumption (marker) options and production tech (color) options
    # in short, iterates over both of the above option dictionaries
    # the 'b' (boolean) key is a lambda function that returns the locations of where the nodes dataframe 
    #   matches the specifications. An iterable way of doing stuff like df[df['production'] == 'smr']
    [nodes[type_plot['b'](nodes) & tech_plot['b'](nodes)].plot(ax=ax, color=tech_plot['color'],marker=type_plot['marker'],zorder=5) for tech, tech_plot in node_plot_tech.items() for type_name, type_plot in node_plot_type.items()]


    # Plot connections: 
    connections = distribution[distribution.type == 'LineString']
    dist_pipelineLowPurity_col = '#9b2226'
    dist_truckLiquefied_color = '#fb8500'
    dist_truckCompressed_color = '#bb3e03'
    connections[connections['dist_type'] == 'dist_pipelineLowPurity'].plot(ax=ax, color = dist_pipelineLowPurity_col, zorder=1)
    connections[connections['dist_type'] == 'dist_truckLiquefied'].plot(ax=ax, color = dist_truckLiquefied_color, zorder=1)
    connections[connections['dist_type'] == 'dist_truckCompressed'].plot(ax=ax, color = dist_truckCompressed_color, legend=True, zorder=1)

    legend_elements = [Line2D([0], [0], color=dist_pipelineLowPurity_col, lw=2, label='Gas Pipeline'), 
                       Line2D([0], [0], color=dist_truckLiquefied_color, lw=2, label='Liquid Truck Route'), 
                       Line2D([0], [0], color=dist_truckCompressed_color, lw=2, label='Gas Truck Route'),
                    #    Line2D([0], [0], marker='o', color=node_color, label='Node', markerfacecolor=node_color, markersize=5, lw=0)
                       ]
    legend_elements.extend([Line2D([0], [0], color=tech_plot['color'], label=tech_plot['name'], marker='o',lw=0) for tech, tech_plot in node_plot_tech.items()])
    legend_elements.extend([Line2D([0], [0], color='black', label=type_plot['name'], marker=type_plot['marker'],lw=0) for type_name, type_plot in node_plot_type.items()])


    ax.legend(handles=legend_elements, loc='upper left')


    fig.savefig(path + 'outputs/fig.png')

if __name__ == '__main__':
    from json import load
    data = load(open('base/outputs/outputs.json'))
    path = ''
    main(data, path)