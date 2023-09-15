# SPDX-License-Identifier: GPL-3.0-or-later

"""This module is used to select which module to run when the HOwDI command is
called from the command line based on the arguments provided.

The module defines a `main` function that reads the command line arguments and
imports and runs the appropriate module based on the argument choice.

The following modules can be run:
- `run`: runs the HOwDI model
- `create_fig`: creates a figure from an already run model
- `traceback`: traces how hydrogen is produced from a given (consumer) node
- `traceforward`: traces how hydrogen is consumed from a given (producer) node
- `create_hubs_data` or `create_hub_data`: creates input data for the model
- `monte_carlo`: runs a Monte Carlo simulation on the model
"""
import sys


def main():
    try:
        choice = sys.argv[1]
    except IndexError:
        # if no arguments are provided, print help message
        choice = "-h"

    if choice == "run":
        # run the model
        from HOwDI.run import main as module

    elif choice == "create_fig":
        # create a figure from already run model
        from HOwDI.postprocessing.create_plot import main as module

    elif choice == "traceback":
        # traceback how hydrogen is produced from a given (consumer) node
        from HOwDI.postprocessing.traceback_path import main as module

    elif choice == "traceforward":
        # traceback how hydrogen is consumed from a given (producer) node
        from HOwDI.postprocessing.traceforward_path import main as module

    elif choice == "create_hubs_data" or choice == "create_hub_data":
        # Given a list of location names (in /data), geocodes locations and
        # creates a network of relevant lines between locations. This is used
        # to create input data for the model.
        import warnings

        warnings.simplefilter(action="ignore", category=DeprecationWarning)
        from HOwDI.preprocessing.create_hubs_data import main as module

    elif choice == "monte_carlo":
        # run a monte carlo simulation on the model
        from HOwDI.monte_carlo import monte_carlo as module

    elif choice == "-h" or choice == "--help" or choice == "help":
        # print a help screen
        from HOwDI.help import main as module

    else:
        print("Bad/invalid arguments provided. For a list of options, see `HOwDI -h`")
        return

    module()
