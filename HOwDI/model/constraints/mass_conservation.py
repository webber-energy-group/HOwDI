# SPDX-License-Identifier: GPL-3.0-or-later

import pyomo.environ as pe
from networkx import DiGraph


def rule_flowBalance(m: pe.ConcreteModel, g: DiGraph):
    """
    Mass conservation for each node.

    The amount of hydrogen flowing into a node must equal the
    amount of hydrogen exiting a node, unless that node is a producer or consumer node.
    Producer nodes can create hydrogen, and consumer nodes can consume hydrogen.

    Parameters
    ----------
    m : pyomo.environ.ConcreteModel
        A `pyomo.environ.ConcreteModel` object representing the HOwDI model.
    g : networkx.DiGraph
        A `networkx.DiGraph` object representing the hydrogen network.


    **Constraint**::

        sum of(
            + flow into a node
            - flow out a node
            + flow produced by a node
            - flow consumed by a node
            ) == 0

    .. math::

        \sum_{e^n_{in}}^{E^n_{in}}h_d(e)
        =
        \sum_{e^n_{out}}^{E^n_{out}}h_d(e)
        \quad
        \\forall
        n
        \in
        N\\backslash (N_p \cup N_u)

    For all nodes :math:`n` in the network :math:`N` that are not producers :math:`N_p` or consumers :math:`N_u`,
    the sum of hydrogen flow :math:`h_d(e)` (distributed) from all edges :math:`e_\\text{in} \in E^n_{in}` into the node is equal
    to the sum of flow :math:`h_d(e)` from all edges :math:`e_\\text{out} \in E^n_{out}` exiting the node.

    .. math::

        h_p(n)
        =
        \sum_{e^n_{out}}^{E^n_{out}}h_d(e)
        \quad
        \\forall
        n
        \in
        N_p

    For all producer nodes :math:`n \in N_p`, the flow produced by the node :math:`h_p(n)` is equal to the sum
    of flow :math:`h_d(e)` from all edges :math:`e_\\text{out} \in E^n_{out}` exiting the node.

    .. math::

        \sum_{e^n_{in}}^{E^n_{in}}h_d(e)
        =
        h_u(n)
        \quad
        \\forall
        n
        \in
        N_u

    For all consumer nodes :math:`n \in N_u`, the sum of flow :math:`h_d(e)` from all edges
    :math:`e_\\text{in} \in E^n_{in}` into the node is equal to the flow consumed (utilized) by the node :math:`h_u(n)`.

    Set:
        All nodes :math:`n \in N`

    Notes
    -----
    This function applies mass conservation constraints to the HOwDI model to ensure that the flow of hydrogen is balanced at each node.
    The constraints are based on the sum of the flow into the node, the flow out of the node, the flow produced by the node, and the flow consumed by the node, which should all sum to zero.

    The function loops through each node in the `m.node_set` and applies the appropriate constraint based on whether the node is a producer, consumer, or hub.

    If the node is a producer, the constraint is `m.prod_h[node] + expr == 0.0`, where `expr` is the sum of the flow into and out of the node.

    If the node is a consumer, the constraint is `expr - m.cons_h[node] == 0.0`, where `expr` is the sum of the flow into and out of the node.

    If the node is a hub, the constraint is `expr == 0.0`, where `expr` is the sum of the flow into and out of the node.

    """

    def rule(m, node):
        expr = 0
        if g.in_edges(node):
            expr += pe.summation(m.dist_h, index=g.in_edges(node))
        if g.out_edges(node):
            expr += -pe.summation(m.dist_h, index=g.out_edges(node))

        # the equality depends on whether the node is a producer, consumer, or hub
        if node in m.producer_set:  # if producer:
            constraint = m.prod_h[node] + expr == 0.0
        elif node in m.consumer_set:  # if consumer:
            constraint = expr - m.cons_h[node] == 0.0
        else:  # if hub:
            constraint = expr == 0.0
        return constraint

    m.constr_flowBalance = pe.Constraint(m.node_set, rule=rule)


def rule_truckCapacityConsistency(m: pe.ConcreteModel, g: DiGraph):
    """
    Truck mass balance.

    Parameters
    ----------
    m : pyomo.environ.ConcreteModel
        A `pyomo.environ.ConcreteModel` object representing the HOwDI model.
    g : networkx.DiGraph
        A `networkx.DiGraph` object representing the hydrogen network.


    **Constraint**:
        The number of trucks entering a node must be greater than or equal to
        the number of trucks leaving a node.

    .. math::

        \sum_{e^n_{in}}^{E^n_{in}}\\rho_d(e)
        =
        \sum_{e^n_{out}}^{E^n_{out}}\\rho_d(e)
        \quad
        \\forall
        n
        \in
        N_{\\text{truck}}

    The sum of capacities :math:`\\rho` of all edges :math:`e` entering a node :math:`n` must be equal
    to the sum of capacities of all edges exiting the node.

    Set:
        All nodes relevant to trucks (all distribution centers in distribution.csv that include truck),
        :math:`n \in N_{\\text{truck}}`.



    Notes
    -----
    In nodes are only liquid/gas terminals (only converters).
    Out nodes can be converters (dispensers), demand centers, or nodes that distribute to other hubs.
    FIXME I don't know if this is correct. Should hydrogen coming from other hubs be allowed as an
    in node?

    """

    def rule(m, truck_dist_center):
        # truck_dist_center should be all the hubs (nodes for collection) that are defined in distribution.csv
        in_trucks = sum(
            m.dist_capacity[(in_node, truck_dist_center)]
            for in_node, _ in g.in_edges(truck_dist_center)
            if "converter" in in_node
        )
        out_trucks = sum(
            m.dist_capacity[(truck_dist_center, out_node)]
            for _, out_node in g.out_edges(truck_dist_center)
            if "converter" in out_node or "dist" in out_node or "demand" in out_node
        )

        constraint = in_trucks - out_trucks == 0
        return constraint

    m.const_truckConsistency = pe.Constraint(m.truck_set, rule=rule)


def rule_consumerSize(m: pe.ConcreteModel):
    """
    .. _consumerSize:

    Each consumer's consumption cannot exceed its size

    Parameters
    ----------
    m : pe.ConcreteModel


    **Constraint**:
        consumed hydrogen <= consumption size

    .. math::

        h_u(n) \\le Q_{\\text{H}_2}(\\omega^n, \\xi^n) \quad \\forall n \\in N_u

    The amount of hydrogen demanded/consumed/utilized :math:`h_u` at a consumer node :math`n \\in N_u`
    must be less that or equal to the amount of hydrogen demanded by that node :math:`Q_{\\text{H}_2}`.
    The value :math:`Q_{\\text{H}_2}` is defined by the demand sector :math:`\\xi^n` and hub :math:`\\omega^n`
    corresponding to the node.

    Set:
        All consumers :math:`n \\in N_u`

    """

    def rule(m, node):
        constraint = m.cons_h[node] <= m.cons_size[node]
        return constraint

    m.constr_consumerSize = pe.Constraint(m.consumer_set, rule=rule)


def apply_mass_conservation(m: pe.ConcreteModel, g: DiGraph):
    """Apply all mass conservation constraints to a model

    Args:
        m (ConcreteModel): Pyomo model
        g (DiGraph): Networkx graph
    """
    rule_flowBalance(m=m, g=g)
    rule_truckCapacityConsistency(m=m, g=g)
    rule_consumerSize(m=m)
