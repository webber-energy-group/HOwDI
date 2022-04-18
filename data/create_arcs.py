import pandas as pd
import geopandas as gpd
import itertools
from shapely.geometry import LineString
import matplotlib.pyplot as plt

def main(min_nodes=2,length_factor=0.8):
    # read files and establish parameters
    current_dir = ''
    
    nodes_df = pd.read_csv(current_dir+'nodes/nodes.csv')
    nodes = nodes_df['node'].tolist()

    epsg=3082
    geonodes=gpd.read_file(current_dir+'nodes/nodes.geojson')
    geonodes = geonodes.set_index('node')
    geonodes = geonodes.to_crs(epsg=epsg)

    existing_arcs = pd.read_csv(current_dir+'nodes/existing_arcs.csv')

    # Initialize Figure with Texas base
    fig, ax = plt.subplots(figsize=(10,10),dpi=300)
    us_county = gpd.read_file(current_dir+'US_COUNTY_SHPFILE/US_county_cont.shp')
    tx_county = us_county[us_county['STATE_NAME'] == 'Texas']
    tx = tx_county.dissolve().to_crs(epsg=epsg)
    tx.plot(ax=ax,color='white',edgecolor='black')

    # get all possible combinations of size 2, output is list of tuples turned into a multiindex
    nodes_combinations = list(itertools.combinations(nodes,2))
    index = pd.MultiIndex.from_tuples(nodes_combinations,names=['nodeA','nodeB'])
    gdf = gpd.GeoDataFrame(index=index)

    nodeA = gdf.join(geonodes.rename_axis('nodeA'))
    nodeB = gdf.join(geonodes.rename_axis('nodeB'))

    # create line from nodeA to nodeB (for plotting purposes)
    gdf['LINE'] = [LineString([[a.x, a.y],[b.x, b.y]])for (a,b) in zip(nodeA.geometry, nodeB.geometry)]
    gdf = gpd.GeoDataFrame(gdf, geometry='LINE')

    # get euclidian distance
    gdf['distance'] = nodeA.distance(nodeB) 

    class _Connections:
        def __init__(self, node):
            self.node = node

            # get list of tuples that describe the connection for this node
            self.connections = list(filter(lambda x:node in x, nodes_combinations))
            
            # number of connections
            self.n = len(self.connections)

            # get the nodes that are not the current node (destinations)
            self.dests = [x[0] if x[0] != node else x[1] for x in self.connections]

            self.lengths = self._make_length_dict()

        def _make_length_dict(self):
            # make dictionary that describes euclidian distance to destination
            distances = list(gdf.loc[self.connections]['distance'])
            return {self.dests[i] : distances[i] for i in range(len(distances))}
        def get_length(self, nodeB):
            # nodeB is a _Connections object
            return self.lengths[nodeB.node]
        def remove_connection(self, nodeB):
            # nodeB should be of type _Connections
            # think of self as nodeA
            a_str = self.node
            b_str = nodeB.node

            self.dests.remove(b_str)
            nodeB.dests.remove(a_str)

            tuple1 = (a_str, b_str)
            tuple2 = (a_str, b_str)

            for t in [tuple1, tuple2]:
                if t in self.connections:
                    self.connections.remove(t)
                if t in nodeB.connections:
                    nodeB.connections.remove(t)

            del self.lengths[b_str]
            del nodeB.lengths[a_str]

            self.n = self.n - 1
            nodeB.n = nodeB.n - 1

        def has_remaining_valid_connections(self, l):
            # returns boolean if has enough remaining valid connections
            # (has a number of connections greater than min_nodes with length less than length_factor times current length)
            return len([length for length in self.lengths if self.lengths[length] < length_factor*l]) > min_nodes

    nodal_c = {node: _Connections(node) for node in nodes} #initialize

    for nodeA_str, _nodeA in nodal_c.items():
        for _nodeB in [nodal_c[node] for node in _nodeA.dests]:
            current_length = _nodeA.get_length(_nodeB)
            if _nodeB.has_remaining_valid_connections(current_length) and _nodeA.has_remaining_valid_connections(current_length):
                _nodeA.remove_connection(_nodeB)

    valid_connections = []
    [valid_connections.extend(nodal_c[node].connections) for node in nodal_c]
    valid_connections = set(valid_connections)

    gdf_trimmed1 = gdf.loc[valid_connections]
    gdf_trimmed1.plot(ax=ax)

    # TODO maybe trim down list even further based on triangle l to h ratios

    df = pd.DataFrame(gdf_trimmed1)
    df = df.rename(columns={'distance':'kmLength'})
    df['kmLength'] = df['kmLength']/1000
    df = df.rename_axis(['startNode','endNode'])
    df['exist_pipeline'] = 0
    del df['LINE']
    df.to_csv('test.csv')

    return fig

if __name__ == '__main__':
    fig = main()