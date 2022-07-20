# HOwDI (Hydrogen Optimization with Distribution Infrastructure)

[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

## Installation

1. Create a conda environment from the `env.yml` file and activate it:

    ```bash
    conda env create -f env.yml
    ```

2. Activate the conda environment

    ```bash
    conda activate HOwDI
    ```

3. Install an editable version of HOwDI in your HOwDI environment with pip.

    ```bash
    pip install -e .
    ```

## Usage

Within a directory that contains a subdirectory named "inputs" (that contains the necessary inputs), run the model:

```bash
(HOwDI) ~ ls
inputs
(HOwDI) ~ HOwDI run
```

Use `HOwDI run -h` for a list of options.

## Postprocessing Tools

HOwDI has several postprocessing tools. Use `HOwDI help` for a full list.

```bash
Create a figure:        HOwDI create_fig
Traceback:              HOwDI traceback
Traceforward:           HOwDI tracefoward
```

## Contributing

HOwDI uses the Black code style. Please format your code accordingly before making a pull request.
