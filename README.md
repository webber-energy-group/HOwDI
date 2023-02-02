# HOwDI (Hydrogen Optimization with Distribution Infrastructure)

[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

* This README is under development. For temporary reference, please consult [Modeling Hydrogen Infrastructure with the HOwDI Model](http://dx.doi.org/10.26153/tsw/43878)

## Installation

1. Create a conda environment from the `env.yml` file and activate it. This may be faster with [mamba](https://mamba.readthedocs.io/en/latest/).

    ```bash
    conda env create -f env.yml
    ```

    Note: M1 Mac users should change the Python version to 3.9 in `env.yml`

2. Activate the conda environment

    ```bash
    conda activate HOwDI
    ```

3. Install an editable version of HOwDI in your HOwDI environment with pip.

    ```bash
    pip install -e .
    ```

If you have already installed HOwDI but would like to update the dependencies:

```bash
conda env update --file env.yml --prune
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
Traceforward:           HOwDI traceforward
```

## Contributing

HOwDI uses the Black code style. Please format your code accordingly before making a pull request.

## : Local Config

Adjust the config without worrying about git tracking by creating a file called `HOwDI/config_local.yml`. Add key `db` and follow with db path.
