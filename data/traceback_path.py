"""
Author:Braden Pecora
Generates tree describing Hydrogen flow up from a consumer.

Consumer location is the first argument, for example run on Austin with `python traceback_path.py austin`

****
Displays percent going downstream in the tree:
Total hydrogen at current node * percent sent downstream = hydrogen sent downstream

****
TODO
Get prices associated with each step
Generate graphic to show cost breakdown
"""
import json, sys
from anytree import Node, RenderTree, Resolver

class MetaNode(Node):
    """ Class that inherits from anytree.Node and adds additional metadata & methods"""
    def __init__(self, name, current_node = None, scope=None, parent=None, prod_data = None, dist_data = None, conv_data = None, cons_data = None,):
        super().__init__(name, parent=parent)
        
        self.local_node = current_node
        self.scope = scope

        self.prod_data = prod_data
        self.dist_data = dist_data
        self.conv_data = conv_data
        self.cons_data = cons_data
        
        self.h = self.get_h()
        self.percent_downstream = 0
        self.h_downstream = 0

    def get_h(self):
        if self.dist_data:
            return self.dist_data['dist_h']
        elif self.cons_data:
            return self.cons_data['cons_h']
        elif self.prod_data:
            return self.prod_data['prod_h']
        else:
            return 0

        # add price later

    def get_children(self):
        r = Resolver('name')
        return [r.get(child,'.') for child in self.children]
            

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
                convertor_class = dist_params['source_class'].replace('converter_','')
                conv_data = full_data[current_node]['conversion'][convertor_class]
            else:
                conv_data = None

                
            child = MetaNode(name = dist_params['source_class'],
                             current_node = current_node,
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

def find_percent_downstream(parent):
    children = parent.get_children()
    total_child_h = sum([child.h for child in children])
    for child in children:
        child.percent_downstream = parent.h  / total_child_h
        child.h_downstream = child.percent_downstream*child.h
        # change the above into a method so that price fraction can be updated
        find_percent_downstream(child)

def print_tree(parent):
    for pre, fill, node in RenderTree(parent):
        # if isinstance(node, MetaNode):
        #     h = node.h
        # else:
        #     h = None
        print("{}{} ({:2.2f}*{:2.2f}%={:2.2f})".format(pre, node.name, node.h, 100*node.percent_downstream, node.h_downstream))


def main(node, full_data):
    
    # #debug
    # node = 'channelview'
    # full_data = json.load(open('base/outputs/outputs.json'))

    local_data = full_data[node]
    parent_node = MetaNode(node)


    for consumer_name, consumer_data in local_data['consumption'].items():
        consumer_node = MetaNode(name = consumer_name, parent = parent_node, cons_data=consumer_data, scope='local')

        find_children_dist(full_data, consumer_node, node)
    find_percent_downstream(parent_node)
    print_tree(parent_node)


if __name__ == '__main__':
    node = sys.argv[1]
    data = json.load(open('base/outputs/outputs.json'))
    main(node, data)