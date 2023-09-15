.. _inputs:

Input files
===========
An explanation of the provided example input files can be found in :ref:`tutorial`.

arcs.csv
--------
Describes the arcs in the network and distance between them.

.. csv-table:: arcs.csv
    :file: descriptions/inputs/arcs.csv
    :header-rows: 1

Example
^^^^^^^

.. csv-table:: example of arcs.csv
    :file: ../tutorial/scenario/inputs/arcs.csv
    :header-rows: 1

Relevance to model
^^^^^^^^^^^^^^^^^^
- The model index and set :math:`e \in E` is the set of all edges/arcs. Regrettably, the model's terminology is not consistent or established for this.
  The `arcs.csv` file describes all the edges/arcs that connect a hub to another, but, :ref:`since a hub contains many nodes <node_vs_hub_terms>`,
  there are many model edges connecting nodes within a hub and nodes that are in different hubs.
- In :ref:`create_network.py <create_network_module>`, costs associated with transportation are multiplied by
  the road distance between hubs to get costs per unit (pipeline, truck) that will be used as parameters in the model.
  The capital :math:`D_c(\delta)` [#Ref-fixed]_ and variable :math:`D_v(\delta)` costs of pipelines
  are functions of road length. Only the variable cost of a truck route is multiplied by road length; capital costs are
  determined only by the number of trucks on the route.
- Determines existing pipelines when constructing the network, which sets the capital cost of the pipeline to zero.

.. [#Ref-fixed] Fixed costs are calculated as a user-inputted fraction :math:`\kappa` of the capital costs.

.. raw:: html

    <hr>
   
ccs.csv
-------
Describes the carbon capture and storage (CCS) technologies that can be used to retrofit existing thermal hydrogen producers.

.. note::
    This feature is not fully implemented yet. The currently supported types are :code:`ccs1` and :code:`ccs2`.

.. csv-table:: ccs.csv
    :file: descriptions/inputs/ccs.csv
    :header-rows: 1

Example
^^^^^^^

.. csv-table:: example of ccs.csv
    :file: ../tutorial/scenario/inputs/ccs.csv
    :header-rows: 1

Relevance to model
^^^^^^^^^^^^^^^^^^
- :code:`type` is :math:`\psi \in \Psi` in the model formulation.
- :code:`variable_usdPerTonCO2` is :math:`CCS_v(\psi)`, used :ref:`here <variable-costs-of-retrofitted-ccs>`.
- :code:`percent_CO2_captured` is :math:`\beta(\psi)`, used :ref:`here <rule_ccs1CapacityRelationship>`.
- :code:`h2_tax_credit` is :math:`\tau_{\text{H}_2}(\psi)`, used :ref:`here <utility-gained-through-carbon-capture-tax-credits>`.

.. raw:: html

    <hr>
   
conversion.csv
--------------

Parameters associated with conversion technologies and their locations in the supply chain.

.. csv-table:: conversion.csv
    :file: descriptions/inputs/conversion.csv
    :header-rows: 1

.. todo ::
    Remove :code:`fixed_usdPerTon` from the model (:code:`create_network.py`).
    It is technically required at the moment (see how it is included in the example).

Example
^^^^^^^

.. csv-table:: example of conversion.csv
    :file: ../tutorial/scenario/inputs/conversion.csv
    :header-rows: 1

Relevance to model
^^^^^^^^^^^^^^^^^^
- :code:`converter` is :math:`\pi \in \Pi` in the model framework.
- :code:`variable_usdPerTon` is :math:`C_v`, used :ref:`here <variable-costs-of-conversion>`.
- :code:`capital_usdTonPerDay` is :math:`C_c`, used :ref:`here <capital-costs-of-conversion>`.
- :code:`kWh_perTon` is :math:`C_e`, used :ref:`here <electricity-costs-of-conversion>`.
- In the model, the convertor is placed between :code:`arc_start_class` and :code:`arc_end_class`.
- :code:`utilization` is :math:`\mu`, used :ref:`here <variable-costs-of-conversion>` and :ref:`here <capacity-converters>`.

.. raw:: html

    <hr>
   
demand.csv
----------
Describes demand sectors. The amount of of hydrogen consumed per demand sector at each hub is defined in :ref:`hubs.csv <inputs-hubs.csv>`.

.. csv-table:: demand.csv
    :file: descriptions/inputs/demand.csv
    :header-rows: 1

Example
^^^^^^^

.. csv-table:: example of demand.csv
    :file: ../tutorial/scenario/inputs/demand.csv
    :header-rows: 1

Relevance to model
^^^^^^^^^^^^^^^^^^
- :code:`sector` corresponds to :math:`\xi \in \Xi` in the model formulation.
- :code:`breakevenPrice` is :math:`U_{bp}`, used :ref:`here <utility-gained-through-consumption-of-hydrogen>`.
- :code:`carbonSensitive` is :math:`S_{\text{CO}_2}`, used :ref:`here <rule_consumerChecs>`.
- :code:`avoided_emissions_tonsCO2_per_H2` is :math:`Q'_{\text{CO}_2}`, used :ref:`here <utility-gained-through-avoided-carbon-taxes>`.
- The model currently only supports :code:`fuelStation`, :code:`lowPurity`, and :code:`highPurity` as demand sectors.

.. raw:: html

    <hr>
   
distribution.csv
----------------
Describes methods of distribution.

.. csv-table:: distribution.csv
    :file: descriptions/inputs/distribution.csv
    :header-rows: 1

Example
^^^^^^^

.. csv-table:: example of distribution.csv
    :file: ../tutorial/scenario/inputs/distribution.csv
    :header-rows: 1

Relevance to model
^^^^^^^^^^^^^^^^^^
- The :code:`distributor` column decides if the distribution method is a pipeline or a truck.
  This column refers to :math:`\delta \in \Delta` in the model.
  The item :code:`pipeline` is required, and only looks at other distribution methods that contain the word :code:`truck`.

  .. todo::
    This should probably be changed based on unit, look at the code.

- Consequently, the :code:`unit` column is useless in the current version of the model.
- :code:`capital_usdPerUnit` is :math:`D_c`, used :ref:`here <capital-costs-of-distribution>`.
- :code:`fixed_usdPerUnitPerDay` is not used since fixed costs are calculated as :math:`\kappa` percent of capital costs.

    .. todo::
        Make sure that this is not used anywhere in the code and remove. 

- :code:`variable_usdPerUnit` is :math:`D_v`, used :ref:`here <variable-costs-of-distribution>`.
- :code:`flowLimit_tonsPerDay` is :math:`y_d^{\text{max}}` used :ref:`here <capacity-distribution>`.

.. _inputs-hubs.csv:

.. raw:: html

    <hr>
   
hubs.csv
--------
Describes hubs, which locations can build specific technologies, the amount of hydrogen demand that *could* be consumed
at each hub, the local natural gas price, the local electricity price, and the local capital price multiplier.

.. csv-table:: hubs.csv
    :file: descriptions/inputs/hubs.csv
    :header-rows: 1

Example
^^^^^^^

.. csv-table:: example of hubs.csv
    :file: ../tutorial/scenario/inputs/hubs.csv
    :header-rows: 1

Relevance to model
^^^^^^^^^^^^^^^^^^
- :code:`hub` is :math:`\omega \in \Omega` in the model formulation.
- Replace :code:`<producer>` in :code:`build_<producer>` with the name of a producer :math:`\phi \in \Phi`. If there is not a 
  column for each producer :math:`\phi \in \Phi`, the model will assume that the producer without a column can be built at any hub.
- Replace :code:`<demandSector>` in :code:`demand_<demandSector>` with the name of a demand sector :math:`\xi \in \Xi`.
  The column corresponds to the model variable :math:`Q_{H_2}(\omega, \xi)`, used :ref:`here <consumerSize>`.
- :code:`ng_usd_per_mmbtu` is :math:`\gamma(\omega)`, which is used to calculate :ref:`thermal hydrogen production costs <natural-gas-costs>`.
- :code:`e_usd_per_kwh` is :math:`\varepsilon(\omega)`, which is used to calculate :ref:`electric hydrogen production costs <electricity-costs-of-production>`
  and :ref:`conversion costs <electricity-costs-of-conversion>`.
- :code:`capital_pm` is :math:`\lambda(\omega)`, used in calculating all capital costs.

.. raw:: html

    <hr>

production_electric.csv
-----------------------

Describes prices and relevant information regarding carbon impacts of electricity production (electrolyzers).

.. csv-table:: production_electric.csv
    :file: descriptions/inputs/production_electric.csv
    :header-rows: 1

Example
^^^^^^^

.. csv-table:: example of production_electric.csv
    :file: ../tutorial/scenario/inputs/production_electric.csv
    :header-rows: 1

In this example, the :code:`electolyzer-RE` (electrolyzer that uses renewable electricity) differs from the other electrolyzers
in that the grid intensity is zero and the utilization is lower (representing the fact that renewable electricity is not always available).
The electrolyzer that uses renewable electricity also gets a larger tax credit.

Relevance to model
^^^^^^^^^^^^^^^^^^

.. todo::
    As before, remove fixed costs of production?

- :code:`type` is :math:`\phi_{\text{electric}} \in \Phi_e \in \Phi` in the model formulation.
- The product of :code:`capEx_$_per_kW` [#capex_units]_ and :code:`kWh_perTon` is :math:`P_c(\phi_e)`, used :ref:`here <capital-costs-of-production>`.
- :code:`kWh_perTon` is also used :ref:`here <electricity-costs-of-production>`.
- :code:`variable_usdPerTon` is :math:`P_v(\phi_e)`, used :ref:`here <variable-costs-production>`.
- :code:`utilization` is :math:`\mu(\phi_e)`, used :ref:`here <capacity-production>`.
- :code:`purity` determines how the producer is connected to the network.
- :code:`min_h2` is :math:`y_p^{\text{min}}(\phi_e)`, used :ref:`here <capacity-production-min>`.
- :code:`max_h2` is :math:`y_p^{\text{max}}(\phi_e)`, used :ref:`here <capacity-production-max>`.
- :code:`h2_tax_credit` is :math:`\tau_{\text{new}}(\phi_e)`, used :ref:`here <utility-gained-through-clean-hydrogen-production-tax-credits>`.
- :code:`grid_intensity_tonsCO2_per_h2` is :math:`G(\phi_e)`, used :ref:`here <electric-chec>`.

.. [#capex_units] I believe this is $/kW/day. There is a document somewhere that explains these units and how that ties into amortization.

.. todo::
    Double check footnote [#capex_units]_ with Dr. Emily Beagle.

.. raw:: html

    <hr>

production_existing.csv
-----------------------

Describes existing production costs and hubs at which the producers are located.

.. csv-table:: production_existing.csv
    :file: descriptions/inputs/production_existing.csv
    :header-rows: 1

Example
^^^^^^^

.. csv-table:: example of production_existing.csv
    :file: ../tutorial/scenario/inputs/production_existing.csv
    :header-rows: 1

Relevance to model
^^^^^^^^^^^^^^^^^^

- :code:`type` will match a :code:`type` in :ref:`production_thermal.csv <inputs-production_thermal.csv>`. Corresponding data will be gathered from that row.

.. todo::
    Figure out which data are used (good way to learn about the code) and remove unnecessary columns from this input file.

- :code:`hub` will match a :code:`hub` in :ref:`hubs.csv <inputs-hubs.csv>`. The existing producer will be built at that hub.
- :code:`capacity_tonPerDay` is used :ref:`here <rule_productionCapacityExisting>`.
- :code:`capital_usdPerTonPerDay` is :math:`P_c` used :ref:`here <capital-costs-of-production>`.

.. todo::
    Fixed costs

- :code:`kWh_perTon` is :math:`P_e` used :ref:`here <electricity-costs-of-production>`.
- :code:`ng_mmbtu_per_tonH2` is :math:`P_g` used :ref:`here <natural-gas-costs>`.
- :code:`variable_usdPerTon` is :math:`P_v` used :ref:`here <variable-costs-production>`.
- :code:`co2_emissions_per_h2_tons` is :math:`B_{\text{exist}}` used :ref:`here <carbon-tax-costs>` and :ref:`here <rule_ccs1CapacityRelationship>`.
- :code:`can_ccs1` is :math:`\zeta_{CCS}(n_{p_{\text{exist}}})` used :ref:`here <rule_ccs1CapacityRelationship>`.
- :code:`utilization` is :math:`\mu` used :ref:`here <capacity-production>`.

.. raw:: html

    <hr>

.. _inputs-production_thermal.csv:

production_thermal.csv
----------------------

Describes prices and relevant information regarding carbon impacts of thermal hydrogen production.

.. csv-table:: production_thermal.csv
    :file: descriptions/inputs/production_thermal.csv
    :header-rows: 1

Example
^^^^^^^

.. csv-table:: example of production_thermal.csv
    :file: ../tutorial/scenario/inputs/production_thermal.csv
    :header-rows: 1

Relevance to model
^^^^^^^^^^^^^^^^^^
   
settings.yml
------------
1. Price tracking settings

These settings control how the delivered price of hydrogen is determined.
See :ref:`price nodes <price_nodes>` for more information.

- :code:`find_prices`: if :code:`True`, the model will find the price of hydrogen for each specified hub.
- :code:`price_tracking_array`
- - :code:`start` : the lower bound of the price tracking array