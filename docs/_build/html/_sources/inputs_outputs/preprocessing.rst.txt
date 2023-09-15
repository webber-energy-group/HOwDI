Preprocessing
=============

HOwDI's preprocessing tools are used to create the input files necessary for HOwDI's main algorithm.
The preprocessing pipeline determines relevant connections by hubs, geocodes the locations, and determines the
straight-line (euclidean) and road distances between hubs.

Use the following from the command line to see the available options:

.. code-block:: bash

    HOwDI create_hub_data -h

The following function drives the preprocessing pipeline. The documentation describes the necessary inputs and outputs files.

.. autofunction:: HOwDI.preprocessing.create_hubs_data.create_hubs_data

.. note::

    Preprocessing mainly uses data from the :code:`/data` directory. However, to remove confusion, all necessary data in
    :code:`/data` should eventually be included in the the input files directory and :code:`/data` should be removed.
    Writing this note is faster than implementing this change myself and hopefully a future developer will do so.

Geocoding method
----------------

The following function is used to geocode the locations found in the inputs to :func:`HOwDI.preprocessing.create_hubs_data.create_hubs_data`.

.. autofunction:: HOwDI.preprocessing.geocode.geocode_hubs

The following function is used to determine the road and euclidean between hubs.

.. autofunction:: HOwDI.preprocessing.create_arcs.get_route

Determining relevant arcs
-------------------------

.. automodule:: HOwDI.preprocessing.create_arcs

.. autofunction:: HOwDI.preprocessing.create_arcs.create_arcs