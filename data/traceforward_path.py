"""
Author:Braden Pecora
Generates tree describing Hydrogen flow down from a producer.

Producer location is the first argument, for example run on Austin with `python traceforward_path.py austin`

****
Displays percent from upstream in a tree, either:
Parent hydrogen * percent of parent hydrogen sent downstream = hydrogen at node

or, if relevant parent or children are missing from tree:
Parent hydrogen -> (feeds into) total mass above node (sum of parent hydrogen),
sum of parent hydrogen * percent sent downstream (from sum) = hydrogen at node 
"""

import json, sys
from anytree import Node, RenderTree, Resolver
from math import isclose

class MetaNode(Node):
    """Inherits from anytree.Node and adds data storage"""
    def __init__(self, name, title=None, location=None, parent=None, data=None, order=None):
        super().__init__(name, parent=parent)

        self.title = title
        self.location = location
        self.data = data
        self.order = order

        self.print_name = self.get_print_name()

        self.h = self.get_h()
        self.parent_h = self.get_parent_h()

        self.percent_of_parent = self.get_percent_of_parent() # percent of parent sent to current node
        self.mass_in = None # initialized later

    def get_print_name(self):
        """get name used when printing to show proper prefix"""
        if self.parent == None:
            # "origin"
            prefix = self.location
        else:
            if self.parent.location == self.location:
                # local distribution
                prefix = self.location
            else:
                # outgoing distribution
                prefix = self.parent.location

        return "{}-{}".format(prefix, self.name)


    def get_h(self):
        if self.order == "production":
            h = self.data['prod_h']
        elif self.order == "distribution":
            h = self.data["dist_h"]
        elif self.order == "consumption":
            h = self.data["cons_h"]
        else:
            h = 0

        return h

    def get_siblings(self):
        """get siblings associated with node, only works after tree created"""
        r = Resolver('name')
        return [r.get(sibling,'.') for sibling in self.siblings]

    def get_children(self):
        """get children associated with node, only works after tree created"""
        r = Resolver('name')
        return [r.get(child,'.') for child in self.children]
    
    def get_percent_of_parent(self):
        """
        Calculates amount of parent hydrogen sent to current node,
        not always accurate if all parents not in tree
        """
        percent_above = 1
        if self.parent != None:
            if self.parent.h != 0:
                percent_above = self.h/self.parent.h

        return percent_above

    def get_parent_h(self):
        """Finds parent hydrogen, if available"""
        h = 0
        if self.parent != None:
            h = self.parent.h

        return h

    def get_mass_equation(self, tol = 0.0001):
        """
        Returns a string describing the mass flow associated with the node.
        
        See docstring at top of file
        """
        siblings = self.get_siblings()
        self.mass_in = self.h + sum(sibling.h for sibling in siblings)

        if isclose(self.mass_in, self.parent_h, abs_tol=tol): #check mass flow
            out = "{:2.2f}*{:2.2f}%={:2.2f}".format(self.parent_h,100*self.percent_of_parent,self.h)
        else:
            # if mass flow is incorrect for whatever reason (this is to be expected as not all parents are accounted for),
            # fix the mass flow to make sense. Describes that mass of parent flows into a pool (sum of parents).
            # The size of this 'pool' is known, but all sources are not. Use `traceback_path.py` for that.
            self.percent_of_parent = self.h/self.mass_in
            out = "{:2.2f} -> {:2.2f}, {:2.2f}*{:2.2f}%={:2.2f}".format(self.parent_h, self.mass_in, self.mass_in,100*self.percent_of_parent,self.h)
        return out

def find_children_prod(full_data, parent_node, current_location = None, title=None):
    # current node is the city 
    # title is the type, i.e., "demandSector_existing", "smrExisting"
    # order is production, distribution, conversion, consumption

    # distribution
    dist_data = full_data[current_location]["distribution"]
    for scope_of_child in ['local','outgoing']:
        for dist_name, dist_params in dist_data[scope_of_child].items():
            if dist_params['source_class'] == title:

                destination_class = dist_params['destination_class']

                if scope_of_child == 'outgoing':
                    current_location = dist_params['destination']

                child = MetaNode(name = dist_name, 
                                parent=parent_node, 
                                location=current_location,
                                title=destination_class,
                                data = dist_params,
                                order="distribution")

                find_children_prod(full_data, child, 
                                    current_location=current_location,
                                    title=destination_class)
        
    # consumption
    for consumer_name, consumer_data in full_data[current_location]['consumption'].items():
        if consumer_name == title:
            child = MetaNode(name = consumer_name, parent=parent_node, location=current_location, data=consumer_data,order="consumption")

def print_tree(parent):
    for pre, fill, node in RenderTree(parent):
        print("{}{} ({})".format(pre, node.print_name, node.get_mass_equation()))


def main(producer_node_name, full_data):
    # # debug
    # producer_node_name = 'elPaso'
    # full_data = json.load(open('base/outputs/outputs.json'))

    parent_node = MetaNode(producer_node_name, location="origin")

    local_data = full_data[producer_node_name]

    for producer_name, producer_data in local_data['production'].items():
        producer_node = MetaNode(name = producer_name, parent=parent_node, location=producer_node_name, order='production', data=producer_data)

        find_children_prod(full_data, producer_node, title="production_{}".format(producer_name), current_location=producer_node_name)
    
    print_tree(parent_node)

if __name__ == '__main__':
    node = sys.argv[1]
    data = json.load(open('base/outputs/outputs.json'))
    main(node, data)