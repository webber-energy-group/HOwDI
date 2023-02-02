import argparse
import sys
from pathlib import Path


def parse_command_line(module=Path(sys.argv[1]).name, argv=sys.argv):
    def name(*args):
        return any([arg == module for arg in args])

    # TODO filenames for fig, outputs.json

    parser = argparse.ArgumentParser()

    if name("run", "create_fig", "traceback", "traceforward"):
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
    if name("run", "create_fig", "traceback", "traceforward"):
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
        parser.add_argument(
            "--no-fig",
            dest="output_fig",
            action="store_false",
            help="Don't print model outputs as a figure",
        )
    if name("traceback", "traceforward"):
        parser.add_argument("-hub", "--hub", dest="hub", required=True)
    if name("create_hub_data"):
        parser.add_argument(
            "-d",
            "--dir",
            dest="hub_dir",
            required=True,
            help="""
Location where necessary hub files are required. (hubs.csv, arcs_blacklist.csv, arcs_whitelist.csv)
""",
        )
        parser.add_argument(
            "-out",
            "--outputs-dir",
            dest="out",
            default=None,
            help="Location of where to save output files. Defaults to --dir",
        )
        parser.add_argument(
            "-f" "--create_figure",
            dest="create_fig",
            action="store_true",
            help="Create a figure showing all arcs.",
        )
        parser.add_argument(
            "-shp",
            "--shapefile",
            dest="shapefile",
            default=None,
            help="Location of Shapefile to be used in figure.",
        )
        parser.add_argument(
            "-pm",
            "--price_multipliers",
            dest="price_multipliers",
            default=False,
            help="Location of price multiplier file",
        )
        parser.add_argument(
            "-c",
            "--price_multipliers_column",
            dest="price_multipliers_column",
            default="County",
            help="Column to merge price multipliers on. ONLY SUPPORT COUNTY (which is the default).",
        )
        parser.add_argument(
            "-r",
            "--replace_model_inputs",
            dest="replace_model_inputs",
            action="store_true",
            help="Replace the hubs.csv and arcs.csv to use the new generated hubs and price multipliers. Other columns are preserved.",
        )
        parser.add_argument(
            "-i",
            "--model_inputs_dir",
            dest="model_inputs_dir",
            default=None,
            help="Location of model inputs where files we be adjusted with new hubs.",
        )
    if name("monte_carlo"):
        parser.add_argument(
            "-f",
            "--file",
            dest="monte_carlo_file",
            type=str,
            default="monte_carlo.yml",
            help="Specify the scenario directory. Defaults to CWD.",
        )
    return parser.parse_args(argv[2:])


s = """
Location where necessary hub files are required. Make sure that the hubs directory (specified with -d) contains the following files: 

hubs_list.csv                   List of hubs to be used.                            Columns = hub, 
                                                                                              status:{
                                                                                                      -1: Minor hub (less connections),
                                                                                                       0: Neither major nor minor
                                                                                                       1: Major hub (more connections)
                                                                                                     } 
arcs_blacklist.csv              Excludes arcs from being formed between hubs.       Columns = startHub, endHub 
arcs_whitelist.csv              Forces arcs to be built between hubs                Columns = startHub, endHub, exist_pipeline (binary) 
"""
