.. _tutorial:

Running HOwDI Example/Tutorial
------------------------------

This page walks through a simple example of using HOwDI to determine the optimal infrastructure in a reduced version of Texas.

In this scenario, Dallas, Waco, Austin, Houston, and Freeport are the cities of interest.
Freeport has an existing Steam Methane Reformer (SMR) and a pipeline to Houston.
We would like to determine the optimal way to build hydrogen infrastructure given a potential demand.

Step 1: Preprocessing
=====================

As a first step, the initial data must be preprocessed to generate necessary input files.
The preprocessing steps involve finding the geographic location of cities and determining the distance between them.
These steps can be skipped if the necessary input files are already available.

1. Create a :code:`hubs.csv` file with the following columns:

    - :code:`hub`: The name of the hub. This will be used to geocode the hub, so it should correspond to an actual city.
    - :code:`status`: The "reach" of the hub. 1 corresponds to a major hub, -1 corresponds to a minor hub, and 0 corresponds to a regular hub. A major hub will be more likely to connect to other hubs than a regular hub will (an regular > minor).

    For this example, the :code:`hubs.csv` file should look like:

    .. csv-table:: hubs.csv
        :file: data/texas_example/inputs/hubs.csv
        :header-rows: 1

2. Create :code:`arcs_whitelist.csv` and :code:`arcs_blacklist.csv` in the same directory.
   Both have columns :code:`startHub` and :code:`endHub` corresponding to the hubs that should or should not be forced to connect.
   :code:`arcs_whitelist.csv` also contains a third column, :code:`exist_pipeline`, which is :code:`True` if there is an existing hydrogen pipeline that connects the hubs.

   For this example, the preprocessing code should connect Houston and Freeport, but we would like to specify that a pipeline exists.
   The preprocessing code may also connect Dallas and Austin, which is unnecessary since any route from Dallas to Austin must go through Waco.

    .. csv-table:: arcs_whitelist.csv
        :file: data/texas_example/inputs/arcs_whitelist.csv
        :header-rows: 1

    .. csv-table:: arcs_blacklist.csv
        :file: data/texas_example/inputs/arcs_blacklist.csv
        :header-rows: 1

3. The preprocessing code can be run from the directory containing the three generated files. We'll add other parameters to create a figure.

   .. code-block:: bash

        HOwDI create_hub_data -f -shp US_COUNTY_SHPFILE/US_county_cont.shp

The following file is generated:

.. csv-table:: arcs.csv
    :file: data/texas_example/outputs/arcs.csv

Additionally, for generating output figures, :code:`fig.png`, :code:`hubs.geojson`, and :code:`roads.csv` are generated.
These files are not necessary to run the HOwDI model, but are useful for visualizing the results.

.. figure:: data/texas_example/outputs/fig.png
    :align: center

    fig.png

.. literalinclude:: data/texas_example/outputs/hubs.geojson
    :language: JSON
    :caption: hubs.geojson

.. csv-table:: roads.csv
    :file: data/texas_example/outputs/roads.csv
    :header-rows: 1

Step 2: Generating Inputs
=========================

Inputs for the HOwDI model can be placed anywhere.
Create a directory corresponding to the scenario, and create an inputs directory within that.
The output directory will be created automatically within this scenario directory.

For more detail on the inputs, see :ref:`inputs <inputs>`.

The following input files are required for the HOwDI model:

- :ref:`arcs.csv <arcs-csv>`: distances between hubs (generated in the previous step, no additional data required)
- :ref:`ccs.csv <ccs-csv>`: parameters and costs for retrofitting existing SMRs with CCS
- :ref:`conversion.csv <conversion-csv>`: parameters and costs for conversion technologies (liquefaction, compression, terminals, fuel dispensers, purification)
- :ref:`demand.csv <demand-csv>`: demand sector descriptions
- :ref:`hubs.csv <hubs-csv>`: name of each each hub, ability to build infrastructure, and demand per demand sector
- :ref:`production_electric.csv <production_electric-csv>`: parameters and costs for electrolysis and other electric production technologies
- :ref:`production_existing.csv <production_existing-csv>`: parameters, costs, and hubs for existing SMRs
- :ref:`production_thermal.csv <production_thermal-csv>`: parameters and costs for thermal production technologies (SMR)
- :ref:`settings.yml <settings-yml>`: settings for the model


.. _arcs-csv:

arcs.csv
********

This file is generated in the previous step. No additional data are required.

.. csv-table:: arcs.csv
    :file: scenario/inputs/arcs.csv
    :header-rows: 1

.. _ccs-csv:

ccs.csv
*******

This file contains the parameters and costs for retrofitting existing SMRs with CCS.
It currently only supports the use of two CCS retrofit technologies aptly named :code:`ccs1` and :code:`ccs2`.
The model will choose to build or or none of these for :ref:`existing SMRs <production_existing-csv>`.

.. csv-table:: ccs.csv
    :file: scenario/inputs/ccs.csv
    :header-rows: 1

.. _conversion-csv:

conversion.csv
**************

This file describes conversion steps that occur between production, distribution, and demand, and the associated costs.

.. warning::
    Adding or subtracting converters from the :code:`converter` index or changing
    :code:`arc_start_class` and :code:`arc_end_class` is only for advanced users.

.. csv-table:: conversion.csv
    :file: scenario/inputs/conversion.csv
    :header-rows: 1

.. _demand-csv:

demand.csv
**********

This file describes the price a consumer is willing to pay for hydrogen in each demand sector (:code:`breakevenPrice`),
wether or not the demand sector is carbon sensitive (:py:mod:`CHECs <HOwDI.model.constraints.checs>`),
the amount of carbon emissions avoided by switching to a hydrogen for a demand sector, and the demand type
(:code:`lowPurity`, :code:`highPurity`, or :code:`fuelStation`).

.. csv-table:: demand.csv
    :file: scenario/inputs/demand.csv
    :header-rows: 1

.. _distribution-csv:

distribution.csv
****************

This file describes the cost of building and operating distribution infrastructure.

.. csv-table:: distribution.csv
    :file: scenario/inputs/distribution.csv
    :header-rows: 1

.. _hubs-csv:

hubs.csv
********

This file describes which hubs are used by the model, if a technology can be built at that hub
(:code:`build_<tech>`, binary), the demand per demand sector at that hub (:code:`<demandSector>_tonnesperday`, where 
:code:`<demandSector>` is defined in :ref:`demand.csv <demand-csv>`), and the hub's natural gas price, electricity price, and capital price multiplier.

.. csv-table:: hubs.csv
    :file: scenario/inputs/hubs.csv
    :header-rows: 1

.. _production_electric-csv:

production_electric.csv
***********************
This file describes the cost of building and operating electric production infrastructure, size restrictions, tax credits, and the carbon intensity of the electricity used.
Since HOwDI does not have a time domain, :code:`utilization` refers to the fraction of the time (day) that the technology is operating.

.. csv-table:: production_electric.csv
    :file: scenario/inputs/production_electric.csv
    :header-rows: 1

.. _production_existing-csv:

production_existing.csv
***********************
This file describes existing production capacity. The :code:`type` column corresponds to a thermal producer defined in
:ref:`production_thermal.csv <production_thermal-csv>`. The :code:`hub` is the location, and :code:`capacity_tonPerDay` is the existing capacity.
The columns :code:`can_ccs1` and :code:`can_ccs2` are binaries allowing the addition of CCS to the existing SMR.

.. csv-table:: production_existing.csv
    :file: scenario/inputs/production_existing.csv
    :header-rows: 1

.. _production_thermal-csv:

production_thermal.csv
***********************
Similar to other production files, this file describes the costs associated with building and operating thermal production infrastructure.

.. note::
    Although the zeros in the :code:`build_smr-noCCS` column of :ref:`hubs.csv <hubs-csv>` prevent the model from building this type of CCS,
    this "type" is used in the :ref:`production_existing.csv <production_existing-csv>`, indicating that the prices in :ref:`production_thermal.csv <production_thermal-csv>` are used.

    .. todo::
        This is a bit confusing and I'm not sure which data are used at the moment.

.. csv-table:: production_thermal.csv
    :file: scenario/inputs/production_thermal.csv
    :header-rows: 1

.. _settings-yml:

settings.yml
************

The settings file specifies any options outside of the scope of
the other input files.

The only setting that may need to be changed now is :code:`solver_settings/solver`.

.. literalinclude:: scenario/inputs/settings.yml
    :language: YAML
    :caption: settings.yml

Step 3: Running the Model
=========================

Navigate to the "scenario" directory that is above/contains the "inputs" directory.

.. code-block:: bash

    ls
    > /inputs

Run the model with the following command:

.. code-block:: bash

    HOwDI run

Step 4: Outputs and Viewing Results
===================================

The model will generate a directory called "outputs" in the scenario directory.
This directory contains the following files:

- :ref:`production.csv <o-production-csv>`: production infrastructure built
- :ref:`distribution.csv <o-distribution-csv>`: distribution infrastructure built
- :ref:`consumption.csv <o-consumption-csv>`: demand met and theoretical delivered prices
- :ref:`conversion.csv <o-conversion-csv>`: conversion infrastructure built
- :ref:`fig.png <o-fig-png>`: a figure showing the infrastructure built
- :ref:`outputs.json <o-outputs-json>`: A JSON file containing all the outputs in a single file

.. _o-production-csv:

outputs/production.csv
**********************

This file describes the production infrastructure built by the model.
In this case, the model decided to add CCS2 to the existing SMR in Freeport, and build electrolyzers in Freeport and Waco.

.. csv-table:: production.csv
    :file: scenario/outputs/production.csv
    :header-rows: 1

.. _o-distribution-csv:

outputs/distribution.csv
************************

This file describes the distribution infrastructure built by the model. In this case, the existing pipeline is utilized and 
new pipelines transport hydrogen from Waco to Austin and Dallas.

This file can be better understood by looking at :ref:`fig.png <o-fig-png>` or using the :code:`HOwDI traceback` or 
:code:`HOwDI traceforward` commands.

.. csv-table:: distribution.csv
    :file: scenario/outputs/distribution.csv
    :header-rows: 1

.. _o-consumption-csv:

outputs/consumption.csv
***********************

This file describes the demand met by the model. There are also very small demands that are met to determine the
:ref:`price-nodes <price_nodes>` price. In this `demonstrative` case, all demand is met, and hydrogen can be delivered to fuel stations
for just above $2/kg.

.. csv-table:: consumption.csv
    :file: scenario/outputs/consumption.csv
    :header-rows: 1

.. _o-conversion-csv:

outputs/conversion.csv
***********************

This file describes the conversion infrastructure built by the model.

.. csv-table:: conversion.csv
    :file: scenario/outputs/conversion.csv
    :header-rows: 1

.. _o-fig-png:

outputs/fig.png
***************

This file is a figure showing the infrastructure built by the model.
Hydrogen is produced in electrolysis Waco, consumed locally, and transported to Dallas and Austin via pipeline.
Hydrogen is also produced in Freeport, consumed locally, and transported to Houston via pipeline.

.. figure:: scenario/outputs/fig.png
    :align: center

    fig.png

.. _o-outputs-json:

outputs/outputs.json
********************

This file contains all the outputs in a single file, which is useful for some data manipulation.

.. literalinclude:: scenario/outputs/outputs.json
    :language: JSON
    :caption: outputs.json (first few lines)
    :lines: 1-22

Step 5: Further result analysis
===============================

The :code:`HOwDI traceback` and :code:`HOwDI traceforward` commands can be used to trace the flow of hydrogen through the network.

Using :code:`HOwDI traceforward`, we can see that hydrogen from freeport is consumed locally and transported to Houston via pipeline.

.. code-block:: bash
    
    howdi traceforward --hub freeport

    origin-freeport (0.00*100.00%=0.00)
    ├── origin-electrolyzer-RE (0.00 -> 897.00, 897.00*51.64%=463.20)
    │   └── freeport-production_electrolyzer-RE_TO_center_highPurity (463.20*100.00%=463.20)
    │       └── freeport-center_highPurity_TO_dist_pipelineHighPurity (463.20*100.00%=463.20)
    │           ├── freeport-dist_pipelineHighPurity_TO_demand_lowPurity (463.20*22.50%=104.20)
    │           │   └── freeport-demand_lowPurity_TO_demandSector_existing (104.20 -> 538.00, 538.00*100.00%=538.00)
    │           │       └── freeport-demandSector_existing (538.00*100.00%=538.00)
    │           └── freeport-dist_pipelineHighPurity_TO_houston_dist_pipelineHighPurity (463.20*77.50%=359.00)
    │               └── houston-dist_pipelineHighPurity_TO_converter_fuelDispenserPipeline (359.00*100.00%=359.00)
    │                   └── houston-converter_fuelDispenserPipeline_TO_demand_fuelStation (359.00*100.00%=359.00)
    │                       └── houston-demand_fuelStation_TO_demandSector_transportationFuel_carbonSensitive (359.00 -> 359.00, 359.00*100.00%=359.00)
    │                           └── houston-demandSector_transportationFuel_carbonSensitive (359.00*100.00%=359.00)
    └── origin-smr-noCCSExisting (0.00 -> 897.00, 897.00*48.36%=433.80)
        └── freeport-production_smr-noCCSExisting_TO_center_lowPurity (433.80*100.00%=433.80)
            └── freeport-center_lowPurity_TO_dist_pipelineLowPurity (433.80*100.00%=433.80)
                └── freeport-dist_pipelineLowPurity_TO_demand_lowPurity (433.80*100.00%=433.80)
                    └── freeport-demand_lowPurity_TO_demandSector_existing (433.80 -> 538.00, 538.00*100.00%=538.00)
                        └── freeport-demandSector_existing (538.00*100.00%=538.00)

.. note::
    Production numbers can sometimes seem off, but this is a result of utilization. For instance, the existing steam methane reformer in Freeport is producing 433.80
    tonnes of hydrogen, but the capacity in :ref:`production_existing.csv <production_existing-csv>` is 482 tonnes.
    However, the utilization of this SMR is 0.9, so the actual production is capacity times utilization, 482*0.9 = 433.80.