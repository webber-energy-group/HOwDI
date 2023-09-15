# SPDX-License-Identifier: GPL-3.0-or-later

"""Runs the HOwDI model.

This file is useful for debugging purposes. It can be run from the command
line, however, it is not recommended to do so. Instead, use the `HOwDI`
command. See the README for more information, or use `setup.py` to follow
the code.
"""
from pathlib import Path

from HOwDI.model.create_model import build_h2_model
from HOwDI.model.create_network import build_hydrogen_network
from HOwDI.model.HydrogenData import HydrogenData
from HOwDI.postprocessing.create_plot import create_plot
from HOwDI.postprocessing.generate_outputs import create_outputs_dfs, create_output_dict


def main():
    scenario_dir = Path("scenarios") / "base"

    # read inputs
    H = HydrogenData(scenario_dir)
    # generate network
    g = build_hydrogen_network(H)
    # build model
    m = build_h2_model(H, g)

    # clean outputs
    H.output_dfs = create_outputs_dfs(m, H)
    H.output_dict = create_output_dict(H)

    # write outputs dataframes
    H.write_output_dataframes()

    # write outputs to json
    H.write_output_dict()

    # create figure
    create_plot(H).savefig(H.outputs_dir / "fig.png")


if __name__ == "__main__":
    main()
