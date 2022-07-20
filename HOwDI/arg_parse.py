import argparse
import sys
from pathlib import Path


module = Path(sys.argv[1]).name


def name(*args):
    return any([arg == module for arg in args])


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
    if name("run", "create_fig"):
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
    if name("run"):
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
    if name("run"):
        parser.add_argument(
            "--no-fig",
            dest="output_fig",
            action="store_false",
            help="Don't print model outputs as a figure",
        )
    if name("traceback", "traceforward"):
        parser.add_argument("-hub", "--hub", dest="hub", required=True)

    return parser.parse_args(argv[2:])
