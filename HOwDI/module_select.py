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

    elif choice == "-h" or choice == "--help" or choice == "help":
        from HOwDI.help import main as module

    a = module()
