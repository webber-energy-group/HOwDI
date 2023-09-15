# SPDX-License-Identifier: GPL-3.0-or-later

"""
Since HOwDI is a mixed-integer linear model and lacks a time domain,
the capacity of a node :math:`\\rho` and the amount of hydrogen :math:`h` produced/consumed/distributed by a node
seem similar and are often the same value.
The capacity of a producer/converter is the maximum amount of hydrogen that can be be produced or processed.
The actual amount produced or processed is :math:`h`.
For distribution, the capacity is the number of pipelines or trucks that can are used to transport hydrogen while
:math:`h` is the amount of hydrogen transported.

In a real world system, :math:`h` may vary with time. 
However, since the model does not have a time domain, 
a utilization term :math:`\\mu` is introduced that represents the percentage of the day that a given producer or converter is utilized.
For new builds, :math:`h = \\rho \\mu`
Existing builds may not choose to utilize the full capacity to save variable costs, so :math:`h \\le \\rho \\mu`.
"""

import pyomo.environ as pe
from networkx import DiGraph


def rule_flowCapacity(m: pe.ConcreteModel):
    """
    .. _capacity-distribution:

    Capacity-distribution relationship.

    Parameters
    ----------
    m : pyomo.environ.ConcreteModel
        A `pyomo.environ.ConcreteModel` object representing the HOwDI model.


    **Constraint**:
        The amount of hydrogen through a distribution arc :math:`e` must be less than or
        equal to the capacity of the arc (number of pipelines or trucks) :math:`\\rho_d (e)` times the
        allowable flow through one unit of capacity :math:`y_d^\\text{max}(\\delta^e)` for the
        type of distributor :math:`\\delta^e` associated with edge :math:`e` for all distribution arcs.

    .. math ::
        h_d(e) \\le \\rho_d(e) \\cdot y_{d}^{\\text{max}}(\\delta^e)
        \\quad
        \\forall e_{d} \\in E_{d}

    Set:
        All distribution arcs :math:`\\forall e_{d} \\in E_{d}`.
    """

    def rule(m, startNode, endNode):
        constraint = (
            m.dist_h[startNode, endNode]
            <= m.dist_capacity[startNode, endNode]
            * m.dist_flowLimit[startNode, endNode]
        )
        return constraint

    m.constr_flowCapacity = pe.Constraint(m.distribution_arcs, rule=rule)


def rule_flowCapacityConverters(m: pe.ConcreteModel, g: DiGraph):
    """
    .. _capacity-converters:

    Flow across a convertor is limited
    by the capacity of the conversion node

    The amount of hydrogen processed by a converter is not explicitly calculated.
    Instead, the hydrogen leaving the conversion node is considered the amount processed.

    Parameters
    ----------
    m : pyomo.environ.ConcreteModel
        A `pyomo.environ.ConcreteModel` object representing the HOwDI model.
    g : networkx.DiGraph
        A `networkx.DiGraph` object representing the HOwDI model.


    **Constraint**::

        flow out of a conversion node <=
        (capacity of convertor) * (utilization of convertor)

    .. math ::
        \\sum_{e_{out}^n}^{E_{out}^n} h_d(e) \\le \\rho_{cv}(n) \\cdot \\mu_{cv}(\\pi^n)
        \\quad
        \\forall n_{cv} \\in N_{cv}

    The sum of all flow exiting a conversion node :math:`\\sum h_d(e)` must be less than or equal
    to the capacity of the conversion node :math:`\\rho_{cv}(n)` times the utilization factor
    :math:`\\mu_{cv}(\\pi^n)` of the conversion method :math:`\\pi` associated with the conversion node :math:`n`
    for all conversion nodes :math:`n_{cv} \\in N_{cv}`.

    Set:
        All convertor nodes :math:`n_{cv} \\in N_{cv}`.
    """

    def rule(m, converterNode):
        flow_out = pe.summation(m.dist_h, index=g.out_edges(converterNode))
        constraint = (
            flow_out
            <= m.conv_capacity[converterNode] * m.conv_utilization[converterNode]
        )
        return constraint

    m.constr_flowCapacityConverters = pe.Constraint(m.converter_set, rule=rule)


def rule_productionCapacity(m: pe.ConcreteModel):
    """
    .. _capacity-production:

    Each producer's production capacity
    cannot exceed its capacity

    Parameters
    ----------
    m : pyomo.environ.ConcreteModel
        A `pyomo.environ.ConcreteModel` object representing the HOwDI model.


    **Constraint**:
        The amount of hydrogen produced by a producer :math:`n_p` must be less than or equal to
        the capacity of the producer :math:`\\rho_p(n_p)` times the utilization factor
        :math:`\\mu_p(\\phi^n)` of the production method :math:`\\phi` associated with the producer :math:`n_p`.

    .. math ::
        h_p(n) \\le \\rho_p(n) \\cdot \\mu_p (\\phi^n)
        \\quad
        \\forall n_p \\in N_p

    Set:
        All producers :math:`n_p \\in N_p`.
    """

    def rule(m, node):
        constraint = m.prod_h[node] <= m.prod_capacity[node] * m.prod_utilization[node]
        return constraint

    m.constr_productionCapacity = pe.Constraint(m.producer_set, rule=rule)


def rule_minProductionCapacity(m: pe.ConcreteModel, g: DiGraph):
    """
    .. _capacity-production-min:

    Establishes a minimum bound of production for a producer
    (only for new producers)

    Parameters
    ----------
    m : pyomo.environ.ConcreteModel
        A `pyomo.environ.ConcreteModel` object representing the HOwDI model.
    g : networkx.DiGraph
        A `networkx.DiGraph` object representing the HOwDI model.


    **Constraint**:
        The production capacity :math:`\\rho_p` of a producer node :math:`n_p` must be greater than or equal to
        the minimum hydrogen production :math:`y_{p}^{\\text{min}}` of the production method :math:`\\phi` associated
        with the node times a binary variable :math:`z_p(n_p)` that represents if the model has built the producer node.

    .. math ::

        \\rho_p(n)
        \\ge
        y_{p}^{\\text{min}}(\\phi(n))
        \\cdot
        z_p(n)
        \\quad
        \\forall n_{p_\\text{new}} \\in N_{p_\\text{new}}

    Set:
        All new producers :math:`n_{p_\\text{new}} \\in N_{p_\\text{new}}`.

    Note
    ----
        If `prod_exists` (:math:`z_p(n)`) is zero (false), the minimum allowed hydrogen production is zero.
        Paired with the maximum constraint :func:`rule_maxProductionCapacity`, the forces capacity of producers
        not built to be zero.
    """

    # multiply by "prod_exists" (a binary) so that constraint is only enforced if the producer exists
    # this gives the model the option to not build the producer
    def rule(m, node):
        constraint = (
            m.prod_capacity[node] >= g.nodes[node]["min_h2"] * m.prod_exists[node]
        )
        return constraint

    m.constr_minProductionCapacity = pe.Constraint(m.new_producers, rule=rule)


def rule_maxProductionCapacity(m: pe.ConcreteModel, g: DiGraph):
    """
    .. _capacity-production-max:

    Establishes a upper bound of production for a producer
    (only for new producers)

    Parameters
    ----------
    m : pyomo.environ.ConcreteModel
        A `pyomo.environ.ConcreteModel` object representing the HOwDI model.
    g : networkx.DiGraph
        A `networkx.DiGraph` object representing the HOwDI model.


    **Constraint**:
        The production capacity :math:`\\rho_p` of a producer node :math:`n_p` must be less than or equal to
        the maximum hydrogen production :math:`y_{p}^{\\text{min}}` of the production method :math:`\\phi` associated
        with the node times a binary variable :math:`z_p(n_p)` that represents if the model has built the producer node.

    .. math ::

        \\rho_p(n)
        \\le
        y_{p}^{\\text{max}}(\\phi(n))
        \\cdot
        z_p(n)
        \\quad
        \\forall n_{p_\\text{new}} \\in N_{p_\\text{new}}

    Set:
        All new producers :math:`n_{p_\\text{new}} \\in N_{p_\\text{new}}`.

    Note
    ----
        If `prod_exists` (:math:`z_p(n)`) is zero (false), the maximum allowed hydrogen production is zero.
        Paired with the minimum constraint :func:`rule_minProductionCapacity`, the forces capacity of producers
        not built to be zero.
    """

    # multiply by "prod_exists" (a binary) so that constraint is only enforced
    # if the producer exists with the prior constraint, forces 0 production
    # if producer DNE
    def rule(m, node):
        constraint = (
            m.prod_capacity[node] <= g.nodes[node]["max_h2"] * m.prod_exists[node]
        )
        return constraint

    m.constr_maxProductionCapacity = pe.Constraint(m.new_producers, rule=rule)


def apply_capacity_relationships(m: pe.ConcreteModel, g: DiGraph):
    """
    Applies all capacity constraints to the model, in the general form of

    .. math ::
        h \\le \\rho \\cdot \\mu

    where :math:`h` is the flow, :math:`\\rho` is the capacity, and :math:`\\mu` is the utilization factor.

    Parameters
    ----------
    m : pyomo.environ.ConcreteModel
        A `pyomo.environ.ConcreteModel` object representing the HOwDI model.
    g : networkx.DiGraph
        A `networkx.DiGraph` object representing the HOwDI model.
    """
    rule_flowCapacity(m)
    rule_flowCapacityConverters(m, g)
    rule_productionCapacity(m)
    rule_minProductionCapacity(m, g)
    rule_maxProductionCapacity(m, g)
