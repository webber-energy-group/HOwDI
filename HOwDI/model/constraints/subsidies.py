# SPDX-License-Identifier: GPL-3.0-or-later
"""
An option of the model to utilize subsidies for hydrogen infrastructure.
"""
import pyomo.environ as pe

from HOwDI.model.HydrogenData import HydrogenData

###subsidy for infrastructure
# total subsidy dollars must be less than or equal to the available subsidy funds
# =============================================================================
# def rule_subsidyTotal(m, node):
#     constraint = sum(m.fuelStation_cost_capital_subsidy[fs] for fs in m.fuelStation_set) <= (H.subsidy_dollar_billion * 1E9)
#     return constraint
# m.constr_subsidyTotal = pe.Constraint(rule=rule_subsidyTotal)
# =============================================================================


# conversion facility subsidies
def rule_subsidyConverter(m, H):
    """Subsidies for a convertor is equal to the cost share fraction

    Parameters
    ----------
    m : pe.ConcreteModel
        Pyomo ConcreteModel object
    H : HydrogenData
        HydrogenData object


    **Constraint**::

        Subsidies from conversion == Cost of conversion * fraction of cost paid by subsidies

    Set:
        All fuel stations
    """

    def rule(m, node):
        conversion_cost = m.conv_capacity[node] * m.conv_cost_capital[node]

        constraint = m.fuelStation_cost_capital_subsidy[node] == conversion_cost * (
            1 - H.subsidy_cost_share_fraction
        )
        # note that existing production facilities have a cost_capital
        #  of zero, so they cannot be subsidized
        return constraint

    m.constr_subsidyConverter = pe.Constraint(m.fuelStation_set, rule=rule)


def apply_subsidy_constraints(m, H):
    """
    Apply all subsidy constraints

    Parameters
    ----------
    m : pe.ConcreteModel
        Pyomo ConcreteModel object
    H : HydrogenData
        HydrogenData object

    """
    rule_subsidyConverter(m, H)
