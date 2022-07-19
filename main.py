from json import dump
from pathlib import Path

from HOwDI.create_model import build_h2_model
from HOwDI.create_network import build_hydrogen_network
from HOwDI.create_plot import main as create_plot
from HOwDI.generate_outputs import generate_outputs
from HOwDI.read_inputs import HydrogenInputs


def main():

    scenario = "base"

    data_dir = Path("data")
    scenario_dir = Path("scenarios") / scenario
    inputs_dir = scenario_dir / "inputs"
    outputs_dir = scenario_dir / "outputs"

    # read inputs
    H = HydrogenInputs(inputs_dir)
    # generate network
    g = build_hydrogen_network(H)
    # build model
    m = build_h2_model(H, g)

    # clean outputs
    output_dfs, output_json = generate_outputs(m, H)

    # write outputs dataframes
    [df.to_csv(outputs_dir / "{}.csv".format(key)) for key, df in output_dfs.items()]

    # write outputs to json
    with (outputs_dir / "outputs.json").open("w", encoding="utf-8") as f:
        dump(output_json, f, ensure_ascii=False, indent=4)

    # create figure
    create_plot(output_json, data_dir, scenario_dir, H.get_prod_types())


if __name__ == "__main__":
    main()
