from json import dump, load
from pathlib import Path

from data.create_plot import main as create_plot
from data.generate_inputs_json import main as generate_inputs_json
from data.generate_outputs import main as generate_outputs
from hydrogen_model.hydrogen_model import build_h2_model


def main(scenario="base", read_inputs_from_file=False):

    scenario = "base"

    data_dir = Path("data")
    scenario_dir = data_dir / scenario
    inputs_dir = scenario_dir / "inputs"
    outputs_dir = scenario_dir / "outputs"

    if read_inputs_from_file == False:
        inputs = generate_inputs_json(inputs_path=inputs_dir, filename="inputs.json")
        # will create file to save inputs
    else:
        inputs = load(open(inputs_dir / "inputs.json"))

    input_parameters = load(open(inputs_dir / "parameters.json"))

    hubs_list = [hub_data["hub"] for hub_data in inputs["hubs"]]

    m = build_h2_model(inputs, input_parameters)

    output_dfs, output_json = generate_outputs(m, hubs_list, input_parameters)
    [df.to_csv(outputs_dir / "{}.csv".format(key)) for key, df in output_dfs.items()]

    outputs_json_file = outputs_dir / "outputs.json"
    with outputs_json_file.open("w", encoding="utf-8") as f:
        dump(output_json, f, ensure_ascii=False, indent=4)

    create_plot(output_json, data_dir, scenario_dir)

    # #debug :
    # from idaes.core.util import to_json
    # output_json = to_json(m, return_dict=True)


if __name__ == "__main__":
    main()
