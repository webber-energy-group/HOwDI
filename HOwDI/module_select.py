import sys


def main():
    try:
        choice = sys.argv[1]
    except IndexError:
        choice = "-h"

    if choice == "run":
        from HOwDI.run import main as module

    elif choice == "create_fig":
        from HOwDI.postprocessing.create_plot import main as module

    elif choice == "traceback":
        from HOwDI.postprocessing.traceback_path import main as module

    elif choice == "tracefoward":
        from HOwDI.postprocessing.traceforward_path import main as module

    elif choice == "create_hubs_data" or choice == "create_hub_data":
        import warnings

        warnings.simplefilter(action="ignore", category=DeprecationWarning)
        from HOwDI.preprocessing.create_hubs_data import main as module

    elif choice == "monte_carlo":
        from HOwDI.monte_carlo import monte_carlo as module

    elif choice == "-h" or choice == "--help" or choice == "help":
        from HOwDI.help import main as module

    else:
        print("Bad/invalid arguments provided. For a list of options, see `HOwDI -h`")
        return

    module()
