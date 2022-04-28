# TODO
# Get amounts flowing through edge of tree
# associate prices with each node
import json
from anytree import Node, RenderTree

class MetaNode(Node):
    """ Class that inherits from anytree.Node and adds additional metadata & methods"""
    def __init__(self, name, scope=None, parent=None, prod_data = None, dist_data = None, conv_data = None, cons_data = None,):
        super().__init__(name, parent=parent)
        self.scope = scope

        self.prod_data = prod_data
        self.dist_data = dist_data
        self.conv_data = conv_data
        self.cons_data = cons_data
        
        self.h = self.get_h()

    def get_h(self):
        if self.dist_data:
            return self.dist_data['dist_h']
        elif self.cons_data:
            return self.cons_data['cons_h']
        elif self.prod_data:
            return self.prod_data['prod_h']

        # add price later

def find_children_dist(full_data, parent,current_node,scope='local',past_node = None):

    dist_data = full_data[current_node]['distribution']
    destination_class = parent.name
    if scope == 'outgoing':
        destination_class = destination_class.replace(current_node+'_','')

    for dist_name, dist_params in dist_data[scope].items():
        if dist_params['destination_class'] == destination_class:
            if scope == 'outgoing':
                if dist_params['destination'] != past_node:
                    continue

            if dist_name.startswith("converter"):
                convertor_class = dist_data['source_class'].replace('convertor_','')
                conv_data = full_data[current_node]['conversion'][convertor_class]
            else:
                conv_data = None

                
            child = MetaNode(name = dist_params['source_class'],
                             parent=parent,
                             scope = scope,
                             dist_data=dist_params,
                             conv_data=conv_data,
                             )

            if scope in ['local','outgoing']:
                find_children_dist(full_data,child,current_node)
                find_children_dist(full_data,child,current_node,'incoming')
            elif scope == 'incoming':
                new_node = dist_params['source']
                find_children_dist(full_data,child,new_node,'outgoing',current_node)

def print_tree(parent):
    for pre, fill, node in RenderTree(parent):
        if isinstance(node, MetaNode):
            h = node.h
        else:
            h = None
        print("%s%s (%s)" % (pre, node.name, h))


def main(node, full_data):
    
    # #debug
    # node = 'channelview'
    # full_data = json.load(open('base/outputs/outputs.json'))

    local_data = full_data[node]
    parent_node = Node(node)


    for consumer_name, consumer_data in local_data['consumption'].items():
        consumer_node = MetaNode(name = consumer_name, parent = parent_node, cons_data=consumer_data, scope='local')

        find_children_dist(full_data, consumer_node, node)

    print_tree(parent_node)


if __name__ == '__main__':
    node = 'channelview'
    data = json.load(open('base/outputs/outputs.json'))
    main(node, data)