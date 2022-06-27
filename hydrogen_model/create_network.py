"""
hydrogen model module
takes input csvs and creates the networkx graph object
needed to run the Pyomo-based hydrogen model
"""

from itertools import permutations

from networkx import DiGraph


def cap_first(s):
    """capitalizes the first letter of a string
    without putting other letters in lowercase"""
    return s[0].upper() + s[1:]


def free_flow_dict(class_of_flow=None):
    """returns a dict with free flow values"""
    free_flow = {
        "kmLength": 0.0,
        "capital_usdPerUnit": 0.0,
        "fixed_usdPerUnitPerDay": 0.0,
        "variable_usdPerTon": 0.0,
        "flowLimit_tonsPerDay": 99999999.9,
        "class": class_of_flow,
    }
    return free_flow


def initialize_graph(H):
    """
    create a directional graph to represent the hydrogen distribution system
    ---
    returns g: a network.DiGraph object
    """
    g = DiGraph()

    for _, hub_series in H.hubs.iterrows():
        ### 1) create the nodes and associated data for each hub_name
        hub_data = dict(hub_series)

        hub_name = hub_data["hub"]
        capital_price_multiplier = hub_data["capital_pm"]

        ## 1.1) add a node for each of the hubs, separating low-purity
        # from high-purity (i.e., fuel cell quality)
        for purity_type in ["lowPurity", "highPurity"]:
            hub_data["node"] = "{}_center_{}".format(hub_name, purity_type)
            hub_data["class"] = "center_{}".format(purity_type)

            g.add_node(hub_data["node"], **hub_data)

        ## 1.2) add a node for each distribution type (i.e., pipelines and trucks)
        for d in H.distributors["distributor"]:
            # add both low and high purity pipelines
            if d == "pipeline":
                for purity_type in ["LowPurity", "HighPurity"]:
                    node_char = {
                        "node": "{}_dist_{}{}".format(hub_name, d, purity_type),
                        "class": "dist_{}{}".format(d, purity_type),
                        "hub": hub_name,
                    }
                    g.add_node(node_char["node"], **(node_char))

            else:  # trucks are assumed to be high purity
                node_char = {
                    "node": "{}_dist_{}".format(hub_name, d),
                    "class": "dist_{}".format(d),
                    "hub": hub_name,
                }
                g.add_node(node_char["node"], **(node_char))

        ## 1.3) add a node for each demand type
        for demand_type in ["lowPurity", "highPurity", "fuelStation"]:
            node_char = {
                "node": "{}_demand_{}".format(hub_name, demand_type),
                "class": "demand_{}".format(demand_type),
                "hub": hub_name,
            }
            g.add_node(node_char["node"], **(node_char))

        ### 2) connect the hub nodes, distribution nodes, and demand nodes
        ## 2.1) Connect center to pipeline and pipeline to center for each purity
        for purity in ["lowPurity", "highPurity"]:
            nodeA = "{}_center_{}".format(hub_name, purity)
            nodeB = "{}_dist_pipeline{}".format(hub_name, cap_first(purity))
            for arc, flow_direction in zip(
                permutations((nodeA, nodeB)),
                ["flow_within_hub", "reverse_flow_within_hub"],
            ):
                # this inner for loop iterates over the following connections, with purity x:
                # xPurity_center -> xPurityPipeline (class: flow_within_hub)
                # xPurityPipeline -> xPurity_center (class: reverse_flow_within_hub)
                g.add_edge(*arc, **free_flow_dict(flow_direction))

        ## 2.2) the connection of hub node to truck distribution hub incorporates the
        # capital and fixed cost of the trucks--it represents the trucking fleet that
        # is based out of that hub. The truck fleet size ultimately limits the amount
        # of hydrogen that can flow from the hub node to the truck distribution hub.
        truck_distribution = H.distributors[
            H.distributors["distributor"].str.contains("truck")
        ].set_index("distributor")

        for truck_type, truck_info in truck_distribution.iterrows():
            # costs and flow limits, (note the the unit for trucks is an individual
            #  truck, as compared to km for pipelines--i.e., when the model builds
            # 1 truck unit, it is building 1 truck, but when it builds 1 pipeline
            # unit, it is building 1km of pipeline. However, truck variable costs
            #  are in terms of km. This is why we separate the truck capital and
            # fixed costs onto this arc, and the variable costs onto the arcs that
            #  go from one hub to another.)
            depot_char = free_flow_dict("hub_depot_{}".format(truck_type))
            depot_char["startNode"] = "{}_center_highPurity".format(hub_name)
            depot_char["endNode"] = "{}_dist_{}".format(hub_name, truck_type)
            depot_char["capital_usdPerUnitPerDay"] = (
                truck_info.capital_usdPerUnit * capital_price_multiplier
            )
            depot_char["fixed_usdPerUnitPerDay"] = (
                truck_info.fixed_usdPerUnitPerDay * capital_price_multiplier
            )
            g.add_edge(depot_char["startNode"], depot_char["endNode"], **depot_char)

        ## 2.3) Connect distribution nodes to demand nodes

        # Series where index is flow type and value is flow limit:
        flow_limit_series = H.distributors.set_index("distributor")[
            "flowLimit_tonsPerDay"
        ]
        # for every distribution node and every demand node,
        # add an edge:
        # Flow from truck distribution and flow from highPurity
        # pipelines can satisfy all types of demand
        for flow_type, flow_limit in flow_limit_series.iteritems():

            flow_char = free_flow_dict("flow_to_demand_node")
            flow_char["flowLimit_tonsPerDay"] = flow_limit

            if flow_type == "pipeline":
                # connect lowPurity pipeline to lowPurity demand
                distribution_node = "{}_dist_pipelineLowPurity".format(hub_name)
                demand_node = "{}_demand_lowPurity".format(hub_name)
                g.add_edge(distribution_node, demand_node, **flow_char)

                # connect highPurity demand to every demand type
                distribution_node = "{}_dist_pipelineHighPurity".format(hub_name)
            else:
                # connect trucks to every demand type
                distribution_node = "{}_dist_{}".format(hub_name, flow_type)

            # iterate over all demand types;
            # all can be satisfied by trucks or highPurity pipelines
            for demand_type in ["fuelStation", "highPurity", "lowPurity"]:
                demand_node = "{}_demand_{}".format(hub_name, demand_type)
                g.add_edge(distribution_node, demand_node, **flow_char)

        ## 2.4) connect the center_lowPurity to the
        # hub_highPurity. We will add a purifier between
        # the two using the add_converters function
        g.add_edge(
            "{}_center_lowPurity".format(hub_name),
            "{}_center_highPurity".format(hub_name),
            **free_flow_dict("flow_through_purifier")
        )

    ### 3) create the arcs and associated data that connect hub_names to each other
    #  (e.g., baytown to montBelvieu): i.e., add pipelines and truck routes between
    # connected hub_names

    pipeline_data = H.distributors.set_index("distributor").loc["pipeline"]

    for _, arc_data in H.arcs.iterrows():
        start_hub = arc_data["startHub"]
        end_hub = arc_data["endHub"]
        hubs_df = H.hubs[(H.hubs["hub"] == start_hub) | (H.hubs["hub"] == end_hub)]

        # take the average of the two hubs' capital price multiplier to get the pm of the arc
        capital_price_multiplier = hubs_df["capital_pm"].sum() / 2

        # TODO adjust this value, `arc_data['kmLength_euclid]` is the straight line distance
        pipeline_length = arc_data["kmLength_road"]
        road_length = arc_data["kmLength_road"]

        ## 3.1) add a pipeline going in each direction to allow bi-directional flow
        for purity_type in ["LowPurity", "HighPurity"]:
            if purity_type == "HighPurity":
                # if it's an existing pipeline, we assume it's a low purity pipeline
                arc_data["exist_pipeline"] = 0

            for arc in permutations([start_hub, end_hub]):
                # generate node names based on arc and purity
                # yields ({hubA}_dist_pipeline{purity}, {hubB}_dist_pipeline{purity})
                node_names = tuple(
                    map(lambda hub: "{}_dist_pipeline{}".format(hub, purity_type), arc)
                )

                pipeline_char = {
                    "startNode": node_names[0],
                    "endNode": node_names[1],
                    "kmLength": pipeline_length,
                    "capital_usdPerUnit": pipeline_data["capital_usdPerUnit"]
                    * pipeline_length
                    * capital_price_multiplier,
                    "fixed_usdPerUnitPerDay": pipeline_data["fixed_usdPerUnitPerDay"]
                    * pipeline_length
                    * capital_price_multiplier,
                    "variable_usdPerTon": pipeline_data["variable_usdPerKilometer-Ton"]
                    * pipeline_length,
                    "flowLimit_tonsPerDay": pipeline_data["flowLimit_tonsPerDay"],
                    "class": "arc_pipeline{}".format(purity_type),
                    "existing": arc_data["exist_pipeline"],
                }
                # add the edge to the graph
                g.add_edge(node_names[0], node_names[1], **(pipeline_char))

                # 2.2) add truck routes and their variable costs,
                # note that that the capital and fixed costs of the trucks
                # are stored on the (hubName_center_highPurity, hubName_center_truckType) arcs
                if purity_type == "HighPurity":
                    for truck_type, truck_info in truck_distribution.iterrows():
                        # information for the trucking routes between hydrogen hubs

                        # generate node names based on arc and truck_type
                        # yields ({hubA}_dist_{truck_type}, {hubB}_dist_{truck_type})
                        node_names = tuple(
                            map(lambda hub: "{}_dist_{}".format(hub, truck_type), arc)
                        )

                        truck_char = {
                            "startNode": node_names[0],
                            "endNode": node_names[1],
                            "kmLength": road_length,
                            "capital_usdPerUnit": 0.0,
                            "fixed_usdPerUnitPerDay": 0.0,
                            "flowLimit_tonsPerDay": truck_info["flowLimit_tonsPerDay"],
                            "variable_usdPerTon": truck_info[
                                "variable_usdPerKilometer-Ton"
                            ]
                            * road_length,
                            "class": "arc_{}".format(
                                truck_type,
                            ),
                        }
                        # add the distribution arc for the truck
                        g.add_edge(node_names[0], node_names[1], **(truck_char))

    # 4) clean up and return
    # add startNode and endNode to any edges that don't have them
    edges_without_startNode = [
        s for s in list(g.edges) if "startNode" not in g.edges[s]
    ]
    for e in edges_without_startNode:
        g.edges[e]["startNode"] = e[0]
        g.edges[e]["endNode"] = e[1]

    return g


def add_consumers(g: DiGraph, H):
    """Add consumers to the graph

    For each hub, there are arcs from the nodes that represent demand type
    (e.g., fuelStation, lowPurity, highPurity) to the nodes that represent
    different demand sectors (e.g., industrialFuel, transportationFuel).
    In practice, one could create multiple sectors that connect to the same
    demand type (e.g., long-haul HDV, regional MDV, and LDV all connecting
    to a fuel station)
    """
    # loop through the hubs, add a node for each demand, and connect it to the appropriate demand hub
    # loop through the hub names, add a network node for each type of demand, and add a network arc
    # connecting that demand to the appropriate demand hub
    for _, hub_data in H.hubs.iterrows():
        hub_name = hub_data["hub"]

        for _, demand_data in H.demand.iterrows():
            demand_sector = demand_data["sector"]
            demand_value = hub_data["{}_tonnesperday".format(demand_sector)]
            demand_type = demand_data["demandType"]
            demand_node = "{}_demand_{}".format(hub_name, demand_type)

            # add the demandSector nodes
            if demand_value == 0:
                # don't add a demandSector node to hubs where that demand is 0
                pass
            else:
                ### 1) create a carbon sensitive and a carbon indifferent version of
                #  the demandSector based on the 0--1 fraction value of the
                # "carbonSensitiveFraction" in the csv file.

                ## 1.1) create the carbon indifferent version
                demand_node_char = demand_data.to_dict()
                demand_node_char["class"] = "demandSector_{}".format(demand_sector)
                demand_node_char["node"] = "{}_{}".format(
                    hub_name,
                    demand_node_char["class"],
                )
                demand_node_char["size"] = demand_value * (
                    1 - demand_node_char["carbonSensitiveFraction"]
                )
                demand_node_char["carbonSensitive"] = 0
                demand_node_char["hub"] = hub_name

                ## 1.2) create the carbon sensitive version
                # by copying and editing carbon indifferent version
                demand_node_char_carbon = demand_node_char.copy()
                demand_node_char_carbon["node"] = "{}_carbonSensitive".format(
                    demand_node_char["node"]
                )
                demand_node_char_carbon["size"] = (
                    demand_value * demand_node_char_carbon["carbonSensitiveFraction"]
                )
                demand_node_char_carbon["carbonSensitive"] = 1

                ### 2) connect the demandSector nodes to the demand nodes
                g.add_node(demand_node_char["node"], **(demand_node_char))
                g.add_node(demand_node_char_carbon["node"], **(demand_node_char_carbon))

                flow_dict = free_flow_dict("flow_to_demand_sector")
                for demand_sector_node in [
                    demand_node_char["node"],
                    demand_node_char_carbon["node"],
                ]:
                    g.add_edge(demand_node, demand_sector_node, **flow_dict)


def add_producers(g: DiGraph, H):
    """
    add producers to the graph
    each producer is a node that send hydrogen to a hub_lowPurity or hub_highPurity node
    """
    # loop through the hubs and producers to add the necessary nodes and arcs

    for prod_tech_type, prod_df in {
        "electric": H.prod_elec,
        "thermal": H.prod_therm,
    }.items():
        for _, prod_data_series in prod_df.iterrows():
            prod_type = prod_data_series["type"]

            try:
                H.hubs["build_{}".format(prod_type)]
            except KeyError:
                print(
                    "The ability to build {} at each location was not specified in "
                    "'hubs.csv'. Assuming {} can be built at all hubs.".format(
                        prod_type, prod_type
                    )
                )
                H.hubs["build_{}".format(prod_type)] = 1

            for _, hub_data in H.hubs.iterrows():
                hub_name = hub_data["hub"]
                capital_price_multiplier = hub_data["capital_pm"]
                ng_price = hub_data["ng_usd_per_mmbtu"]
                e_price = hub_data["e_usd_per_kwh"]

                if hub_data["build_{}".format(prod_type)] == 0:
                    # if the node is unable to build that producer type, pass
                    pass
                else:
                    purity = prod_data_series["purity"]
                    prod_node = "{}_production_{}".format(hub_name, prod_type)
                    destination_node = "{}_center_{}Purity".format(hub_name, purity)

                    prod_data = prod_data_series.to_dict()
                    prod_data["node"] = prod_node
                    prod_data["class"] = "producer"
                    prod_data["existing"] = 0
                    prod_data["hub"] = hub_name
                    prod_data["fixed_usdPerTon"] = (
                        prod_data["fixed_usdPerTon"] * capital_price_multiplier
                    )
                    prod_data["e_price"] = prod_data["kWh_coefficient"] * e_price

                    # data specific to thermal or electric
                    if prod_tech_type == "thermal":
                        prod_data["capital_usd_coefficient"] = (
                            prod_data["capital_usd_coefficient"]
                            * capital_price_multiplier
                        )
                        prod_data["ng_price"] = prod_data["ng_coefficient"] * ng_price
                    elif prod_tech_type == "electric":
                        prod_data["capital_usd_coefficient"] = (
                            prod_data["capEx_$_per_kW"]
                            * prod_data["kWh_coefficient"]
                            * H.time_slices
                            / 8760
                            / prod_data["utilization"]
                            * capital_price_multiplier
                        )
                    else:
                        raise Exception(
                            "Production type that is not thermal or electric"
                        )
                    g.add_node(prod_node, **prod_data)

                    # add edge
                    edge_dict = free_flow_dict("flow_from_producer")
                    edge_dict["startNode"] = prod_node
                    edge_dict["endNode"] = destination_node

                    g.add_edge(prod_node, destination_node, **(edge_dict))

    # loop through the existing producers and add them
    for _, prod_existing_series in H.producers_existing.iterrows():
        hub_name = prod_existing_series["hub"]
        prod_type = prod_existing_series["type"]
        prod_node = "{}_production_{}Existing".format(hub_name, prod_type)
        destination_node = "{}_center_{}Purity".format(hub_name, purity)

        # get corresponding data about that type of production
        prod_data = H.prod_therm.set_index("type").loc[prod_type]
        purity = prod_data["purity"]

        prod_exist_data = prod_existing_series.to_dict()
        prod_exist_data["node"] = prod_node
        prod_exist_data["class"] = "producer"
        prod_exist_data["existing"] = 1
        g.add_node(prod_node, **prod_exist_data)
        # add edge

        edge_dict = free_flow_dict("flow_from_producer")
        edge_dict["startNode"] = prod_node
        edge_dict["endNode"] = destination_node

        g.add_edge(prod_node, destination_node, **(edge_dict))


def add_converters(g: DiGraph, H):
    """
    add converters to the graph
    each converter is a node and arc that splits an existing arc into two
    """
    # loop through the nodes and converters to add the necessary nodes and arcs
    for _, converter_data_series in H.converters.iterrows():
        if converter_data_series["arc_start_class"] == "pass":
            pass
        else:
            # For computational efficiency, it would make sense to declare
            # potential_start_nodes outside of the H.converters.iterrows() loop.
            # However, since a converter may be connected to another converter,
            # potential_start_nodes changes on every iteration of H.converters.
            #
            # Thus, when defining converters, a converter that has a start class
            # that is another converter must be defined after the "start class"
            # converter.

            potential_start_nodes = list(g.nodes(data="class"))
            for node_b4_cv, node_b4_cv_class in potential_start_nodes:
                if node_b4_cv_class == converter_data_series["arc_start_class"]:
                    hub_name = g.nodes[node_b4_cv]["hub"]
                    hub_data = H.hubs.set_index("hub").loc[hub_name]
                    # regional values:
                    capital_pm = hub_data["capital_pm"]
                    e_price = hub_data["e_usd_per_kwh"]

                    # add a new node for the converter at the hub
                    cv_data = converter_data_series.to_dict()
                    cv_data["hub"] = hub_name
                    cv_class = "converter_{}".format(cv_data["converter"])
                    cv_data["class"] = cv_class
                    cv_node = "{}_{}".format(hub_name, cv_class)
                    cv_data["node"] = cv_node
                    cv_destination = cv_data["arc_end_class"]

                    cv_data["capital_usd_coefficient"] = (
                        cv_data["capital_usd_coefficient"] * capital_pm
                    )
                    cv_data["fixed_usdPerTonPerDay"] = (
                        cv_data["fixed_usdPerTonPerDay"] * capital_pm
                    )
                    cv_data["e_price"] = cv_data["kWh_coefficient"] * e_price
                    g.add_node(cv_node, **cv_data)

                    # grab the tuples of any edges that have the correct arc_end type--
                    # i.e., any edges where the start_node is equal to the node we are
                    #  working on in our for loop, and where the end_node has a class equal
                    #  to the "arc_end_class" parameter in converters_df
                    change_edges_list = [
                        (start_node, end_node)
                        for start_node, end_node in g.edges()
                        if (
                            (node_b4_cv == start_node)
                            & (cv_destination == g.nodes[end_node]["class"])
                        )
                    ]
                    # insert converter node between "arc_start_class" node
                    # and "arc_end_class" node
                    for start_node, end_node in change_edges_list:
                        arc_data = g.edges[(start_node, end_node)]

                        # add "arc_start_class" node -> cv_node
                        start2cv_data = free_flow_dict("flow_to_converter")
                        free_flow_flowLimit = start2cv_data["flowLimit_tonsPerDay"]
                        start2cv_data["startNode"] = start_node
                        start2cv_data["endNode"] = cv_node
                        start2cv_data["flowLimit_tonsPerDay"] = arc_data[
                            "flowLimit_tonsPerDay"
                        ]
                        g.add_edge(start_node, cv_node, **start2cv_data)

                        # add cv_node -> "arc_end_class" node
                        cv2dest_data = arc_data.copy()
                        cv2dest_data["startNode"] = cv_node
                        cv2dest_data["flowLimit_tonsPerDay"] = free_flow_flowLimit
                        cv2dest_data["class"] = "flow_from_converter"
                        g.add_edge(cv_node, end_node, **cv2dest_data)

                        # remove "arc_start_class" -> "arc_end_class" node
                        g.remove_edge(start_node, end_node)


def add_price_nodes(g: DiGraph, H):
    """
    add price nodes to the graph
    each price is a node that has very little demand and series of breakeven
    price points to help us estimate the price that customers are paying for
    hydrogen at that node.
    ---
    #TODO maybe the below should be copied somewhere else:

    H.price_range is a iterable array of prices. The model will use this array
    of discrete prices as fake consumers. In the solution, the price of
    hydrogen at that node is between the most expensive "price consumer" who
    does not use hydrogen and the least expensive "price consumer" who does.
    H.price_hubs is a list of the hubs where we want to calculate prices for.
    if it equals 'all' then all of the hubs will be priced H.price_demand is
    the total amount of pricing demand at each hub. this can be set to a higher
    value if you are trying to just test sensitivity to amount of demand
    """

    if not H.find_prices:
        return
    else:
        demand_sector2type_map = H.demand.set_index("sector")["demandType"].to_dict()
        # demand sectors are "transportationFuel, industrialFuel, existing"
        # demand types are "fuelStation, lowPurity, highPurity"

        if H.price_hubs == "all":
            H.price_hubs = set([s[1] for s in list(g.nodes(data="hub"))])
        for ph in H.price_hubs:
            # array to track demand types that have price hubs already.
            # we don't want duplicate price hubs since sectors can
            # share a price hub
            demand_types_for_this_ph = []
            # add nodes to store pricing information
            for demand_sector, demand_type in demand_sector2type_map.items():
                # check if demand sector in nodes
                demand_sector_node = "{}_demandSector_{}".format(ph, demand_sector)
                if demand_sector_node in g.nodes():
                    # check if demand type already has a price hub for this hub
                    if demand_type not in demand_types_for_this_ph:
                        # if not, add the price hub
                        demand_types_for_this_ph.append(demand_type)

                        demand_node = ph + "_demand_{}".format(demand_type)
                        for p in H.price_tracking_array:
                            # 1) fuelStation prices
                            p = round(p, 2)
                            ph_node = ph + "_price{}_{:.2f}".format(
                                cap_first(demand_type), p
                            )

                            price_node_dict = {
                                "node": ph_node,
                                "sector": "price",
                                "hub": ph,
                                "breakevenPrice": p * 1000,
                                "size": H.price_demand,
                                "carbonSensitiveFraction": 0,
                                "breakevenCarbon_g_MJ": 0,
                                "demandType": demand_type,
                                "class": "price",
                            }
                            g.add_node(ph_node, **price_node_dict)
                            # add the accompanying edge
                            price_edge_dict = {
                                "startNode": demand_node,
                                "endNode": ph_node,
                                "kmLength": 0.0,
                                "capital_usdPerUnit": 0.0,
                            }
                            g.add_edge(demand_node, ph_node, **price_edge_dict)


def build_hydrogen_network(H) -> DiGraph:
    """Builds appropriate hydrogen network
    from H (a HydrogenInputs object)

    returns g: a networkx.DiGraph object
    """
    g = initialize_graph(H)
    add_consumers(g, H)
    add_producers(g, H)
    add_converters(g, H)
    add_price_nodes(g, H)

    return g
