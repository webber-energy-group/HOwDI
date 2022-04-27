# TODO
# Goal 1: Get tree of locations - complete
# Goal 2: match values to get breakdown of where h2 came from
import json
from anytree import Node, RenderTree

def find_children_dist(full_data, parent,current_node,scope='local',past_node = None):

    dist_data = full_data[current_node]['distribution']
    destination_class = parent.name
    if scope == 'outgoing':
        destination_class = destination_class.replace(current_node+'_','')

    for _, dist_params in dist_data[scope].items():
        if dist_params['destination_class'] == destination_class:
            if scope == 'outgoing':
                if dist_params['destination'] != past_node:
                    continue
                
            child = Node(dist_params['source_class'], parent=parent)

            if scope in ['local','outgoing']:
                find_children_dist(full_data,child,current_node)
                find_children_dist(full_data,child,current_node,'incoming')
            elif scope == 'incoming':
                new_node = dist_params['source']
                find_children_dist(full_data,child,new_node,'outgoing',current_node)

def print_tree(parent):
    for pre, fill, node in RenderTree(parent):
        print("%s%s" % (pre, node.name))


def main(node, full_data):
    
    # #debug
    # node = 'channelview'
    # full_data = json.load(open('base/outputs/outputs.json'))

    local_data = full_data[node]
    parent_node = Node(node)


    for consumer in local_data['consumption'].keys():
        consumer_node = Node(consumer, parent = parent_node)

        find_children_dist(full_data, consumer_node, node)

    print_tree(parent_node)


if __name__ == '__main__':
    node = 'channelview'
    data = json.load(open('base/outputs/outputs.json'))
    main(node, data)