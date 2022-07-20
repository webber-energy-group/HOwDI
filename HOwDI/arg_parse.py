import argparse
import sys
from pathlib import Path


script_name = Path(sys.argv[0]).name


def name(*args):
    return any([arg == script_name for arg in args])


def parse_command_line(argv=sys.argv):

    # TODO filenames for fig, outputs.json

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "-sd",
        "--scenario_dir",
        dest="scenario_dir",
        type=str,
        default="./",
        help="Specify the scenario directory. Defaults to CWD.",
    )
    if name("HOwDI-run", "HOwDI-create_fig"):
        parser.add_argument(
            "-in",
            "--inputs_dir",
            dest="inputs_dir",
            type=str,
            default="inputs",
            help="Specify inputs directory relative to the scenario directory",
        )
    parser.add_argument(
        "-out",
        "--outputs_dir",
        dest="outputs_dir",
        type=str,
        default="outputs",
        help="Specify outputs directory relative to the scenario directory",
    )
    if name("HOwDI-run"):
        parser.add_argument(
            "--no-csv",
            dest="output_csvs",
            action="store_false",
            help="Don't print model outputs as csv files",
        )
        parser.add_argument(
            "--no-json",
            dest="output_json",
            action="store_false",
            help="Don't print model outputs as a JSON file",
        )
    if name("HOwDI-run"):
        parser.add_argument(
            "--no-fig",
            dest="output_fig",
            action="store_false",
            help="Don't print model outputs as a figure",
        )
    if name("HOwDI-traceback", "HOwDI-traceforward"):
        parser.add_argument(
            "--hub",
            dest="hub",
        )

    return parser.parse_args(argv[1:])
